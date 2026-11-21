"""SQLite storage for page notes (one short-lived connection per operation)."""

import contextlib
import datetime
import pathlib
import sqlite3
import tempfile
import threading

DOCUMENT_ID = "sample"
DB_FILENAME = "annotator.sqlite3"

# Ordered migrations; index i upgrades user_version i -> i + 1.
_MIGRATIONS = [
    (
        """CREATE TABLE notes (
  document_id TEXT NOT NULL, page INTEGER NOT NULL CHECK(page >= 1),
  title TEXT NOT NULL CHECK(length(title) <= 120),
  body TEXT NOT NULL CHECK(length(body) <= 4000),
  revision INTEGER NOT NULL CHECK(revision >= 1),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (document_id, page)) WITHOUT ROWID""",
    ),
]
SCHEMA_VERSION = len(_MIGRATIONS)


class StorageError(Exception):
    """The data directory or database cannot be used."""


def _now_iso():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _rollback(conn):
    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


class Storage:
    def __init__(self, data_dir):
        self.data_dir = pathlib.Path(data_dir)
        self._closed = False
        self._lock = threading.Lock()
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError("cannot create data directory: %s" % exc)
        if not self.data_dir.is_dir():
            raise StorageError("data directory is not a directory")
        try:
            with tempfile.TemporaryFile(dir=str(self.data_dir)):
                pass
        except OSError as exc:
            raise StorageError("data directory is not writable: %s" % exc)
        self.db_path = self.data_dir / DB_FILENAME
        self._migrate()

    def _connect(self):
        if self._closed:
            raise StorageError("storage is closed")
        try:
            return sqlite3.connect(
                str(self.db_path), timeout=10, isolation_level=None
            )
        except sqlite3.Error as exc:
            raise StorageError("cannot open database: %s" % exc)

    def _migrate(self):
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current > SCHEMA_VERSION:
                raise StorageError(
                    "database schema version %d is newer than supported %d"
                    % (current, SCHEMA_VERSION)
                )
            for version in range(current, SCHEMA_VERSION):
                for statement in _MIGRATIONS[version]:
                    conn.execute(statement)
                conn.execute("PRAGMA user_version = %d" % (version + 1))
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            _rollback(conn)
            raise StorageError("database error: %s" % exc)
        except BaseException:
            _rollback(conn)
            raise
        finally:
            conn.close()

    def schema_version(self):
        with contextlib.closing(self._connect()) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    @staticmethod
    def _note(page, row):
        if row is None:
            return {"page": page, "title": "", "body": "", "revision": 0,
                    "updated_at": None}
        return {"page": page, "title": row[0], "body": row[1],
                "revision": row[2], "updated_at": row[3]}

    _SELECT = ("SELECT title, body, revision, updated_at FROM notes "
               "WHERE document_id = ? AND page = ?")

    def get_note(self, page, document_id=DOCUMENT_ID):
        with contextlib.closing(self._connect()) as conn:
            row = conn.execute(self._SELECT, (document_id, page)).fetchone()
        return self._note(page, row)

    def put_note(self, page, title, body, base_revision,
                 document_id=DOCUMENT_ID):
        """Store a note if base_revision matches. Returns (saved, note).

        When not saved, `note` is the current stored note and nothing was
        written.
        """
        with contextlib.closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(self._SELECT, (document_id, page)).fetchone()
                current = row[2] if row else 0
                if current != base_revision:
                    conn.execute("ROLLBACK")
                    return False, self._note(page, row)
                now = _now_iso()
                if row is None:
                    try:
                        conn.execute(
                            "INSERT INTO notes (document_id, page, title, body,"
                            " revision, updated_at) VALUES (?, ?, ?, ?, 1, ?)",
                            (document_id, page, title, body, now),
                        )
                    except sqlite3.IntegrityError:
                        # Lost an insert race: report the winner as a conflict.
                        _rollback(conn)
                        row = conn.execute(
                            self._SELECT, (document_id, page)
                        ).fetchone()
                        if row is None:
                            raise  # a CHECK failure, not a lost race
                        return False, self._note(page, row)
                else:
                    conn.execute(
                        "UPDATE notes SET title = ?, body = ?, revision = ?,"
                        " updated_at = ? WHERE document_id = ? AND page = ?"
                        " AND revision = ?",
                        (title, body, current + 1, now, document_id, page,
                         current),
                    )
                conn.execute("COMMIT")
            except BaseException:
                _rollback(conn)
                raise
            row = conn.execute(self._SELECT, (document_id, page)).fetchone()
        return True, self._note(page, row)

    def close(self):
        self._closed = True

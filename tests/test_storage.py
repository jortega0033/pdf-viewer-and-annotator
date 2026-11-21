import contextlib
import io
import pathlib
import sqlite3
import tempfile
import unittest

from pdf_annotator import cli
from pdf_annotator.storage import SCHEMA_VERSION, Storage, StorageError


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = pathlib.Path(self._tmp.name)

    def test_migration_is_idempotent(self):
        first = Storage(self.dir)
        self.assertEqual(first.schema_version(), 1)
        first.put_note(1, "t", "b", 0)
        second = Storage(self.dir)
        self.assertEqual(second.schema_version(), SCHEMA_VERSION)
        self.assertEqual(second.get_note(1)["revision"], 1)

    def test_creates_missing_directory(self):
        target = self.dir / "a" / "b"
        Storage(target)
        self.assertTrue((target / "annotator.sqlite3").is_file())

    def test_data_dir_is_a_file(self):
        path = self.dir / "file"
        path.write_text("x")
        with self.assertRaises(StorageError):
            Storage(path)

    def test_newer_schema_refused(self):
        db = self.dir / "annotator.sqlite3"
        with contextlib.closing(sqlite3.connect(str(db))) as conn:
            conn.execute("PRAGMA user_version = 99")
            conn.commit()
        with self.assertRaises(StorageError):
            Storage(self.dir)
        with contextlib.closing(sqlite3.connect(str(db))) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_corrupt_database_refused(self):
        (self.dir / "annotator.sqlite3").write_bytes(b"this is not sqlite" * 50)
        with self.assertRaises(StorageError):
            Storage(self.dir)

    def test_default_note(self):
        self.assertEqual(
            Storage(self.dir).get_note(2),
            {"page": 2, "title": "", "body": "", "revision": 0,
             "updated_at": None})

    def test_put_and_conflict(self):
        s = Storage(self.dir)
        saved, note = s.put_note(1, " t ", "line\n  ", 0)
        self.assertTrue(saved)
        self.assertEqual((note["title"], note["body"], note["revision"]),
                         (" t ", "line\n  ", 1))
        self.assertRegex(note["updated_at"],
                         r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z$")
        saved, current = s.put_note(1, "x", "y", 0)
        self.assertFalse(saved)
        self.assertEqual(current, note)
        saved, note2 = s.put_note(1, "x", "y", 1)
        self.assertTrue(saved)
        self.assertEqual(note2["revision"], 2)
        self.assertEqual(s.get_note(1)["title"], "x")

    def test_pages_are_independent(self):
        s = Storage(self.dir)
        s.put_note(1, "one", "", 0)
        self.assertEqual(s.get_note(2)["revision"], 0)


class CliTests(unittest.TestCase):
    def test_data_dir_file_exits_2_with_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "file"
            path.write_text("x")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = cli.main(["--data-dir", str(path), "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1)

    def test_bad_port_exits_2(self):
        for port in ("65536", "-1", "abc"):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cli.main(["--data-dir", "x", "--port", port])
            self.assertEqual(ctx.exception.code, 2)

    def test_args_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main([])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

"""Loopback HTTP server: routing, request validation, security headers."""

import http.server
import json
import os
import pathlib
import re
import socketserver
import sys
import threading

from . import __version__
from .pdfgen import build_sample_pdf
from .pdfparse import PdfError, parse_pdf
from .storage import DOCUMENT_ID, SCHEMA_VERSION, Storage

STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"

# Fixed allowlist: request path -> (file name inside STATIC_DIR, content type).
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

NOTES_PREFIX = "/api/v1/notes/"
MAX_BODY_BYTES = 16384
MAX_DRAIN_BYTES = 1 << 20
MAX_TITLE_CHARS = 120
MAX_NOTE_BODY_CHARS = 4000
MAX_CONNECTIONS = 64

_PAGE_RE = re.compile(r"-?[0-9]{1,9}")
_LENGTH_RE = re.compile(r"[0-9]{1,10}")

SECURITY_HEADERS = (
    ("Content-Security-Policy",
     "default-src 'none'; script-src 'self'; style-src 'self'; "
     "img-src 'self'; connect-src 'self'; base-uri 'none'; "
     "form-action 'none'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Cache-Control", "no-store"),
    ("Referrer-Policy", "no-referrer"),
)

_JSON_TYPE = "application/json; charset=utf-8"


class _BadRequest(Exception):
    pass


def _reject_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _reject_constant(name):
    raise ValueError("non-finite number")


def _validate_note(payload):
    if not isinstance(payload, dict) or set(payload) != {
            "title", "body", "base_revision"}:
        raise _BadRequest("Body must be an object with exactly title, body "
                          "and base_revision.")
    title = payload["title"]
    body = payload["body"]
    base = payload["base_revision"]
    if not isinstance(title, str) or not isinstance(body, str):
        raise _BadRequest("title and body must be strings.")
    if isinstance(base, bool) or not isinstance(base, int) or base < 0:
        raise _BadRequest("base_revision must be an integer >= 0.")
    if len(title) > MAX_TITLE_CHARS:
        raise _BadRequest("title is longer than %d characters." % MAX_TITLE_CHARS)
    if len(body) > MAX_NOTE_BODY_CHARS:
        raise _BadRequest("body is longer than %d characters." % MAX_NOTE_BODY_CHARS)
    if "\x00" in title or "\x00" in body:
        raise _BadRequest("NUL characters are not allowed.")
    if "\n" in title or "\r" in title:
        raise _BadRequest("title may not contain line breaks.")
    try:
        title.encode("utf-8")
        body.encode("utf-8")
    except UnicodeEncodeError:
        raise _BadRequest("Text is not valid Unicode.")
    return title, body, base


def _error_payload(code, message):
    return {"error": {"code": code, "message": message}}


class _Handler(http.server.BaseHTTPRequestHandler):
    timeout = 10
    server_version = "pdf-annotator"
    sys_version = ""
    protocol_version = "HTTP/1.0"  # one request per connection, no desync

    _responded = False
    _body_consumed = False

    # -- plumbing ---------------------------------------------------------

    @property
    def app(self):
        return self.server.app

    def log_message(self, format, *args):
        pass

    def _send(self, status, body, content_type, extra_headers=()):
        self._responded = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
        for name, value in extra_headers:
            self.send_header(name, value)
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def _send_json(self, status, payload, extra_headers=()):
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, _JSON_TYPE, extra_headers)

    def _drain(self):
        """Read and discard a small declared request body before replying."""
        self._body_consumed = True
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_DRAIN_BYTES:
                return
            while length > 0:
                chunk = self.rfile.read(min(length, 65536))
                if not chunk:
                    break
                length -= len(chunk)
        except (OSError, ValueError):
            pass

    def _fail(self, status, code, message, extra_headers=(), extra_body=None):
        if self.command == "PUT" and not self._body_consumed:
            self._drain()
        payload = _error_payload(code, message)
        if extra_body:
            payload.update(extra_body)
        self._send_json(status, payload, extra_headers)

    def send_error(self, code, message=None, explain=None):
        # Replaces http.server's HTML error pages (parse errors, timeouts).
        names = {400: "bad_request", 408: "request_timeout",
                 414: "bad_request", 431: "bad_request",
                 501: "method_not_allowed"}
        error_code = names.get(code, "bad_request" if code < 500
                               else "internal_error")
        try:
            self._send_json(code, _error_payload(
                error_code, "The request could not be processed."))
        except OSError:
            self.close_connection = True

    # -- dispatch ---------------------------------------------------------

    def _dispatch(self):
        self._responded = False
        self._body_consumed = False
        try:
            self._route()
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            sys.stderr.write("internal error: %s\n" % type(exc).__name__)
            if not self._responded:
                try:
                    self._fail(500, "internal_error",
                               "Internal server error.")
                except OSError:
                    self.close_connection = True

    do_GET = do_PUT = do_POST = do_DELETE = do_PATCH = _dispatch
    do_OPTIONS = do_HEAD = _dispatch

    def _host_ok(self):
        hosts = self.headers.get_all("Host") or []
        return len(hosts) == 1 and hosts[0].lower() in self.app.allowed_hosts

    def _method_not_allowed(self, allow):
        self._fail(405, "method_not_allowed",
                   "Method not allowed; use %s." % allow,
                   extra_headers=(("Allow", allow),))

    def _route(self):
        if not self._host_ok():
            self._fail(403, "forbidden_host", "Host header not allowed.")
            return
        method = self.command
        # Route against the original target, including any leading slashes.
        path = self.requestline.split(maxsplit=2)[1].split("?", 1)[0]
        if path in STATIC_ROUTES:
            if method != "GET":
                self._method_not_allowed("GET")
            else:
                self._static(path)
        elif path == "/api/v1/health":
            if method != "GET":
                self._method_not_allowed("GET")
            else:
                self._send_json(200, {"status": "ok", "version": __version__,
                                      "schema_version": SCHEMA_VERSION})
        elif path == "/api/v1/document":
            if method != "GET":
                self._method_not_allowed("GET")
            else:
                self._document()
        elif path == "/api/v1/document/file":
            if method != "GET":
                self._method_not_allowed("GET")
            else:
                self._document_file()
        elif path.startswith(NOTES_PREFIX) and "/" not in path[len(NOTES_PREFIX):]:
            rest = path[len(NOTES_PREFIX):]
            if method == "GET":
                self._get_note(rest)
            elif method == "PUT":
                self._put_note(rest)
            else:
                self._method_not_allowed("GET, PUT")
        else:
            self._fail(404, "not_found", "Not found.")

    # -- handlers ---------------------------------------------------------

    def _static(self, path):
        filename, content_type = STATIC_ROUTES[path]
        try:
            body = (STATIC_DIR / filename).read_bytes()
        except OSError:
            self._fail(404, "not_found", "Not found.")
            return
        self._send(200, body, content_type)

    def _document(self):
        try:
            doc = parse_pdf(self.app.pdf_bytes)
        except PdfError as exc:
            self._fail(422, "unsupported_pdf", str(exc))
            return
        self._send_json(200, doc)

    def _document_file(self):
        self._send(200, self.app.pdf_bytes, "application/pdf", (
            ("Content-Disposition", 'attachment; filename="sample.pdf"'),))

    def _resolve_page(self, rest):
        """Return a valid page number, or None after sending an error."""
        if not _PAGE_RE.fullmatch(rest):
            self._fail(400, "bad_request", "Page must be an integer.")
            return None
        page = int(rest)
        try:
            count = parse_pdf(self.app.pdf_bytes)["page_count"]
        except PdfError as exc:
            self._fail(422, "unsupported_pdf", str(exc))
            return None
        if page < 1 or page > count:
            self._fail(404, "page_not_found", "No such page.")
            return None
        return page

    def _get_note(self, rest):
        page = self._resolve_page(rest)
        if page is not None:
            self._send_json(200, self.app.storage.get_note(page, DOCUMENT_ID))

    def _put_note(self, rest):
        origins = self.headers.get_all("Origin")
        if origins is not None and (
                len(origins) != 1 or origins[0].lower() not in self.app.allowed_origins):
            self._fail(403, "forbidden_origin", "Origin not allowed.")
            return
        page = self._resolve_page(rest)
        if page is None:
            return

        parts = [p.strip() for p in
                 (self.headers.get("Content-Type") or "").split(";")]
        ok_type = parts[0].lower() == "application/json"
        for param in parts[1:]:
            key, _, value = param.partition("=")
            if key.strip().lower() == "charset" and \
                    value.strip().strip('"').lower() != "utf-8":
                ok_type = False
        if not ok_type:
            self._fail(415, "unsupported_media_type",
                       "Content-Type must be application/json.")
            return

        lengths = self.headers.get_all("Content-Length") or []
        if (len(lengths) != 1 or self.headers.get("Transfer-Encoding")
                or not _LENGTH_RE.fullmatch(lengths[0].strip())):
            self._fail(400, "bad_request",
                       "A valid Content-Length header is required.")
            return
        length = int(lengths[0].strip())
        if length > MAX_BODY_BYTES:
            self._fail(413, "too_large", "Request body is too large.")
            return
        raw = self.rfile.read(length)
        self._body_consumed = True
        if len(raw) != length:
            self._fail(400, "bad_request", "Request body was truncated.")
            return

        try:
            payload = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_reject_duplicates,
                parse_constant=_reject_constant)
            title, body, base = _validate_note(payload)
        except _BadRequest as exc:
            self._fail(400, "bad_request", str(exc))
            return
        except (ValueError, RecursionError):
            self._fail(400, "bad_request", "Body is not valid UTF-8 JSON.")
            return

        saved, note = self.app.storage.put_note(
            page, title, body, base, DOCUMENT_ID)
        if saved:
            self._send_json(200, note)
        else:
            self._fail(409, "revision_conflict",
                       "The note changed since you loaded it.",
                       extra_body={"current": note})


class _HttpServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64
    # SO_REUSEADDR on Windows would let another process share the port.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, handler, app):
        self.app = app
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(address, handler)

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        pass


class AppServer:
    def __init__(self, data_dir, port=0):
        if isinstance(port, bool) or not isinstance(port, int) \
                or not 0 <= port <= 65535:
            raise ValueError("port must be an integer from 0 to 65535")
        self.storage = Storage(data_dir)
        self.pdf_bytes = build_sample_pdf()
        try:
            self._httpd = _HttpServer(("127.0.0.1", port), _Handler, self)
        except BaseException:
            self.storage.close()
            raise
        self.port = self._httpd.server_address[1]
        self.allowed_hosts = frozenset(
            ["127.0.0.1:%d" % self.port, "localhost:%d" % self.port])
        self.allowed_origins = frozenset(
            "http://" + h for h in self.allowed_hosts)
        self._thread = None
        self._stopped = False

    def start(self):
        if self._thread is not None or self._stopped:
            raise RuntimeError("server already started or stopped")
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.1},
            daemon=True)
        self._thread.start()

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        try:
            if self._thread is not None:
                self._httpd.shutdown()
        finally:
            self._httpd.server_close()
            if self._thread is not None:
                self._thread.join(timeout=10)
            self.storage.close()


def create_server(data_dir, port=0):
    return AppServer(pathlib.Path(data_dir), port)

import http.client
import json
import pathlib
import socket
import tempfile
import threading
import unittest

from pdf_annotator import __version__
from pdf_annotator.pdfgen import build_sample_pdf
from pdf_annotator.pdfparse import parse_pdf
from pdf_annotator.server import STATIC_DIR, create_server


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = pathlib.Path(self._tmp.name) / "data"
        self.start_server()

    def start_server(self):
        self.server = create_server(self.data_dir, 0)
        self.server.start()
        self.port = self.server.port
        self._stop_cleanup = self.addCleanup(self.server.stop)

    def request(self, method, path, body=None, headers=None, raw=False):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            hdrs = dict(headers or {})
            if isinstance(body, (dict, list, str)):
                body = json.dumps(body).encode("utf-8")
                hdrs.setdefault("Content-Type", "application/json")
            conn.request(method, path, body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            if not raw and resp.getheader("Content-Type", "").startswith(
                    "application/json"):
                data = json.loads(data.decode("utf-8"))
            return resp.status, resp, data
        finally:
            conn.close()

    def put_note(self, page, title, body, base, **kw):
        return self.request(
            "PUT", "/api/v1/notes/%d" % page,
            {"title": title, "body": body, "base_revision": base}, **kw)

    def assertError(self, result, status, code):
        got_status, _, data = result
        self.assertEqual(got_status, status, data)
        self.assertEqual(data["error"]["code"], code)
        self.assertTrue(data["error"]["message"])


class BasicEndpoints(ApiTestCase):
    def test_health(self):
        status, resp, data = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok", "version": __version__,
                                "schema_version": 1})

    def test_security_headers(self):
        _, resp, _ = self.request("GET", "/api/v1/health")
        self.assertIn("default-src 'none'",
                      resp.getheader("Content-Security-Policy"))
        self.assertIn("frame-ancestors 'none'",
                      resp.getheader("Content-Security-Policy"))
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(resp.getheader("Referrer-Policy"), "no-referrer")
        self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))

    def test_document(self):
        status, _, data = self.request("GET", "/api/v1/document")
        self.assertEqual(status, 200)
        self.assertEqual(data, parse_pdf(build_sample_pdf()))
        self.assertEqual(data["page_count"], 2)

    def test_document_file(self):
        status, resp, data = self.request("GET", "/api/v1/document/file")
        self.assertEqual(status, 200)
        self.assertEqual(data, build_sample_pdf())
        self.assertEqual(resp.getheader("Content-Type"), "application/pdf")
        self.assertEqual(resp.getheader("Content-Disposition"),
                         'attachment; filename="sample.pdf"')

    def test_unparseable_document_is_422(self):
        self.server.pdf_bytes = b"not a pdf"
        result = self.request("GET", "/api/v1/document")
        self.assertError(result, 422, "unsupported_pdf")
        self.assertIn("malformed", result[2]["error"]["message"])

    def test_static_allowlist(self):
        for path, ctype in (("/", "text/html"), ("/app.css", "text/css"),
                            ("/app.js", "text/javascript")):
            name = {"/": "index.html"}.get(path, path.lstrip("/"))
            f = STATIC_DIR / name
            if not f.is_file():
                continue
            status, resp, data = self.request("GET", path, raw=True)
            self.assertEqual(status, 200, path)
            self.assertTrue(resp.getheader("Content-Type").startswith(ctype))
            self.assertEqual(data, f.read_bytes())

    def test_unknown_and_traversal_paths_404(self):
        for path in ("/nope", "/index.html", "/static/app.js",
                     "/../pdf_annotator/server.py", "/%2e%2e/server.py",
                     "/app.js/", "/static/../app.js", "/api/v1/",
                     "/api/v1/notes/1/extra",
                     "/..%5cserver.py"):
            self.assertError(self.request("GET", path), 404, "not_found")

    def test_method_not_allowed(self):
        status, resp, data = self.request("POST", "/api/v1/health", b"{}")
        self.assertEqual(status, 405)
        self.assertEqual(data["error"]["code"], "method_not_allowed")
        self.assertEqual(resp.getheader("Allow"), "GET")
        status, resp, data = self.request("OPTIONS", "/api/v1/notes/1")
        self.assertEqual(status, 405)
        self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))
        self.assertEqual(self.request("PUT", "/api/v1/document", b"{}")[0], 405)
        self.assertEqual(self.request("DELETE", "/")[0], 405)

    def test_foreign_host_rejected(self):
        for host in ("evil.example", "127.0.0.1", "localhost:1",
                     "127.0.0.1:%d.evil.example" % self.port):
            self.assertError(
                self.request("GET", "/api/v1/health", headers={"Host": host}),
                403, "forbidden_host")
        status, _, _ = self.request(
            "GET", "/api/v1/health",
            headers={"Host": "localhost:%d" % self.port})
        self.assertEqual(status, 200)


class NoteTests(ApiTestCase):
    def test_default_note(self):
        status, _, data = self.request("GET", "/api/v1/notes/1")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"page": 1, "title": "", "body": "",
                                "revision": 0, "updated_at": None})

    def test_create_and_read(self):
        status, _, note = self.put_note(1, " Title ", "  line1\nline2  ", 0)
        self.assertEqual(status, 200)
        self.assertEqual(note["revision"], 1)
        self.assertTrue(note["updated_at"].endswith("Z"))
        _, _, again = self.request("GET", "/api/v1/notes/1")
        self.assertEqual(again, note)
        self.assertEqual(again["title"], " Title ")
        self.assertEqual(again["body"], "  line1\nline2  ")
        _, _, other = self.request("GET", "/api/v1/notes/2")
        self.assertEqual(other["revision"], 0)

    def test_unicode_round_trip(self):
        self.put_note(2, "café", "☃ \U0001F600", 0)
        _, _, note = self.request("GET", "/api/v1/notes/2")
        self.assertEqual((note["title"], note["body"]),
                         ("café", "☃ \U0001F600"))

    def test_limits_accept_maximum(self):
        status, _, _ = self.put_note(1, "t" * 120, "b" * 4000, 0)
        self.assertEqual(status, 200)

    def test_conflict_preserves_current(self):
        self.put_note(1, "first", "one", 0)
        result = self.put_note(1, "second", "two", 0)
        self.assertError(result, 409, "revision_conflict")
        current = result[2]["current"]
        self.assertEqual((current["title"], current["body"],
                          current["revision"]), ("first", "one", 1))
        _, _, stored = self.request("GET", "/api/v1/notes/1")
        self.assertEqual(stored, current)
        status, _, ok = self.put_note(1, "second", "two", 1)
        self.assertEqual((status, ok["revision"]), (200, 2))
        # A base revision from the future is also a conflict.
        self.assertError(self.put_note(1, "x", "y", 99), 409,
                         "revision_conflict")

    def test_page_errors(self):
        self.assertError(self.request("GET", "/api/v1/notes/abc"), 400,
                         "bad_request")
        self.assertError(self.request("GET", "/api/v1/notes/1.5"), 400,
                         "bad_request")
        for page in ("0", "3", "-1", "999999999"):
            self.assertError(self.request("GET", "/api/v1/notes/" + page),
                             404, "page_not_found")
        self.assertError(self.put_note(3, "", "", 0), 404, "page_not_found")
        self.assertError(self.request("PUT", "/api/v1/notes/x", b"{}"), 400,
                         "bad_request")

    def test_validation_errors(self):
        good = {"title": "t", "body": "b", "base_revision": 0}
        bad = [
            {**good, "extra": 1},
            {"title": "t", "body": "b"},
            {"title": "t", "base_revision": 0},
            {**good, "title": 5},
            {**good, "body": None},
            {**good, "base_revision": "0"},
            {**good, "base_revision": True},
            {**good, "base_revision": 1.5},
            {**good, "base_revision": -1},
            {**good, "title": "t" * 121},
            {**good, "body": "b" * 4001},
            {**good, "title": "a\x00b"},
            {**good, "body": "a\x00b"},
            {**good, "title": "a\nb"},
            {**good, "title": "\ud800"},
            [],
            "text",
        ]
        for payload in bad:
            self.assertError(
                self.request("PUT", "/api/v1/notes/1", payload), 400,
                "bad_request")
        for raw in (b"", b"{", b"\xff\xfe", b'{"title":"a","title":"b",'
                    b'"body":"","base_revision":0}',
                    b'{"title":"","body":"","base_revision":NaN}'):
            self.assertError(
                self.request("PUT", "/api/v1/notes/1", raw,
                             {"Content-Type": "application/json"}),
                400, "bad_request")
        self.assertEqual(self.request("GET", "/api/v1/notes/1")[2]["revision"], 0)

    def test_body_may_contain_newline_but_title_may_not(self):
        self.assertEqual(self.put_note(1, "a", "x\ny", 0)[0], 200)

    def test_bad_content_type(self):
        body = json.dumps({"title": "", "body": "", "base_revision": 0}).encode()
        for ctype in ("text/plain", "application/x-www-form-urlencoded",
                      "application/json; charset=latin-1", ""):
            self.assertError(
                self.request("PUT", "/api/v1/notes/1", body,
                             {"Content-Type": ctype}),
                415, "unsupported_media_type")
        status, _, _ = self.request(
            "PUT", "/api/v1/notes/1", body,
            {"Content-Type": "Application/JSON; charset=UTF-8"})
        self.assertEqual(status, 200)

    def test_oversize_body_413(self):
        big = b'{"title":"","body":"' + b"a" * 20000 + b'","base_revision":0}'
        self.assertError(
            self.request("PUT", "/api/v1/notes/1", big,
                         {"Content-Type": "application/json"}),
            413, "too_large")
        # A body of exactly 16384 bytes is accepted.
        pad = b'{"title":"","body":"","base_revision":0}'
        pad = pad + b" " * (16384 - len(pad))
        status, _, _ = self.request("PUT", "/api/v1/notes/1", pad,
                                    {"Content-Type": "application/json"})
        self.assertEqual(status, 200)

    def test_missing_content_length_400(self):
        with socket.create_connection(("127.0.0.1", self.port), 10) as s:
            s.sendall(("PUT /api/v1/notes/1 HTTP/1.0\r\nHost: 127.0.0.1:%d\r\n"
                       "Content-Type: application/json\r\n\r\n"
                       % self.port).encode("ascii"))
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8")
        self.assertTrue(text.startswith("HTTP/1.0 400"), text)
        self.assertIn('"bad_request"', text)

    def test_invalid_content_length_400(self):
        for value in ("abc", "-5", "1e3"):
            with socket.create_connection(("127.0.0.1", self.port), 10) as s:
                s.sendall(("PUT /api/v1/notes/1 HTTP/1.0\r\nHost: "
                           "127.0.0.1:%d\r\nContent-Type: application/json\r\n"
                           "Content-Length: %s\r\n\r\n"
                           % (self.port, value)).encode("ascii"))
                data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            self.assertTrue(data.startswith(b"HTTP/1.0 400"), data)

    def test_origin_checks(self):
        for origin in ("http://evil.example", "null",
                       "https://127.0.0.1:%d" % self.port,
                       "http://127.0.0.1",
                       "http://127.0.0.1:%d.evil.example" % self.port):
            self.assertError(
                self.put_note(1, "t", "b", 0, headers={"Origin": origin}),
                403, "forbidden_origin")
        _, _, note = self.request("GET", "/api/v1/notes/1")
        self.assertEqual(note["revision"], 0)
        for origin in ("http://127.0.0.1:%d" % self.port,
                       "http://localhost:%d" % self.port):
            base = self.request("GET", "/api/v1/notes/1")[2]["revision"]
            status, _, _ = self.put_note(1, "t", "b", base,
                                         headers={"Origin": origin})
            self.assertEqual(status, 200)
        # Absent Origin is allowed (covered by the other tests).

    def test_restart_persistence(self):
        self.put_note(1, "kept", "across restart", 0)
        self.server.stop()
        self.start_server()
        _, _, note = self.request("GET", "/api/v1/notes/1")
        self.assertEqual((note["title"], note["body"], note["revision"]),
                         ("kept", "across restart", 1))
        self.assertEqual(self.put_note(1, "again", "x", 1)[0], 200)

    def test_concurrent_puts_one_winner(self):
        workers = 10
        barrier = threading.Barrier(workers)
        results = [None] * workers

        def work(i):
            barrier.wait(timeout=10)
            results[i] = self.put_note(1, "w%d" % i, "body", 0)

        threads = [threading.Thread(target=work, args=(i,))
                   for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        statuses = sorted(r[0] for r in results)
        self.assertEqual(statuses, [200] + [409] * (workers - 1))
        winner = next(r[2] for r in results if r[0] == 200)
        for status, _, data in results:
            if status == 409:
                self.assertEqual(data["error"]["code"], "revision_conflict")
                self.assertEqual(data["current"]["revision"], 1)
        _, _, stored = self.request("GET", "/api/v1/notes/1")
        self.assertEqual(stored, winner)
        self.assertEqual(stored["revision"], 1)


class ServerLifecycle(unittest.TestCase):
    def test_stop_is_idempotent_and_port_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = create_server(pathlib.Path(tmp), 0)
            server.start()
            self.assertGreater(server.port, 0)
            server.stop()
            server.stop()
            with self.assertRaises(ValueError):
                create_server(pathlib.Path(tmp), 70000)

    def test_stop_without_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_server(pathlib.Path(tmp), 0).stop()


if __name__ == "__main__":
    unittest.main()

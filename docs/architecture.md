# Architecture notes and PRD reconciliation

This document describes the code as it is at commit `32f8cf1` (M1), follows one workflow from the command line to the database, and lists where [PRD.md](PRD.md) and the code differ. It complements the PRD; it does not replace it. The backlog is the epic, issue #1, and its sub-issues.

Status words used below:

- **Implemented**: in the code, and seen working during preparation (a passing test, a request against a running server, or a step in a local browser).
- **Planned**: not in the code; tracked by the issue named.
- **Needs verification**: in the code or claimed in a document, but not observed during preparation.

Preparation ran on Windows 11 with Python 3.13.14, on 2026-11-22. Section 9 says what was run.

## 1. The system at a glance

One Python process, standard library only. It serves a static page and a JSON API on `127.0.0.1`, parses one PDF that it generates itself, and keeps page notes in one SQLite file. Nothing is uploaded and nothing is fetched from another host.

| Module | Job | It must not |
|---|---|---|
| `pdf_annotator/__main__.py`, `cli.py` | Command line: `--data-dir` and `--port` (both required), start, clean stop, exit code 2 for an unusable data directory, 1 for a port that cannot be bound (`cli.py:38-57`) | hold application logic |
| `pdf_annotator/server.py` | HTTP: routing (`_route`, `:201-238`), request guards, static allowlist, security headers, JSON encoding, note validation (`_validate_note`, `:66-91`), mapping of results to status codes. `AppServer` (`:382-421`) owns the listener, the `Storage` object and the sample bytes | run SQL or parse PDF syntax itself |
| `pdf_annotator/pdfparse.py` | Pure function `parse_pdf(bytes) -> dict` (`:533-581`). Reads the cross-reference table, the objects and the page content, and returns the display list. Raises `PdfError(code, message)` | touch the network, the file system or the database |
| `pdf_annotator/pdfgen.py` | `build_sample_pdf()` (`:17-54`): the deterministic two-page sample, 952 bytes | read any input |
| `pdf_annotator/storage.py` | The only module that imports `sqlite3`. Migrations by `PRAGMA user_version` (`:74-96`), `get_note`, `put_note` | know about HTTP |
| `pdf_annotator/static/` | One page (`index.html`), one script (`app.js`, 370 lines, no framework), one stylesheet. Draws the display list on a Canvas2D and mirrors it as a text list | read PDF bytes, or put server text into the page as HTML |
| `tests/` | `unittest`: `test_pdfparse.py` (22 tests), `test_storage.py` (11, including the command line), `test_api.py` (26, against a real server on port 0). `tests/__init__.py` holds `build_pdf`, a builder for small PDFs | use a fixed port, the network or a third-party file |

The server composes the other modules; none of them imports the server. The page talks to the server through `/api/v1` only.

## 2. Traced workflow: save a page note and see it again after a restart

1. `python -m pdf_annotator --data-dir D --port P` enters `cli.main` (`cli.py:38`), which calls `create_server` (`:41`).
2. `AppServer.__init__` (`server.py:382-400`) builds `Storage(D)`: create the directory, check that it is writable, open `D/annotator.sqlite3` and migrate inside one `BEGIN IMMEDIATE` transaction (`storage.py:46-96`). A database with a higher `user_version` than the code knows is refused untouched. Then the sample bytes are generated once (`server.py:388`) and the listener binds `127.0.0.1` (`:390`). The allowed `Host` values are `127.0.0.1:<port>` and `localhost:<port>` (`:395-398`).
3. The browser requests `/`, `/app.css` and `/app.js`. Each is looked up in the fixed table `STATIC_ROUTES` (`server.py:20-24`, `:242-249`); the request path is never joined into a file path.
4. `loadDocument` (`app.js:344-365`) requests `GET /api/v1/document`. The handler calls `parse_pdf` on the sample bytes for every request (`server.py:251-257`) and returns the whole display list, all pages at once.
5. `renderPage` (`app.js:149-158`) calls `drawPage` (`:96-126`), which sizes the canvas to the page, flips the y axis and draws rectangles and text, and `describePage` (`:128-147`), which writes the same operations as list items with `textContent`.
6. `loadNote` (`app.js:169-198`) requests `GET /api/v1/notes/{page}`. `_resolve_page` (`server.py:263-277`) parses the PDF again to learn the page count, then `Storage.get_note` (`storage.py:113-116`) returns the row, or a note with revision 0 when there is none.
7. Save: `save` (`app.js:218-262`) sends `PUT /api/v1/notes/{page}` with `{title, body, base_revision}`. `_put_note` (`server.py:284-342`) checks `Origin` when the header is present, resolves the page, checks the media type, requires one valid `Content-Length`, refuses more than 16,384 bytes with 413, reads exactly that many bytes, rejects duplicate keys and non-finite numbers, and validates the shape.
8. `Storage.put_note` (`storage.py:118-163`) opens `BEGIN IMMEDIATE`, compares the stored revision with `base_revision`, and inserts revision 1 or updates to revision + 1. When the revisions differ nothing is written and the answer is 409 `revision_conflict` with the stored note under `current`. The page then shows the conflict panel and keeps the typed text (`app.js:207-215`, `:310-333`).
9. After a restart with the same data directory the same row is read again in step 6.

## 3. Who owns which data

| Data | Owner | Lifetime |
|---|---|---|
| PDF bytes | `AppServer.pdf_bytes`, produced by `pdfgen` | Memory only. No file chosen by the person reaches the server at M1 |
| Parsed document (display list) | Nobody: it is rebuilt on every `/api/v1/document` request and on every note request | One request |
| Notes | SQLite table `notes(document_id, page, title, body, revision, updated_at)`, primary key `(document_id, page)`, `CHECK` constraints on lengths, page and revision (`storage.py:14-24`) | The data directory |
| Document identity | The constant `"sample"`, defined twice: `storage.py:10` and `pdfparse.py:24` | Fixed |
| Page state in the browser | The `state` object in `app.js:20-29`. Nothing is kept in browser storage | The tab |

## 4. Rules the code keeps

A change that breaks one of these needs a stated reason in the pull request and, for the first five, the owner's agreement.

1. **No length from a file is trusted.** Every size, count and nesting depth is checked against a constant before it is used (`pdfparse.py:12-22`); a stream is sliced only after its declared length is checked against the cap and the file end (`:233-245`). Nothing is evaluated.
2. **Unknown input is refused, not guessed.** Operators outside `w RG rg re S f BT ET Tf Td Tj` raise `unsupported_operator`; the names in `_FORBIDDEN_NAMES` (`:31-35`: filters, object and cross-reference streams, `/Prev`, `/Encrypt`, `/Rotate`, script and launch actions, embedded files, forms) raise `unsupported_feature` wherever they appear in an object, as a dictionary key or as a name value (`_parse_name`, `:80-92`).
3. **Loopback only.** The listener binds `127.0.0.1`. Every request must carry exactly one allowed `Host` header (`server.py:192-194`). A `PUT` with an `Origin` header must carry an allowed one (`:285-289`); a `PUT` without `Origin` is accepted. No CORS header is ever sent, and `OPTIONS` answers 405.
4. **A save is a compare-and-set.** It succeeds only when `base_revision` equals the stored revision, inside one `BEGIN IMMEDIATE` transaction. A stale save writes nothing.
5. **Text is data.** Document text and note text reach the page through `textContent`, form values and canvas drawing only. The CSP is `default-src 'none'` with `script-src 'self'` and `style-src 'self'`, so inline script and style do not run (`server.py:36-44`).
6. **One request per connection.** The handler speaks HTTP/1.0 and closes after each response (`server.py:102`, `:125-129`). At most 64 requests are handled at once (`:31`, `:353-376`); a socket operation times out after 10 seconds (`:99`).
7. **Errors have one shape**, `{"error": {"code", "message"}}`, and never carry a traceback (`:173-187`). A 409 adds `current` beside `error`.
8. **One short-lived SQLite connection per operation** (`storage.py:64-72`), so handler threads share nothing.
9. **Typed text is never dropped** without a choice by the person (conflict panel, retry button, unload prompt).

## 5. The display list, as the code emits it

The PRD names the display list but does not give its shape. This is what `parse_pdf` returns and what `GET /api/v1/document` sends (`pdfparse.py:357-363`, `:402-406`, `:525-530`, `:574-581`):

```json
{"document_id": "sample", "title": "Sample platform review", "size_bytes": 952,
 "sha256": "<64 hex>", "page_count": 2,
 "pages": [{"index": 1, "width": 300, "height": 200,
   "ops": [{"op": "rect", "x": 20, "y": 30, "w": 260, "h": 120,
            "stroke": [0, 0, 0], "fill": null, "line_width": 1},
           {"op": "text", "x": 20, "y": 170, "size": 18, "font": "Helvetica",
            "text": "Platform map", "fill": [0, 0, 0]}]}]}
```

Coordinates are PDF user space in points, origin at the bottom left; the page flips the y axis. Colours are three numbers from 0 to 1. A rectangle has either `stroke` or `fill`, the other is `null`. Whole numbers are sent as integers. `index` starts at 1.

## 6. Status and error codes in the code

| Status | `error.code` | When |
|---|---|---|
| 400 | `bad_request` | Page is not an integer; missing, repeated or invalid `Content-Length`; `Transfer-Encoding` present; truncated body; body is not UTF-8 JSON, has duplicate keys, or fails the shape and length rules; malformed request line |
| 403 | `forbidden_host`, `forbidden_origin` | Rule 3 above |
| 404 | `not_found`, `page_not_found` | Unknown path; page outside 1 to the page count |
| 405 | `method_not_allowed` | Known path, other method; the `Allow` header lists the methods |
| 409 | `revision_conflict` | Stale `base_revision`; `current` holds the stored note |
| 413 | `too_large` | Declared body over 16,384 bytes |
| 415 | `unsupported_media_type` | `Content-Type` is not `application/json` (a `charset` other than UTF-8 also fails) |
| 422 | `unsupported_pdf` | `parse_pdf` raised; the message starts with the parser code |
| 500 | `internal_error` | Any other exception |

Parser codes (`PdfError.code`): `too_large`, `bad_xref`, `bad_offset`, `unsupported_feature`, `unsupported_operator`, `malformed`, `limit_exceeded`.

## 7. PRD compared with the code

| PRD item | Status | Evidence or issue |
|---|---|---|
| M1 generated two-page sample (section 7) | Implemented | `pdfgen.py`; 952 bytes, same hash on every start |
| Parsing of the classic cross-reference table and ASCII content, operator allowlist, limits (6.3) | Implemented | `tests/test_pdfparse.py`, 22 tests |
| Canvas drawing and text equivalent (6.3, 6.4) | Implemented | Seen in a local browser: both pages, the list under the preview, the swatch pixel `rgb(51,102,204)` |
| Page navigation (6.4) | Implemented | "Next page" pressed in a local browser; "Previous page" was enabled on page 2 but not pressed |
| Page note in SQLite, kept across a restart (6.2, 8) | Implemented | `test_restart_persistence`; also seen in a local browser after a restart |
| Stale-save handling with the conflict panel (6.3, 8) | Implemented | `test_conflict_preserves_current`, `test_concurrent_puts_one_winner`; panel and "Keep my text and save over" seen in a local browser |
| API (6.1) and security rules (9) | Implemented | `tests/test_api.py`; 403, 404, 405, 409, 415 also seen with `curl` |
| Acceptance matrix rows 1 to 10 (section 10) | Implemented | Covered by the 59 tests |
| Acceptance matrix row 11, no horizontal scroll at 800x600; also 360 px wide (6.4) | Implemented | Seen in a local browser: document width 785 at a window width of 800, and 360 at 360 |
| "Use saved version", the Retry button, Ctrl+S, the unload prompt, keyboard-only operation, contrast of 4.5:1 (6.4, 8) | Needs verification | In the code (`app.js`, `app.css`); not exercised during preparation |
| Linux and Python 3.12 (section 5, README) | Needs verification | The README reports a run on Ubuntu 24.04 under WSL with Python 3.12.3; preparation ran Windows and Python 3.13.14 only |
| P1 opening a file chosen by the person | Planned | #NEW-A (document routes and parse cache), #NEW-B (upload and store) |
| P1 cross-reference streams, object streams, Flate, update chains | Planned | #2 |
| P2 page tree, inherited resources, vector and text operators | Planned | #3; text in fonts outside the standard set: #NEW-C |
| P3 images, rotation, zoom, bounded page cache | Planned | #4 |
| P4 notes anchored to page regions | Planned | #5 |
| P5 export as an incremental update | Planned | #6 |
| Reconciling the PRD, the README and this file once the work is in | Planned | #NEW-D |

## 8. Where the PRD and the code differ

| # | Finding | Effect | Handled by |
|---|---|---|---|
| D1 | PRD 6.1 says a note request answers 404 "outside 1..2". The code compares with the parsed page count (`server.py:270-275`) | Same result for the sample only | #NEW-A rewrites the route table in PRD 6.1 |
| D2 | The PRD gives no shape for the display list, and its API table does not list `document_id`, `title`, `size_bytes` and `sha256`. The only written contract was a preparation note that is not in the repository | A reader of the repository cannot learn the contract from the PRD | Section 5 above; #NEW-A moves the shape into the PRD when it splits the list by page |
| D3 | PRD 6.1 lists statuses but not the error codes, the 405 or the 422 on note routes. `send_error` also maps 408 to `request_timeout` (`server.py:158-169`), which was not seen and may be unreachable | Clients must read the code | Section 6 above; #NEW-A |
| D4 | PRD 9 says mutating requests "check Origin". A `PUT` without an `Origin` header is accepted (`server.py:285-289`) | Deliberate: non-browser local tools can write. Every new mutating route must make the same choice on purpose | Stated in #NEW-B, #5 and #6 |
| D5 | PRD 6.4 does not list the link "Download sample PDF" (`index.html:14`), the counters `title-count` and `body-count`, or the ids `note-form`, `conflict-title` and `conflict-body` | Minor | #NEW-D |
| D6 | PRD 6.3 lists four limits. The code has eleven (`pdfparse.py:12-22`), among them 1,000 cross-reference entries, nesting depth 8, 64 entries per array or dictionary, 16 operands, page side 14,400 points | The planned work changes most of them; each ticket must say which | #2, #3; README "Limits" in the same pull request |
| D7 | The PRD says nothing about cost. Every note request parses the whole PDF again (`server.py:263-277`), and the document request sends all pages at once | Harmless at 952 bytes; not acceptable for files of megabytes | #NEW-A |
| D8 | The document id is the constant `"sample"` in two modules. PRD 13 leaves open whether notes are keyed by a content hash | Notes of two files would collide | #NEW-A (one definition, id in the route), #NEW-B (SHA-256 of the file as the id) |
| D9 | PRD 3 makes P2 depend on P1, P3 on P2, P4 on P3. Read against the code, the content work (P2) needs the document object but not the compressed file structures, and the storage half of P4 needs neither images nor rotation | The strict chain hides work that can run side by side | The epic's dependency table |
| D10 | Issue #3 keeps the limit of 500 operators per page; issue #4 asks for a 30-page document while the code allows 10 pages; no issue states the new page, object or operator limits | Real files exceed 500 operators on almost every page, so the epic's outcome cannot be met with that limit | #2 and #3 set and document the new limits |
| D11 | PRD 10 ends with "execution results are not claimed here", while the README reports a verified baseline | Not a contradiction, but the PRD statuses will go stale | #NEW-D |
| D12 | PRD 12 says browser behaviour is checked by hand. Issue #4 introduces a self-check page in plain JavaScript | The PRD test plan must name it once it exists | #4, #NEW-D |
| D13 | The PRD asks that an independent checker for P5 be confirmed in the workspace first. On the preparation machine `pdftotext` 4.00 (Xpdf, shipped with Git for Windows) is on the path and read the sample without a message; `qpdf`, `mutool` and Ghostscript are not installed | One independent reader is available on this machine; none is guaranteed elsewhere | #6 |

## 9. What was run during preparation

All on Windows 11, Python 3.13.14, SQLite 3.50.4, once each, from a worktree at `32f8cf1`:

- `python -m unittest discover -s tests`: `Ran 59 tests in 3.880s`, `OK`.
- `python -m pdf_annotator --data-dir <scratch> --port 18791`: printed `Serving on http://127.0.0.1:18791/`; the listener was on `127.0.0.1` only.
- `curl`: health 200; `/` 200; document 200 with 2 pages; document file 200; note read 200 with revision 0; `PUT` 200 with revision 1; stale `PUT` 409 with `current`; page 3 gives 404; foreign `Host` and foreign `Origin` give 403; `text/plain` gives 415; `POST` on the document gives 405; a traversal-looking path gives 404; the four security headers present and no CORS header.
- A local browser (Chromium 156 engine) on `http://127.0.0.1:18791/`: both pages, the text list, save ("Saved revision 2"), a stale save with the conflict panel and the typed text kept, "Keep my text and save over" ("Saved revision 4"), the same note after a server restart, no horizontal overflow at 800x600 and 360x640, nine requests, all to `127.0.0.1`.
- Both server processes were stopped by process id and the port was free afterwards.

Not run: Linux, Python 3.12, Firefox, a screen reader, keyboard-only operation, a click on "Previous page", the Retry path, "Use saved version".

## 10. Risks for the planned work

1. **The parser's attack surface grows with every ticket.** Compressed streams can expand without bound, object streams and update chains can loop, and image sizes are declared by the file. Rule 1 has to hold for each new structure: cap the output of decompression while it runs, count visited objects, and refuse before allocating.
2. **The HTTP layer is hand-written for bodies of 16 KiB.** An upload of megabytes needs chunked reading to a file, a cap that is applied before the body is read, and a limit on how many uploads are parsed at once. A response sent while the client is still sending may show up in a browser as a network error instead of a status code.
3. **Schema changes.** Two planned tickets add tables. `tests/test_api.py::BasicEndpoints::test_health` and `tests/test_storage.py::StorageTests::test_migration_is_idempotent` pin schema version 1 and must change in the pull request that adds a migration. Version numbers follow merge order.
4. **Text positions cannot be checked in a browser.** The page draws with system fonts, so widths differ from the PDF's. Position checks belong in parser tests; the page fits each run into the width that the parser computed.
5. **No browser automation is allowed**, so every ticket that changes the page needs a recorded manual run or the self-check page from #4.
6. **Fixtures must be generated in the repository.** No third-party or private PDF may be committed. Real files can be used for a manual check whose result is described, not attached.
7. **There is no CI.** The only gate is a local `python -m unittest discover -s tests`.

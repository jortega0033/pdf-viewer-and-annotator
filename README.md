# PDF Viewer and Annotator

An offline, single-person browser workbench for inspecting a PDF and saving review notes. No sign-in, no upload, no external services. At M1 it opens only a generated two-page sample document.

M1 implements an authored fixture reader and saved page annotations. See the baseline verification below.

## Requirements

Python 3.12, standard library only. Nothing to install.

## Launch

Linux:

```
python3 -m pdf_annotator --data-dir ./data --port 8765
```

Windows:

```
python -m pdf_annotator --data-dir .\data --port 8765
```

Then open http://127.0.0.1:8765/. The server binds to 127.0.0.1 only. Stop with Ctrl+C. `--port 0` picks a free port (printed at startup). An unusable data directory exits with code 2.

## M1 smoke steps

1. Open the page: title "Sample platform review", preview of page 1 shows the text "Platform map" inside a rectangle; status says it loaded.
2. Press **Next page**: page 2 shows "Legend", a blue swatch and a rectangle; indicator reads "Page 2 of 2". **Previous page** returns.
3. Check the text list under the preview repeats the drawn text.
4. On page 2 enter note title `Check legend` and text in **Page note**, press **Save note**; status shows "Saved revision 1".
5. Stop the server, start it again with the same `--data-dir`, open the page, go to page 2: the title and note are shown.
6. Optional: open two tabs, save in one, edit and save in the other: a conflict panel appears and your typed text stays until you choose.
7. Resize the window to 800x600 (and narrower): no horizontal page scroll.

## Limits

Classic `xref` table, uncompressed ASCII content streams only; max 64 KiB file, 10 pages, 8 KiB content stream, 500 operators per page. Supported operators: `w RG rg re S f BT ET Tf Td Tj`. Anything else is rejected with a coded message. Notes: title up to 120 characters, text up to 4000, requests up to 16 KiB. PDF content is never evaluated as script and no browser PDF plug-in is used.

## Local persistence

Notes are stored in `<data-dir>/annotator.sqlite3` (SQLite, versioned with `PRAGMA user_version`). Delete the directory to erase them.

## Tests

```
python -m unittest discover -s tests
```

Tests use disposable temporary directories and a loopback server on an ephemeral port.

## Planned scope

Open user-chosen PDFs with bounded intake, page trees and richer vector/text, images and rotation, region-anchored notes with conflict handling, and incremental PDF export of annotations. See [docs/PRD.md](docs/PRD.md).

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 59 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- Chrome 157 verified the main workflow with external requests blocked. The generated PDF rendered both pages, keyboard navigation switched pages, and a saved page-two note reopened after a server restart.

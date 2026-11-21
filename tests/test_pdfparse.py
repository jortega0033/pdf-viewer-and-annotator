import hashlib
import re
import unittest

from pdf_annotator.pdfgen import build_sample_pdf
from pdf_annotator.pdfparse import PdfError, parse_pdf

from tests import build_pdf

GOOD = b"1 w 0 0 0 RG 20 30 260 120 re S BT /F1 18 Tf 20 170 Td (Hi) Tj ET"


def _code(test, data):
    with test.assertRaises(PdfError) as ctx:
        parse_pdf(data)
    return ctx.exception.code


class SampleRoundTrip(unittest.TestCase):
    def test_generator_is_deterministic_ascii(self):
        a, b = build_sample_pdf(), build_sample_pdf()
        self.assertEqual(a, b)
        a.decode("ascii")
        self.assertLessEqual(len(a), 65536)

    def test_xref_offsets_point_at_objects(self):
        data = build_sample_pdf()
        start = int(re.search(rb"startxref\n(\d+)", data).group(1))
        self.assertTrue(data[start:].startswith(b"xref"))
        entries = re.findall(rb"(\d{10}) 00000 n ", data)
        self.assertEqual(len(entries), 7)
        for number, off in enumerate(entries, start=1):
            self.assertTrue(
                data[int(off):].startswith(b"%d 0 obj" % number))

    def test_exact_display_list(self):
        data = build_sample_pdf()
        doc = parse_pdf(data)
        black = [0, 0, 0]
        frame = {"op": "rect", "x": 20, "y": 30, "w": 260, "h": 120,
                 "stroke": black, "fill": None, "line_width": 1}
        expected = {
            "document_id": "sample",
            "title": "Sample platform review",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "page_count": 2,
            "pages": [
                {"index": 1, "width": 300, "height": 200, "ops": [
                    frame,
                    {"op": "text", "x": 20, "y": 170, "size": 18,
                     "font": "Helvetica", "text": "Platform map",
                     "fill": black}]},
                {"index": 2, "width": 300, "height": 200, "ops": [
                    {"op": "rect", "x": 30, "y": 40, "w": 40, "h": 20,
                     "stroke": None, "fill": [0.2, 0.4, 0.8],
                     "line_width": 1},
                    frame,
                    {"op": "text", "x": 20, "y": 170, "size": 18,
                     "font": "Helvetica", "text": "Legend",
                     "fill": black}]},
            ],
        }
        self.assertEqual(doc, expected)

    def test_helper_pdf_parses(self):
        doc = parse_pdf(build_pdf([GOOD, GOOD]))
        self.assertEqual(doc["page_count"], 2)
        self.assertEqual(doc["pages"][0]["ops"][1]["text"], "Hi")

    def test_string_escapes(self):
        data = build_pdf([b"BT /F1 12 Tf 0 0 Td (a\\(b\\)\\\\c) Tj ET"])
        text = parse_pdf(data)["pages"][0]["ops"][0]["text"]
        self.assertEqual(text, "a(b)\\c")


class Rejections(unittest.TestCase):
    def test_bad_startxref(self):
        data = re.sub(rb"startxref\n\d+", b"startxref\n7", build_sample_pdf())
        self.assertEqual(_code(self, data), "bad_xref")

    def test_missing_startxref(self):
        data = build_sample_pdf().replace(b"startxref", b"startxrex")
        self.assertEqual(_code(self, data), "bad_xref")

    def test_wrong_offset(self):
        data = build_sample_pdf()
        self.assertIn(b"0000000009 00000 n", data)
        data = data.replace(b"0000000009 00000 n", b"0000000010 00000 n")
        self.assertEqual(_code(self, data), "bad_offset")

    def test_offset_past_end(self):
        data = build_sample_pdf().replace(b"0000000009 00000 n",
                                          b"9999999999 00000 n")
        self.assertEqual(_code(self, data), "bad_offset")

    def test_unsupported_operators(self):
        for op in (b"Do", b"cm", b"m", b"l", b"JS", b"q"):
            data = build_pdf([GOOD, b"1 0 0 1 0 0 " + op])
            self.assertEqual(_code(self, data), "unsupported_operator", op)

    def test_filter_rejected(self):
        data = build_pdf([GOOD], stream_extra=b"/Filter /FlateDecode")
        self.assertEqual(_code(self, data), "unsupported_feature")

    def test_other_forbidden_features(self):
        self.assertEqual(
            _code(self, build_pdf([GOOD], page_extra=b"/Rotate 90")),
            "unsupported_feature")
        self.assertEqual(
            _code(self, build_pdf([GOOD], trailer_extra=b"/Prev 0")),
            "unsupported_feature")
        self.assertEqual(
            _code(self, build_pdf([GOOD], trailer_extra=b"/Encrypt 1 0 R")),
            "unsupported_feature")
        self.assertEqual(
            _code(self, build_pdf([GOOD], stream_extra=b"/Type /ObjStm")),
            "unsupported_feature")
        self.assertEqual(
            _code(self, build_pdf([GOOD], stream_extra=b"/Type /XRef")),
            "unsupported_feature")

    def test_oversize_file(self):
        self.assertEqual(_code(self, b"%PDF-1.4\n" + b" " * 65536), "too_large")

    def test_too_many_pages(self):
        self.assertEqual(_code(self, build_pdf([GOOD] * 11)), "limit_exceeded")
        self.assertEqual(parse_pdf(build_pdf([GOOD] * 10))["page_count"], 10)

    def test_stream_too_large(self):
        big = GOOD + b" " * 8200
        self.assertEqual(_code(self, build_pdf([big])), "limit_exceeded")

    def test_declared_length_is_not_trusted(self):
        data = build_pdf([GOOD], length_override=999999999)
        self.assertEqual(_code(self, data), "limit_exceeded")
        data = build_pdf([GOOD], length_override=5000)
        self.assertEqual(_code(self, data), "malformed")

    def test_too_many_ops(self):
        self.assertEqual(_code(self, build_pdf([b"1 w " * 501])),
                         "limit_exceeded")
        self.assertEqual(len(parse_pdf(build_pdf([b"1 w " * 500]))
                             ["pages"][0]["ops"]), 0)

    def test_text_limits_and_validation(self):
        long_text = b"BT /F1 12 Tf 0 0 Td (" + b"a" * 201 + b") Tj ET"
        self.assertEqual(_code(self, build_pdf([long_text])), "limit_exceeded")
        ok_text = b"BT /F1 12 Tf 0 0 Td (" + b"a" * 200 + b") Tj ET"
        parse_pdf(build_pdf([ok_text]))
        bad_escape = b"BT /F1 12 Tf 0 0 Td (a\\nb) Tj ET"
        self.assertEqual(_code(self, build_pdf([bad_escape])), "malformed")
        non_ascii = b"BT /F1 12 Tf 0 0 Td (a\xe9) Tj ET"
        self.assertEqual(_code(self, build_pdf([non_ascii])), "malformed")
        control = b"BT /F1 12 Tf 0 0 Td (a\x01) Tj ET"
        self.assertEqual(_code(self, build_pdf([control])), "malformed")

    def test_structure_errors(self):
        self.assertEqual(_code(self, b"not a pdf"), "malformed")
        self.assertEqual(_code(self, b""), "malformed")
        self.assertEqual(_code(self, build_pdf([b"BT ET ET"])), "malformed")
        self.assertEqual(_code(self, build_pdf([b"20 30 re"])), "malformed")
        self.assertEqual(_code(self, build_pdf([b"S"])), "malformed")
        self.assertEqual(_code(self, build_pdf([b"BT (x) Tj ET"])), "malformed")

    def test_unsupported_syntax(self):
        self.assertEqual(_code(self, build_pdf([b"[1 2] w"])),
                         "unsupported_feature")

    def test_mediabox_must_be_origin_zero(self):
        data = build_pdf([GOOD], mediabox=b"[10 0 300 200]")
        self.assertEqual(_code(self, data), "unsupported_feature")

    def test_truncated_inputs_never_crash(self):
        data = build_sample_pdf()
        for cut in range(0, len(data), 37):
            try:
                parse_pdf(data[:cut])
            except PdfError:
                pass


if __name__ == "__main__":
    unittest.main()

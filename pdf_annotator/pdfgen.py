"""Deterministic generator for the two-page sample PDF fixture."""

_PAGE1 = (
    b"1 w 0 0 0 RG 20 30 260 120 re S\n"
    b"BT /F1 18 Tf 20 170 Td (Platform map) Tj ET"
)
# The swatch is drawn before the stroke; the fill colour is reset to black
# afterwards so the page text is black.
_PAGE2 = (
    b"0.2 0.4 0.8 rg 30 40 40 20 re f\n"
    b"0 0 0 rg\n"
    b"1 w 0 0 0 RG 20 30 260 120 re S\n"
    b"BT /F1 18 Tf 20 170 Td (Legend) Tj ET"
)


def build_sample_pdf() -> bytes:
    """Return the sample PDF bytes (identical on every call)."""
    contents = [_PAGE1, _PAGE2]
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
    ]
    for content_num in (5, 6):
        bodies.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            b"/Resources << /Font << /F1 7 0 R >> >> "
            b"/Contents " + str(content_num).encode("ascii") + b" 0 R >>"
        )
    for content in contents:
        bodies.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\n"
            b"stream\n" + content + b"\nendstream"
        )
    bodies.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += str(number).encode("ascii") + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(bodies) + 1).encode("ascii") + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += ("%010d 00000 n \n" % offset).encode("ascii")
    out += (
        b"trailer\n<< /Size " + str(len(bodies) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode("ascii") + b"\n%%EOF\n"
    )
    return bytes(out)

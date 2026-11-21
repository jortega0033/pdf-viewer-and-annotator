"""Test package; also hosts a small PDF builder shared by the tests."""


def build_pdf(contents, page_extra=b"", mediabox=b"[0 0 300 200]",
              stream_extra=b"", trailer_extra=b"", length_override=None,
              font_body=None):
    """Build a valid classical-xref PDF with one page per content stream."""
    count = len(contents)
    font_num = 3 + 2 * count
    kids = b" ".join(b"%d 0 R" % (3 + i) for i in range(count))
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " +
        str(count).encode("ascii") + b" >>",
    ]
    for i in range(count):
        bodies.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox " + mediabox +
            b" /Resources << /Font << /F1 " + str(font_num).encode("ascii") +
            b" 0 R >> >> /Contents " + str(3 + count + i).encode("ascii") +
            b" 0 R " + page_extra + b" >>"
        )
    for content in contents:
        length = len(content) if length_override is None else length_override
        bodies.append(
            b"<< /Length " + str(length).encode("ascii") + b" " +
            stream_extra + b" >>\nstream\n" + content + b"\nendstream"
        )
    bodies.append(font_body or
                  b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
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
    out += (b"trailer\n<< /Size " + str(len(bodies) + 1).encode("ascii") +
            b" /Root 1 0 R " + trailer_extra + b" >>\nstartxref\n" +
            str(xref_pos).encode("ascii") + b"\n%%EOF\n")
    return bytes(out)

"""Minimal, strict PDF parser for the restricted dialect used by the app.

Only classical xref tables, uncompressed ASCII content streams and a tiny
operator set are accepted. Nothing is evaluated; every length is validated
against fixed limits before it is used.
"""

import collections
import hashlib
import re

MAX_FILE_BYTES = 65536
MAX_PAGES = 10
MAX_STREAM_BYTES = 8192
MAX_OPS = 500
MAX_TEXT_CHARS = 200
MAX_XREF_ENTRIES = 1000
MAX_DEPTH = 8
MAX_CONTAINER = 64
MAX_OPERANDS = 16
MAX_PAGE_DIMENSION = 14400
MAX_ABS_NUMBER = 1e7

DOCUMENT_ID = "sample"
DOCUMENT_TITLE = "Sample platform review"

SUPPORTED_OPERATORS = frozenset(
    ["w", "RG", "rg", "re", "S", "f", "BT", "ET", "Tf", "Td", "Tj"]
)

_FORBIDDEN_NAMES = frozenset([
    "Filter", "DecodeParms", "ObjStm", "Encrypt", "XRef", "XRefStm", "Prev",
    "Rotate", "JS", "JavaScript", "OpenAction", "AA", "Launch",
    "EmbeddedFile", "EmbeddedFiles", "URI", "AcroForm",
])

Ref = collections.namedtuple("Ref", "num gen")


class PdfError(Exception):
    """Raised for any rejected input; `code` is one of the contract codes."""

    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code
        self.message = message


_WS = b"\x00\t\n\x0c\r "
_DELIMS = b"()<>[]{}/%"
_NUM_RE = re.compile(rb"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)")
_INT_RE = re.compile(rb"[+-]?[0-9]+")
_OBJ_RE = re.compile(
    rb"([0-9]{1,10})[ \t\r\n]+([0-9]{1,5})[ \t\r\n]+obj(?![A-Za-z0-9])"
)


def _skip_ws(d, p):
    n = len(d)
    while p < n:
        c = d[p]
        if c in _WS:
            p += 1
        elif c == 0x25:  # '%' comment
            while p < n and d[p] not in b"\r\n":
                p += 1
        else:
            break
    return p


def _read_regular(d, p):
    n = len(d)
    q = p
    while q < n and d[q] not in _WS and d[q] not in _DELIMS:
        q += 1
    return d[p:q], q


def _parse_name(d, p):
    tok, q = _read_regular(d, p + 1)
    if not tok or len(tok) > 64:
        raise PdfError("malformed", "bad name token")
    if b"#" in tok:
        raise PdfError("unsupported_feature", "escaped names are not supported")
    try:
        name = tok.decode("ascii")
    except UnicodeDecodeError:
        raise PdfError("malformed", "non-ASCII name")
    if name in _FORBIDDEN_NAMES:
        raise PdfError("unsupported_feature", "/%s is not supported" % name)
    return name, q


def _parse_value(d, p, depth):
    p = _skip_ws(d, p)
    if p >= len(d):
        raise PdfError("malformed", "unexpected end of data")
    if depth > MAX_DEPTH:
        raise PdfError("limit_exceeded", "objects nested too deeply")
    c = d[p]
    if d.startswith(b"<<", p):
        out = {}
        p += 2
        while True:
            p = _skip_ws(d, p)
            if d.startswith(b">>", p):
                return out, p + 2
            if p >= len(d) or d[p] != 0x2F:
                raise PdfError("malformed", "bad dictionary")
            key, p = _parse_name(d, p)
            if key in out:
                raise PdfError("malformed", "duplicate dictionary key")
            out[key], p = _parse_value(d, p, depth + 1)
            if len(out) > MAX_CONTAINER:
                raise PdfError("limit_exceeded", "dictionary too large")
    if c == 0x5B:  # '['
        out = []
        p += 1
        while True:
            p = _skip_ws(d, p)
            if p < len(d) and d[p] == 0x5D:
                return out, p + 1
            if p >= len(d):
                raise PdfError("malformed", "unterminated array")
            val, p = _parse_value(d, p, depth + 1)
            out.append(val)
            if len(out) > MAX_CONTAINER:
                raise PdfError("limit_exceeded", "array too large")
    if c == 0x2F:
        return _parse_name(d, p)
    if c in b"+-.0123456789":
        tok, q = _read_regular(d, p)
        if len(tok) > 20 or not _NUM_RE.fullmatch(tok):
            raise PdfError("malformed", "bad number")
        if tok.isdigit():
            # Possible indirect reference "N G R".
            tok2, q2 = _read_regular(d, _skip_ws(d, q))
            if tok2.isdigit() and len(tok2) <= 5:
                tok3, q3 = _read_regular(d, _skip_ws(d, q2))
                if tok3 == b"R":
                    return Ref(int(tok), int(tok2)), q3
        if b"." in tok:
            return float(tok), q
        return int(tok), q
    if c in b"(<":
        raise PdfError("unsupported_feature", "string objects are not supported")
    tok, q = _read_regular(d, p)
    if tok == b"true":
        return True, q
    if tok == b"false":
        return False, q
    if tok == b"null":
        return None, q
    raise PdfError("malformed", "unexpected token in object")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _read_xref(data):
    idx = data.rfind(b"startxref")
    if idx < 0:
        raise PdfError("bad_xref", "startxref not found")
    tok, _ = _read_regular(data, _skip_ws(data, idx + 9))
    if not tok.isdigit() or len(tok) > 10:
        raise PdfError("bad_xref", "invalid startxref offset")
    off = int(tok)
    if off >= len(data) or not data.startswith(b"xref", off):
        raise PdfError("bad_xref", "startxref does not point at an xref table")
    p = off + 4
    entries = {}
    seen = set()
    total = 0
    while True:
        tok, p = _read_regular(data, _skip_ws(data, p))
        if tok == b"trailer":
            break
        if not tok.isdigit() or len(tok) > 10:
            raise PdfError("bad_xref", "invalid xref subsection")
        first = int(tok)
        tok, p = _read_regular(data, _skip_ws(data, p))
        if not tok.isdigit() or len(tok) > 6:
            raise PdfError("bad_xref", "invalid xref subsection count")
        count = int(tok)
        total += count
        if total > MAX_XREF_ENTRIES:
            raise PdfError("limit_exceeded", "too many xref entries")
        for i in range(count):
            t_off, p = _read_regular(data, _skip_ws(data, p))
            t_gen, p = _read_regular(data, _skip_ws(data, p))
            t_flag, p = _read_regular(data, _skip_ws(data, p))
            if (not t_off.isdigit() or len(t_off) > 10
                    or not t_gen.isdigit() or len(t_gen) > 5):
                raise PdfError("bad_xref", "invalid xref entry")
            num = first + i
            if num in seen:
                raise PdfError("bad_xref", "duplicate xref entry")
            seen.add(num)
            if t_flag == b"n":
                entries[num] = (int(t_off), int(t_gen))
            elif t_flag != b"f":
                raise PdfError("bad_xref", "invalid xref entry flag")
    trailer, _ = _parse_value(data, p, 0)
    if not isinstance(trailer, dict):
        raise PdfError("bad_xref", "trailer is not a dictionary")
    if not isinstance(trailer.get("Root"), Ref):
        raise PdfError("bad_xref", "trailer has no /Root reference")
    size = trailer.get("Size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise PdfError("bad_xref", "trailer has no valid /Size")
    return entries, trailer


def _read_object(data, num, offset, gen):
    if offset >= len(data):
        raise PdfError("bad_offset", "object %d offset out of range" % num)
    m = _OBJ_RE.match(data, offset)
    if m is None or int(m.group(1)) != num or int(m.group(2)) != gen:
        raise PdfError("bad_offset", "object %d offset is wrong" % num)
    val, p = _parse_value(data, m.end(), 0)
    p = _skip_ws(data, p)
    stream = None
    if data.startswith(b"stream", p):
        if not isinstance(val, dict):
            raise PdfError("malformed", "stream without dictionary")
        length = val.get("Length")
        if isinstance(length, Ref):
            raise PdfError("unsupported_feature", "indirect /Length")
        if not isinstance(length, int) or isinstance(length, bool) or length < 0:
            raise PdfError("malformed", "stream has no valid /Length")
        if length > MAX_STREAM_BYTES:
            raise PdfError("limit_exceeded", "content stream too large")
        p += 6
        if data.startswith(b"\r\n", p):
            p += 2
        elif data.startswith(b"\n", p):
            p += 1
        else:
            raise PdfError("malformed", "bad stream keyword line ending")
        end = p + length
        if end > len(data):
            raise PdfError("malformed", "stream extends past end of file")
        stream = data[p:end]
        p = _skip_ws(data, end)
        if not data.startswith(b"endstream", p):
            raise PdfError("malformed", "missing endstream")
        p = _skip_ws(data, p + 9)
    if not data.startswith(b"endobj", p):
        raise PdfError("malformed", "missing endobj")
    return val, stream


def _get(objs, ref):
    if not isinstance(ref, Ref):
        raise PdfError("malformed", "expected an indirect reference")
    entry = objs.get(ref.num)
    if entry is None or entry[2] != ref.gen:
        raise PdfError("malformed", "reference to missing object %d" % ref.num)
    return entry[0], entry[1]


def _deref(objs, v):
    if isinstance(v, Ref):
        return _get(objs, v)[0]
    return v


def _norm(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


# ---------------------------------------------------------------- content

_CWS = " \t\r\n\f\0"
_CDELIMS = "()<>[]{}/%"
_CNUM_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)")
_COP_RE = re.compile(r"[A-Za-z][A-Za-z0-9*'\"]{0,7}")


class _State:
    def __init__(self):
        self.line_width = 1
        self.stroke = [0, 0, 0]
        self.fill = [0, 0, 0]
        self.rect = None
        self.in_text = False
        self.font = None
        self.tx = 0
        self.ty = 0


def _read_string(text, p):
    out = []
    p += 1
    n = len(text)
    while p < n:
        c = text[p]
        if c == ")":
            s = "".join(out)
            return s, p + 1
        if c == "(":
            raise PdfError("malformed", "unescaped '(' in string")
        if c == "\\":
            p += 1
            if p >= n or text[p] not in "()\\":
                raise PdfError("malformed", "unsupported string escape")
            c = text[p]
        if not (0x20 <= ord(c) <= 0x7E):
            raise PdfError("malformed", "non-printable character in string")
        out.append(c)
        if len(out) > MAX_TEXT_CHARS:
            raise PdfError("limit_exceeded", "text string too long")
        p += 1
    raise PdfError("malformed", "unterminated string")


def _nums(args, count, op):
    if len(args) != count or any(a[0] != "num" for a in args):
        raise PdfError("malformed", "bad operands for %s" % op)
    return [a[1] for a in args]


def _color(args, op):
    vals = _nums(args, 3, op)
    if any(v < 0 or v > 1 for v in vals):
        raise PdfError("malformed", "colour component out of range")
    return [_norm(v) for v in vals]


def _exec(op, args, st, out, fonts):
    if op == "w":
        (v,) = _nums(args, 1, op)
        if v < 0:
            raise PdfError("malformed", "negative line width")
        st.line_width = _norm(v)
    elif op == "RG":
        st.stroke = _color(args, op)
    elif op == "rg":
        st.fill = _color(args, op)
    elif op == "re":
        if st.in_text or st.rect is not None:
            raise PdfError("malformed", "unexpected re")
        x, y, w, h = _nums(args, 4, op)
        if w < 0 or h < 0:
            raise PdfError("malformed", "negative rectangle size")
        st.rect = (x, y, w, h)
    elif op in ("S", "f"):
        _nums(args, 0, op)
        if st.rect is None:
            raise PdfError("malformed", "paint operator without path")
        x, y, w, h = st.rect
        st.rect = None
        out.append({
            "op": "rect", "x": _norm(x), "y": _norm(y),
            "w": _norm(w), "h": _norm(h),
            "stroke": list(st.stroke) if op == "S" else None,
            "fill": list(st.fill) if op == "f" else None,
            "line_width": st.line_width,
        })
    elif op == "BT":
        _nums(args, 0, op)
        if st.in_text or st.rect is not None:
            raise PdfError("malformed", "unexpected BT")
        st.in_text = True
        st.tx = 0
        st.ty = 0
    elif op == "ET":
        _nums(args, 0, op)
        if not st.in_text:
            raise PdfError("malformed", "ET without BT")
        st.in_text = False
    elif op == "Tf":
        if not st.in_text:
            raise PdfError("malformed", "Tf outside text object")
        if (len(args) != 2 or args[0][0] != "name" or args[1][0] != "num"):
            raise PdfError("malformed", "bad operands for Tf")
        if args[0][1] not in fonts:
            raise PdfError("malformed", "unknown font resource")
        size = args[1][1]
        if size <= 0 or size > 1000:
            raise PdfError("malformed", "font size out of range")
        st.font = (fonts[args[0][1]], _norm(size))
    elif op == "Td":
        if not st.in_text:
            raise PdfError("malformed", "Td outside text object")
        dx, dy = _nums(args, 2, op)
        st.tx += dx
        st.ty += dy
        if abs(st.tx) > MAX_ABS_NUMBER or abs(st.ty) > MAX_ABS_NUMBER:
            raise PdfError("malformed", "text position out of range")
    elif op == "Tj":
        if not st.in_text:
            raise PdfError("malformed", "Tj outside text object")
        if len(args) != 1 or args[0][0] != "str":
            raise PdfError("malformed", "bad operands for Tj")
        if st.font is None:
            raise PdfError("malformed", "Tj before Tf")
        out.append({
            "op": "text", "x": _norm(st.tx), "y": _norm(st.ty),
            "size": st.font[1], "font": st.font[0], "text": args[0][1],
            "fill": list(st.fill),
        })


def _interpret(content, fonts):
    try:
        text = content.decode("ascii")
    except UnicodeDecodeError:
        raise PdfError("malformed", "content stream is not ASCII")
    out = []
    args = []
    st = _State()
    op_count = 0
    p = 0
    n = len(text)
    while p < n:
        c = text[p]
        if c in _CWS:
            p += 1
            continue
        if c == "%":
            while p < n and text[p] not in "\r\n":
                p += 1
            continue
        if c == "(":
            s, p = _read_string(text, p)
            args.append(("str", s))
        elif c == "/":
            q = p + 1
            while q < n and text[q] not in _CWS and text[q] not in _CDELIMS:
                q += 1
            name = text[p + 1:q]
            if not name or len(name) > 64 or "#" in name:
                raise PdfError("malformed", "bad name operand")
            args.append(("name", name))
            p = q
        elif c in "<>[]{}":
            raise PdfError("unsupported_feature", "unsupported syntax %r" % c)
        elif c == ")":
            raise PdfError("malformed", "unbalanced ')'")
        else:
            q = p
            while q < n and text[q] not in _CWS and text[q] not in _CDELIMS:
                q += 1
            word = text[p:q]
            p = q
            if _CNUM_RE.fullmatch(word) and len(word) <= 20:
                v = float(word) if "." in word else int(word)
                if abs(v) > MAX_ABS_NUMBER:
                    raise PdfError("malformed", "number out of range")
                args.append(("num", v))
            elif _COP_RE.fullmatch(word):
                op_count += 1
                if op_count > MAX_OPS:
                    raise PdfError("limit_exceeded", "too many operators")
                if word not in SUPPORTED_OPERATORS:
                    raise PdfError(
                        "unsupported_operator", "operator %s is not supported" % word
                    )
                _exec(word, args, st, out, fonts)
                args = []
                continue
            else:
                raise PdfError("malformed", "bad token in content stream")
        if len(args) > MAX_OPERANDS:
            raise PdfError("malformed", "too many operands")
    if st.in_text or st.rect is not None or args:
        raise PdfError("malformed", "content stream ends mid-construct")
    return out


# ------------------------------------------------------------------ driver

def _page_fonts(objs, page):
    res = _deref(objs, page.get("Resources"))
    if res is None:
        return {}
    if not isinstance(res, dict):
        raise PdfError("malformed", "bad /Resources")
    fdict = _deref(objs, res.get("Font"))
    if fdict is None:
        return {}
    if not isinstance(fdict, dict):
        raise PdfError("malformed", "bad /Font resources")
    fonts = {}
    for name, ref in fdict.items():
        font = _deref(objs, ref)
        if not isinstance(font, dict) or font.get("Type") != "Font":
            raise PdfError("malformed", "bad font object")
        if font.get("Subtype") != "Type1" or font.get("BaseFont") != "Helvetica":
            raise PdfError("unsupported_feature", "only Helvetica Type1 is supported")
        fonts[name] = "Helvetica"
    return fonts


def _parse_page(objs, ref, index):
    page, _ = _get(objs, ref)
    if not isinstance(page, dict):
        raise PdfError("malformed", "page is not a dictionary")
    ptype = page.get("Type")
    if ptype == "Pages":
        raise PdfError("unsupported_feature", "nested page trees")
    if ptype != "Page":
        raise PdfError("malformed", "kid is not a /Page")
    box = page.get("MediaBox")
    if (not isinstance(box, list) or len(box) != 4
            or not all(_is_num(v) for v in box)):
        raise PdfError("malformed", "page needs a direct /MediaBox")
    if box[0] != 0 or box[1] != 0:
        raise PdfError("unsupported_feature", "MediaBox must start at 0 0")
    width, height = box[2], box[3]
    if not (0 < width <= MAX_PAGE_DIMENSION and 0 < height <= MAX_PAGE_DIMENSION):
        raise PdfError("unsupported_feature", "MediaBox size out of range")
    contents = page.get("Contents")
    if isinstance(contents, list):
        raise PdfError("unsupported_feature", "content stream arrays")
    cval, stream = _get(objs, contents)
    if stream is None:
        raise PdfError("malformed", "/Contents is not a stream")
    fonts = _page_fonts(objs, page)
    return {
        "index": index,
        "width": _norm(width),
        "height": _norm(height),
        "ops": _interpret(stream, fonts),
    }


def parse_pdf(data):
    """Parse `data` and return the display-list dictionary."""
    if not isinstance(data, (bytes, bytearray)):
        raise PdfError("malformed", "input must be bytes")
    data = bytes(data)
    if len(data) > MAX_FILE_BYTES:
        raise PdfError("too_large", "file exceeds %d bytes" % MAX_FILE_BYTES)
    if not data.startswith(b"%PDF-"):
        raise PdfError("malformed", "missing PDF header")
    try:
        entries, trailer = _read_xref(data)
        objs = {}
        for num in sorted(entries):
            offset, gen = entries[num]
            val, stream = _read_object(data, num, offset, gen)
            objs[num] = (val, stream, gen)
        catalog, _ = _get(objs, trailer["Root"])
        if not isinstance(catalog, dict) or catalog.get("Type") != "Catalog":
            raise PdfError("malformed", "bad catalog")
        pages, _ = _get(objs, catalog.get("Pages"))
        if not isinstance(pages, dict) or pages.get("Type") != "Pages":
            raise PdfError("malformed", "bad page tree root")
        kids = pages.get("Kids")
        if not isinstance(kids, list) or not kids:
            raise PdfError("malformed", "page tree has no /Kids")
        if len(kids) > MAX_PAGES:
            raise PdfError("limit_exceeded", "more than %d pages" % MAX_PAGES)
        count = pages.get("Count")
        if count is not None and count != len(kids):
            raise PdfError("malformed", "/Count does not match /Kids")
        seen = set()
        page_list = []
        for i, kid in enumerate(kids, start=1):
            if not isinstance(kid, Ref) or kid.num in seen:
                raise PdfError("malformed", "bad or duplicate kid")
            seen.add(kid.num)
            page_list.append(_parse_page(objs, kid, i))
    except PdfError:
        raise
    except (IndexError, ValueError, OverflowError, RecursionError, KeyError):
        raise PdfError("malformed", "unparseable PDF structure")
    return {
        "document_id": DOCUMENT_ID,
        "title": DOCUMENT_TITLE,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "page_count": len(page_list),
        "pages": page_list,
    }

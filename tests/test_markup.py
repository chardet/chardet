# tests/test_markup.py
from __future__ import annotations

import re
import time
from unittest.mock import patch

import pytest

import chardet.pipeline.markup as markup_mod
from chardet import detect
from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult
from chardet.pipeline.markup import (
    Declaration,
    detect_markup_charset,
    iter_declarations,
)
from chardet.registry import REGISTRY, EncodingInfo

#: See the note in tests/test_confusion.py: mypyc resolves a compiled
#: module's calls to functions imported into it at compile time, so patching
#: those names only takes effect on interpreted builds.
_needs_interpreted_build = pytest.mark.skipif(
    markup_mod.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
)

#: Every encoding the registry knows, the stage's ``allowed`` with no filters.
_ALL = frozenset(e.name for e in REGISTRY.values())

_LATIN1_TEXT = "Voilà, un résumé très détaillé. ".encode("latin-1") * 10


def _declarations(data: bytes) -> list[Declaration]:
    return list(iter_declarations(data))


def _html(encoding: str | None) -> list[Declaration]:
    return [Declaration(encoding, "text/html")]


# --- The parser: which declarations a head contains -------------------------


def test_xml_encoding_declaration():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    assert _declarations(data) == [Declaration("iso8859-1", "text/xml")]


def test_html5_meta_charset():
    data = b'<html><head><meta charset="utf-8"></head></html>'
    assert _declarations(data) == _html("utf-8")


def test_charset_inside_another_attribute_is_not_a_declaration():
    # A refresh URL or a description can contain the letters charset=.
    # That is not the page encoding. The meta charset attribute is.
    data = (
        b'<meta http-equiv="refresh" '
        b'content="0;url=http://example.com/?charset=iso-8859-1">'
        b'<meta charset="utf-8">'
    )
    assert _declarations(data) == _html("utf-8")

    data = (
        b'<meta name="description" '
        b'content="see charset=iso-8859-1 for notes">'
        b'<meta charset="utf-8">'
    )
    assert _declarations(data) == _html("utf-8")


def test_name_content_type_is_accepted():
    """``name='content-type'`` is wrong by the spec but common in the wild."""
    data = (
        b"<html><head>"
        b"<meta name='content-type' content='text/html;charset=iso-8859-6'>"
        b"</head></html>"
    )
    assert _declarations(data) == _html("iso8859-6")


def test_first_value_wins_when_attribute_repeats():
    data = b'<meta charset="iso-8859-5" charset="utf-8">'
    assert _declarations(data) == _html("iso8859-5")


def test_unquoted_charset_value():
    assert _declarations(b"<meta charset=koi8-r>") == _html("koi8-r")


def test_unclosed_meta_tag_is_not_a_declaration():
    assert _declarations(b'<meta charset="utf-8"') == []


def test_non_ascii_xml_encoding_name_ignored():
    assert _declarations(b'<?xml version="1.0" encoding="\xff\xfe"?><root/>') == []


def test_html4_content_type():
    data = (
        b"<html><head>"
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
        b"</head></html>"
    )
    assert _declarations(data) == _html("cp1252")


@pytest.mark.parametrize(
    "parameter",
    [
        b'charset="windows-1252"',
        b"charset='windows-1252'",
        b"charset = windows-1252",
        b'CHARSET\t=\t"windows-1252"',
    ],
)
def test_html4_content_type_quoted_or_spaced_charset(parameter: bytes):
    outer_quote = b'"' if b"'" in parameter else b"'"
    data = (
        b'<meta http-equiv="Content-Type" content='
        + outer_quote
        + b"text/html; "
        + parameter
        + outer_quote
        + b">caf\xe9"
    )
    assert _declarations(data) == _html("cp1252")
    assert detect(data)["encoding"] == "Windows-1252"
    assert detect(data)["mime_type"] == "text/html"


@pytest.mark.parametrize("parameter", [b'charset="windows-1252', b'charset=""'])
def test_html4_content_type_invalid_quoted_charset(parameter: bytes):
    data = b"<meta http-equiv='Content-Type' content='text/html; " + parameter + b"'>"
    assert _declarations(data) == []


def test_no_markup():
    assert _declarations(b"Just plain text with no HTML or XML") == []


def test_empty_input():
    assert _declarations(b"") == []
    assert detect_markup_charset(b"", _ALL) is None


def test_xml_single_quotes():
    data = b"<?xml version='1.0' encoding='shift_jis'?><root/>"
    assert _declarations(data) == [Declaration("shift_jis_2004", "text/xml")]


def test_case_insensitive_meta():
    assert _declarations(b'<META CHARSET="UTF-8">') == _html("utf-8")


def test_charset_with_whitespace():
    assert _declarations(b'<meta charset = "utf-8" >') == _html("utf-8")


def test_charset_within_scan_limit_found():
    data = b"x" * 100 + b'<meta charset="utf-8">'
    assert _declarations(data) == _html("utf-8")


def test_charset_beyond_scan_limit_ignored():
    data = b"x" * 5000 + b'<meta charset="utf-8">'  # past _SCAN_LIMIT (4096)
    assert _declarations(data) == []


def test_non_ascii_charset_name_ignored():
    """A charset name containing non-ASCII bytes is skipped."""
    assert _declarations(b'<meta charset="\xff\xfe">') == []


def test_null_byte_in_charset_name():
    """A null byte in the charset value must not crash.

    Regression test for https://github.com/chardet/chardet/issues/369:
    codecs.lookup() raises ValueError on embedded null characters.
    """
    data = b'<meta charset="\x00utf-8">'
    assert _declarations(data) == _html(None)
    assert detect_markup_charset(data, _ALL) is None


def test_pep263_non_ascii_coding_name():
    """A PEP 263 coding name with non-ASCII bytes is skipped."""
    # The default PEP263 regex only captures ASCII via \\w on bytes, so
    # swap in a broader regex that can capture high bytes.
    broad_re = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([^\s]+)", re.MULTILINE)
    data = b"# -*- coding: \xff\xfe -*-\n"
    with patch("chardet.pipeline.markup._PEP263_RE", broad_re):
        assert _declarations(data) == []


@pytest.mark.parametrize(
    "first_line",
    [b'print("hello")', b'print("hello") # a trailing comment', b'"a docstring"'],
)
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_pep263_second_line_after_code_is_not_a_declaration(
    first_line: bytes, newline: bytes
):
    """A second-line cookie is ignored after a Python statement."""
    data = first_line + newline + b"# coding: cp1251" + newline
    assert _declarations(data) == []
    assert detect(data)["encoding"] == "ascii"


@pytest.mark.parametrize(
    "first_line", [b"# ordinary comment", b"#!/usr/bin/python", b"", b" \t\f"]
)
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_pep263_second_line_after_comment_or_blank_is_a_declaration(
    first_line: bytes, newline: bytes
):
    """Valid second-line cookies remain usable after comments and blank lines."""
    data = first_line + newline + b"# coding: cp1251" + newline
    assert _declarations(data) == [Declaration("cp1251", "text/x-python")]


def test_pep263_cookie_after_code_does_not_override_utf8():
    """An ignored cookie must not override the actual UTF-8 source encoding."""
    data = 'print("привет")\n# coding: cp1251\n'.encode()
    assert detect(data)["encoding"] == "utf-8"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (b"iso-latin-1", "iso8859-1"),
        (b"ISO_LATIN_1", "iso8859-1"),
        (b"latin-1-unix", "iso8859-1"),
        (b"utf-8-sig", "utf-8"),
        (b"utf_8", "utf-8"),
        (b"cp1251", "cp1251"),
    ],
)
def test_pep263_names_resolve_like_tokenize(name: bytes, expected: str):
    """The cookie is read the way :func:`tokenize.detect_encoding` reads it.

    ``iso-latin-1`` is a valid cookie that no codec answers to, and a
    ``utf-8-sig`` cookie names plain UTF-8 rather than a file that starts
    with a mark.
    """
    data = b"# -*- coding: " + name + b" -*-\nx = 1\n"
    assert _declarations(data) == [Declaration(expected, "text/x-python")]


@pytest.mark.parametrize("first_line", [b" " * 300, b"# " + b"x" * 300])
def test_pep263_long_first_line_then_cookie(first_line: bytes):
    """A first line longer than the old 200 byte guard no longer hides line 2."""
    data = first_line + b"\n# coding: cp1251\n" + "привет".encode("cp1251")
    assert _declarations(data) == [Declaration("cp1251", "text/x-python")]


def test_pep263_cookie_past_the_scan_limit_is_ignored():
    data = b"# " + b"x" * 5000 + b"\n# coding: cp1251\n" + "привет".encode("cp1251")
    assert _declarations(data) == []


def test_ebcdic_meta_charset_declaration():
    """A charset declaration inside EBCDIC-encoded markup is found.

    The head is dominated by high bytes (EBCDIC letters) and decodes
    through cp037 to a ``<meta charset=...>`` tag naming a MAINFRAME-era
    encoding.
    """
    html = "<meta charset=cp500><p>hello there dear reader of mainframe pages</p>"
    assert _declarations(html.encode("cp500")) == _html("cp500")


def test_ebcdic_declaration_ignored_for_non_mainframe_name():
    """An EBCDIC-decoded declaration naming a non-MAINFRAME encoding is ignored."""
    html = "<meta charset=utf-8><p>hello there dear reader of mainframe pages</p>"
    assert _declarations(html.encode("cp500")) == []


def test_ebcdic_page_yields_only_the_mainframe_name():
    html = (
        "<meta charset=utf-8><meta charset=cp500>"
        "<p>hello there dear reader of mainframe pages</p>"
    )
    assert _declarations(html.encode("cp500")) == _html("cp500")


def test_ebcdic_xml_declaration_reports_xml():
    xml = (
        '<?xml version="1.0" encoding="cp500"?>'
        "<doc>hello there dear reader of mainframe pages</doc>"
    )
    assert _declarations(xml.encode("cp500")) == [Declaration("cp500", "text/xml")]


@pytest.mark.parametrize(
    ("junk", "declaration", "mime_type"),
    [
        (b"<meta ", b'<meta charset="iso-8859-1">', "text/html"),
        (b"<?xml ", b'<?xml version="1.0" encoding="iso-8859-1"?>', "text/xml"),
    ],
)
def test_a_head_of_unclosed_tags_still_finds_the_declaration(
    junk: bytes, declaration: bytes, mime_type: str
):
    """A tag scan stops at the next ``<``, so unclosed tags hide only themselves.

    The old ``[^>]`` class ran every unclosed tag to the end of the head
    before giving up, which made a head of nothing else quadratic.
    """
    data = junk * 600 + declaration + _LATIN1_TEXT
    assert _declarations(data) == [Declaration("iso8859-1", mime_type)]


def test_unclosed_meta_does_not_swallow_the_next_one():
    data = (
        b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-5" '
        b'<meta charset="iso-8859-1">' + _LATIN1_TEXT
    )
    assert _declarations(data) == _html("iso8859-1")


@pytest.mark.parametrize(
    "label", [b"utf-16", b"utf-16le", b"UTF-16BE", b"utf-32", b"utf-32le"]
)
def test_utf16_label_in_ascii_markup_reads_as_utf8(label: bytes):
    """A UTF-16 or UTF-32 label found in ASCII bytes cannot be right.

    UTF-16 text would have null bytes between the letters of the tag, so
    the WHATWG prescan reads the label as UTF-8.  Any even run of ASCII is
    valid UTF-16, so honoring the label returned a confident, decodable,
    wrong answer.
    """
    body = "café".encode() * 10
    page = b'<html><head><meta charset="' + label + b'"></head><body>' + body
    assert _declarations(page) == _html("utf-8")
    assert detect(page)["encoding"] == "utf-8"

    xml = b'<?xml version="1.0" encoding="' + label + b'"?><a>' + body + b"</a>"
    assert _declarations(xml) == [Declaration("utf-8", "text/xml")]
    assert detect(xml)["encoding"] == "utf-8"


@pytest.mark.parametrize(
    ("label", "body"),
    [
        (b"utf-7", b"+ADw-script+AD4-alert(1)+ADw-/script+AD4-"),
        (b"UTF-7", b"+ADw-img src=x onerror=alert(1)+AD4-"),
        (b"hz-gb-2312", b"<~{~}script>alert(1)<~{~}/script>"),
    ],
)
def test_utf7_and_hz_labels_are_ignored(label: bytes, body: bytes):
    """A browser never decodes a page as UTF-7 or HZ, whatever it declares.

    Both decoders turn bytes that are not markup into tags, so honoring
    the label told the caller to decode inert text into ``<script>``.  The
    escape stage leaves these bodies alone, and the declaration was the
    only thing naming the encoding.
    """
    page = b'<html><head><meta charset="' + label + b'"></head><body>' + body
    assert _declarations(page) == _html(None)
    result = detect(page)
    assert result["encoding"] == "ascii"
    assert b"<script" not in body
    assert "<script" not in page.decode(result["encoding"])

    xml = b'<?xml version="1.0" encoding="' + label + b'"?><a>' + body + b"</a>"
    assert _declarations(xml) == [Declaration(None, "text/xml")]
    assert detect(xml)["encoding"] == "ascii"

    # The PEP 263 scanner resolves its cookie separately; same rule.
    source = b"# -*- coding: " + label + b" -*-\ns = '" + body + b"'\n"
    assert _declarations(source) == [Declaration(None, "text/x-python")]
    assert detect(source)["encoding"] == "ascii"


def test_x_user_defined_reads_as_windows_1252():
    page = b'<meta charset="x-user-defined">' + "“café”".encode("cp1252") * 10
    assert _declarations(page) == _html("cp1252")
    assert detect(page)["encoding"] == "Windows-1252"


def test_declaration_inside_a_comment_is_not_a_declaration():
    live = b'<meta charset="iso-8859-1">' + _LATIN1_TEXT
    for commented in (
        b'<!-- <meta charset="iso-8859-5"> -->',
        b'<!-- <?xml version="1.0" encoding="iso-8859-5"?> -->',
        b"<!-- \n<meta\ncharset='iso-8859-5'>\n-->",
    ):
        assert _declarations(commented + live) == _html("iso8859-1")
        assert detect(commented + live)["encoding"] == "ISO-8859-1"
    assert _declarations(b'<!-- <meta charset="iso-8859-5"> -->' + _LATIN1_TEXT) == []


def test_unclosed_comment_hides_the_rest_of_the_head():
    assert _declarations(b'<!-- <meta charset="iso-8859-1">' + _LATIN1_TEXT) == []


@pytest.mark.parametrize("opener", [b"<!-->", b"<!--->"])
def test_comment_may_close_on_its_own_dashes(opener: bytes):
    """As in the WHATWG prescan, ``<!-->`` is a whole comment."""
    data = opener + b'<meta charset="iso-8859-1">' + _LATIN1_TEXT
    assert _declarations(data) == _html("iso8859-1")


def test_declarations_come_in_scan_order():
    """The XML prolog first, then each meta in document order."""
    data = (
        b'<?xml version="1.0" encoding="iso-8859-5"?><html><head>'
        b'<meta http-equiv="Content-Type" content="text/html; charset=koi8-r">'
        b'<meta charset="no-such-encoding">'
        b'<meta charset="windows-1251">'
        b"</head></html>"
    )
    assert _declarations(data) == [
        Declaration("iso8859-5", "text/xml"),
        Declaration("koi8-r", "text/html"),
        Declaration(None, "text/html"),
        Declaration("cp1251", "text/html"),
    ]


def test_pep263_cookie_comes_after_markup():
    data = b"# coding: latin-1\nhtml = '<meta charset=\"utf-8\">'\n"
    assert _declarations(data) == [
        Declaration("utf-8", "text/html"),
        Declaration("iso8859-1", "text/x-python"),
    ]


@_needs_interpreted_build
def test_parser_never_decodes_the_window():
    """Finding declarations is parsing only; the stage owns the decodes."""
    calls: list[str] = []

    def counting(buf: bytes, encoding: str) -> bool:
        calls.append(encoding)
        return True

    pages = [
        b'<?xml version="1.0" encoding="shift_jis"?><meta charset="euc-kr">'
        + "日本語".encode("shift_jis") * 2000,
        ("<meta charset=cp500>" + "mainframe " * 500).encode("cp500"),
        b"# coding: cp1251\n" + "привет".encode("cp1251") * 2000,
    ]
    with patch.object(markup_mod, "decodes_without_error", counting):
        found = [d for page in pages for d in iter_declarations(page)]
    assert len(found) == 4
    assert calls == []


def test_ebcdic_declaration_regex_is_linear_in_whitespace() -> None:
    r"""A charset token trailed by whitespace must not backtrack quadratically.

    ``_EBCDIC_DECL_RE`` put the optional pre-value junk character between
    two ``\s*`` runs, so an EBCDIC ``charset=`` whose value never arrives
    (a long run of spaces instead) made the engine try every way to split
    the spaces across the two runs: the match ran quadratically in the
    whitespace length (16 KiB of spaces cost ~2.6s and grew as the square).
    The budget is far above the linear cost and still catches a relapse.
    """
    probe = "charset=" + " " * 16384
    start = time.perf_counter()
    assert markup_mod._EBCDIC_DECL_RE.search(probe) is None
    assert time.perf_counter() - start < 1.0


# --- The stage: which declaration is the answer -----------------------------


def test_stage_reports_a_declaration_at_deterministic_confidence():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    assert detect_markup_charset(data, _ALL) == DetectionResult(
        "iso8859-1", DETERMINISTIC_CONFIDENCE, None, "text/xml"
    )


def test_bad_declaration_does_not_hide_a_later_one():
    data = b'<meta charset="no-such-encoding"><meta charset="utf-8">'
    result = detect_markup_charset(data, _ALL)
    assert result is not None
    assert result.encoding == "utf-8"


def test_unknown_encoding_returns_none():
    assert detect_markup_charset(b'<meta charset="not-a-real-encoding">', _ALL) is None


def test_lying_charset_declaration_rejected():
    # Declares shift_jis but contains invalid bytes for that encoding.
    #
    # The body must be undecodable before its final character: validity
    # tolerates an incomplete trailing one, so a body whose only defect is a
    # dangling lead byte would pass.  It must also be undecodable under
    # shift_jis_2004 -- what "shift_jis" resolves to, with a wider repertoire
    # than shift_jis itself.
    data = (
        b'<meta charset="shift_jis">'
        + "これは文字コード判定のテストに用いる日本語の文章です。".encode()
    )
    assert detect_markup_charset(data, _ALL) is None


def test_lying_euc_kr_declaration_rejected():
    data = b'<meta charset="euc-kr">' + "日本語のテキストです。".encode() * 20
    assert detect_markup_charset(data, _ALL) is None


def test_valid_charset_declaration_accepted():
    data = b'<meta charset="shift_jis">' + "日本語テスト".encode("shift_jis")
    result = detect_markup_charset(data, _ALL)
    assert result is not None
    assert result.encoding == "shift_jis_2004"


def test_charset_declaration_not_honored_when_window_fails_to_decode():
    """A declaration whose encoding stops decoding past the head is dropped.

    The stage validates the declaration against the whole window, so it
    returns nothing and the other stages answer as if there were no
    declaration.
    """
    data = b'<meta charset="euc-jp">' + b"x" * 5000 + b"\x80\x80\x80"
    assert detect_markup_charset(data, _ALL) is None
    result = detect(data)
    assert result["encoding"] != "EUC-JP"
    assert result["mime_type"] != "text/html"


def test_utf16_label_on_non_utf8_bytes_is_dropped():
    page = b'<meta charset="utf-16">' + _LATIN1_TEXT
    assert detect_markup_charset(page, _ALL) is None
    assert not detect(page)["encoding"].lower().startswith("utf-16")


def test_pep263_not_honored_when_window_fails_to_decode():
    """A PEP 263 coding line is dropped when the window fails to decode."""
    data = b"# coding: euc-jp\n# " + b"x" * 5000 + b"\n\x80\x80\x80"
    assert detect(data)["encoding"] != "EUC-JP"


def test_ebcdic_declaration_not_honored_when_window_fails_to_decode():
    """An EBCDIC declaration is dropped when it cannot decode the window.

    cp424 leaves byte 0x70 undefined.  The declaration and the high-byte
    head decode cleanly, but a 0x70 byte past the head does not, so honouring
    cp424 would return an answer that cannot decode the examined window.
    """
    decl = "<meta charset=cp424>".encode("cp037")
    body = ("hello mainframe " * 400).encode("cp037")  # high-byte EBCDIC head
    data = decl + body + b"\x70"  # 0x70 is undefined in cp424, past the head
    assert detect(data)["encoding"] != "cp424"


def test_stale_prolog_does_not_hide_a_correct_meta():
    """The first declaration decodes the head but not the window; the second is right."""
    latin1 = "Voilà, un résumé très détaillé à lire. ".encode("latin-1") * 40
    data = (
        b'<?xml version="1.0" encoding="utf-8"?><html><head>'
        b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
        b"</head><body>" + b"x" * 4200 + latin1
    )
    result = detect(data)
    assert result["encoding"] == "ISO-8859-1"
    assert result["confidence"] == 0.95
    assert result["mime_type"] == "text/html"


_CYRILLIC_1251 = "Съешь же ещё этих мягких французских булок. ".encode("cp1251") * 20


def test_filtered_out_declaration_that_decodes_ends_the_scan():
    """A declaration that decodes but is filtered out leaves the page unanswered.

    The page named an encoding that fits its bytes.  Moving on to the next
    declaration would mostly find a Latin-1 default that decodes anything,
    and report Shift_JIS text as ISO-8859-1 at declaration confidence.
    """
    sjis = "日本語のテキストです。東京都の天気は晴れです。".encode("shift_jis") * 5
    data = (
        b'<?xml version="1.0" encoding="Shift_JIS"?>'
        b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
        + sjis
    )
    assert detect_markup_charset(data, _ALL - {"shift_jis_2004"}) is None
    result = detect(data, exclude_encodings=["shift_jis_2004"])
    assert result["encoding"] == "CP932"
    assert result["mime_type"] == "text/plain"

    cyrillic = (
        b'<?xml version="1.0" encoding="iso-8859-5"?>'
        b'<meta charset="windows-1251">' + _CYRILLIC_1251
    )
    assert detect_markup_charset(cyrillic, _ALL - {"iso8859-5"}) is None


def test_filtered_out_declaration_that_fails_does_not_hide_a_later_one():
    data = (
        b'<?xml version="1.0" encoding="euc-jp"?>'
        b'<meta charset="windows-1251">' + _CYRILLIC_1251 + b"\x8e\xff"
    )
    assert detect_markup_charset(data, _ALL - {"euc_jis_2004"}) == DetectionResult(
        "cp1251", DETERMINISTIC_CONFIDENCE, None, "text/html"
    )


def test_single_filtered_out_declaration_falls_through():
    data = b'<meta charset="iso-8859-5">' + _CYRILLIC_1251
    assert detect_markup_charset(data, _ALL - {"iso8859-5"}) is None
    result = detect(data, exclude_encodings=["iso-8859-5"])
    assert result["encoding"] != "ISO-8859-5"
    assert result["mime_type"] == "text/plain"


def test_utf8_override_keeps_the_declaration_mime_type():
    """Genuine UTF-8 structure beats the declared name, not its MIME type."""
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><a>' + "café".encode()
    precheck = DetectionResult("utf-8", 0.9, None, None)
    assert detect_markup_charset(data, _ALL, precheck) == DetectionResult(
        "utf-8", 0.9, None, "text/xml"
    )


def test_utf8_override_needs_utf8_to_be_allowed():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><a>' + "café".encode()
    precheck = DetectionResult("utf-8", 0.9, None, None)
    assert detect_markup_charset(data, _ALL - {"utf-8"}, precheck) == (
        DetectionResult("iso8859-1", DETERMINISTIC_CONFIDENCE, None, "text/xml")
    )


# --- The stage: superset promotion ------------------------------------------

_SJIS_TEXT = "こんにちは、世界。".encode("shift_jis")
#: CP932's NEC row 13 (circled digit one): shift_jis_2004 decodes it, but
#: the reported name "SHIFT_JIS" resolves to plain shift_jis, which cannot.
_SJIS_NEC = _SJIS_TEXT + b"\x87\x40"
#: A JIS X 0213 bracket only shift_jis_2004 maps: neither plain shift_jis
#: nor CP932 decodes it.
_SJIS_X0213 = _SJIS_TEXT + "〖".encode("shift_jis_2004")
_XML_SJIS = b'<?xml version="1.0" encoding="shift_jis"?>'


def test_promote_when_reported_codec_cannot_decode():
    """Declared Shift_JIS with CP932 NEC extensions promotes to cp932.

    The promotion fires regardless of structural-score ties so the reported
    name can actually decode the data.
    """
    _SJIS_NEC.decode("cp932")  # sanity: superset decodes
    result = detect_markup_charset(_XML_SJIS + _SJIS_NEC, _ALL)
    assert result == DetectionResult("cp932", 0.95, None, "text/xml")


def test_no_promotion_when_reported_codec_decodes_and_structure_ties():
    """Plain Shift_JIS data stays shift_jis_2004 (no promotion on ties)."""
    result = detect_markup_charset(_XML_SJIS + _SJIS_TEXT, _ALL)
    assert result is not None
    assert result.encoding == "shift_jis_2004"


def test_declared_encoding_kept_when_only_it_decodes():
    """A JIS X 0213 character keeps the declared shift_jis_2004.

    Neither the reported codec nor the superset decodes it, but the
    declared encoding does, so the declaration still stands.
    """
    result = detect_markup_charset(_XML_SJIS + _SJIS_X0213, _ALL)
    assert result is not None
    assert result.encoding == "shift_jis_2004"


def test_superset_not_allowed_falls_back_to_the_declared_name():
    allowed = _ALL - {"cp932"}
    result = detect_markup_charset(_XML_SJIS + _SJIS_NEC, allowed)
    assert result is not None
    assert result.encoding == "shift_jis_2004"

    kr = "한국어 텍스트입니다.".encode("euc-kr")
    data = b'<meta charset="euc-kr">' + kr * 400 + "똠".encode("cp949")
    assert detect_markup_charset(data, _ALL - {"cp949"}) is None


def test_superset_stands_in_only_when_the_declared_name_fails():
    """With only the superset allowed, a declaration that decodes is not reported.

    The superset is reported in the declared name's place only when the
    declared encoding cannot decode the window, as before the allowed gate
    moved into the stage.
    """
    kr = "한국어 텍스트입니다.".encode("euc-kr") * 400
    meta = b'<meta charset="euc-kr">'
    allowed = frozenset({"cp949"})
    assert detect_markup_charset(meta + kr, allowed) is None
    assert detect_markup_charset(meta + kr + "똠".encode("cp949"), allowed) == (
        DetectionResult("cp949", 0.95, None, "text/html")
    )
    assert detect_markup_charset(meta + kr + b"\xff\xff", allowed) is None


def test_declared_subset_promotes_when_superset_bytes_sit_past_the_head():
    """Whole-window validation must not pre-empt superset promotion.

    A declared EUC-KR page usually meets its first CP949-only hangul well
    past the scanned head.  EUC-KR cannot decode the window, CP949 can, so
    the answer is the promoted superset at declaration confidence, not a
    statistical guess after the declaration was thrown away.
    """
    kr = "한국어 텍스트입니다.".encode("euc-kr")
    data = b'<meta charset="euc-kr">' + kr * 400 + "똠".encode("cp949") + kr * 10
    stage = detect_markup_charset(data, _ALL)
    assert stage == DetectionResult("cp949", 0.95, None, "text/html")
    result = detect(data)
    assert result["encoding"] == "CP949"
    assert result["confidence"] == 0.95
    assert result["mime_type"] == "text/html"


def _favour_cp932(head: bytes, info: EncodingInfo, ctx: object) -> float:
    return 2.0 if info.name == "cp932" else 1.0


@_needs_interpreted_build
def test_promotion_when_superset_structure_scores_higher():
    """The superset wins when its structural score beats the declared base.

    Both codecs decode the data, so the decision falls to the structural
    comparison; the scorer is patched to favour the superset, which is the
    one regime the mutually-decodable inputs in the corpus never reach
    (a genuine CP932-only byte already fails the shift_jis decode check).
    """
    with patch.object(markup_mod, "compute_structural_score", _favour_cp932):
        result = detect_markup_charset(b'<meta charset="shift_jis">' + _SJIS_TEXT, _ALL)
    assert result == DetectionResult("cp932", 0.95, None, "text/html")


@_needs_interpreted_build
def test_no_promotion_when_better_scoring_superset_cannot_decode():
    """A superset the structure prefers is still refused when it cannot decode."""
    data = _XML_SJIS + _SJIS_X0213
    with patch.object(markup_mod, "compute_structural_score", _favour_cp932):
        result = detect_markup_charset(data, _ALL)
        assert result is not None
        assert result.encoding == "shift_jis_2004"
        # Nothing decodes a lead byte with a bad trail.
        assert detect_markup_charset(data + b"\x81\x20", _ALL) is None


@_needs_interpreted_build
@pytest.mark.parametrize(
    ("data", "expected", "budget"),
    [
        (
            b'<meta charset="windows-1252">' + "café résumé ".encode("cp1252") * 2000,
            "Windows-1252",
            1,
        ),
        (
            b'<meta charset="shift_jis">'
            + "日本語のテキストです。".encode("shift_jis") * 1000,
            "SHIFT_JIS",
            1,
        ),
        (
            b'<meta charset="euc-kr">'
            + "한국어 텍스트입니다.".encode("euc-kr") * 1000
            + "똠".encode("cp949"),
            "CP949",
            2,
        ),
        (
            b'<meta charset="shift_jis">'
            + "Voilà, un résumé très détaillé de la journée. ".encode("cp1252") * 200,
            "Windows-1252",
            3,
        ),
    ],
    ids=["single-byte", "shift_jis-clean", "euc-kr-promoted", "shift_jis-lying"],
)
def test_declared_page_window_decode_budget(data: bytes, expected: str, budget: int):
    """A declared page pays one window decode, two when it promotes to a superset.

    A clean declared Shift_JIS page needs only the reported codec's decode:
    plain shift_jis decodes nothing that shift_jis_2004 cannot.  The dual
    is a Shift_JIS declaration on bytes none of the three codecs accept:
    the reported codec, the superset, and the declared encoding are each
    tried, three decodes where the old two-step paid two, and each stops
    at the first bad byte.
    """
    real = markup_mod.decodes_without_error
    window_decodes: list[str] = []

    def counting(buf: bytes, encoding: str) -> bool:
        if len(buf) > markup_mod._SCAN_LIMIT:
            window_decodes.append(encoding)
        return real(buf, encoding)

    with patch.object(markup_mod, "decodes_without_error", counting):
        assert detect(data)["encoding"] == expected
    assert len(window_decodes) == budget, window_decodes


@_needs_interpreted_build
@pytest.mark.parametrize(
    ("data", "allowed", "expected", "budget"),
    [
        (
            b"<meta charset=euc-kr>" * 150
            + b"<meta charset=windows-1252>"
            + b"plain text " * 1000
            + b"\xb0 ",
            _ALL,
            "cp1252",
            3,
        ),
        (
            "<meta charset=cp424>".encode("cp037") * 150
            + ("hello mainframe " * 400).encode("cp037")
            + b"\x70",
            _ALL,
            None,
            1,
        ),
        (
            b"<meta charset=shift_jis>" * 150
            + "日本語のテキストです。".encode("shift_jis") * 1000,
            _ALL - {"shift_jis_2004"},
            None,
            1,
        ),
    ],
    ids=["html", "ebcdic", "filtered"],
)
def test_repeated_declaration_decodes_the_window_once(
    data: bytes, allowed: frozenset[str], expected: str | None, budget: int
):
    """A label that already failed the window decode is not decoded again.

    Each failed declaration costs a decode of the whole window, so a head
    repeating one bad label multiplied the window by the number of tags: 195
    ``<meta charset=euc-kr>`` tags over a 16 MiB window took 36s instead of
    0.4s.  The next distinct label is still tried.  A filtered-out label that
    decodes ends the scan on its first decode.
    """
    real = markup_mod.decodes_without_error
    window_decodes: list[str] = []

    def counting(buf: bytes, encoding: str) -> bool:
        if len(buf) > markup_mod._SCAN_LIMIT:
            window_decodes.append(encoding)
        return real(buf, encoding)

    with patch.object(markup_mod, "decodes_without_error", counting):
        result = detect_markup_charset(data, allowed)
    assert (result.encoding if result else None) == expected
    assert len(window_decodes) == budget, window_decodes


def test_promotion_table_derives_from_the_registry():
    """The registry's CJK superset pairs reproduce the old hand-written table.

    Each value is (codec the reported name resolves to, superset).  The
    ISO/Windows pairs stay out: markup promotion was never about them.
    """
    assert markup_mod._MARKUP_SUPERSET_PROMOTIONS == {
        "shift_jis_2004": ("shift_jis", "cp932"),
        "euc_kr": ("euc_kr", "cp949"),
    }


@pytest.mark.parametrize(
    "data",
    [
        b'<me<!-- comment -->ta charset="cp1251">Hello world',
        b'<meta char<!-- comment -->set="cp1251">Hello world',
        b'<meta charset="cp<!-- comment -->1251">Hello world',
        b'<?xm<!-- comment -->l encoding="cp1251"?>Hello world',
        b'<?xml encod<!-- comment -->ing="cp1251"?>Hello world',
        b'<?xml encoding="cp<!-- comment -->1251"?>Hello world',
    ],
)
def test_comments_do_not_join_declaration_fragments(data: bytes):
    declarations = _declarations(data)
    assert all(declaration.encoding is None for declaration in declarations)
    result = detect(data)
    assert result["encoding"] == "ascii"
    live = b'<meta charset="iso-8859-1">'
    assert _declarations(data + live) == declarations + _html("iso8859-1")

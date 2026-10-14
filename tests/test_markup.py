# tests/test_markup.py
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

import chardet.pipeline.markup as markup_mod
from chardet import detect
from chardet.pipeline import DetectionResult
from chardet.pipeline.markup import detect_markup_charset, promote_markup_superset
from chardet.registry import EncodingInfo

#: See the note in tests/test_confusion.py: mypyc resolves a compiled
#: module's calls to functions imported into it at compile time, so patching
#: those names only takes effect on interpreted builds.
_needs_interpreted_build = pytest.mark.skipif(
    markup_mod.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
)


def test_promote_markup_superset_passthrough_none_encoding():
    """promote_markup_superset passes through results with encoding=None."""
    result = DetectionResult(None, 0.95, None, None)
    allowed = frozenset({"cp932", "shift_jis_2004"})
    assert promote_markup_superset(b"", result, allowed) is result


def test_xml_encoding_declaration():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "iso8859-1"
    assert result.confidence < 1.0


def test_html5_meta_charset():
    data = b'<html><head><meta charset="utf-8"></head></html>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_charset_inside_another_attribute_does_not_hide_meta_charset():
    # A refresh URL or a description can contain the letters charset=.
    # That is not the page encoding. The meta charset attribute is.
    data = (
        b'<meta http-equiv="refresh" '
        b'content="0;url=http://example.com/?charset=iso-8859-1">'
        b'<meta charset="utf-8">'
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"

    data = (
        b'<meta name="description" '
        b'content="see charset=iso-8859-1 for notes">'
        b'<meta charset="utf-8">'
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_name_content_type_is_accepted():
    """``name='content-type'`` is wrong by the spec but common in the wild."""
    data = (
        b"<html><head>"
        b"<meta name='content-type' content='text/html;charset=iso-8859-6'>"
        b"</head></html>"
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "iso8859-6"


def test_first_value_wins_when_attribute_repeats():
    data = b'<meta charset="iso-8859-5" charset="utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "iso8859-5"


def test_unquoted_charset_value():
    data = b"<meta charset=koi8-r>"
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "koi8-r"


def test_unclosed_meta_tag_is_not_a_declaration():
    data = b'<meta charset="utf-8"'
    assert detect_markup_charset(data) is None


def test_bad_declaration_does_not_hide_a_later_one():
    data = b'<meta charset="no-such-encoding"><meta charset="utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_non_ascii_xml_encoding_name_ignored():
    data = b'<?xml version="1.0" encoding="\xff\xfe"?><root/>'
    assert detect_markup_charset(data) is None


def test_html4_content_type():
    data = (
        b"<html><head>"
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
        b"</head></html>"
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "cp1252"


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
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "cp1252"
    assert result.mime_type == "text/html"
    assert detect(data)["encoding"] == "Windows-1252"
    assert detect(data)["mime_type"] == "text/html"


@pytest.mark.parametrize("parameter", [b'charset="windows-1252', b'charset=""'])
def test_html4_content_type_invalid_quoted_charset(parameter: bytes):
    data = b"<meta http-equiv='Content-Type' content='text/html; " + parameter + b"'>"
    assert detect_markup_charset(data) is None


def test_no_markup():
    result = detect_markup_charset(b"Just plain text with no HTML or XML")
    assert result is None


def test_empty_input():
    result = detect_markup_charset(b"")
    assert result is None


def test_xml_single_quotes():
    data = b"<?xml version='1.0' encoding='shift_jis'?><root/>"
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "shift_jis_2004"


def test_case_insensitive_meta():
    data = b'<META CHARSET="UTF-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_charset_with_whitespace():
    data = b'<meta charset = "utf-8" >'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_unknown_encoding_returns_none():
    data = b'<meta charset="not-a-real-encoding">'
    result = detect_markup_charset(data)
    assert result is None


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
    result = detect_markup_charset(data)
    assert result is None


def test_valid_charset_declaration_accepted():
    # Declares shift_jis and contains valid shift_jis bytes
    data = b'<meta charset="shift_jis">' + "日本語テスト".encode("shift_jis")
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "shift_jis_2004"


def test_charset_within_scan_limit_found():
    padding = b"x" * 100
    data = padding + b'<meta charset="utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "utf-8"


def test_charset_beyond_scan_limit_ignored():
    padding = b"x" * 5000  # Exceeds _SCAN_LIMIT (4096)
    data = padding + b'<meta charset="utf-8">'
    result = detect_markup_charset(data)
    assert result is None


def test_charset_declaration_not_honored_when_window_fails_to_decode():
    """A declaration whose encoding stops decoding past the head is dropped.

    The stage validates the declaration against the whole window, so it
    returns nothing and the other stages answer as if there were no
    declaration.
    """
    data = b'<meta charset="euc-jp">' + b"x" * 5000 + b"\x80\x80\x80"
    assert detect_markup_charset(data) is None
    result = detect(data)
    assert result["encoding"] != "EUC-JP"
    assert result["mime_type"] != "text/html"


def test_pep263_not_honored_when_window_fails_to_decode():
    """A PEP 263 coding line is dropped when the window fails to decode."""
    data = b"# coding: euc-jp\n# " + b"x" * 5000 + b"\n\x80\x80\x80"
    assert detect(data)["encoding"] != "EUC-JP"


def test_non_ascii_charset_name_ignored():
    """A charset name containing non-ASCII bytes should be skipped."""
    # Build a meta tag whose charset value contains a non-ASCII byte (0xff)
    data = b'<meta charset="' + b"\xff\xfe" + b'">'
    result = detect_markup_charset(data)
    assert result is None


def test_null_byte_in_charset_name():
    """A null byte in the charset value must not crash.

    Regression test for https://github.com/chardet/chardet/issues/369:
    codecs.lookup() raises ValueError on embedded null characters.
    """
    data = b'<meta charset="\x00utf-8">'
    result = detect_markup_charset(data)
    assert result is None


def test_pep263_non_ascii_coding_name():
    """PEP 263 coding name with non-ASCII bytes should return None."""
    # The default PEP263 regex only captures ASCII via \\w on bytes, so
    # swap in a broader regex that can capture high bytes.
    broad_re = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([^\s]+)", re.MULTILINE)
    data = b"# -*- coding: \xff\xfe -*-\n"
    with patch("chardet.pipeline.markup._PEP263_RE", broad_re):
        result = detect_markup_charset(data)
    assert result is None


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
    assert detect_markup_charset(data) is None
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
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "cp1251"


def test_pep263_cookie_after_code_does_not_override_utf8():
    """An ignored cookie must not override the actual UTF-8 source encoding."""
    data = 'print("привет")\n# coding: cp1251\n'.encode()
    assert detect(data)["encoding"] == "utf-8"


def test_promote_when_reported_codec_cannot_decode():
    """Declared Shift_JIS with CP932 NEC extensions promotes to cp932.

    The internal shift_jis_2004 codec decodes NEC row 13 (e.g. 0x87 0x40,
    the circled digit one), but the reported name "SHIFT_JIS" resolves to
    plain shift_jis for callers, which cannot.  The promotion must fire
    regardless of structural-score ties so the reported name can actually
    decode the data.
    """
    data = "こんにちは".encode("shift_jis") + b"\x87\x40"
    data.decode("cp932")  # sanity: superset decodes
    result = DetectionResult("shift_jis_2004", 0.95, None, "text/xml")
    allowed = frozenset({"cp932", "shift_jis_2004"})
    promoted = promote_markup_superset(data, result, allowed)
    assert promoted.encoding == "cp932"
    assert promoted.confidence == 0.95
    assert promoted.mime_type == "text/xml"


def test_no_promotion_when_reported_codec_decodes_and_structure_ties():
    """Plain Shift_JIS data stays shift_jis_2004 (no promotion on ties)."""
    data = "こんにちは、世界。".encode("shift_jis")
    result = DetectionResult("shift_jis_2004", 0.95, None, "text/html")
    allowed = frozenset({"cp932", "shift_jis_2004"})
    promoted = promote_markup_superset(data, result, allowed)
    assert promoted.encoding == "shift_jis_2004"


def test_ebcdic_meta_charset_declaration():
    """A charset declaration inside EBCDIC-encoded markup is honoured.

    The head is dominated by high bytes (EBCDIC letters), decodes through
    cp037 to a ``<meta charset=...>`` tag naming a MAINFRAME-era encoding
    that decodes the data, so the declaration wins.
    """
    html = "<meta charset=cp500><p>hello there dear reader of mainframe pages</p>"
    data = html.encode("cp500")
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "cp500"
    assert result.mime_type == "text/html"


def test_ebcdic_declaration_ignored_for_non_mainframe_name():
    """An EBCDIC-decoded declaration naming a non-MAINFRAME encoding is ignored."""
    html = "<meta charset=utf-8><p>hello there dear reader of mainframe pages</p>"
    data = html.encode("cp500")
    result = detect_markup_charset(data)
    assert result is None or result.encoding != "utf-8"


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


def test_declared_subset_promotes_when_superset_bytes_sit_past_the_head():
    """Whole-window validation must not pre-empt superset promotion.

    A declared EUC-KR page usually meets its first CP949-only hangul well
    past the scanned head.  EUC-KR cannot decode the window, CP949 can, so
    the answer is the promoted superset at declaration confidence, not a
    statistical guess after the declaration was thrown away.
    """
    kr = "한국어 텍스트입니다.".encode("euc-kr")
    data = b'<meta charset="euc-kr">' + kr * 400 + "똠".encode("cp949") + kr * 10
    result = detect(data)
    assert result["encoding"] == "CP949"
    assert result["confidence"] == 0.95
    assert result["mime_type"] == "text/html"


@_needs_interpreted_build
def test_promotion_when_superset_structure_scores_higher():
    """The superset wins when its structural score beats the declared base.

    Both codecs decode the data, so the decision falls to the structural
    comparison; the scorer is patched to favour the superset, which is the
    one regime the mutually-decodable inputs in the corpus never reach
    (a genuine CP932-only byte already fails the shift_jis decode check).
    """
    data = "こんにちは、世界。".encode("shift_jis")
    result = DetectionResult("shift_jis_2004", 0.95, None, "text/html")
    allowed = frozenset({"cp932", "shift_jis_2004"})

    def fake_score(head: bytes, info: EncodingInfo, ctx: object) -> float:
        return 2.0 if info.name == "cp932" else 1.0

    with patch.object(markup_mod, "compute_structural_score", fake_score):
        promoted = promote_markup_superset(data, result, allowed)
    assert promoted.encoding == "cp932"
    assert promoted.confidence == result.confidence
    assert promoted.mime_type == "text/html"


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


def test_declared_subset_promotes_from_the_stage():
    """The stage reports the superset when only it decodes the window."""
    kr = "한국어 텍스트입니다.".encode("euc-kr")
    data = b'<meta charset="euc-kr">' + kr * 400 + "똠".encode("cp949") + kr * 10
    stage = detect_markup_charset(data)
    assert stage is not None
    assert stage.encoding == "cp949"
    assert stage.mime_type == "text/html"


@_needs_interpreted_build
def test_no_promotion_when_better_scoring_superset_cannot_decode():
    """A superset the structure prefers is still refused when it cannot decode."""
    data = "こんにちは、世界。".encode("shift_jis") + b"\x81\x20"  # lead, bad trail
    result = DetectionResult("shift_jis_2004", 0.95, None, "text/html")
    allowed = frozenset({"cp932", "shift_jis_2004"})

    def fake_score(head: bytes, info: EncodingInfo, ctx: object) -> float:
        return 2.0 if info.name == "cp932" else 1.0

    with patch.object(markup_mod, "compute_structural_score", fake_score):
        assert promote_markup_superset(data, result, allowed) is result


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
            2,
        ),
        (
            b'<meta charset="euc-kr">'
            + "한국어 텍스트입니다.".encode("euc-kr") * 1000
            + "똠".encode("cp949"),
            "CP949",
            2,
        ),
    ],
    ids=["single-byte", "shift_jis-clean", "euc-kr-promoted"],
)
def test_declared_page_window_decode_budget(data: bytes, expected: str, budget: int):
    """Declared pages pay at most one window decode, two when a superset is in play."""
    real = markup_mod.decodes_without_error
    window_decodes: list[str] = []

    def counting(buf: bytes, encoding: str) -> bool:
        if len(buf) > markup_mod._SCAN_LIMIT:
            window_decodes.append(encoding)
        return real(buf, encoding)

    with patch.object(markup_mod, "decodes_without_error", counting):
        assert detect(data)["encoding"] == expected
    assert len(window_decodes) <= budget, window_decodes

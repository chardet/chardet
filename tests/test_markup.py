# tests/test_markup.py
from __future__ import annotations

import re
from unittest.mock import patch

from chardet.pipeline import DetectionResult
from chardet.pipeline.markup import detect_markup_charset, promote_markup_superset


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


def test_html4_content_type():
    data = (
        b"<html><head>"
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
        b"</head></html>"
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "cp1252"


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

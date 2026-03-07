# tests/test_markup.py
from __future__ import annotations

from chardet.pipeline.markup import detect_markup_charset


def test_xml_encoding_declaration():
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "ISO-8859-1"
    assert result.confidence < 1.0


def test_html5_meta_charset():
    data = b'<html><head><meta charset="utf-8"></head></html>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "UTF-8"


def test_html4_content_type():
    data = (
        b"<html><head>"
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
        b"</head></html>"
    )
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "Windows-1252"


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
    assert result.encoding == "Shift-JIS-2004"


def test_case_insensitive_meta():
    data = b'<META CHARSET="UTF-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "UTF-8"


def test_charset_with_whitespace():
    data = b'<meta charset = "utf-8" >'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "UTF-8"


def test_unknown_encoding_returns_none():
    data = b'<meta charset="not-a-real-encoding">'
    result = detect_markup_charset(data)
    assert result is None


def test_lying_charset_declaration_rejected():
    # Declares shift_jis but contains invalid bytes for that encoding
    data = b'<meta charset="shift_jis">' + "日本語テスト".encode()
    result = detect_markup_charset(data)
    assert result is None


def test_valid_charset_declaration_accepted():
    # Declares shift_jis and contains valid shift_jis bytes
    data = b'<meta charset="shift_jis">' + "日本語テスト".encode("shift_jis")
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "Shift-JIS-2004"


def test_charset_within_scan_limit_found():
    padding = b"x" * 100
    data = padding + b'<meta charset="utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.encoding == "UTF-8"


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

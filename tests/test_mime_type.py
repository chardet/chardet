from __future__ import annotations

from chardet.pipeline.markup import detect_markup_charset


def test_markup_xml_mime_type() -> None:
    data = b'<?xml version="1.0" encoding="iso-8859-1"?><root/>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/xml"


def test_markup_html5_mime_type() -> None:
    data = b'<meta charset="utf-8"><html><body>Hello</body></html>'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/html"


def test_markup_html4_mime_type() -> None:
    data = b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/html"


def test_markup_pep263_mime_type() -> None:
    data = b"# -*- coding: utf-8 -*-\nprint('hello')\n"
    result = detect_markup_charset(data)
    assert result is not None
    assert result.mime_type == "text/x-python"


def test_markup_no_match_returns_none() -> None:
    result = detect_markup_charset(b"Hello, world!")
    assert result is None

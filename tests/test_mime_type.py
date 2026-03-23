from __future__ import annotations

import pytest
from utils import get_data_dir

import chardet
from chardet.detector import UniversalDetector
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


def test_detect_png_returns_mime_type() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "image/png"


def test_detect_jpeg_returns_mime_type() -> None:
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "image/jpeg"


def test_detect_pdf_returns_mime_type() -> None:
    data = b"%PDF-1.4 " + b"\x00" * 100
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "application/pdf"


def test_text_result_defaults_to_text_plain() -> None:
    result = chardet.detect(b"Hello world")
    assert result["mime_type"] == "text/plain"


def test_binary_result_defaults_to_octet_stream() -> None:
    # Control bytes that trigger binary detection but don't match any magic number.
    # Mix of control chars (no nulls to avoid UTF-16 detection) with high bytes.
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0E, 0x0F, 0x10, 0x11]) * 20
    result = chardet.detect(data)
    assert result["encoding"] is None
    assert result["mime_type"] == "application/octet-stream"


def test_utf8_result_has_text_plain() -> None:
    data = "Héllo wörld café".encode()
    result = chardet.detect(data)
    assert result["mime_type"] == "text/plain"


def test_empty_input_has_text_plain() -> None:
    result = chardet.detect(b"")
    assert result["mime_type"] == "text/plain"


def test_detect_all_includes_mime_type() -> None:
    data = "Héllo wörld café résumé".encode()
    results = chardet.detect_all(data, ignore_threshold=True)
    for r in results:
        assert "mime_type" in r
        assert r["mime_type"] == "text/plain"


def test_detect_all_binary_mime_type() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    results = chardet.detect_all(data)
    assert results[0]["mime_type"] == "image/png"


def test_universal_detector_mime_type() -> None:
    det = UniversalDetector()
    det.feed(b"Hello world")
    result = det.close()
    assert result["mime_type"] == "text/plain"


def test_universal_detector_binary_mime_type() -> None:
    det = UniversalDetector()
    det.feed(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    result = det.close()
    assert result["mime_type"] == "image/png"


def test_universal_detector_pre_close_mime_type() -> None:
    """Before close(), mime_type is None (placeholder result)."""
    det = UniversalDetector()
    assert det.result["mime_type"] is None


def test_none_none_files_have_correct_mime_types() -> None:
    """Binary files in None-None folder should get specific MIME types."""
    data_dir = get_data_dir()
    none_dir = data_dir / "None-None"
    if not none_dir.exists():
        pytest.skip("test data not available")

    expected_mimes = {
        "sample-1.gif": "image/gif",
        "sample-1.jpg": "image/jpeg",
        "sample-1.mp4": "video/mp4",
        "sample-1.png": "image/png",
        "sample-1.webp": "image/webp",
        "sample-1.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sample-2.png": "image/png",
        "sample-3.png": "image/png",
    }

    tested = 0
    for filename, expected_mime in expected_mimes.items():
        filepath = none_dir / filename
        if not filepath.exists():
            continue
        tested += 1
        data = filepath.read_bytes()
        result = chardet.detect(data)
        assert result["encoding"] is None, f"{filename}: expected binary"
        assert result["mime_type"] == expected_mime, (
            f"{filename}: expected mime_type={expected_mime}, got={result['mime_type']}"
        )
    assert tested > 0, "no test data files found in None-None directory"

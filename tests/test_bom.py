# tests/test_bom.py
from __future__ import annotations

import codecs

import pytest

import chardet
from chardet import detect
from chardet.pipeline import DetectionResult
from chardet.pipeline.bom import detect_bom


def test_utf8_bom():
    data = b"\xef\xbb\xbfHello"
    result = detect_bom(data)
    assert result == DetectionResult("utf-8-sig", 1.0, None)


def test_utf16_le_bom():
    data = b"\xff\xfeH\x00e\x00l\x00l\x00o\x00"
    result = detect_bom(data)
    assert result == DetectionResult("utf-16", 1.0, None)


def test_utf16_be_bom():
    data = b"\xfe\xff\x00H\x00e\x00l\x00l\x00o"
    result = detect_bom(data)
    assert result == DetectionResult("utf-16", 1.0, None)


def test_utf32_le_bom():
    data = b"\xff\xfe\x00\x00" + b"\x48\x00\x00\x00"
    result = detect_bom(data)
    assert result == DetectionResult("utf-32", 1.0, None)


def test_utf32_be_bom():
    data = b"\x00\x00\xfe\xff" + b"\x00\x00\x00\x48"
    result = detect_bom(data)
    assert result == DetectionResult("utf-32", 1.0, None)


def test_no_bom():
    data = b"Hello, world!"
    result = detect_bom(data)
    assert result is None


def test_empty_input():
    assert detect_bom(b"") is None


def test_too_short_for_bom():
    assert detect_bom(b"\xef") is None
    assert detect_bom(b"\xef\xbb") is None


def test_utf32_le_checked_before_utf16_le():
    # UTF-32-LE BOM starts with \xff\xfe (same as UTF-16-LE) but has \x00\x00 after
    data = b"\xff\xfe\x00\x00" + b"\x48\x00\x00\x00"
    result = detect_bom(data)
    assert result is not None
    assert result.encoding == "utf-32"


def test_utf32_le_bom_only():
    # Bare UTF-32-LE BOM with no payload is valid (0 % 4 == 0)
    result = detect_bom(b"\xff\xfe\x00\x00")
    assert result is not None
    assert result.encoding == "utf-32"


def test_utf32_le_bom_falls_through_to_utf16_when_payload_not_aligned():
    # FF FE 00 00 30 00 looks like UTF-32-LE BOM, but the remaining
    # 2 bytes are not a valid UTF-32 code unit (need multiple of 4).
    # Should fall through to UTF-16-LE BOM instead.
    data = b"\xff\xfe\x00\x000\x00"
    result = detect_bom(data)
    assert result is not None
    assert result.encoding == "utf-16"


def test_utf32_be_bom_falls_through_when_payload_not_aligned():
    # Same logic for UTF-32-BE: payload must be a multiple of 4 bytes
    data = b"\x00\x00\xfe\xff\x00\x48"  # 2-byte payload, not aligned
    result = detect_bom(data)
    # No UTF-16-BE fallback here (00 00 FE FF doesn't start with FE FF)
    assert result is None


@pytest.mark.parametrize("encoding", ["utf-32-le", "utf-32-be"])
@pytest.mark.parametrize("max_bytes", [1020, 1021, 1022, 1023])
@pytest.mark.parametrize("api", ["detect", "detect_all", "stream", "split-stream"])
def test_utf32_bom_survives_max_bytes_cut(encoding: str, max_bytes: int, api: str):
    """A window ending mid-unit must retain the BOM's UTF-32 interpretation."""
    text = "Hello world, this is a UTF-32 document. " * 50
    bom = codecs.BOM_UTF32_LE if encoding.endswith("le") else codecs.BOM_UTF32_BE
    data = bom + text.encode(encoding)
    if api == "detect":
        result = chardet.detect(data, max_bytes=max_bytes)
    elif api == "detect_all":
        result = chardet.detect_all(data, max_bytes=max_bytes)[0]
    else:
        detector = chardet.UniversalDetector(max_bytes=max_bytes)
        if api == "split-stream":
            detector.feed(data[:max_bytes])
            detector.feed(data[max_bytes:])
        else:
            detector.feed(data)
        result = detector.close()
    assert result["encoding"] == "UTF-32"
    assert result["confidence"] == 1.0
    assert data.decode(result["encoding"]) == text


@pytest.mark.parametrize(
    "text", ["\0" + "中文测试" * 30, "\0" + "Hello world. " * 30], ids=["cjk", "ascii"]
)
@pytest.mark.parametrize("max_bytes", [101, 102, 103])
@pytest.mark.parametrize("api", ["detect", "detect_all", "stream", "split-stream"])
def test_utf16_bom_fallback_survives_max_bytes_cut(text: str, max_bytes: int, api: str):
    """An invalid UTF-32 interpretation must still try the overlapping UTF-16 BOM."""
    data = codecs.BOM_UTF16_LE + text.encode("utf-16-le")
    if api == "detect":
        result = chardet.detect(data, max_bytes=max_bytes)
    elif api == "detect_all":
        result = chardet.detect_all(data, max_bytes=max_bytes)[0]
    else:
        detector = chardet.UniversalDetector(max_bytes=max_bytes)
        if api == "split-stream":
            detector.feed(data[:max_bytes])
            detector.feed(data[max_bytes:])
        else:
            detector.feed(data)
        result = detector.close()
    assert result["encoding"] == "UTF-16"
    assert result["confidence"] == 1.0
    assert data.decode(result["encoding"]) == text


@pytest.mark.parametrize("encoding", ["utf-32-le", "utf-32-be"])
def test_cut_utf32_bom_rejects_corruption_before_tail(encoding: str):
    """Tolerating a cut code unit must not tolerate an invalid complete one."""
    bom = codecs.BOM_UTF32_LE if encoding.endswith("le") else codecs.BOM_UTF32_BE
    order = "little" if encoding.endswith("le") else "big"
    data = bom + "Hello world. ".encode(encoding)
    data += (0x110000).to_bytes(4, order) + "more text".encode(encoding)
    result = chardet.detect(data, max_bytes=len(data) - 1)
    assert result["encoding"] != "UTF-32"


# ---------------------------------------------------------------------------
# A mark names the encoding; the body has to decode under it
# ---------------------------------------------------------------------------


def _decodes_or_none(data: bytes) -> None:
    result = detect(data)
    if result["encoding"] is not None:
        data.decode(result["encoding"])


def test_utf16_bom_with_lone_surrogate_is_no_answer():
    data = (
        b"\xff\xfe" + "Hello, world. ".encode("utf-16-le") * 20 + b"\x00\xd8" + b"t\x00"
    )
    assert detect_bom(data) is None
    _decodes_or_none(data)


def test_utf16_be_bom_with_lone_surrogate_is_no_answer():
    data = (
        b"\xfe\xff" + "Hello, world. ".encode("utf-16-be") * 20 + b"\xd8\x00" + b"\x00t"
    )
    assert detect_bom(data) is None
    _decodes_or_none(data)


@pytest.mark.parametrize("input_truncated", [False, True])
def test_utf32_bom_with_out_of_range_unit_is_no_answer(*, input_truncated: bool):
    data = b"\xff\xfe\x00\x00" + "x ".encode("utf-32-le") * 20 + b"\x00\x00\x11\x00"
    assert detect_bom(data, input_truncated=input_truncated) is None
    _decodes_or_none(data)


def test_utf8_bom_over_cp1252_bytes_is_no_answer():
    data = b"\xef\xbb\xbf" + "café résumé ".encode("cp1252") * 20
    assert detect_bom(data) is None
    result = detect(data)
    assert result["encoding"] != "UTF-8-SIG"
    _decodes_or_none(data)


def test_bom_with_decodable_body_still_certain():
    data = b"\xef\xbb\xbf" + "café résumé ".encode() * 20
    result = detect_bom(data)
    assert result is not None
    assert result.encoding == "utf-8-sig"
    assert result.confidence == 1.0

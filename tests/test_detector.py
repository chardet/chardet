# tests/test_detector.py
from __future__ import annotations

import pytest

import chardet
from chardet.detector import UniversalDetector
from chardet.enums import EncodingEra


def test_basic_lifecycle():
    detector = UniversalDetector()
    detector.feed(b"Hello world")
    detector.close()
    result = detector.result
    assert result["encoding"] is not None


def test_result_before_close():
    detector = UniversalDetector()
    detector.feed(b"Hello world")
    result = detector.result
    assert "encoding" in result
    assert "confidence" in result
    assert "language" in result


def test_reset():
    detector = UniversalDetector()
    detector.feed(b"Hello world")
    detector.close()
    detector.reset()
    result = detector.result
    assert result["encoding"] is None
    assert result["confidence"] == 0.0


def test_done_property():
    detector = UniversalDetector()
    assert detector.done is False


def test_feed_after_close_raises():
    detector = UniversalDetector()
    detector.feed(b"Hello")
    detector.close()
    with pytest.raises(ValueError):
        detector.feed(b"more data")


def test_feed_after_done_is_ignored():
    detector = UniversalDetector(max_bytes=10)
    detector.feed(b"x" * 20)
    assert detector.done is True
    detector.feed(b"more data")  # Should not raise
    # Buffer should not grow beyond max_bytes
    detector.close()


def test_multiple_feeds():
    detector = UniversalDetector()
    data = "Héllo wörld café".encode()
    chunk_size = 5
    for i in range(0, len(data), chunk_size):
        detector.feed(data[i : i + chunk_size])
    detector.close()
    assert detector.result["encoding"] is not None


def test_done_when_max_bytes_reached():
    """Done is set to True when the buffer reaches max_bytes."""
    detector = UniversalDetector(max_bytes=50)
    detector.feed(b"x" * 30)
    assert detector.done is False
    detector.feed(b"x" * 20)
    assert detector.done is True


def test_done_not_set_before_max_bytes():
    """Done stays False when buffer is under max_bytes."""
    detector = UniversalDetector(max_bytes=100)
    detector.feed(b"Hello world")
    assert detector.done is False


def test_encoding_era_parameter():
    detector = UniversalDetector(encoding_era=EncodingEra.MODERN_WEB)
    detector.feed(b"Hello world")
    detector.close()
    assert detector.result is not None


def test_max_bytes_parameter():
    detector = UniversalDetector(max_bytes=100)
    detector.feed(b"x" * 200)
    detector.close()
    assert detector.result is not None


def test_max_bytes_zero_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        UniversalDetector(max_bytes=0)


def test_max_bytes_negative_raises():
    with pytest.raises(ValueError, match="max_bytes"):
        UniversalDetector(max_bytes=-1)


def test_close_idempotent():
    detector = UniversalDetector()
    detector.feed(b"Hello world, this is enough text. " * 3)
    result1 = detector.close()
    result2 = detector.close()
    assert result1 == result2


def test_reset_allows_new_detection():
    detector = UniversalDetector()
    detector.feed(b"\xef\xbb\xbfHello")
    detector.close()
    assert detector.result["encoding"] == "UTF-8-SIG"

    detector.reset()
    detector.feed("Héllo wörld café".encode())
    detector.close()
    assert detector.result["encoding"] == "utf-8"


# -- Equivalence tests: UniversalDetector must match detect() --

# Test data covering various pipeline stages
_EQUIVALENCE_SAMPLES = {
    "bom_utf8": b"\xef\xbb\xbfHello world",
    "bom_utf16le": b"\xff\xfeH\x00e\x00l\x00l\x00o\x00",
    "bom_utf16be": b"\xfe\xff\x00H\x00e\x00l\x00l\x00o",
    "ascii": b"Hello world, this is plain ASCII text. " * 5,
    "utf8": "Héllo wörld café résumé naïve über Ελληνικά".encode(),
    "escape_iso2022jp": b"Hello \x1b$B$3$s$K$A$O\x1b(B World",
    "markup_charset": b'<html><head><meta charset="windows-1252"></head><body>text</body></html>',
    "markup_xml": b'<?xml version="1.0" encoding="iso-8859-1"?><root>text</root>',
    "windows1252": bytes(range(0x20, 0x7F)) + b"\xe9\xe8\xea\xeb\xf6\xfc\xe4" * 20,
    "cjk_shiftjis": b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd" * 10,
}


@pytest.mark.parametrize(("label", "data"), list(_EQUIVALENCE_SAMPLES.items()))
@pytest.mark.parametrize("chunk_size", [1, 64, None])
def test_equivalence_with_detect(label: str, data: bytes, chunk_size: int | None):
    """UniversalDetector must produce the same result as chardet.detect()."""
    expected = chardet.detect(data)

    detector = UniversalDetector()
    if chunk_size is None:
        detector.feed(data)
    else:
        for i in range(0, len(data), chunk_size):
            detector.feed(data[i : i + chunk_size])
    result = detector.close()

    assert result["encoding"] == expected["encoding"], (
        f"[{label}, chunk={chunk_size}] "
        f"detector={result['encoding']}, detect={expected['encoding']}"
    )
    assert result["confidence"] == expected["confidence"], (
        f"[{label}, chunk={chunk_size}] "
        f"detector={result['confidence']}, detect={expected['confidence']}"
    )
    assert result["language"] == expected["language"], (
        f"[{label}, chunk={chunk_size}] "
        f"detector={result['language']}, detect={expected['language']}"
    )

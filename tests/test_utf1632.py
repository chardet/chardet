# tests/test_utf1632.py
"""Tests for BOM-less UTF-16/UTF-32 detection."""

from __future__ import annotations

from chardet.pipeline import DETERMINISTIC_CONFIDENCE, DetectionResult
from chardet.pipeline.utf1632 import detect_utf1632_patterns

# ---------------------------------------------------------------------------
# UTF-16-LE detection
# ---------------------------------------------------------------------------


def test_utf16_le_ascii_text() -> None:
    """ASCII-range text encoded as UTF-16-LE should be detected."""
    text = "Hello, this is a test of UTF-16 LE detection."
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"
    assert result.confidence == DETERMINISTIC_CONFIDENCE
    assert result.language is None


def test_utf16_le_longer_text() -> None:
    """A longer ASCII string should still be detected as UTF-16-LE."""
    text = "The quick brown fox jumps over the lazy dog. " * 5
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


# ---------------------------------------------------------------------------
# UTF-16-BE detection
# ---------------------------------------------------------------------------


def test_utf16_be_ascii_text() -> None:
    """ASCII-range text encoded as UTF-16-BE should be detected."""
    text = "Hello, this is a test of UTF-16 BE detection."
    data = text.encode("UTF-16-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE
    assert result.language is None


def test_utf16_be_longer_text() -> None:
    """A longer ASCII string should still be detected as UTF-16-BE."""
    text = "The quick brown fox jumps over the lazy dog. " * 5
    data = text.encode("UTF-16-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


# ---------------------------------------------------------------------------
# UTF-32-LE detection
# ---------------------------------------------------------------------------


def test_utf32_le_ascii_text() -> None:
    """ASCII-range text encoded as UTF-32-LE should be detected."""
    text = "Hello, this is a test of UTF-32 LE detection."
    data = text.encode("UTF-32-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-le"
    assert result.confidence == DETERMINISTIC_CONFIDENCE
    assert result.language is None


def test_utf32_le_longer_text() -> None:
    """A longer ASCII string should still be detected as UTF-32-LE."""
    text = "The quick brown fox jumps over the lazy dog. " * 5
    data = text.encode("UTF-32-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-le"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


# ---------------------------------------------------------------------------
# UTF-32-BE detection
# ---------------------------------------------------------------------------


def test_utf32_be_ascii_text() -> None:
    """ASCII-range text encoded as UTF-32-BE should be detected."""
    text = "Hello, this is a test of UTF-32 BE detection."
    data = text.encode("UTF-32-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE
    assert result.language is None


def test_utf32_be_longer_text() -> None:
    """A longer ASCII string should still be detected as UTF-32-BE."""
    text = "The quick brown fox jumps over the lazy dog. " * 5
    data = text.encode("UTF-32-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


# ---------------------------------------------------------------------------
# UTF-32 is checked before UTF-16
# ---------------------------------------------------------------------------


def test_utf32_checked_before_utf16() -> None:
    """UTF-32 patterns are more specific and should be tried first.

    UTF-32-LE data has nulls in positions that could look like UTF-16 as well,
    but UTF-32 should win because it is checked first.
    """
    text = "Hello world test"
    data = text.encode("UTF-32-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-le"


# ---------------------------------------------------------------------------
# Too-short input
# ---------------------------------------------------------------------------


def test_too_short_for_utf16_returns_none() -> None:
    """Input shorter than _MIN_BYTES_UTF16 (10) should return None."""
    # 4 code units = 8 bytes, below the 10-byte minimum
    text = "Test"
    data = text.encode("UTF-16-LE")
    assert len(data) == 8
    result = detect_utf1632_patterns(data)
    assert result is None


def test_too_short_for_utf32_returns_none() -> None:
    """UTF-32 data shorter than _MIN_BYTES_UTF32 (16) should fall through.

    With 3 characters (12 bytes), UTF-32 detection should not trigger,
    but if enough bytes for UTF-16 it may still be detected as UTF-16.
    """
    text = "Tes"
    data = text.encode("UTF-32-LE")
    # 3 characters * 4 bytes = 12 bytes: too short for UTF-32 (needs 16)
    assert len(data) == 12
    result = detect_utf1632_patterns(data)
    # Should not detect as UTF-32 (below minimum), may detect as UTF-16 or None
    if result is not None:
        assert result.encoding != "utf-32-le"


def test_exactly_min_utf16_bytes() -> None:
    """Exactly _MIN_BYTES_UTF16 (10) bytes should be enough for detection."""
    text = "Hello"
    data = text.encode("UTF-16-LE")
    assert len(data) == 10
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


def test_exactly_min_utf32_bytes() -> None:
    """Exactly _MIN_BYTES_UTF32 (16) bytes should be enough for detection."""
    text = "Test"
    data = text.encode("UTF-32-LE")
    assert len(data) == 16
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-le"


# ---------------------------------------------------------------------------
# Non-UTF-16/32 data
# ---------------------------------------------------------------------------


def test_plain_ascii_returns_none() -> None:
    """Regular ASCII text has no null-byte patterns and should return None."""
    data = b"Hello, this is plain ASCII text with no special encoding."
    result = detect_utf1632_patterns(data)
    assert result is None


def test_latin1_text_returns_none() -> None:
    """Latin-1 encoded text should not be detected as UTF-16/32."""
    data = b"Caf\xe9 cr\xe8me avec des r\xe9sum\xe9s fran\xe7ais"
    result = detect_utf1632_patterns(data)
    assert result is None


def test_random_bytes_returns_none() -> None:
    """Arbitrary byte sequences without null patterns should return None."""
    # Build a byte string that has no null bytes and is long enough
    data = bytes(range(1, 256)) * 2
    assert len(data) >= 10
    result = detect_utf1632_patterns(data)
    assert result is None


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_input_returns_none() -> None:
    """Empty byte string should return None."""
    result = detect_utf1632_patterns(b"")
    assert result is None


def test_single_byte_returns_none() -> None:
    """A single byte is well below the minimum threshold."""
    result = detect_utf1632_patterns(b"\x00")
    assert result is None


# ---------------------------------------------------------------------------
# Alignment trimming
# ---------------------------------------------------------------------------


def test_utf16_odd_byte_count_trimmed() -> None:
    """An odd number of bytes for UTF-16 data should be trimmed to even.

    The function trims to an even length before analysis; detection should
    still work when there is a trailing stray byte.
    """
    text = "Hello, world! Test"
    data = text.encode("UTF-16-LE")
    # Append a stray byte to make the total length odd
    data_odd = data + b"\x42"
    assert len(data_odd) % 2 == 1
    result = detect_utf1632_patterns(data_odd)
    assert result is not None
    assert result.encoding == "utf-16-le"


def test_utf32_non_aligned_byte_count() -> None:
    """UTF-32 data not aligned to 4 bytes should be trimmed.

    The function trims to a multiple of 4 before analysis; detection should
    still work when there are trailing extra bytes.
    """
    text = "Hello, world! Test"
    data = text.encode("UTF-32-LE")
    # Append 1-3 stray bytes to break alignment
    data_unaligned = data + b"\x42\x43"
    assert len(data_unaligned) % 4 != 0
    result = detect_utf1632_patterns(data_unaligned)
    assert result is not None
    assert result.encoding == "utf-32-le"


def test_utf32_trimming_below_minimum_returns_none() -> None:
    """If trimming UTF-32 data to a multiple of 4 drops below the minimum.

    UTF-32 detection should not trigger.
    """
    # 15 bytes: trimmed to 12, which is below _MIN_BYTES_UTF32 (16)
    text = "Tes"
    data = text.encode("UTF-32-LE")  # 12 bytes
    data_padded = data + b"\x00\x00\x00"  # 15 bytes, trims to 12
    assert len(data_padded) == 15
    result = detect_utf1632_patterns(data_padded)
    # Should not detect as UTF-32 since trimmed length < 16
    if result is not None:
        assert result.encoding != "utf-32-le"


# ---------------------------------------------------------------------------
# CJK text in UTF-16 (non-ASCII Unicode)
# ---------------------------------------------------------------------------


def test_utf16_le_cjk_text() -> None:
    """Chinese text in UTF-16-LE should be detected.

    CJK characters have non-zero high bytes but the null-byte fraction
    threshold (_UTF16_MIN_NULL_FRACTION = 0.03) accommodates this.
    """
    # Mix of CJK and some ASCII punctuation/spaces to ensure some nulls
    text = "This document contains Chinese: \u4f60\u597d\u4e16\u754c\uff0c\u6b22\u8fce\u6765\u5230\u8fd9\u91cc\u3002"
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


def test_utf16_be_cjk_text() -> None:
    """Chinese text in UTF-16-BE should be detected."""
    text = "This document contains Chinese: \u4f60\u597d\u4e16\u754c\uff0c\u6b22\u8fce\u6765\u5230\u8fd9\u91cc\u3002"
    data = text.encode("UTF-16-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"


def test_utf16_le_japanese_text() -> None:
    """Japanese text in UTF-16-LE should be detected."""
    text = "This is Japanese text: \u3053\u3093\u306b\u3061\u306f\u4e16\u754c\u3002\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8\u3067\u3059\u3002"
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


def test_utf16_le_korean_text() -> None:
    """Korean text in UTF-16-LE should be detected."""
    text = "This is Korean text: \uc548\ub155\ud558\uc138\uc694 \uc138\uacc4\uc5d0 \uc624\uc2e0 \uac83\uc744 \ud658\uc601\ud569\ub2c8\ub2e4."
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


# ---------------------------------------------------------------------------
# Mixed ASCII and non-ASCII in UTF-16
# ---------------------------------------------------------------------------


def test_utf16_le_mixed_scripts() -> None:
    """UTF-16-LE text mixing Latin, CJK, and accented characters."""
    text = (
        "Hello World. \u00c0 bient\u00f4t! "
        "\u4f60\u597d\u4e16\u754c. "
        "More English text follows here to pad the sample."
    )
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


def test_utf16_be_mixed_scripts() -> None:
    """UTF-16-BE text mixing Latin, CJK, and accented characters."""
    text = (
        "Hello World. \u00c0 bient\u00f4t! "
        "\u4f60\u597d\u4e16\u754c. "
        "More English text follows here to pad the sample."
    )
    data = text.encode("UTF-16-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"


def test_utf16_le_mostly_ascii_with_some_non_ascii() -> None:
    """Predominantly ASCII with occasional non-ASCII in UTF-16-LE."""
    text = "This is mostly ASCII text with a few accented chars: r\u00e9sum\u00e9, na\u00efve, caf\u00e9."
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


# ---------------------------------------------------------------------------
# Return type is DetectionResult
# ---------------------------------------------------------------------------


def test_result_is_detection_result_instance() -> None:
    """Successful detection should return a proper DetectionResult."""
    text = "Hello, this is a test of the return type."
    data = text.encode("UTF-16-LE")
    result = detect_utf1632_patterns(data)
    assert isinstance(result, DetectionResult)
    assert result == DetectionResult(
        encoding="utf-16-le",
        confidence=DETERMINISTIC_CONFIDENCE,
        language=None,
    )


# ---------------------------------------------------------------------------
# UTF-32 with non-ASCII Unicode
# ---------------------------------------------------------------------------


def test_utf32_le_non_ascii_text() -> None:
    """UTF-32-LE with non-ASCII BMP characters should be detected.

    BMP characters in UTF-32 have the top two bytes as zero, so the
    null-byte pattern is still very strong.
    """
    text = "Caf\u00e9 cr\u00e8me \u00e0 la fran\u00e7aise avec des r\u00e9sum\u00e9s."
    data = text.encode("UTF-32-LE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-le"


def test_utf32_be_non_ascii_text() -> None:
    """UTF-32-BE with non-ASCII BMP characters should be detected."""
    text = "Caf\u00e9 cr\u00e8me \u00e0 la fran\u00e7aise avec des r\u00e9sum\u00e9s."
    data = text.encode("UTF-32-BE")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-32-be"


# ---------------------------------------------------------------------------
# Edge case: data with many null bytes but not valid text
# ---------------------------------------------------------------------------


def test_all_null_bytes_returns_none() -> None:
    """A buffer of all null bytes should not be detected as valid text.

    While the null-byte pattern might match, the decoded text (all U+0000
    control characters) fails the _looks_like_text check.
    """
    data = b"\x00" * 64
    result = detect_utf1632_patterns(data)
    assert result is None


def test_utf32_be_decode_error() -> None:
    """UTF-32-BE pattern check passes but decode fails on invalid code point."""
    # Mix valid BMP (U+0041='A') with invalid U+110000 so pattern check passes
    # but utf-32-be decode raises UnicodeDecodeError.
    valid = b"\x00\x00\x00\x41"  # U+0041 BE
    invalid = b"\x00\x11\x00\x00"  # U+110000 BE (above max)
    data = valid * 6 + invalid * 2
    result = detect_utf1632_patterns(data)
    # BE decode fails, LE pattern doesn't match → None
    assert result is None


def test_utf32_le_decode_error() -> None:
    """UTF-32-LE pattern check passes but decode fails on invalid code point."""
    valid = b"\x41\x00\x00\x00"  # U+0041 LE
    invalid = b"\x00\x00\x11\x00"  # U+110000 LE (above max)
    data = valid * 6 + invalid * 2
    result = detect_utf1632_patterns(data)
    # LE decode fails, BE pattern doesn't match → None
    assert result is None


def test_utf16_single_candidate_decode_error() -> None:
    """UTF-16-LE single candidate with unpaired surrogate triggers decode error."""
    # Build data with nulls only in odd positions (LE pattern) but an
    # unpaired high surrogate that causes UnicodeDecodeError on decode.
    good = b"H\x00e\x00l\x00l\x00o\x00"  # UTF-16-LE "Hello"
    bad = b"\x01\xd8"  # high surrogate D801 — even byte is non-null
    more = b" \x00w\x00o\x00r\x00l\x00d\x00"  # UTF-16-LE " world"
    data = good + bad + more
    # Only LE has enough nulls (single candidate), decode raises, returns None
    result = detect_utf1632_patterns(data)
    assert result is None


def test_utf16_both_candidates_low_quality() -> None:
    """Both UTF-16 endiannesses decode but produce garbage."""
    data = b"\x01\x00\x00\x01" * 20
    result = detect_utf1632_patterns(data)
    assert result is None


def test_looks_like_text_empty_string() -> None:
    """_looks_like_text with empty string should return False."""
    from chardet.pipeline.utf1632 import _looks_like_text

    assert _looks_like_text("") is False


def test_text_quality_rejects_many_combining_marks() -> None:
    """Text with >20% combining marks should get quality -1.0."""
    from chardet.pipeline.utf1632 import _text_quality

    # U+0300 (combining grave accent) is category Mn (Mark, nonspacing)
    text = "a\u0300" * 20  # 50% marks
    quality = _text_quality(text)
    assert quality == -1.0


# ---------------------------------------------------------------------------
# UTF-16 tie-breaking: both LE and BE candidates
# ---------------------------------------------------------------------------


def test_utf16_both_candidates_tiebreak() -> None:
    """When both LE and BE show null patterns, tie-breaking picks the correct one.

    To trigger the tie-breaking path, BOTH endiannesses need >= 3% null
    bytes in their respective positions.  Mixing ASCII chars (null in odd
    positions as LE) with U+0100-range chars (null in even positions as LE)
    puts nulls in both even AND odd byte positions.
    """
    # 'A' (U+0041) in LE = 0x41 0x00: even=non-null, odd=null
    # 'Ā' (U+0100) in LE = 0x00 0x01: even=null, odd=non-null
    # Mixing them produces nulls at >= 3% in both positions.
    text = "A\u0100" * 30
    data = text.encode("utf-16-le")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding in ("utf-16-le", "utf-16-be")
    assert result.confidence == DETERMINISTIC_CONFIDENCE


def test_utf16_tiebreak_one_side_decode_error() -> None:
    """When both candidates match but one raises UnicodeDecodeError, the other wins.

    We craft data with nulls in both even and odd positions (triggering both
    candidates) but include bytes that form an unpaired surrogate in BE,
    causing BE decode to fail while LE succeeds.
    """
    # Base: alternating A (0x41,0x00) and Ā (0x00,0x01) in LE → nulls in both positions
    base = b"\x41\x00\x00\x01" * 20
    # 0xD8,0x41 in BE = U+D841 (unpaired high surrogate → decode error)
    # 0xD8,0x41 in LE = U+41D8 (valid CJK character)
    surrogate_trap = b"\xd8\x41\x00\x01"
    data = base + surrogate_trap
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"


# ---------------------------------------------------------------------------
# Direct _text_quality tests
# ---------------------------------------------------------------------------


def test_text_quality_with_spaces() -> None:
    """_text_quality should give a bonus for whitespace in text > 20 chars."""
    from chardet.pipeline.utf1632 import _text_quality

    # Text with spaces and letters, long enough (> 20 chars) to trigger space bonus
    text = "Hello World this is a test of text quality scoring"
    quality = _text_quality(text)
    # Should have letter ratio + ascii bonus + space bonus (0.1)
    assert quality > 0.5


def test_text_quality_ascii_letters() -> None:
    """_text_quality with all ASCII letters gives high score."""
    from chardet.pipeline.utf1632 import _text_quality

    text = "abcdefghijklmnopqrstuvwxyz"
    quality = _text_quality(text)
    # letters/n = 1.0, ascii_letters/n * 0.5 = 0.5, no space bonus (n > 20 but no spaces)
    assert quality >= 1.4


def test_text_quality_rejects_many_controls() -> None:
    """_text_quality should return -1.0 for text with >10% control chars."""
    from chardet.pipeline.utf1632 import _text_quality

    # More than 10% control characters
    text = "ab\x01\x02\x03\x04\x05\x06\x07\x08"
    quality = _text_quality(text)
    assert quality == -1.0


def test_text_quality_no_letters() -> None:
    """_text_quality with digits and punctuation but no letters gives low score."""
    from chardet.pipeline.utf1632 import _text_quality

    text = "12345!@#$%67890^&*()"
    quality = _text_quality(text)
    # No letters, so letter ratio is 0, ascii bonus is 0
    assert quality < 0.5


# ---------------------------------------------------------------------------
# Null-separator guard: sparse nulls in ASCII should NOT trigger UTF-16
# ---------------------------------------------------------------------------


def test_null_separated_ascii_not_utf16() -> None:
    """ASCII with null byte separators should not be detected as UTF-16.

    Regression test for chardet/chardet#346.
    """
    data = (
        b"master:README.md\x002\x00For support slack to #kodiak-support\n"
        b"master:support.txt\x001\x00For support slack to #kodiak-support\n"
    )
    result = detect_utf1632_patterns(data)
    assert result is None


def test_null_separated_paths_not_utf16() -> None:
    """Find -print0 style output should not be detected as UTF-16."""
    data = (
        b"/home/user/documents/report.txt\x00"
        b"/home/user/documents/notes.txt\x00"
        b"/home/user/downloads/image.png\x00"
        b"/home/user/music/song.mp3\x00"
    )
    result = detect_utf1632_patterns(data)
    assert result is None


def test_real_utf16_be_still_detected() -> None:
    """Real UTF-16-BE text must still be detected after the guard is added."""
    text = "The quick brown fox jumps over the lazy dog."
    data = text.encode("utf-16-be")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-be"
    assert result.confidence == DETERMINISTIC_CONFIDENCE


def test_real_utf16_le_cjk_still_detected() -> None:
    """CJK UTF-16-LE must still be detected (low null fraction but non-ASCII non-null bytes)."""
    text = "This document: \u4f60\u597d\u4e16\u754c\uff0c\u6b22\u8fce\u6765\u5230\u8fd9\u91cc\u3002"
    data = text.encode("utf-16-le")
    result = detect_utf1632_patterns(data)
    assert result is not None
    assert result.encoding == "utf-16-le"

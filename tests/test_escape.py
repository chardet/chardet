# tests/test_escape.py
"""Tests for escape-sequence-based encoding detection."""

from __future__ import annotations

from chardet import detect
from chardet.pipeline.escape import _is_valid_utf7_b64, detect_escape_encoding


def test_iso_2022_jp_esc_dollar_b() -> None:
    data = b"Hello \x1b$B$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-JP-2"
    assert result.confidence == 0.95


def test_iso_2022_jp_esc_dollar_at() -> None:
    data = b"Hello \x1b$@$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-JP-2"


def test_iso_2022_kr() -> None:
    data = b"\x1b$)C\x0e\x21\x21\x0f"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-KR"
    assert result.confidence == 0.95


def test_hz_gb_2312() -> None:
    data = b"Hello ~{CEDE~} World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "HZ-GB-2312"
    assert result.confidence == 0.95


def test_hz_gb_2312_needs_both_markers() -> None:
    # Only shift-in without shift-out should not match
    data = b"Hello ~{CEDE World"
    result = detect_escape_encoding(data)
    assert result is None


def test_hz_gb_2312_rejects_english_with_tildes() -> None:
    # English text containing ~{ and ~} must NOT be detected as HZ-GB-2312
    data = b"The formula ~{x + y~} is simple."
    result = detect_escape_encoding(data)
    assert result is None


def test_hz_gb_2312_rejects_odd_length_region() -> None:
    # Odd-length region between markers is not valid GB2312 pairs
    data = b"~{ABC~}"
    result = detect_escape_encoding(data)
    assert result is None


def test_hz_gb_2312_rejects_empty_region() -> None:
    data = b"~{~}"
    result = detect_escape_encoding(data)
    assert result is None


def test_hz_gb_2312_rejects_bytes_outside_range() -> None:
    # Bytes outside 0x21-0x7E (e.g., space 0x20) are not valid GB2312
    data = b"~{ a ~}"
    result = detect_escape_encoding(data)
    assert result is None


def test_plain_ascii_returns_none() -> None:
    data = b"Hello World"
    result = detect_escape_encoding(data)
    assert result is None


def test_random_bytes_returns_none() -> None:
    data = bytes(range(256))
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_basic() -> None:
    # "Hello, 世界" encoded as UTF-7
    data = "Hello, 世界".encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "UTF-7"
    assert result.confidence == 0.95


def test_utf7_shifted_sequence() -> None:
    # UTF-7 with explicit +<Base64>- regions
    data = b"Hello +AGkAbgB0AGUAbgBzAGU-"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "UTF-7"


def test_utf7_literal_plus() -> None:
    # +- is the UTF-7 escape for literal '+', not a shifted sequence
    data = b"2+- 2 = 4"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_plain_ascii_with_plus() -> None:
    # A stray + in ASCII text should not trigger UTF-7 detection
    data = b"C++ is a programming language"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_empty_shift() -> None:
    # +- followed by nothing is just a literal plus, not UTF-7
    data = b"price: 10+- tax"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_url_with_plus() -> None:
    data = b"https://www.google.com/search?q=hello+ABC-DEF"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_short_base64_in_text() -> None:
    data = b"x+ABC-y"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_mime_boundary() -> None:
    data = b"--boundary+ABCdef123-end"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_cpp_version() -> None:
    """C++20, C++11, etc. should not trigger UTF-7 (Guard A)."""
    data = b"#include <ranges>  // C++20 feature\nint main() { return 0; }\n"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_pem_base64() -> None:
    """PEM certificate base64 blobs should not trigger UTF-7 (Guard B)."""
    data = (
        b"-----BEGIN CERTIFICATE-----\n"
        b"MIICpDCCAYwCCQDU+pQ4pHgSpDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls\n"
        b"b2NhbGhvc3QwHhcNMjMwNTI5MTI0ODQ3WhcNMjQwNTI4MTI0ODQ3WjAUMRIwEAYD\n"
        b"VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC+\n"
        b"7e1RRz+BI/kHMBbOz+FN5bEwMmJ2KKQGXN+yTDaj8bKRMqgJ7MJifi3eFmFnqYg\n"
        b"-----END CERTIFICATE-----\n"
    )
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_multi_paragraph_document() -> None:
    """A longer UTF-7 document with multiple shifted sequences must still be detected."""
    parts = [
        "From: sender@example.com\r\n",
        "Subject: Meeting notes\r\n",
        "\r\n",
        "Meeting at 3pm.\r\n",
        "Topic: 日本語テスト.\r\n",
        "Attendees: Müller, René, 田中.\r\n",
        "\r\n",
        "Please review the 資料 before Thursday.\r\n",
        "Best regards,\r\n",
        "André\r\n",
    ]
    data = "".join(parts).encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "UTF-7"


def test_utf7_mixed_ascii_and_shifted() -> None:
    """UTF-7 with interspersed ASCII and shifted blocks must be detected."""
    # Multiple short non-ASCII words spread across ASCII text
    text = "Price: 100€, shipping to München, estimated 3-5 days. Sincerely, José."
    data = text.encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "UTF-7"


def test_utf7_consecutive_shifted_sequences() -> None:
    """Back-to-back shifted sequences (common in CJK text) must be detected."""
    text = "これはテストです"  # All non-ASCII
    data = text.encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "UTF-7"


def test_iso2022_jp_base_returns_jp2() -> None:
    """Base ISO-2022-JP escape codes should default to iso2022-jp-2 (broadest)."""
    data = b"Hello \x1b$B$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-JP-2"


def test_iso2022_jp_2004_codes() -> None:
    """JIS X 0213 escape codes should return iso2022-jp-2004."""
    # ESC $ ( O designates JIS X 0213 plane 1
    data = b"\x1b$B$3$s\x1b(B\x1b$(O\x21\x21\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-JP-2004"


def test_iso2022_jp_ext_codes() -> None:
    """Half-width katakana SI/SO should return iso2022-jp-ext."""
    # ESC $ B for JIS X 0208, then SI (0x0E) / SO (0x0F) for half-width katakana
    data = b"\x1b$B$3$s\x1b(B\x0e\xb1\xb2\x0f"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "ISO-2022-JP-EXT"


def test_hz_close_marker_before_open_marker() -> None:
    """When ~} appears before ~{ but a valid region follows, HZ is still detected."""
    data = b"prefix ~} text ~{CEDE~}"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "HZ-GB-2312"


def test_hz_only_close_before_open() -> None:
    """Data where ~} only appears before ~{ — no valid HZ region."""
    data = b"~} some text ~{ invalid"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_short_base64_rejected() -> None:
    """UTF-7 shifted sequence with fewer than 3 base64 chars is rejected."""
    data = b"text +AB- more text"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_b64_rejects_lone_low_surrogate() -> None:
    """A low surrogate (0xDC00) without a preceding high surrogate is invalid."""
    # 0xDC00 in UTF-16BE = DC 00, base64 = "3AA"
    assert not _is_valid_utf7_b64(b"3AA")


def test_utf7_b64_rejects_consecutive_high_surrogates() -> None:
    """Two back-to-back high surrogates are invalid UTF-16BE."""
    # 0xD800 0xD801 encoded as UTF-7 base64
    assert not _is_valid_utf7_b64(b"2ADYAQ")


def test_utf7_b64_rejects_high_surrogate_without_low() -> None:
    """A high surrogate followed by a non-surrogate is invalid UTF-16BE."""
    # 0xD800 0x4F60 encoded as UTF-7 base64
    assert not _is_valid_utf7_b64(b"2ABPYA")


def test_utf7_b64_rejects_trailing_high_surrogate() -> None:
    """A high surrogate at the end of the sequence with no low surrogate."""
    # 0xD800 alone encoded as UTF-7 base64
    assert not _is_valid_utf7_b64(b"2AA")


def test_utf7_b64_accepts_valid_surrogate_pair() -> None:
    """A valid surrogate pair (U+10000 = 0xD800 0xDC00) must be accepted."""
    # 0xD800 0xDC00 encoded as UTF-7 base64
    assert _is_valid_utf7_b64(b"2ADcAA")


def test_utf7_rejects_increment_operator() -> None:
    """++row in C code must not trigger UTF-7 detection (regression #332).

    The ``++`` prefix causes Guard A to skip the first ``+``, but the second
    ``+`` starts a new candidate sequence with ``row`` as Base64.  ``row``
    (3 chars) decodes to the valid code point U+AE8C, which previously
    caused a false positive.
    """
    data = b"int f() {\n  int row = 0;\n  ++row;\n}"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_triple_plus_variable() -> None:
    """+++i should not trigger UTF-7 — all consecutive pluses must be skipped."""
    data = b"for (int i = 0; i < n; +++i) {}"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_double_plus_at_end() -> None:
    """++ at end of data should not cause issues (Guard A boundary)."""
    data = b"I love C++"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_all_lowercase_base64() -> None:
    """All-lowercase base64 blocks like +foo are variable names, not UTF-7.

    UTF-7 encodes UTF-16BE, so real base64 blocks almost always contain
    uppercase letters or digits.
    """
    data = b"hello +foo world"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_sha1_git_hash() -> None:
    """SHA-1 git hash after '+' must not be detected as UTF-7 (regression #323).

    pip-tools and similar tools emit requirements lines where a VCS pin
    starts with '+', followed by a 40-character lowercase hex SHA-1 digest.
    These look superficially like a UTF-7 shifted sequence because every hex
    character is in the Base64 alphabet and 40 chars x 6 bits = 240 bits,
    which is a multiple of 16 (no padding bits to reject).  However, the
    decoded UTF-16BE contains a lone low surrogate (0xDDC6), which is invalid
    UTF-16 and proves the sequence is not real UTF-7.
    """
    data = b"+4bafdea31b1a83b6eff5dac6cedcff073cb984f6"
    result = detect_escape_encoding(data)
    assert result is None


def test_utf7_rejects_hex_hash_in_requirements_file() -> None:
    """A pure-ASCII requirements file with git VCS pins must not be UTF-7.

    Two formats are tested:
    - ``+sha1hash`` at the start of a line (the format that triggered #323)
    - ``git+https://...@sha1hash`` (common pip/uv format, also must not regress)
    """
    data = (
        b"requests==2.31.0\n"
        b"numpy==1.24.0\n"
        # Line-leading '+hash' — this is the format that triggered the bug
        b"+4bafdea31b1a83b6eff5dac6cedcff073cb984f6\n"
        # Full VCS URL form — the '+' in 'git+https' is terminated early by ':'
        b"mypackage @ git+https://github.com/org/repo@"
        b"4bafdea31b1a83b6eff5dac6cedcff073cb984f6\n"
    )
    result = detect(data)
    assert result["encoding"] != "UTF-7"

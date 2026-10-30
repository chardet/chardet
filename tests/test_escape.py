# tests/test_escape.py
"""Tests for escape-sequence-based encoding detection."""

from __future__ import annotations

import time

import pytest

from chardet import detect
from chardet._utils import _DECODE_CHUNK_SIZE
from chardet.pipeline.escape import (
    _has_valid_hz_regions,
    _has_valid_utf7_sequences,
    _is_embedded_in_base64,
    _is_valid_utf7_b64,
    detect_escape_encoding,
    utf7_shifts_markup,
)


def test_iso_2022_jp_esc_dollar_b() -> None:
    data = b"Hello \x1b$B$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2"
    assert result.confidence == 0.95


def test_iso_2022_jp_esc_dollar_at() -> None:
    data = b"Hello \x1b$@$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2"


def test_iso_2022_kr() -> None:
    data = b"\x1b$)C\x0e\x21\x21\x0f"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_kr"
    assert result.confidence == 0.95


def test_hz_gb_2312() -> None:
    data = b"Hello ~{CEDE~} World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "hz"
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
    assert result.encoding == "utf-7"
    assert result.confidence == 0.95


def test_utf7_shifted_sequence() -> None:
    # UTF-7 with explicit +<Base64>- regions
    data = b"Hello +AGkAbgB0AGUAbgBzAGU-"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "utf-7"


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
    assert result.encoding == "utf-7"


def test_utf7_mixed_ascii_and_shifted() -> None:
    """UTF-7 with interspersed ASCII and shifted blocks must be detected."""
    # Multiple short non-ASCII words spread across ASCII text
    text = "Price: 100€, shipping to München, estimated 3-5 days. Sincerely, José."
    data = text.encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "utf-7"


def test_utf7_consecutive_shifted_sequences() -> None:
    """Back-to-back shifted sequences (common in CJK text) must be detected."""
    text = "これはテストです"  # All non-ASCII
    data = text.encode("utf-7")
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "utf-7"


def test_iso2022_jp_base_returns_jp2() -> None:
    """Base ISO-2022-JP escape codes should default to iso2022-jp-2 (broadest)."""
    data = b"Hello \x1b$B$3$s$K$A$O\x1b(B World"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2"


def test_iso2022_jp_2004_codes() -> None:
    """JIS X 0213 escape codes should return iso2022-jp-2004."""
    # ESC $ ( Q designates JIS X 0213:2004 plane 1
    data = b"\x1b$B$3$s\x1b(B\x1b$(Q\x21\x21\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2004"


def test_iso2022_jp_2004_esc_dollar_paren_q() -> None:
    """ESC$(Q designates JIS X 0213:2000 plane 1 -> ISO-2022-JP-2004."""
    data = b"\x1b$B$3$s\x1b(B\x1b$(Q\x21\x21\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2004"


def test_iso2022_jp_ext_codes() -> None:
    """Half-width katakana SI/SO should return iso2022-jp-ext."""
    # ESC $ B for JIS X 0208, then SO (0x0E) / SI (0x0F) around 7-bit
    # half-width katakana (ISO-2022 streams are 7-bit)
    data = b"\x1b$B$3$s\x1b(B\x0e\x31\x32\x0f"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_ext"


def test_iso2022_jp_ext_esc_kana() -> None:
    """ESC(I (JIS X 0201 Kana designation) should trigger JP-EXT even without SI/SO."""
    data = b"\x1b$B$3$s\x1b(B\x1b(I\x31\x32\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_ext"


def test_iso2022_jp_ext_esc_kana_only() -> None:
    """ESC(I alone (no base sequences, no SI/SO) should detect JP-EXT."""
    data = b"\x1b(I\x31\x32\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_ext"


def test_iso2022_jp_jis_x_0212_entry() -> None:
    """ESC$(D (JIS X 0212-1990) alone should enter the JP branch -> JP-2."""
    data = b"\x1b$(D\x30\x21\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2"


def test_iso2022_jp_2004_without_base() -> None:
    """JIS X 0213 escape alone (no ESC$B/ESC$@/ESC(J) should detect JP-2004."""
    data = b"\x1b$(Q\x21\x21\x1b(B"
    result = detect_escape_encoding(data)
    assert result is not None
    assert result.encoding == "iso2022_jp_2004"


def test_hz_close_marker_before_open_marker() -> None:
    """A ~} before the first ~{ does not stop the region scan.

    The region validator still finds the GB region after the stray marker.
    The stage itself answers ``None``, since HZ cannot decode a ``~}`` in
    ASCII mode and the answer has to decode the window; with the stray
    tilde escaped as ``~~`` the same text is HZ.
    """
    data = b"prefix ~} text ~{CEDE~}"
    assert _has_valid_hz_regions(data, len(data), len(data))
    assert detect_escape_encoding(data) is None
    result = detect_escape_encoding(b"prefix ~~ text ~{CEDE~}")
    assert result is not None
    assert result.encoding == "hz"


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


def test_embedded_base64_guard_boundary() -> None:
    """The guard fires at four preceding base64 characters, not three."""
    assert not _is_embedded_in_base64(b"abc+rest", 3)
    assert _is_embedded_in_base64(b"abcd+rest", 4)
    # Newlines are skipped rather than ending the walk, so a line-wrapped
    # run still counts.
    assert _is_embedded_in_base64(b"ab\ncd\n+rest", 6)
    # A non-base64, non-newline byte ends the walk.
    assert not _is_embedded_in_base64(b"ab cd+rest", 5)


def test_utf7_validator_is_linear_in_base64_blobs() -> None:
    """Line-wrapped base64 must not drive the '+' scan quadratic.

    ``_is_embedded_in_base64`` skips newlines, so without an early exit at
    the fourth character every '+' in a PEM-shaped blob rescans everything
    before it.  At 128 KiB that cost 5.4s and grew as the square; the
    bound below is ~1000x the fixed cost and still catches a relapse.
    """
    unit = b"+abc123def456ghi789jkl012mno345pqr678stu901vwx234yz\n"
    blob = (unit * (131072 // len(unit) + 1))[:131072]
    start = time.perf_counter()
    _has_valid_utf7_sequences(blob, len(blob), len(blob))
    assert time.perf_counter() - start < 1.0


def test_utf7_b64_decode_is_linear_in_run_length() -> None:
    """A long base64 run must not make the UTF-16 decode quadratic.

    The decode loop never trimmed its bit buffer, so it grew to a
    run-length integer that every sextet shifted again.  ``+A+A...`` is one
    base64 run of the whole window; 200 KB of it cost 4.7s through
    ``detect()`` and grew as the square.

    A wall-clock budget cannot tell the two apart on every runner: the
    linear decode of 128 KB takes 20ms on a laptop and over a second on
    the free-threaded macOS job, which failed a 1s budget on half of one
    day's runs.  The ratio between two run lengths can.  Quadrupling the
    run quadruples a linear decode and multiplies the old one by about
    15, so the bound sits between them with a 2x margin for noise, and
    the best of three runs keeps a busy runner from inflating one side.
    """

    def best_of_three(run: bytes) -> float:
        best = float("inf")
        for _ in range(3):
            start = time.perf_counter()
            assert _is_valid_utf7_b64(run)
            best = min(best, time.perf_counter() - start)
        return best

    short = best_of_three(b"A+" * 8192)
    quadrupled = best_of_three(b"A+" * 32768)
    assert quadrupled / short < 8


def test_utf7_base64_run_outrunning_the_bound_is_skipped() -> None:
    """A base64 run that reaches max_end while more follows is not judged.

    The run cannot be validated whole, so it must be skipped rather than
    judged on a truncated prefix (ADR-0006).
    """
    data = b"+" + b"AAAA" * 10
    assert _has_valid_utf7_sequences(data, max_start=10, max_end=5) is False


# ---------------------------------------------------------------------------
# Whole-window gate: a designation is evidence, the decode is the answer
# ---------------------------------------------------------------------------


def test_designation_inside_plain_text_is_not_iso2022() -> None:
    """Three bytes of a JIS designation in a log line are not ISO-2022-JP."""
    data = b"log: \x1b$B is the escape\n" + b"plain text " * 50
    assert detect_escape_encoding(data) is None
    assert detect(data)["encoding"] != "ISO-2022-JP"


def test_iso2022_jp_with_bad_byte_past_header_falls_through() -> None:
    data = "こんにちは世界".encode("iso-2022-jp") + b" plain " * 50 + b"\x80"
    assert detect_escape_encoding(data) is None
    result = detect(data)
    if result["encoding"] is not None:
        data.decode(result["encoding"])  # whatever answers must decode


def test_iso2022_kr_with_bad_byte_falls_through() -> None:
    data = b"\x1b$)C" + b"plain " * 50 + b"\x0e\x7f\x7f\x0f"
    assert detect_escape_encoding(data) is None


def test_jis_x0213_2000_designation_falls_through() -> None:
    """Python's iso2022_jp_2004 codec cannot read ESC $ ( O, so neither can the caller."""
    data = b"\x1b$(O\x21\x21\x1b(B"
    assert detect_escape_encoding(data) is None


def test_hz_with_stray_tilde_falls_through() -> None:
    data = "你好世界".encode("hz") + b" ok " * 30 + b" a~b end"
    assert detect_escape_encoding(data) is None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # Markup written directly decodes to itself: nothing is added.
        (b"<p>a + b = c</p>", False),
        ("<p>Héllo, 世界</p>".encode("utf-7"), False),
        # A shifted run that decodes to a non-markup ASCII letter.
        (b"<p>+AEE-</p>", False),
        # Each markup character smuggled through a shifted run.
        (b"+ADw-script+AD4-", True),
        (b"+ACY-amp;", True),
        (b"+ACI-quoted+ACI-", True),
        (b"+ACc-quoted+ACc-", True),
        # The window ends inside the run, with and without a whole character.
        (b"<p>+ADwAcwBjAHIAaQBwAHQAPg", True),
        (b"<p>+ADwAcwBj", True),
        # Too few bits for any character: replaced, and nothing to count.
        (b"<p>+AD", False),
    ],
)
def test_utf7_shifts_markup(data: bytes, *, expected: bool) -> None:
    assert utf7_shifts_markup(data) is expected


def test_utf7_shifts_markup_across_chunk_edge() -> None:
    """A run straddling the decode chunk boundary is read as one run."""
    data = b"a" * (_DECODE_CHUNK_SIZE - 3) + b"+ADw-"
    assert data.decode("utf-7").endswith("a<")
    assert utf7_shifts_markup(data) is True
    data = b"a" * (_DECODE_CHUNK_SIZE + 3) + b"+ADw"
    assert utf7_shifts_markup(data) is True

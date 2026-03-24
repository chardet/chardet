"""Tests for test-data exclusion set building."""

from __future__ import annotations

from pathlib import Path

from exclusions import build_exclusion_set, fingerprint_text, is_excluded


def test_fingerprint_text_basic() -> None:
    """fingerprint_text returns a hex digest string."""
    fp = fingerprint_text("Hello, world!  This is   a test.")
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex digest


def test_fingerprint_text_normalizes_whitespace() -> None:
    """Repeated whitespace is collapsed before fingerprinting."""
    fp1 = fingerprint_text("Hello   world")
    fp2 = fingerprint_text("Hello world")
    assert fp1 == fp2


def test_fingerprint_text_strips() -> None:
    """Leading/trailing whitespace is stripped."""
    fp1 = fingerprint_text("  Hello world  ")
    fp2 = fingerprint_text("Hello world")
    assert fp1 == fp2


def test_fingerprint_text_truncates_to_200_chars() -> None:
    """Only the first 200 characters matter."""
    base = "a" * 200
    fp1 = fingerprint_text(base + "EXTRA")
    fp2 = fingerprint_text(base + "DIFFERENT")
    assert fp1 == fp2


def test_fingerprint_text_different_content() -> None:
    """Different content produces different fingerprints."""
    fp1 = fingerprint_text("Hello world")
    fp2 = fingerprint_text("Goodbye world")
    assert fp1 != fp2


def test_build_exclusion_set_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty set."""
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_ignores_non_culturax(tmp_path: Path) -> None:
    """Files not matching culturax_* pattern are ignored."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    (enc_dir / "some_other_file.txt").write_text("Hello world", encoding="utf-8")
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_decodes_and_fingerprints(tmp_path: Path) -> None:
    """CulturaX files are decoded from their encoding and fingerprinted."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    text = "Hello world, this is a test article with enough content."
    (enc_dir / "culturax_00000.txt").write_bytes(text.encode("utf-8"))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1

    expected_fp = fingerprint_text(text)
    assert expected_fp in result


def test_build_exclusion_set_deduplicates_across_encodings(tmp_path: Path) -> None:
    """Same source text in different encodings produces one fingerprint."""
    text = "Héllo wörld, this is a tëst article with enough content."

    for enc in ("utf-8", "iso-8859-1", "windows-1252"):
        enc_dir = tmp_path / f"{enc}-fr"
        enc_dir.mkdir()
        (enc_dir / "culturax_00000.txt").write_bytes(text.encode(enc))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1


def test_build_exclusion_set_skips_none_dir(tmp_path: Path) -> None:
    """The None-None binary test directory is skipped."""
    none_dir = tmp_path / "None-None"
    none_dir.mkdir()
    (none_dir / "culturax_00000.txt").write_bytes(b"\x00\x01\x02")
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_build_exclusion_set_handles_decode_errors(tmp_path: Path) -> None:
    """Files that can't be decoded are skipped gracefully."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    (enc_dir / "culturax_00000.txt").write_bytes(b"\xff\xfe\xfd\xfc" * 50)
    result = build_exclusion_set(tmp_path)
    assert result == frozenset()


def test_is_excluded_by_fingerprint() -> None:
    """Articles matching a fingerprint are excluded."""
    text = "This is a test article with unique content for exclusion."
    fp = fingerprint_text(text)
    exclusions = frozenset([fp])
    assert is_excluded(text, exclusions, source="culturax", stream_index=999)


def test_is_excluded_not_matching() -> None:
    """Articles not matching any fingerprint are not excluded."""
    exclusions = frozenset(["abc123"])
    assert not is_excluded(
        "Completely different text", exclusions, source="culturax", stream_index=999
    )


def test_is_excluded_culturax_fast_path() -> None:
    """CulturaX articles at indices 0-19 are excluded when exclusions are active."""
    # Need a non-empty exclusion set to activate filtering
    exclusions = frozenset(["dummy_fingerprint"])
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=0)
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=19)
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=20)


def test_is_excluded_fast_path_only_for_culturax() -> None:
    """Index-based fast path does not apply to non-CulturaX sources."""
    exclusions = frozenset(["dummy_fingerprint"])
    assert not is_excluded("Any text", exclusions, source="madlad400", stream_index=0)
    assert not is_excluded("Any text", exclusions, source="wikipedia", stream_index=0)


def test_is_excluded_empty_exclusions_disables_all_filtering() -> None:
    """Empty exclusion set disables all filtering, including the fast path.

    This ensures --no-skip-test-overlap fully disables exclusion filtering.
    """
    exclusions: frozenset[str] = frozenset()
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=0)
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=19)
    assert not is_excluded("Any text", exclusions, source="madlad400", stream_index=0)

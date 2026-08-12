"""Tests for test-data exclusion set building."""

from __future__ import annotations

from pathlib import Path

from exclusions import (
    ExclusionIndex,
    _weight,
    build_exclusion_set,
    content_hash,
    fingerprint_text,
    is_excluded,
)


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
    """Empty directory returns an empty index."""
    result = build_exclusion_set(tmp_path)
    assert not result


def test_build_exclusion_set_fingerprints_all_files(tmp_path: Path) -> None:
    """Every test file is fingerprinted, not just culturax_* (ADR-0004)."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    text = "Hello world, this is a wild test article with enough content."
    (enc_dir / "artpack_some_file.txt").write_text(text, encoding="utf-8")
    result = build_exclusion_set(tmp_path)
    assert result.overlaps(text)


def test_build_exclusion_set_decodes_and_fingerprints(tmp_path: Path) -> None:
    """CulturaX files are decoded from their encoding and fingerprinted."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    text = "Hello world, this is a test article with enough content."
    (enc_dir / "culturax_00000.txt").write_bytes(text.encode("utf-8"))

    result = build_exclusion_set(tmp_path)
    assert result.overlaps(text)


def test_build_exclusion_set_deduplicates_across_encodings(tmp_path: Path) -> None:
    """Same source text in different encodings indexes to the same units."""
    text = "Héllo wörld, this is a tëst article with enough content."

    for enc in ("utf-8", "iso-8859-1", "windows-1252"):
        enc_dir = tmp_path / f"{enc}-fr"
        enc_dir.mkdir()
        (enc_dir / "culturax_00000.txt").write_bytes(text.encode(enc))

    result = build_exclusion_set(tmp_path)
    assert len(result) == 1
    assert result.overlaps(text)


def test_build_exclusion_set_skips_none_dir(tmp_path: Path) -> None:
    """The None-None binary test directory is skipped."""
    none_dir = tmp_path / "None-None"
    none_dir.mkdir()
    (none_dir / "culturax_00000.txt").write_bytes(b"\x00\x01\x02")
    result = build_exclusion_set(tmp_path)
    assert not result


def test_build_exclusion_set_handles_decode_errors(tmp_path: Path) -> None:
    """Files that can't be decoded are skipped gracefully."""
    enc_dir = tmp_path / "utf-8-en"
    enc_dir.mkdir()
    (enc_dir / "culturax_00000.txt").write_bytes(b"\xff\xfe\xfd\xfc" * 50)
    result = build_exclusion_set(tmp_path)
    assert not result


def test_is_excluded_by_fingerprint() -> None:
    """Articles matching a fingerprint are excluded."""
    text = "This is a test article with unique content for exclusion, long\n"
    "enough that it carries a sentence worth indexing on its own."
    exclusions = ExclusionIndex()
    exclusions.add(text)
    assert is_excluded(text, exclusions, source="culturax", stream_index=999)


def test_is_excluded_not_matching() -> None:
    """Articles not matching any fingerprint are not excluded."""
    exclusions = ExclusionIndex()
    exclusions.add("Some indexed test article with its own distinct sentence here.")
    assert not is_excluded(
        "Completely different text", exclusions, source="culturax", stream_index=999
    )


def test_is_excluded_culturax_fast_path() -> None:
    """CulturaX articles at indices 0-19 are excluded when exclusions are active."""
    # Need a non-empty exclusion set to activate filtering
    exclusions = ExclusionIndex()
    exclusions.add("A test article that makes the exclusion index non-empty here.")
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=0)
    assert is_excluded("Any text", exclusions, source="culturax", stream_index=19)
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=20)


def test_is_excluded_fast_path_only_for_culturax() -> None:
    """Index-based fast path does not apply to non-CulturaX sources."""
    exclusions = ExclusionIndex()
    exclusions.add("A test article that makes the exclusion index non-empty here.")
    assert not is_excluded("Any text", exclusions, source="madlad400", stream_index=0)
    assert not is_excluded("Any text", exclusions, source="wikipedia", stream_index=0)


def test_is_excluded_empty_exclusions_disables_all_filtering() -> None:
    """Empty exclusion set disables all filtering, including the fast path.

    This ensures --no-skip-test-overlap fully disables exclusion filtering.
    """
    exclusions = ExclusionIndex()
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=0)
    assert not is_excluded("Any text", exclusions, source="culturax", stream_index=19)
    assert not is_excluded("Any text", exclusions, source="madlad400", stream_index=0)


# ---------------------------------------------------------------------------
# Overlap detection.  Each case below is a bug this rule actually had.
# ---------------------------------------------------------------------------


def _indexed(*texts: str) -> ExclusionIndex:
    index = ExclusionIndex()
    for text in texts:
        index.add(text)
    return index


def _document(tag: str, count: int = 12) -> str:
    """Build a document of distinct, index-worthy sentences."""
    return " ".join(
        f"Sentence {i} of the {tag} document describes something specific "
        f"and runs long enough to be worth indexing on its own merits."
        for i in range(count)
    )


def test_overlap_survives_a_different_opening() -> None:
    """A copy whose first characters differ is still detected.

    The prefix-only fingerprint missed exactly this: a corpus article and
    its test-file copy diverged in their opening chrome while 90% of the
    body matched.
    """
    article = _document("shared")
    index = _indexed(article)
    assert index.overlaps("Totally different navigation chrome here. " + article)


def test_overlap_detects_a_test_file_inside_a_longer_article() -> None:
    """Coverage counts the test file's side, not only the candidate's.

    A long article that reproduces a whole test file used to score a low
    fraction *of itself* and escape.
    """
    index = _indexed(_document("small", count=6))
    padded = _document("small", count=6) + " " + _document("filler", count=40)
    assert index.overlaps(padded)


def test_shared_boilerplate_is_not_overlap() -> None:
    """Sharing a header with a test file is not reproducing it."""
    boilerplate = (
        "The text is available under the Creative Commons licence; "
        "additional terms may apply to some of the material shown here. "
    )
    index = _indexed(boilerplate + _document("indexed"))
    assert not index.overlaps(boilerplate + _document("unrelated"))


def test_short_boilerplate_test_file_does_not_swallow_the_corpus() -> None:
    """A test file made only of site furniture must not match everything.

    One 215-character Breton test file consisting of a licence footer
    matched 150 unrelated articles at 100% of itself.
    """
    footer = "The text is available under a Creative Commons licence here. "
    index = _indexed(footer)
    assert not index.overlaps(footer + _document("genuine"))


def test_overlap_works_without_ascii_sentence_punctuation() -> None:
    """CJK text is split on its own terminators, not treated as one blob."""
    japanese = "".join(
        f"\u3053\u308c\u306f{i}\u756a\u76ee\u306e\u65e5\u672c\u8a9e\u306e"
        f"\u6587\u7ae0\u3067\u3059\u304c\u3001\u5341\u5206\u306a\u9577\u3055"
        f"\u3092\u6301\u3063\u3066\u3044\u307e\u3059\u3002"
        for i in range(20)
    )
    index = _indexed(japanese)
    assert index.overlaps("\u524d\u7f6e\u304d\u306e\u6587\u7ae0\u3002" + japanese)
    assert not index.overlaps(
        "".join(
            f"\u5225\u306e{i}\u756a\u76ee\u306e\u5185\u5bb9\u3067\u3042\u308a"
            f"\u3001\u5168\u304f\u7570\u306a\u308b\u6587\u7ae0\u3067\u3059\u3002"
            for i in range(20)
        )
    )


def test_transcode_substitutions_do_not_hide_a_copy() -> None:
    """A typographic apostrophe and its ASCII replacement compare equal."""
    curly = _document("quoted").replace("something", "someone\u2019s thing")
    straight = _document("quoted").replace("something", "someone's thing")
    assert _indexed(curly).overlaps(straight)


def test_digest_is_stable_and_content_dependent() -> None:
    """Provenance hashing tracks the indexed content."""
    one, two = _document("one"), _document("two")
    assert _indexed(one).digest() == _indexed(one).digest()
    assert _indexed(one).digest() != _indexed(two).digest()


def test_content_hash_ignores_formatting_only_differences() -> None:
    """Deduplication sees through whitespace and punctuation styling."""
    assert content_hash("Hello   world.\n\nMore text.") == content_hash(
        "Hello world. More text."
    )
    assert content_hash("Hello world.") != content_hash("Goodbye world.")


def test_repeated_boilerplate_earns_credit_only_once() -> None:
    """A candidate cannot accumulate coverage by repeating one shared line.

    Summing over a list rather than a set let a document that repeated a
    single shared sentence reach the threshold on that sentence alone.
    """
    shared = (
        "This one sentence is shared with the indexed test file and is "
        "long enough to be indexed on its own. "
    )
    index = _indexed(shared + _document("indexed"))
    assert not index.overlaps(shared * 30)


def test_coverage_is_tracked_per_test_file() -> None:
    """Matches against different test files do not pool into one score.

    Counting against the union of every test file's units let a document
    reach the threshold without reproducing any single one of them.
    """
    index = ExclusionIndex()
    for tag in ("alpha", "beta", "gamma", "delta"):
        index.add(_document(tag, count=20))
    # One sentence borrowed from each of four test files, carried inside a
    # mostly original article: no single test file is substantially
    # reproduced, and the article is mostly its own work.
    borrowed = " ".join(
        _document(tag, count=20).split(". ")[0] + "."
        for tag in ("alpha", "beta", "gamma", "delta")
    )
    assert not index.overlaps(borrowed + " " + _document("original", count=60))


def test_matched_text_must_clear_an_absolute_floor() -> None:
    """A fraction alone is not enough; the shared text must be substantial."""
    tiny = "A short shared line that is still long enough to be indexed here."
    index = _indexed(tiny)
    # Same text, so the fraction is 100% either way — only the floor can
    # keep this from counting as reproduction.
    assert _weight(tiny) < 200
    assert not index.overlaps(tiny + " " + _document("padding", count=2))


def test_text_without_sentence_structure_matches_as_a_whole() -> None:
    """ANSI art and fixed-width records have no sentences to split on."""
    art = "\n".join("|" + "=#" * 30 + "|" for _ in range(20))
    index = _indexed(art)
    assert index.overlaps(art)
    assert not index.overlaps("\n".join("+" + "-o" * 30 + "+" for _ in range(20)))


def test_empty_and_blank_text_never_overlap() -> None:
    """Empty input is not a match, and does not poison the index."""
    index = _indexed(_document("indexed"))
    assert not index.overlaps("")
    assert not index.overlaps("   \n\t  ")
    blank = ExclusionIndex()
    blank.add("")
    assert not blank
    assert not blank.overlaps("anything at all")


def test_empty_index_matches_nothing() -> None:
    """With no test data indexed, nothing is excluded."""
    assert not ExclusionIndex().overlaps(_document("anything"))


def test_identical_opening_is_enough_on_its_own() -> None:
    """The opening hash is retained as a floor under the coverage rule.

    Whatever else changes, detection stays at least as strong as the
    prefix rule this replaced.
    """
    original = _document("floor", count=30)
    index = _indexed(original)
    # Same first 200 characters, entirely different body afterwards.
    assert index.overlaps(original[:200] + " " + _document("divergent", count=30))

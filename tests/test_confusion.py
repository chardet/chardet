"""Tests for runtime confusion group resolution."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

from chardet.pipeline import DetectionResult
from chardet.pipeline.confusion import (
    load_confusion_data,
    resolve_by_bigram_rescore,
    resolve_by_category_voting,
    resolve_confusion_groups,
)

# Ukrainian text in koi8-u encoding; bytes 0xa6/0xa7 are in the koi8-r vs koi8-u
# distinguishing set (Ukrainian letters i-with-macron/yi, box-drawing in koi8-r).
_UKRAINIAN_KOI8U = (
    "Привіт, я з України. Це дуже гарно. Будь ласка.".encode("koi8-u") * 5
)

# Turkish text in iso8859-9 encoding; bytes 0xd0/0xdd/0xde/0xf0/0xfd/0xfe are in
# the iso8859-1 vs iso8859-9 distinguishing set (G-breve/I-dot/S-cedilla etc.).  Both encodings
# map those positions to same Unicode category (Lu/Ll), so category voting returns
# None while bigram scoring can still pick the correct encoding.
_TURKISH_ISO8859_9 = "Türkçe İstanbul Şeker Çiçek Ğüşıöç".encode("iso8859-9") * 5


def test_load_confusion_data():
    """Loading confusion data from the bundled file should return valid maps."""
    maps = load_confusion_data()
    assert len(maps) > 0
    found_ebcdic = any(
        ("cp1140" in key[0] and "cp500" in key[1])
        or ("cp500" in key[0] and "cp1140" in key[1])
        for key in maps
    )
    assert found_ebcdic


def test_category_voting_prefers_letter_over_symbol():
    """Category voting should prefer letter (Ll) over symbol (So)."""
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x41, 0xD5, 0x42])
    winner = resolve_by_category_voting(data, "enc_a", "enc_b", diff_bytes, categories)
    assert winner == "enc_a"


def test_category_voting_returns_none_on_no_distinguishing_bytes():
    """Category voting should return None when no distinguishing bytes are in data."""
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x41, 0x42, 0x43])
    winner = resolve_by_category_voting(data, "enc_a", "enc_b", diff_bytes, categories)
    assert winner is None


def test_bigram_rescore_returns_valid_result():
    """Bigram re-scoring should return one of the encodings or None."""
    from chardet.models import load_models  # noqa: PLC0415

    models = load_models()
    if not models:
        return
    diff_bytes = frozenset({0xD5})
    data = bytes([0x41, 0xD5, 0x42, 0xD5, 0x43])
    result = resolve_by_bigram_rescore(data, "CP850", "CP858", diff_bytes)
    assert result in ("CP850", "CP858", None)


def test_resolve_confusion_groups_no_change_when_unrelated():
    """Unrelated encodings should not be reordered by confusion resolution."""
    results = [
        DetectionResult(encoding="utf-8", confidence=0.95, language=None),
        DetectionResult(encoding="koi8-r", confidence=0.80, language="Russian"),
    ]
    resolved = resolve_confusion_groups(b"Hello world", results)
    assert resolved[0].encoding == "utf-8"


def test_resolve_confusion_groups_preserves_all_results():
    """Confusion resolution should preserve all results, only reorder."""
    results = [
        DetectionResult(encoding="cp1140", confidence=0.95, language="English"),
        DetectionResult(encoding="cp500", confidence=0.94, language="English"),
        DetectionResult(encoding="cp1252", confidence=0.50, language="English"),
    ]
    resolved = resolve_confusion_groups(bytes(range(256)), results)
    assert len(resolved) == len(results)
    resolved_encs = {r.encoding for r in resolved}
    assert resolved_encs == {"cp1140", "cp500", "cp1252"}


def test_load_confusion_data_empty_file():
    """Empty confusion.bin should emit RuntimeWarning and return empty dict."""
    import chardet.pipeline.confusion as mod  # noqa: PLC0415

    mod.load_confusion_data.cache_clear()
    try:
        mock_ref = MagicMock()
        mock_ref.read_bytes.return_value = b""
        with (
            patch.object(
                mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.warns(RuntimeWarning, match="confusion.bin is empty"),
        ):
            result = mod.load_confusion_data()
        assert result == {}
    finally:
        mod.load_confusion_data.cache_clear()


def test_load_confusion_data_corrupt_file():
    """Corrupt confusion.bin should raise ValueError."""
    import chardet.pipeline.confusion as mod  # noqa: PLC0415

    mod.load_confusion_data.cache_clear()
    try:
        mock_ref = MagicMock()
        # Valid num_pairs=1 but truncated after that
        mock_ref.read_bytes.return_value = struct.pack("!H", 1)
        with (
            patch.object(
                mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.raises(ValueError, match=r"corrupt confusion\.bin"),
        ):
            mod.load_confusion_data()
    finally:
        mod.load_confusion_data.cache_clear()


def test_resolve_confusion_groups_single_result():
    """A single result should pass through unchanged."""
    results = [DetectionResult(encoding="utf-8", confidence=0.95, language=None)]
    resolved = resolve_confusion_groups(b"Hello", results)
    assert resolved is results


def test_resolve_by_bigram_rescore_empty_freq():
    """When no bigrams contain distinguishing bytes, return None."""
    diff_bytes = frozenset({0xFE})
    data = b"Hello world, this is plain ASCII text without any high bytes at all."
    result = resolve_by_bigram_rescore(data, "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_by_bigram_rescore_short_data():
    """Data shorter than 2 bytes cannot form any bigrams."""
    diff_bytes = frozenset({0xFE})
    result = resolve_by_bigram_rescore(b"x", "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_confusion_groups_none_encoding():
    """When top result has encoding=None (binary), skip confusion resolution."""
    results = [
        DetectionResult(encoding=None, confidence=0.95, language=None),
        DetectionResult(encoding="utf-8", confidence=0.90, language=None),
    ]
    resolved = resolve_confusion_groups(b"Hello", results)
    assert resolved is results


def test_category_voting_returns_enc_b():
    """Category voting should return enc_b when enc_b has better categories."""
    diff_bytes = frozenset({0xD5})
    # enc_a maps to So (score 4), enc_b maps to Ll (score 10) → enc_b wins
    categories = {0xD5: ("So", "Ll")}
    data = bytes([0x41, 0xD5, 0x42])
    winner = resolve_by_category_voting(data, "enc_a", "enc_b", diff_bytes, categories)
    assert winner == "enc_b"


def test_bigram_rescore_returns_enc_a():
    """Bigram re-score returns enc_a when enc_a scores higher.

    Uses Ukrainian text (koi8-u encoded) where koi8-u is passed as enc_a.
    Bytes 0xa6/0xa7 (Ukrainian i-with-macron/yi) are in the koi8-r/koi8-u
    distinguishing set; the koi8-u bigram model scores them higher, so enc_a wins.
    """
    maps = load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    result = resolve_by_bigram_rescore(_UKRAINIAN_KOI8U, "koi8-u", "koi8-r", diff_bytes)
    assert result == "koi8-u"


def test_bigram_rescore_returns_enc_b():
    """Bigram re-score returns enc_b when enc_b scores higher.

    Uses the same Ukrainian / koi8-u data but passes koi8-r as enc_a and
    koi8-u as enc_b, so this time the winning encoding is the second argument.
    """
    maps = load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    result = resolve_by_bigram_rescore(_UKRAINIAN_KOI8U, "koi8-r", "koi8-u", diff_bytes)
    assert result == "koi8-u"


def test_resolve_confusion_groups_skips_none_encoding_candidate():
    """Candidates with encoding=None should be skipped during band scan."""
    results = [
        DetectionResult(encoding="cp1140", confidence=0.95, language="en"),
        DetectionResult(encoding=None, confidence=0.94, language=None),
        DetectionResult(encoding="cp500", confidence=0.93, language="en"),
    ]
    resolved = resolve_confusion_groups(bytes(range(256)), results)
    # The None candidate at position 1 should be skipped; resolution
    # should still check cp500 at position 2.
    assert len(resolved) == len(results)


def test_resolve_confusion_groups_band_limit():
    """Candidates beyond the confidence band should not be checked."""
    results = [
        DetectionResult(encoding="cp1140", confidence=0.95, language="en"),
        DetectionResult(encoding="cp500", confidence=0.94, language="en"),
        DetectionResult(encoding="cp273", confidence=0.50, language="de"),
    ]
    resolved = resolve_confusion_groups(bytes(range(256)), results)
    # cp273 at 0.50 is far outside the 0.005 band from 0.95, so it
    # should not be compared. The result should still have all 3 entries.
    assert len(resolved) == len(results)


def test_resolve_confusion_groups_swaps_top_and_second():
    """Confusion resolution swaps top and second when the second encoding wins.

    Places koi8-r (wrong) as the top result and koi8-u (correct) as second,
    then feeds Ukrainian text.  Both bigram re-scoring and category voting
    identify koi8-u as the winner, so the two results should be swapped and
    the third result should be left in place.
    """
    top = DetectionResult(encoding="koi8-r", confidence=0.95, language="Russian")
    second = DetectionResult(encoding="koi8-u", confidence=0.90, language="Ukrainian")
    third = DetectionResult(encoding="utf-8", confidence=0.50, language=None)
    results = [top, second, third]

    resolved = resolve_confusion_groups(_UKRAINIAN_KOI8U, results)

    assert resolved[0].encoding == "koi8-u"
    assert resolved[1].encoding == "koi8-r"
    assert resolved[2].encoding == "utf-8"


def test_resolve_confusion_groups_bigram_wins_over_category():
    """Bigram re-scoring takes precedence even when category voting returns None.

    Uses the iso8859-1 / iso8859-9 confusion pair with Turkish text.  The
    distinguishing bytes all map to the same Unicode category (Lu / Ll) in
    both encodings, so category voting returns None and cannot drive the
    decision.  Bigram re-scoring detects the Turkish patterns and correctly
    picks iso8859-9, demonstrating that bigram is used as the primary signal.
    """
    top = DetectionResult(encoding="iso8859-1", confidence=0.95, language="English")
    second = DetectionResult(encoding="iso8859-9", confidence=0.90, language="Turkish")
    results = [top, second]

    resolved = resolve_confusion_groups(_TURKISH_ISO8859_9, results)

    assert resolved[0].encoding == "iso8859-9"
    assert resolved[1].encoding == "iso8859-1"


def test_bigram_rescore_no_variants_for_one_encoding():
    """When one encoding has no model variants its score is 0.0 and the other wins.

    Uses the koi8-u / ascii pair.  koi8-u has a bigram model; ascii has none.
    Ukrainian text (koi8-u) produces non-zero distinguishing bigrams, so
    koi8-u (enc_a) should beat ascii (enc_b) whose score defaults to 0.0.
    """
    maps = load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    # ascii has no model in the index; koi8-u does.
    result = resolve_by_bigram_rescore(_UKRAINIAN_KOI8U, "koi8-u", "ascii", diff_bytes)
    assert result == "koi8-u"


def test_resolve_confusion_groups_no_swap_when_winner_is_top():
    """When the winner matches the top result, no swap should happen."""
    top = DetectionResult(encoding="cp1252", confidence=0.95, language="English")
    second = DetectionResult(encoding="iso8859-1", confidence=0.90, language="English")
    results = [top, second]

    with (
        patch(
            "chardet.pipeline.confusion.resolve_by_bigram_rescore",
            return_value="cp1252",
        ),
        patch(
            "chardet.pipeline.confusion.resolve_by_category_voting",
            return_value="cp1252",
        ),
    ):
        resolved = resolve_confusion_groups(b"\xd5\xd6\xd7", results)

    assert resolved[0].encoding == "cp1252"
    assert resolved[1].encoding == "iso8859-1"

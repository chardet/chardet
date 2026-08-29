"""Tests for runtime confusion group resolution."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

import chardet.pipeline.confusion as confusion_mod
from chardet.models import BigramProfile, get_enc_index
from chardet.pipeline import DetectionResult

#: mypyc resolves a compiled module's calls to functions defined in (or
#: imported into) that same module at compile time, so patching those names
#: has no effect: the patch is silently ignored and the test exercises the
#: real code path while appearing to exercise the mock.  Patching module
#: *data* attributes and attributes of uncompiled modules still works, so
#: only tests that replace an internally-called function need this.
#: Verified by audit — see the note in tests/test_orchestrator.py.
_needs_interpreted_build = pytest.mark.skipif(
    confusion_mod.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
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
    maps = confusion_mod.load_confusion_data()
    assert len(maps) > 0
    found_ebcdic = any(
        ("cp1140" in key[0] and "cp500" in key[1])
        or ("cp500" in key[0] and "cp1140" in key[1])
        for key in maps
    )
    assert found_ebcdic


def test_category_voting_prefers_letter_over_symbol():
    """Category voting should prefer letter (Ll) over symbol (So).

    Real encoding names are required (the vote builds per-encoding letter
    tables via the codec), and the distinguishing byte needs lowercase
    letter neighbors so the letter reading forms a plausible word shape.
    """
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x61, 0xD5, 0x62])
    winner = confusion_mod.resolve_by_category_voting(
        data, "latin-1", "mac-roman", diff_bytes, categories
    )
    assert winner == "latin-1"


def test_category_voting_returns_none_on_no_distinguishing_bytes():
    """Category voting should return None when no distinguishing bytes are in data."""
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "So")}
    data = bytes([0x41, 0x42, 0x43])
    winner = confusion_mod.resolve_by_category_voting(
        data, "enc_a", "enc_b", diff_bytes, categories
    )
    assert winner is None


def test_bigram_rescore_returns_valid_result():
    """Bigram re-scoring should return one of the encodings or None."""
    from chardet.models import load_models  # noqa: PLC0415

    models = load_models()
    if not models:
        return
    diff_bytes = frozenset({0xD5})
    data = bytes([0x41, 0xD5, 0x42, 0xD5, 0x43])
    result = confusion_mod.resolve_by_bigram_rescore(data, "CP850", "CP858", diff_bytes)
    assert result in ("CP850", "CP858", None)


def test_resolve_confusion_groups_no_change_when_unrelated():
    """Unrelated encodings should not be reordered by confusion resolution."""
    results = [
        DetectionResult(encoding="utf-8", confidence=0.95, language=None),
        DetectionResult(encoding="koi8-r", confidence=0.80, language="Russian"),
    ]
    resolved = confusion_mod.resolve_confusion_groups(b"Hello world", results)
    assert resolved[0].encoding == "utf-8"


def test_resolve_confusion_groups_preserves_all_results():
    """Confusion resolution should preserve all results, only reorder."""
    results = [
        DetectionResult(encoding="cp1140", confidence=0.95, language="English"),
        DetectionResult(encoding="cp500", confidence=0.94, language="English"),
        DetectionResult(encoding="cp1252", confidence=0.50, language="English"),
    ]
    resolved = confusion_mod.resolve_confusion_groups(bytes(range(256)), results)
    assert len(resolved) == len(results)
    resolved_encs = {r.encoding for r in resolved}
    assert resolved_encs == {"cp1140", "cp500", "cp1252"}


def test_load_confusion_data_empty_file():
    """Empty confusion.bin should emit RuntimeWarning and return empty dict."""
    confusion_mod.load_confusion_data.cache_clear()
    try:
        mock_ref = MagicMock()
        mock_ref.read_bytes.return_value = b""
        with (
            patch.object(
                confusion_mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.warns(RuntimeWarning, match="confusion.bin is empty"),
        ):
            result = confusion_mod.load_confusion_data()
        assert result == {}
    finally:
        confusion_mod.load_confusion_data.cache_clear()


def test_load_confusion_data_corrupt_file():
    """Corrupt confusion.bin should raise ValueError."""
    confusion_mod.load_confusion_data.cache_clear()
    try:
        mock_ref = MagicMock()
        # Valid num_pairs=1 but truncated after that
        mock_ref.read_bytes.return_value = struct.pack("!H", 1)
        with (
            patch.object(
                confusion_mod.importlib.resources,
                "files",
                return_value=MagicMock(joinpath=MagicMock(return_value=mock_ref)),
            ),
            pytest.raises(ValueError, match=r"corrupt confusion\.bin"),
        ):
            confusion_mod.load_confusion_data()
    finally:
        confusion_mod.load_confusion_data.cache_clear()


def test_resolve_confusion_groups_single_result():
    """A single result should pass through unchanged."""
    results = [DetectionResult(encoding="utf-8", confidence=0.95, language=None)]
    resolved = confusion_mod.resolve_confusion_groups(b"Hello", results)
    assert resolved is results


def test_resolve_by_bigram_rescore_empty_freq():
    """When no bigrams contain distinguishing bytes, return None."""
    diff_bytes = frozenset({0xFE})
    data = b"Hello world, this is plain ASCII text without any high bytes at all."
    result = confusion_mod.resolve_by_bigram_rescore(data, "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_by_bigram_rescore_short_data():
    """Data shorter than 2 bytes cannot form any bigrams."""
    diff_bytes = frozenset({0xFE})
    result = confusion_mod.resolve_by_bigram_rescore(b"x", "enc_a", "enc_b", diff_bytes)
    assert result is None


def test_resolve_confusion_groups_none_encoding():
    """When top result has encoding=None (binary), skip confusion resolution."""
    results = [
        DetectionResult(encoding=None, confidence=0.95, language=None),
        DetectionResult(encoding="utf-8", confidence=0.90, language=None),
    ]
    resolved = confusion_mod.resolve_confusion_groups(b"Hello", results)
    assert resolved is results


def test_category_voting_returns_enc_b():
    """Category voting should return enc_b when enc_b has better categories."""
    diff_bytes = frozenset({0xD5})
    # enc_a maps to So (score 4), enc_b maps to Ll (score 10) → enc_b wins
    categories = {0xD5: ("So", "Ll")}
    data = bytes([0x61, 0xD5, 0x62])
    winner = confusion_mod.resolve_by_category_voting(
        data, "latin-1", "mac-roman", diff_bytes, categories
    )
    assert winner == "mac-roman"


def test_category_voting_letter_over_punctuation_is_not_evidence():
    r"""Letter-over-punctuation naive votes are not evidence.

    Punctuation legitimately borders letters (paths like ``KRB\ZUNI``
    under EBCDIC read as ``KRBÖZUNI`` by a sibling), so the vote must
    return None rather than promote the letter interpretation.
    """
    diff_bytes = frozenset({0xD5})
    categories = {0xD5: ("Ll", "Po")}
    data = bytes([0x61, 0xD5, 0x62])
    winner = confusion_mod.resolve_by_category_voting(
        data, "latin-1", "mac-roman", diff_bytes, categories
    )
    assert winner is None


def test_bigram_rescore_returns_enc_a():
    """Bigram re-score returns enc_a when enc_a scores higher.

    Uses Ukrainian text (koi8-u encoded) where koi8-u is passed as enc_a.
    Bytes 0xa6/0xa7 (Ukrainian i-with-macron/yi) are in the koi8-r/koi8-u
    distinguishing set; the koi8-u bigram model scores them higher, so enc_a wins.
    """
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    result = confusion_mod.resolve_by_bigram_rescore(
        _UKRAINIAN_KOI8U, "koi8-u", "koi8-r", diff_bytes
    )
    assert result == "koi8-u"


def test_bigram_rescore_returns_enc_b():
    """Bigram re-score returns enc_b when enc_b scores higher.

    Uses the same Ukrainian / koi8-u data but passes koi8-r as enc_a and
    koi8-u as enc_b, so this time the winning encoding is the second argument.
    """
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    result = confusion_mod.resolve_by_bigram_rescore(
        _UKRAINIAN_KOI8U, "koi8-r", "koi8-u", diff_bytes
    )
    assert result == "koi8-u"


def test_resolve_confusion_groups_skips_none_encoding_candidate():
    """Candidates with encoding=None should be skipped during band scan."""
    results = [
        DetectionResult(encoding="cp1140", confidence=0.95, language="en"),
        DetectionResult(encoding=None, confidence=0.94, language=None),
        DetectionResult(encoding="cp500", confidence=0.93, language="en"),
    ]
    resolved = confusion_mod.resolve_confusion_groups(bytes(range(256)), results)
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
    resolved = confusion_mod.resolve_confusion_groups(bytes(range(256)), results)
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

    resolved = confusion_mod.resolve_confusion_groups(_UKRAINIAN_KOI8U, results)

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

    resolved = confusion_mod.resolve_confusion_groups(_TURKISH_ISO8859_9, results)

    assert resolved[0].encoding == "iso8859-9"
    assert resolved[1].encoding == "iso8859-1"


def test_bigram_rescore_no_variants_for_one_encoding():
    """When one encoding has no model variants its score is 0.0 and the other wins.

    Uses the koi8-u / ascii pair.  koi8-u has a bigram model; ascii has none.
    Ukrainian text (koi8-u) produces non-zero distinguishing bigrams, so
    koi8-u (enc_a) should beat ascii (enc_b) whose score defaults to 0.0.
    """
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    # ascii has no model in the index; koi8-u does.
    result = confusion_mod.resolve_by_bigram_rescore(
        _UKRAINIAN_KOI8U, "koi8-u", "ascii", diff_bytes
    )
    assert result == "koi8-u"


@_needs_interpreted_build
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
        resolved = confusion_mod.resolve_confusion_groups(b"\xd5\xd6\xd7", results)

    assert resolved[0].encoding == "cp1252"
    assert resolved[1].encoding == "iso8859-1"


# Hungarian text whose u-double-acute letters land on 0xF8 in iso8859-16 —
# the one position separating it from iso8859-2, which reads that byte as
# the Czech r-hacek.
_HUNGARIAN_ISO8859_16 = (
    "A műszerfal és a hűtőrács kitűnt a szürkeségből, "
    "krómbetűkkel díszítve, fűtött üléssel. "
) * 4

# Cyrillic prose in cp866.  cp866 cannot encode BYELORUSSIAN-UKRAINIAN I
# (U+0456) at all — that gap is exactly what cp1125 exists to fill — so
# the sample stays within the letters cp866 covers; the languages under
# test come from the constructed results, not from these bytes.
_CYRILLIC_CP866 = (
    "Родная мова не только средство общения, но и сокровище культуры. "
    "Это язык наших предков и наших детей. "
).encode("cp866") * 3


def test_comparable_languages_unrestricted_without_languages():
    """No reported languages means the unrestricted comparison."""
    assert (
        confusion_mod._comparable_languages("iso8859-2", "iso8859-16", frozenset())
        is None
    )


def test_comparable_languages_excludes_what_one_side_cannot_model():
    """The shared set drops languages only one encoding models.

    iso8859-2 models Czech and iso8859-16 does not, so a pair judged on
    Hungarian must not be scored against a Czech model.
    """
    shared = confusion_mod._comparable_languages(
        "iso8859-2", "iso8859-16", frozenset({"hu"})
    )
    assert shared is not None
    assert "hu" in shared
    assert "cs" not in shared


def test_comparable_languages_falls_back_when_a_language_is_unshared():
    """A reported language outside the shared set disables the restriction.

    cp1125 models only Ukrainian, so a Belarusian cp866 document shares
    just ``uk`` with it.  Restricting there would score the right encoding
    under the wrong language, so the pair is compared unrestricted.
    """
    assert (
        confusion_mod._comparable_languages("cp866", "cp1125", frozenset({"uk", "be"}))
        is None
    )


def test_comparable_languages_restricts_when_every_language_is_shared():
    """Both reported languages inside the shared set enables the restriction."""
    assert confusion_mod._comparable_languages(
        "cp866", "cp1125", frozenset({"uk"})
    ) == frozenset({"uk"})


def test_bigram_rescore_judges_hungarian_under_hungarian():
    """The pair is compared in the language both results report."""
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("iso8859-2", "iso8859-16")]
    data = _HUNGARIAN_ISO8859_16.encode("iso8859-16")
    assert (
        confusion_mod.resolve_by_bigram_rescore(
            data, "iso8859-2", "iso8859-16", diff_bytes, frozenset({"hu"})
        )
        == "iso8859-16"
    )


def test_comparable_languages_keeps_the_art_model():
    """The art pseudo-language survives the shared-language intersection.

    cp437 is the only encoding with a ``zxx`` model, so a plain
    intersection would strip box-drawing evidence from every restricted
    rescore cp437 takes part in.
    """
    shared = confusion_mod._comparable_languages("cp850", "cp437", frozenset({"en"}))
    assert shared is not None
    assert "zxx" in shared
    assert "zxx" not in confusion_mod._modelled_languages("cp850")


def test_best_variant_score_none_means_every_variant():
    """``None`` scores every variant; a restriction can only score lower.

    Also pins the ``default=0.0`` branch: a language the encoding does not
    model scores nothing, which loses the comparison rather than
    abstaining — the reason callers must not use it as an abstention.
    """
    index = get_enc_index()
    profile = BigramProfile(_HUNGARIAN_ISO8859_16.encode("iso8859-16"))
    every = confusion_mod._best_variant_score(profile, index, "iso8859-2", None)
    one = confusion_mod._best_variant_score(
        profile, index, "iso8859-2", frozenset({"cs"})
    )
    assert one > 0.0
    assert every >= one
    assert (
        confusion_mod._best_variant_score(
            profile, index, "iso8859-2", frozenset({"vi"})
        )
        == 0.0
    )


@_needs_interpreted_build
def test_resolve_confusion_groups_passes_both_languages_to_the_rescore():
    """Both results' languages reach the rescore, not just the champion's.

    Uses differing ISO codes so dropping either side is detectable — the
    pipeline fills ``.language`` from model keys ('uk', 'be'), never from
    display names.

    Interpreted builds only.  Monkeypatching a module global cannot reach
    a compiled module's internal calls, so under mypyc this would assert
    on an empty list rather than fail loudly on a real regression.  The
    behaviour it guards is covered end to end in the compiled build by
    ``tests/test_accuracy.py`` --- iso-8859-16-hu/culturax_OSCAR-2019_82421
    detects correctly only when both languages reach the rescore.
    """
    seen: list[frozenset[str]] = []
    original = confusion_mod.resolve_by_bigram_rescore

    def spy(
        data: bytes,
        enc_a: str,
        enc_b: str,
        diff_bytes: frozenset[int],
        languages: frozenset[str] = frozenset(),
    ) -> str | None:
        seen.append(languages)
        return original(data, enc_a, enc_b, diff_bytes, languages)

    results = [
        DetectionResult(encoding="cp1125", confidence=0.80, language="uk"),
        DetectionResult(encoding="cp866", confidence=0.80, language="be"),
    ]
    with patch.object(confusion_mod, "resolve_by_bigram_rescore", spy):
        confusion_mod.resolve_confusion_groups(_CYRILLIC_CP866, results)

    assert seen == [frozenset({"uk", "be"})]


def test_resolve_confusion_groups_promotes_on_the_restricted_rescore():
    """The restriction reaches a real promotion through the ranked scan."""
    data = _HUNGARIAN_ISO8859_16.encode("iso8859-16")
    results = [
        DetectionResult(encoding="iso8859-2", confidence=0.50, language="hu"),
        DetectionResult(encoding="iso8859-16", confidence=0.50, language="hu"),
    ]
    resolved = confusion_mod.resolve_confusion_groups(data, results)
    assert resolved[0].encoding == "iso8859-16"


def test_rescore_dense_and_sparse_paths_agree():
    """Both focused-profile scans build the same profile.

    The rescore locates distinguishing bytes with ``bytes.find`` when they
    are sparse and walks every byte when they are not.  Forcing each path
    over identical data pins the claim that they are interchangeable.
    A huge divisor makes the density test fail for any input, selecting
    the straight scan; the shipped value selects the sparse one.
    """
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    # Distinguishing bytes interleaved with plain ASCII: dense enough to
    # exercise the straight scan's skip branch, sparse enough that the
    # find-based path has non-hits to step over.
    mixed = (bytes(sorted(diff_bytes)) + b" plain ascii text ") * 12
    samples = (mixed, _UKRAINIAN_KOI8U, b"no distinguishing bytes here at all")

    results = {}
    for label, divisor in (("sparse", 4), ("dense", 10**9)):
        with patch.object(confusion_mod, "_DENSE_HIT_DIVISOR", divisor):
            results[label] = [
                confusion_mod.resolve_by_bigram_rescore(
                    data, "koi8-r", "koi8-u", diff_bytes
                )
                for data in samples
            ]
    assert results["sparse"] == results["dense"]


def test_rescore_dense_path_skips_non_distinguishing_bigrams():
    """The straight scan drops bigrams that touch no distinguishing byte."""
    maps = confusion_mod.load_confusion_data()
    diff_bytes, _ = maps[("koi8-r", "koi8-u")]
    data = (bytes(sorted(diff_bytes)) + b" plain ascii text ") * 12
    with patch.object(confusion_mod, "_DENSE_HIT_DIVISOR", 10**9):
        assert confusion_mod.resolve_by_bigram_rescore(
            data, "koi8-r", "koi8-u", diff_bytes
        ) in ("koi8-r", "koi8-u", None)
        # No distinguishing byte at all -> empty profile -> no verdict.
        assert (
            confusion_mod.resolve_by_bigram_rescore(
                b"ordinary ascii, nothing to arbitrate",
                "koi8-r",
                "koi8-u",
                diff_bytes,
            )
            is None
        )


def test_confusion_pair_winner_reads_distinguishing_bytes():
    """The pairwise helper resolves a sibling pair from byte evidence.

    postprocess calls this for the classic-Mac line-ending promotion, and
    with only sibling-tier pairs shipped no corpus file reaches it, so it
    is exercised here directly.
    """
    assert confusion_mod.confusion_pair_winner(
        _UKRAINIAN_KOI8U, "koi8-r", "koi8-u"
    ) in ("koi8-r", "koi8-u", None)


def test_confusion_pair_winner_without_a_map_declines():
    """A pair with no distinguishing map yields no verdict."""
    assert (
        confusion_mod.confusion_pair_winner(_UKRAINIAN_KOI8U, "utf-8", "koi8-u") is None
    )


#: One distinguishing occurrence of byte 0x48 between spaces, repeated.  In
#: the cp1026/cp273 map 0x48 reads as punctuation under cp1026 and as a
#: lowercase letter under cp273; with no letter neighbours the cp273 letter
#: reading is word-shape-implausible, so each occurrence is a demotion event
#: for cp1026 — three of them clear both decisiveness gates.
_DECISIVE_CP1026 = b" \x48 " * 3

#: The mirror image: byte 0x43 is a lowercase letter under cp1026 and
#: punctuation under cp273, so the same shape demotes cp1026's rival and
#: cp273 wins decisively.
_DECISIVE_CP273 = b" \x43 " * 3


def test_letter_case_table_skips_zero_char_decodes():
    """A byte that decodes to no character at all gets no letter kind.

    utf-7's ``+`` opens a base64 run and decodes to an empty string, which
    ``unicodedata.category`` would reject; the table must skip it while
    still classifying ordinary letters.
    """
    table = confusion_mod._letter_case_table("utf-7")
    assert table[ord("+")] == 0
    assert table[ord("A")] == 1
    assert table[ord("a")] == 2


def test_context_preference_isolated_letter_is_implausible():
    """A letter with no letter neighbours reads as quoted punctuation."""
    table = confusion_mod._letter_case_table("cp1252")
    pref = confusion_mod._context_preference("Ll", ord(" "), ord(" "), table)
    assert pref == confusion_mod._IMPLAUSIBLE_LETTER_PREFERENCE


def test_context_preference_lowercase_before_uppercase_is_implausible():
    """A lowercase letter immediately followed by an uppercase one is no word."""
    table = confusion_mod._letter_case_table("cp1252")
    pref = confusion_mod._context_preference("Ll", ord("x"), ord("A"), table)
    assert pref == confusion_mod._IMPLAUSIBLE_LETTER_PREFERENCE


def test_vote_demotion_counted_for_first_encoding():
    """enc_a's votes earned against an implausible letter count as demotions."""
    maps = confusion_mod.load_confusion_data()
    diff, cats = maps[("cp1026", "cp273")]
    winner, margin, demotion, events = confusion_mod._vote_with_margin(
        _DECISIVE_CP1026, "cp1026", "cp273", diff, cats
    )
    assert winner == "cp1026"
    assert margin > 0
    assert demotion >= confusion_mod._DECISIVE_VOTE_MARGIN
    assert events >= confusion_mod._DECISIVE_MIN_EVENTS


def test_vote_demotion_counted_for_second_encoding():
    """The mirror byte demotes cp1026 and credits cp273's side."""
    maps = confusion_mod.load_confusion_data()
    diff, cats = maps[("cp1026", "cp273")]
    winner, margin, demotion, events = confusion_mod._vote_with_margin(
        _DECISIVE_CP273, "cp1026", "cp273", diff, cats
    )
    assert winner == "cp273"
    assert margin > 0
    assert demotion >= confusion_mod._DECISIVE_VOTE_MARGIN
    assert events >= confusion_mod._DECISIVE_MIN_EVENTS


def test_vote_letter_beating_punctuation_is_not_evidence():
    """A plausible letter reading over a punctuation reading earns no vote.

    Punctuation legitimately borders letters, so with 0x48 flanked by
    bytes both encodings read as letters, cp273's letter reading beats
    cp1026's punctuation reading on naive preference alone — which must
    not count, leaving the vote tied.
    """
    maps = confusion_mod.load_confusion_data()
    diff, cats = maps[("cp1026", "cp273")]
    winner, margin, demotion, events = confusion_mod._vote_with_margin(
        b"\x81\x48\x82", "cp1026", "cp273", diff, cats
    )
    assert (winner, margin, demotion, events) == (None, 0, 0, 0)


def test_confusion_pair_winner_decisive_vote_short_circuits():
    """A decisive demotion vote answers without the bigram rescore."""
    assert (
        confusion_mod.confusion_pair_winner(_DECISIVE_CP273, "cp1026", "cp273")
        == "cp273"
    )


@_needs_interpreted_build
def test_confusion_pair_winner_cross_family_requires_corroboration():
    """A cross-family pair needs the vote and the rescore to agree.

    Cross-family maps carry 52+ distinguishing bytes.  With categories that
    make the vote favour koi8-u — matching the rescore on Ukrainian koi8-u
    text — the corroborated verdict stands; with the categories reversed
    the vote and rescore disagree and no verdict is returned.
    """
    big_diff = frozenset(range(0x80, 0x80 + confusion_mod._CROSS_FAMILY_MIN_DIFFS))
    assert len(big_diff) >= confusion_mod._CROSS_FAMILY_MIN_DIFFS
    agree = {("koi8-r", "koi8-u"): (big_diff, dict.fromkeys(big_diff, ("So", "Ll")))}
    disagree = {("koi8-r", "koi8-u"): (big_diff, dict.fromkeys(big_diff, ("Ll", "So")))}
    with patch.object(confusion_mod, "load_confusion_data", return_value=agree):
        assert (
            confusion_mod.confusion_pair_winner(_UKRAINIAN_KOI8U, "koi8-r", "koi8-u")
            == "koi8-u"
        )
    with patch.object(confusion_mod, "load_confusion_data", return_value=disagree):
        assert (
            confusion_mod.confusion_pair_winner(_UKRAINIAN_KOI8U, "koi8-r", "koi8-u")
            is None
        )


def test_bigram_rescore_without_distinguishing_bigrams_declines():
    """Data containing no distinguishing bytes yields no rescore verdict."""
    assert (
        confusion_mod.resolve_by_bigram_rescore(
            b"hello world", "cp1252", "cp1250", frozenset({0xFF}), frozenset()
        )
        is None
    )


def test_resolve_confusion_groups_art_top_is_not_reviewed():
    """An art-model win passes through: voting reasons about prose."""
    results = [
        DetectionResult("cp437", 0.30, confusion_mod._ART_LANGUAGE),
        DetectionResult("cp850", 0.299, None),
    ]
    resolved = confusion_mod.resolve_confusion_groups(b"anything", results)
    assert resolved == results


def test_resolve_confusion_groups_in_band_decisive_vote():
    """A decisive demotion vote promotes the in-band sibling."""
    results = [
        DetectionResult("cp1026", 0.10, None),
        DetectionResult("cp273", 0.099, None),
    ]
    resolved = confusion_mod.resolve_confusion_groups(_DECISIVE_CP273, results)
    assert resolved[0].encoding == "cp273"
    assert resolved[0].confidence == 0.10


def test_resolve_confusion_groups_strict_tier_decisive_vote():
    """A decisive vote promotes an out-of-band candidate king-of-the-hill.

    The top sits below the strict-tier confidence ceiling and the candidate
    above the floor, so the tier opens even though the candidate is far
    outside the band; the promotion carries the top confidence.
    """
    results = [
        DetectionResult("cp1026", 0.10, None),
        DetectionResult("ascii", 0.09, None),
        DetectionResult("cp273", 0.06, None),
    ]
    resolved = confusion_mod.resolve_confusion_groups(_DECISIVE_CP273, results)
    assert resolved[0].encoding == "cp273"
    assert resolved[0].confidence == 0.10
    assert [r.encoding for r in resolved[1:]] == ["cp1026", "ascii"]


def test_resolve_confusion_groups_strict_tier_corroborated():
    """Out of band, a non-decisive vote needs the rescore to agree.

    On Ukrainian koi8-u text the koi8-r/koi8-u vote is won on letters
    beating box-drawing symbols — no demotion events, so not decisive —
    and the bigram rescore agrees, which is exactly the corroboration the
    strict tier demands.
    """
    results = [
        DetectionResult("koi8-r", 0.10, "ru"),
        DetectionResult("ascii", 0.09, None),
        DetectionResult("koi8-u", 0.06, "uk"),
    ]
    resolved = confusion_mod.resolve_confusion_groups(_UKRAINIAN_KOI8U, results)
    assert resolved[0].encoding == "koi8-u"
    assert resolved[0].confidence == 0.10


def test_pair_categories_marks_undecodable_bytes_unassigned():
    """A byte one side cannot decode reads as the least plausible category."""
    assert confusion_mod._pair_categories("cp1252", "hp-roman8", frozenset({0x81})) == {
        0x81: ("Cn", "Cc")
    }


def test_pair_categories_marks_zero_char_decodes_unassigned():
    """A stateful codec's zero-character decode has no category to read."""
    assert confusion_mod._pair_categories("utf-7", "ascii", frozenset({0x2B})) == {
        0x2B: ("Cn", "Sm")
    }


def test_arbitrate_distinguishing_bytes_lets_the_models_decide():
    """When the models score the distinguishing bigrams apart, they decide."""
    welsh = "Mae dŵr yn llifo drwy'r dref.".encode("iso8859-14")
    assert (
        confusion_mod.arbitrate_distinguishing_bytes(
            welsh,
            "iso8859-14",
            "cp1252",
            frozenset({0xF0}),
            languages_a=frozenset({"cy"}),
            languages_b=frozenset({"cy"}),
        )
        == "iso8859-14"
    )
    german = "Die Österreicher und die Ärzte in München.".encode("cp1252")
    assert (
        confusion_mod.arbitrate_distinguishing_bytes(
            german,
            "hp-roman8",
            "cp1252",
            frozenset({0xC4, 0xD6}),
            languages_a=frozenset({"de"}),
            languages_b=frozenset({"de"}),
        )
        == "cp1252"
    )


def test_arbitrate_distinguishing_bytes_falls_back_to_word_shape():
    """A byte no model has seen is read by context: letter beats superscript."""
    kven = b"- Mie uskoma, ette se oon mah\xb9olista rakenttaat omaksi tuo m\xf6kki."
    assert (
        confusion_mod.arbitrate_distinguishing_bytes(
            kven,
            "iso8859-10",
            "cp1252",
            frozenset({0xB9}),
            languages_a=frozenset({"fi"}),
            languages_b=frozenset({"fi"}),
        )
        == "iso8859-10"
    )


def test_arbitrate_distinguishing_bytes_declines_without_evidence():
    """Two letter readings the models have never seen decide nothing."""
    assert (
        confusion_mod.arbitrate_distinguishing_bytes(
            b"St\xd6rung? s\xf6mething.",
            "hp-roman8",
            "cp1252",
            frozenset({0xD6}),
            languages_a=frozenset({"en"}),
            languages_b=frozenset({"en"}),
        )
        is None
    )
    # Too short for a bigram: no profile, straight to the (silent) vote.
    assert (
        confusion_mod.arbitrate_distinguishing_bytes(
            b"\xd6",
            "hp-roman8",
            "cp1252",
            frozenset({0xD6}),
            languages_a=None,
            languages_b=None,
        )
        is None
    )

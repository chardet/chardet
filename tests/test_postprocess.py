# tests/test_postprocess.py
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

import pytest

from chardet import detect
from chardet.pipeline import DetectionResult, postprocess
from chardet.pipeline.confusion import CONFUSION_FLOOR_RATIO, STRICT_TIER_MAX_CONF
from chardet.pipeline.postprocess import (
    _demote_niche_latin,
    _high_byte_evidence_margin,
    _promote_koi8t,
    forced_encodings,
    postprocess_results,
    scoring_floor,
)

#: See the note in tests/test_confusion.py: mypyc resolves a compiled
#: module's calls to functions imported into it at compile time, so patching
#: those names only takes effect on interpreted builds.
_needs_interpreted_build = pytest.mark.skipif(
    postprocess.__file__.endswith((".so", ".pyd")),
    reason="patches a function the compiled module calls natively",
)


def test_demote_niche_latin():
    """iso-8859-10 at top should be demoted when no distinguishing bytes."""
    results = [
        DetectionResult("iso8859-10", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    # Data with only bytes shared between iso-8859-10 and iso-8859-1
    data = bytes([0xE9, 0xF6, 0xFC])  # é ö ü in both encodings
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_demote_niche_latin_no_demote_when_evidence():
    """iso-8859-10 stays when its distinguishing bytes carry real evidence.

    The sample is Icelandic prose whose non-ASCII letters give the winning
    model an evidence contribution far above the dead-heat epsilon —
    presence of distinguishing bytes alone is no longer enough (see
    test_demote_niche_latin_noise_level_evidence).
    """
    results = [
        DetectionResult("iso8859-10", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    data = (
        "Ąsta Þetta er íslenskur texti með mörgum séríslenskum "
        "stöfum, æði þægilegt að lesa. "
    ).encode("iso-8859-10") * 3
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "iso8859-10"


def test_demote_niche_latin_noise_level_evidence():
    """A distinguishing byte whose contribution is noise does not veto.

    A mostly-ASCII Windows-1252 file whose only non-ASCII bytes are one
    0xD6/0xF6 pair carries 0xD6 — in hp-roman8's distinguishing set — while
    the winning model's whole high-byte contribution is under the dead-heat
    epsilon.  The demotion must fire: the "real HP-Roman8 text contains
    these bytes" premise assumes evidence, not a costume.
    """
    body = b"plain ascii text that goes on and on, filling space. " * 40
    data = body + b"St\xd6rung? s\xf6mething. " + body
    results = [
        DetectionResult("hp-roman8", 0.39, "en"),
        DetectionResult("cp1252", 0.39, "en"),
    ]
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_promote_koi8t_with_tajik_bytes():
    """KOI8-T should be promoted when Tajik-specific bytes are present."""
    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("koi8-t", 0.88, "tg"),
    ]
    # 0x80 is a Tajik-specific byte in KOI8-T
    data = bytes([0x41, 0x80, 0x42])
    promoted = _promote_koi8t(data, results)
    assert promoted[0].encoding == "koi8-t"


def test_promote_koi8t_no_promote_without_tajik_bytes():
    """KOI8-T should NOT be promoted when no Tajik-specific bytes are present."""
    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("koi8-t", 0.88, "tg"),
    ]
    # Only Cyrillic-range bytes shared between KOI8-R and KOI8-T
    data = bytes([0xC0, 0xC1, 0xC2])
    promoted = _promote_koi8t(data, results)
    assert promoted[0].encoding == "koi8-r"


def test_promote_koi8t_returns_early_when_koi8t_absent():
    """When KOI8-R is first but KOI8-T is not in results, return unchanged."""
    results = [
        DetectionResult("koi8-r", 0.90, "ru"),
        DetectionResult("cp1251", 0.85, "ru"),
    ]
    data = bytes([0x80, 0xC0, 0xC1])  # 0x80 is Tajik-specific but KOI8-T absent
    returned = _promote_koi8t(data, results)
    assert returned is results  # same object, unchanged
    assert returned[0].encoding == "koi8-r"


def test_demote_niche_latin_swap_prefers_prevalent_in_dead_heat():
    """Era prevalence picks the swap target among tied common Latin candidates.

    Inside the dead-heat band the confidence order between iso-8859-1 and
    windows-1252 is noise (the demotion's own premise), so the replacement
    must not depend on it: windows-1252 (era rank 1) wins over iso-8859-1
    (era rank 2) even though iso-8859-1 ranks higher.
    """
    results = [
        DetectionResult("hp-roman8", 0.39, "en"),
        DetectionResult("cp437", 0.389995, "en"),
        DetectionResult("iso8859-1", 0.38999, "en"),
        DetectionResult("cp1252", 0.38998, "en"),
    ]
    data = bytes([0xE9])  # no hp-roman8-distinguishing byte -> demote
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"
    assert demoted[-1].encoding == "hp-roman8"


def test_demote_niche_latin_swap_confidence_wins_outside_band():
    """A real margin between the common Latin rivals still decides.

    windows-1252 trails the best common Latin candidate (iso-8859-1) by
    0.04 — far outside the band — so it lost on real evidence and
    prevalence must not resurrect it.
    """
    results = [
        DetectionResult("hp-roman8", 0.90, "en"),
        DetectionResult("iso8859-1", 0.89, "en"),
        DetectionResult("cp1252", 0.85, "en"),
    ]
    data = bytes([0xE9])  # no hp-roman8-distinguishing byte -> demote
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "iso8859-1"
    assert demoted[-1].encoding == "hp-roman8"


def test_demote_niche_latin_swap_band_anchors_on_best_common_latin():
    """The tie band is anchored at the best common Latin, not the demoted top.

    Both commons sit far below the demoted top (0.05, outside its band)
    but only 5e-6 apart from each other — separable from the top, not
    from each other.  Whether two rivals are separable is a fact about
    their own gap, so era prevalence must still pick windows-1252.
    """
    results = [
        DetectionResult("hp-roman8", 0.90, "en"),
        DetectionResult("iso8859-1", 0.85, "en"),
        DetectionResult("cp1252", 0.849995, "en"),
    ]
    data = bytes([0xE9])  # no hp-roman8-distinguishing byte -> demote
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"
    assert demoted[-1].encoding == "hp-roman8"


def test_demote_niche_latin_iso_8859_14():
    """iso-8859-14 at top should be demoted when no distinguishing bytes."""
    results = [
        DetectionResult("iso8859-14", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    data = bytes([0xC0, 0xC1, 0xC2])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_demote_niche_latin_windows_1254():
    """windows-1254 at top should be demoted when no distinguishing bytes."""
    results = [
        DetectionResult("cp1254", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    data = bytes([0xC0, 0xC1, 0xE9])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"


def test_high_byte_evidence_margin_degenerate_inputs():
    """The margin helper returns 0.0 when there is nothing to measure.

    Three early-outs, none reachable through ``_should_demote`` on real
    rankings: an encoding with no statistical models, a window too short
    to contain a bigram, and a window whose bigrams are all ASCII.
    """
    assert _high_byte_evidence_margin(b"St\xd6rung", "ascii", "en") == 0.0
    assert _high_byte_evidence_margin(b"\xd6", "hp-roman8", "en") == 0.0
    assert _high_byte_evidence_margin(b"plain ascii text", "hp-roman8", "en") == 0.0


def test_demote_niche_latin_end_to_end_lone_umlaut_pair():
    """The full pipeline resolves the costume case to Windows-1252.

    The reproduction from the report that motivated the evidence margin:
    a mostly-ASCII file whose only non-ASCII bytes are one 0xD6/0xF6
    pair.  The tests above hand ``_demote_niche_latin`` a ranking; this
    one pins ``detect()`` itself, so a change anywhere upstream of the
    demotion (scoring, dead-heat priors, chain order) that breaks the
    outcome is caught.  The prevalence swap is pinned separately by the
    swap unit tests: on this input windows-1252 already leads the other
    common Latin candidates inside the tie band.
    """
    sentence = (
        b"This is a mostly ASCII file with plain sentences that go on "
        b"and on, describing nothing in particular, just filling space "
        b"the way source files and configuration files usually do. "
    )
    data = sentence * 6 + b"St\xd6rung? s\xf6mething. " + sentence * 6
    assert detect(data)["encoding"] == "Windows-1252"


def test_demote_niche_latin_survives_a_confidence_resort():
    """The demotion must outlive a re-sort, not just reorder the list.

    ``detect_all`` re-sorts by confidence before returning.  A demoted entry
    that keeps the top score is put straight back near the top by that
    (stable) sort, so the demotion has to move the score too.  Needs a
    lower-scoring tail candidate to be visible at all -- with every result
    tied, position alone survives.
    """
    results = [
        DetectionResult("iso8859-14", 0.1803, None),
        DetectionResult("iso8859-1", 0.1803, None),
        DetectionResult("cp1252", 0.1803, None),
        DetectionResult("hp-roman8", 0.1136, None),
    ]
    data = bytes([0xC0, 0xC1, 0xC2])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "cp1252"  # most prevalent of the tied commons
    assert demoted[-1].encoding == "iso8859-14"
    confidences = [r.confidence for r in demoted]
    assert confidences == sorted(confidences, reverse=True)
    resorted = sorted(demoted, key=lambda r: r.confidence, reverse=True)
    assert [r.encoding for r in resorted] == [r.encoding for r in demoted]


# ---------------------------------------------------------------------------
# The correction chain
# ---------------------------------------------------------------------------

#: Every step of :func:`postprocess_results`, in the order its docstring
#: documents.  The order is load-bearing -- confusion resolution can promote
#: the candidate niche-Latin demotion then reads as its swap target, and the
#: decode-safety flip is specified to see whatever the rest settled on -- but
#: no individual step's test can see it, since each is called directly.
_CHAIN = (
    "_promote_superset_on_dead_heat",
    "_prefer_prevalent_on_dead_heat",
    "_arbitrate_rare_language",
    "resolve_confusion_groups",
    "_demote_niche_latin",
    "_promote_koi8t",
    "_promote_mac_on_cr_line_endings",
    "_prefer_decodable_on_tie",
)


def test_postprocess_results_runs_every_correction_in_order(
    monkeypatch: pytest.MonkeyPatch,
):
    """Pin the chain: a dropped or reordered step shows up here."""
    calls = []

    def recorded(name: str, original: Callable[..., object]) -> Callable[..., object]:
        def wrapper(*args: object, **kwargs: object) -> object:
            calls.append(name)
            return original(*args, **kwargs)

        return wrapper

    for name in _CHAIN:
        monkeypatch.setattr(
            postprocess, name, recorded(name, getattr(postprocess, name))
        )

    results = [
        DetectionResult("iso8859-14", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    postprocess.postprocess_results(bytes([0xC0, 0xC1, 0xC2]), results)
    assert calls == list(_CHAIN)


def test_postprocess_results_applies_the_niche_latin_demotion():
    """The public entry point carries the corrections, not just the helpers."""
    results = [
        DetectionResult("iso8859-14", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    processed = postprocess_results(bytes([0xC0, 0xC1, 0xC2]), results)
    assert processed[0].encoding == "cp1252"


# ---------------------------------------------------------------------------
# The pruning contract (composition is pinned corpus-wide in
# tests/test_statistical.py's parity sweep)
# ---------------------------------------------------------------------------


def test_scoring_floor_trails_second_best():
    """With a confident top, the floor trails top2 by the corrections' reach."""
    floor = scoring_floor(0.9, 0.85)
    assert floor < 0.85
    # The reach must at least cover the confusion band, with room to spare
    # for rare-language arbitration's wider margin.
    assert 0.85 - floor > 0.005


def test_scoring_floor_ignores_top1_when_strict_tier_closed():
    """Above the strict-tier threshold, only top2 positions the floor."""
    assert scoring_floor(0.9, 0.5) == scoring_floor(STRICT_TIER_MAX_CONF, 0.5)


def test_scoring_floor_extends_to_strict_tier():
    """A low top opens the strict tier: the floor drops to its ratio floor."""
    top1 = STRICT_TIER_MAX_CONF / 2
    floor = scoring_floor(top1, top1)
    assert floor == pytest.approx(top1 * CONFUSION_FLOOR_RATIO)


def test_forced_encodings_empty_without_triggers():
    """No demotion candidate and no koi8-r near the top forces nothing."""
    assert forced_encodings(["cp1251", "koi8-u", "cp1252"]) == []


def test_forced_encodings_demotion_candidate_forces_latin_trio():
    """A niche-Latin demotion candidate near the top forces its swap targets."""
    forced = forced_encodings(["iso8859-10"])
    assert set(forced) == {"iso8859-1", "iso8859-15", "cp1252"}


def test_forced_encodings_koi8r_forces_koi8t():
    """koi8-r near the top forces koi8-t for the KOI8-T promotion."""
    assert forced_encodings(["koi8-r"]) == ["koi8-t"]


def test_forced_encodings_triggers_combine():
    """Both triggers near the top force both sets."""
    forced = forced_encodings(["cp1254", "koi8-r"])
    assert set(forced) == {"iso8859-1", "iso8859-15", "cp1252", "koi8-t"}


def test_era_rank_unknown_encoding_ranks_last():
    """An encoding missing from the registry can never win a prevalence tie."""
    assert postprocess._era_rank("not-a-codec") == 1 << 30


def test_high_byte_evidence_without_variants_is_absent():
    """An encoding with no model variants has no high-byte evidence."""
    assert postprocess._has_high_byte_evidence(b"\xe9ab", "not-a-codec", None) is False


def test_prevalent_dead_heat_skips_binary_entries():
    """A ``None``-encoding entry inside the dead heat is skipped, not ranked.

    The evidence-free ASCII data leaves the mainframe top without high-byte
    support, so the modern-web rival wins the heat past the binary entry.
    """
    results = [
        DetectionResult("cp500", 0.30, None),
        DetectionResult(None, 0.30, None),
        DetectionResult("cp1252", 0.29995, None),
    ]
    resolved = postprocess._prefer_prevalent_on_dead_heat(b"hello", results)
    assert resolved[0].encoding == "cp1252"
    assert resolved[0].confidence == 0.30


def test_superset_dead_heat_promotes_decoding_superset():
    """cp932 within the epsilon of shift_jis takes the win."""
    results = [
        DetectionResult("shift_jis", 0.30, "ja"),
        DetectionResult("cp932", 0.29995, "ja"),
    ]
    resolved = postprocess._promote_superset_on_dead_heat(b"hello world", results)
    assert resolved[0].encoding == "cp932"
    assert resolved[0].confidence == 0.30


def test_superset_dead_heat_stops_at_the_epsilon():
    """A superset ranked below the dead-heat band stays where it is."""
    results = [
        DetectionResult("shift_jis", 0.30, "ja"),
        DetectionResult("euc_jp", 0.2999, "ja"),
        DetectionResult("cp932", 0.10, "ja"),
    ]
    resolved = postprocess._promote_superset_on_dead_heat(b"hello world", results)
    assert resolved == results


def test_superset_dead_heat_without_superset_in_band():
    """No superset inside the band leaves the ranking untouched."""
    results = [
        DetectionResult("shift_jis", 0.30, "ja"),
        DetectionResult("euc_jp", 0.29999, "ja"),
    ]
    resolved = postprocess._promote_superset_on_dead_heat(b"hello world", results)
    assert resolved == results


def test_rare_arbitration_stops_past_the_margin():
    """A rival trailing by more than the margin is real evidence, not a flip."""
    results = [
        DetectionResult("iso8859-14", 0.10, "br"),
        DetectionResult("cp1252", 0.05, "fr"),
    ]
    assert postprocess._arbitrate_rare_language(results) == results


def test_rare_arbitration_skips_unlabelled_rivals():
    """A rival with no language cannot arbitrate; the next prevalent one can."""
    results = [
        DetectionResult("iso8859-14", 0.10, "br"),
        DetectionResult("cp1250", 0.099, None),
        DetectionResult("cp1252", 0.098, "fr"),
    ]
    resolved = postprocess._arbitrate_rare_language(results)
    assert resolved[0].encoding == "cp1252"
    assert resolved[0].confidence == 0.10


def test_rare_arbitration_needs_a_prevalent_rival():
    """A neighbourhood of rare-language rivals leaves the winner in place."""
    results = [
        DetectionResult("iso8859-14", 0.10, "br"),
        DetectionResult("iso8859-15", 0.099, "cy"),
    ]
    assert postprocess._arbitrate_rare_language(results) == results


#: Bare-\r line endings, enough of them to clear the classic-Mac gate.
_CR_ONLY_DATA = b"line one\rline two\rline three\rline four\r"


def test_mac_cr_promotion_skips_art_top():
    """An art-model win is not reviewed by the prose-based Mac promotion."""
    results = [
        DetectionResult("cp437", 0.30, postprocess.ART_LANGUAGE),
        DetectionResult("mac-roman", 0.299, None),
    ]
    resolved = postprocess._promote_mac_on_cr_line_endings(_CR_ONLY_DATA, results)
    assert resolved == results


def test_mac_cr_promotion_promotes_banded_mac_candidate():
    r"""Bare-\r line endings promote the in-band classic-Mac candidate."""
    results = [
        DetectionResult("koi8-r", 0.30, "ru"),
        DetectionResult("mac-roman", 0.299, None),
    ]
    resolved = postprocess._promote_mac_on_cr_line_endings(_CR_ONLY_DATA, results)
    assert resolved[0].encoding == "mac-roman"
    assert resolved[0].confidence == 0.30


def test_mac_cr_promotion_stops_at_the_band():
    """A Mac candidate below the confidence band is not promoted."""
    results = [
        DetectionResult("koi8-r", 0.30, "ru"),
        DetectionResult("mac-roman", 0.20, None),
    ]
    resolved = postprocess._promote_mac_on_cr_line_endings(_CR_ONLY_DATA, results)
    assert resolved == results


@_needs_interpreted_build
def test_mac_cr_promotion_vetoed_by_byte_evidence():
    """The platform prior must not overturn distinguishing-byte evidence.

    When the pairwise verdict says the current top beats the best-ranked
    Mac candidate, the promotion stops entirely instead of falling through
    to a lower-ranked sibling with no map to be checked against.
    """
    results = [
        DetectionResult("koi8-r", 0.30, "ru"),
        DetectionResult("mac-cyrillic", 0.299, "ru"),
        DetectionResult("mac-roman", 0.298, None),
    ]
    with patch.object(postprocess, "confusion_pair_winner", return_value="koi8-r"):
        resolved = postprocess._promote_mac_on_cr_line_endings(_CR_ONLY_DATA, results)
    assert resolved == results


def test_decodes_under_public_names_rejects_undecodable():
    """A rival that cannot decode the data is no flip target."""
    assert postprocess._decodes_under_public_names(b"\xff", "ascii") is False


def test_decodable_tie_keeps_winner_when_no_rival_decodes():
    """A dangling-tail winner stays on top when every rival fails to decode."""
    results = [
        DetectionResult("euc_kr", 0.30, "ko"),
        DetectionResult("ascii", 0.29, None),
    ]
    resolved = postprocess._prefer_decodable_on_tie(
        b"hello \xb0", results, input_truncated=False
    )
    assert resolved == results

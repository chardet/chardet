# tests/test_postprocess.py
from __future__ import annotations

from collections.abc import Callable

import pytest

from chardet.pipeline import DetectionResult, postprocess
from chardet.pipeline.confusion import CONFUSION_FLOOR_RATIO, STRICT_TIER_MAX_CONF
from chardet.pipeline.postprocess import (
    _demote_niche_latin,
    _promote_koi8t,
    forced_encodings,
    postprocess_results,
    scoring_floor,
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


def test_demote_niche_latin_no_demote_when_distinguishing():
    """iso-8859-10 should NOT be demoted when distinguishing bytes are present."""
    results = [
        DetectionResult("iso8859-10", 0.90, None),
        DetectionResult("cp1252", 0.85, None),
    ]
    # 0xA1 differs between iso-8859-10 and iso-8859-1
    data = bytes([0xA1, 0xE9, 0xF6])
    demoted = _demote_niche_latin(data, results)
    assert demoted[0].encoding == "iso8859-10"


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
    assert demoted[0].encoding == "iso8859-1"
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

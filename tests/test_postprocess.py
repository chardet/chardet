# tests/test_postprocess.py
from __future__ import annotations

import pytest

from chardet.pipeline import DetectionResult
from chardet.pipeline.confusion import CONFUSION_FLOOR_RATIO, STRICT_TIER_MAX_CONF
from chardet.pipeline.postprocess import (
    _demote_niche_latin,
    _promote_koi8t,
    forced_encodings,
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

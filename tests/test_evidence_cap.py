# tests/test_evidence_cap.py
"""The evidence cap (ADR-0006): invariant and bounded-stage behavior.

The filtering, gating, probing, and rank-correction stages converge on at
most ``EVIDENCE_CAP_BYTES`` of the examination window.  The cap sits above
``DEFAULT_MAX_BYTES`` so every default call is unaffected; for larger
windows, bytes past the cap cannot change what those stages conclude.
"""

from __future__ import annotations

import chardet
from chardet._utils import DEFAULT_MAX_BYTES, EVIDENCE_CAP_BYTES


def test_cap_covers_default_window() -> None:
    """The invariant that makes every default call provably unchanged.

    If this fails, someone raised DEFAULT_MAX_BYTES past the evidence cap:
    default-call results would silently start depending on the cap.  Raise
    EVIDENCE_CAP_BYTES along with it (and re-run the accuracy corpus).
    """
    assert EVIDENCE_CAP_BYTES >= DEFAULT_MAX_BYTES


def _beyond_cap(filler: bytes) -> bytes:
    """Build a body a bit larger than the evidence cap.

    Whole repetitions only: the body must end on a character boundary, or an
    appended garbage byte hides inside the tolerated truncated-tail overrun
    instead of being seen as invalid.
    """
    reps = (EVIDENCE_CAP_BYTES + 50_000) // len(filler) + 1
    return filler * reps


def test_validity_ignores_bytes_past_cap() -> None:
    """Undecodable bytes after the cap no longer eliminate the winner.

    0x81/0x8D/0x9D are undefined in cp1252; before ADR-0006 a tail of them
    knocked Windows-1252 out of the candidate set for the whole input.
    """
    body = _beyond_cap(
        "Le cœur a ses raisons que la raison ne connaît point. ".encode("cp1252")
    )
    garbage = b"\x81\x8d\x9d" * 50
    with_garbage = body + garbage

    clean = chardet.detect(body, max_bytes=len(body))
    dirty = chardet.detect(with_garbage, max_bytes=len(with_garbage))
    assert clean["encoding"] == "Windows-1252"
    assert dirty == clean


def test_structural_ignores_bytes_past_cap() -> None:
    """Structure-breaking bytes after the cap no longer wreck CJK detection.

    0x82 0x39 is an invalid lead/trail pair in Shift_JIS, CP932, and EUC-JP
    alike; before ADR-0006 it eliminated every Japanese candidate.
    """
    body = _beyond_cap("吾輩は猫である。名前はまだ無い。".encode("shift_jis"))
    garbage = b"\x82\x39" * 100
    with_garbage = body + garbage

    clean = chardet.detect(body, max_bytes=len(body))
    dirty = chardet.detect(with_garbage, max_bytes=len(with_garbage))
    assert clean["encoding"] in ("SHIFT_JIS", "CP932")
    assert dirty == clean


def test_exhaustive_checks_still_see_everything() -> None:
    """The UTF-8 verdict stays exact past the cap: an invalid byte at the
    very end of a large window must still reject UTF-8 (the file is *not*
    valid UTF-8, and chardet never claims otherwise)."""
    body = _beyond_cap("héllo wörld —日本語 ".encode())
    assert chardet.detect(body, max_bytes=len(body))["encoding"] == "utf-8"
    broken = body + b"\xff"
    result = chardet.detect(broken, max_bytes=len(broken))
    assert result["encoding"] != "utf-8"

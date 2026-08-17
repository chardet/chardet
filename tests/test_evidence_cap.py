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


def test_utf7_validator_converges_on_cap() -> None:
    """The UTF-7 deep validator walks only the evidence window.

    Base64-heavy ASCII (diffs, JWTs, data URIs) is wall-to-wall '+' runs
    that are not UTF-7.  The verdict is ASCII either way — this pins it on
    an input far past the cap, where the pre-ADR-0006 validator did O(n)
    Python-loop work.
    """
    blob = _beyond_cap(b"+abc123def456ghi789jkl012mno345pqr678stu901vwx234yz\n")
    result = chardet.detect(blob, max_bytes=len(blob))
    assert result["encoding"] == "ascii"


def test_escape_evidence_past_cap_is_not_consulted() -> None:
    """UTF-7 evidence sitting entirely past the cap no longer detects.

    The documented ADR-0006 boundary: the deep validators see a sequence
    only if it both begins and ends inside the evidence window.  Real
    UTF-7 shifts in and out constantly, so a document whose only shifted
    sequence lands past 256 KiB is synthetic.
    """
    body = _beyond_cap(b"plain ascii filler text, nothing special here.\n")
    utf7_tail = "こんにちは".encode("utf-7") * 20
    data = body + utf7_tail
    result = chardet.detect(data, max_bytes=len(data))
    assert result["encoding"] != "utf-7"
    # Within the cap it is still detected.
    head = utf7_tail + body
    assert chardet.detect(head, max_bytes=len(head))["encoding"] == "utf-7"


def test_hz_region_straddling_the_cap_is_not_seen() -> None:
    """A sequence that starts inside the window but ends past it is cut.

    The sliced validator finds the opening ``~{`` with no closing ``~}``,
    so this region contributes nothing.  Pinned because it is the wider
    half of the miss-direction boundary ADR-0006 documents, not the
    narrower "entirely past the cap" case above.
    """
    prefix = b"a" * (EVIDENCE_CAP_BYTES - 100)
    region = b"~{" + b"\x3b\x3c" * 200 + b"~}"
    straddle = prefix + region + b" tail text"
    assert chardet.detect(straddle, max_bytes=len(straddle))["encoding"] == "ascii"
    # The identical region wholly inside the window is still detected.
    inside = prefix[:1000] + region + b" tail text"
    assert chardet.detect(inside, max_bytes=len(inside))["encoding"] == "HZ-GB-2312"


def test_utf7_accept_stays_exhaustive() -> None:
    """A utf-7 answer is never given for data that will not decode.

    The deep validator is capped, but the decode gate is not: an illegal
    shift past the cap must still veto utf-7, or detect() hands back a
    deterministic-confidence encoding the caller's own decode rejects.
    """
    unit = "こんにちは世界".encode("utf-7")
    body = unit * ((EVIDENCE_CAP_BYTES + 20_000) // len(unit) + 1)
    assert len(body) > EVIDENCE_CAP_BYTES
    broken = body + b"+|illegal+|shift+|"
    assert chardet.detect(broken, max_bytes=len(broken))["encoding"] != "utf-7"
    # The same body without the illegal tail is still utf-7.
    assert chardet.detect(body, max_bytes=len(body))["encoding"] == "utf-7"


def test_valid_ascii_past_cap_keeps_utf8_candidate() -> None:
    """Valid UTF-8 carrying no multi-byte evidence is not a rejection.

    detect_utf8 returns None for pure ASCII, ASCII plus control bytes, and
    ASCII plus a truncated tail — all valid UTF-8.  Treating that as "the
    window is not UTF-8" stripped utf-8 from the candidate set for any
    valid window larger than the cap.
    """
    body = _beyond_cap(b"plain ascii log line, nothing special here.\n")
    assert (
        chardet.detect(body, max_bytes=len(body), include_encodings={"utf-8"})[
            "encoding"
        ]
        == "utf-8"
    )
    # ASCII plus a dangling lead byte: valid so far, no complete sequence.
    dangling = body + b"\xc3"
    assert chardet.detect(dangling, max_bytes=len(dangling))["encoding"] is not None
    # A genuine rejection still vetoes utf-8.
    invalid = body + b"\xff\xfe\xff"
    assert chardet.detect(invalid, max_bytes=len(invalid))["encoding"] != "utf-8"


def test_exhaustive_checks_still_see_everything() -> None:
    """The UTF-8 verdict stays exact past the cap.

    An invalid byte at the very end of a large window must still reject
    UTF-8 (the file is *not* valid UTF-8, and chardet never claims
    otherwise), including on the statistical path — the exhaustive check's
    rejection vetoes utf-8 from the candidate set.
    """
    body = _beyond_cap("héllo wörld —日本語 ".encode())
    assert chardet.detect(body, max_bytes=len(body))["encoding"] == "utf-8"
    broken = body + b"\xff"
    result = chardet.detect(broken, max_bytes=len(broken))
    assert result["encoding"] != "utf-8"

"""Stage 3: Statistical bigram scoring.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

from chardet.models import (
    BigramProfile,
    _get_model_norms,
    get_enc_index,
    get_rowmax,
    score_best_language,
    score_with_profile,
)
from chardet.pipeline import DetectionResult
from chardet.pipeline.postprocess import _COMMON_LATIN_ENCODINGS, _DEMOTION_CANDIDATES
from chardet.registry import EncodingInfo

# Margin subtracted from the running second-best encoding score when deciding
# whether a variant's upper bound rules it out.  Must be at least
# ``confusion._CONFUSION_BAND`` (0.005) so that every result position
# ``resolve_confusion_groups`` may examine (position 1 plus all candidates
# within the band of the top score) is scored exactly; 0.01 gives a 2x
# cushion for float noise.
_PRUNE_MARGIN = 0.01

# Below this many distinct bigrams the upper-bound prescreen costs about as
# much as the full dot products it would avoid, so score everything directly.
_MIN_NONZERO_FOR_PRESCREEN = 64


def _score_all(
    data: bytes,
    candidates: tuple[EncodingInfo, ...],
    profile: BigramProfile,
) -> list[tuple[str, float, str | None]]:
    """Score every candidate fully (no pruning).  Returns (enc, score, lang)."""
    scores: list[tuple[str, float, str | None]] = []
    for enc in candidates:
        s, lang = score_best_language(data, enc.name, profile=profile)
        if s > 0.0:
            scores.append((enc.name, s, lang))
    return scores


def _split_variants(
    candidates: tuple[EncodingInfo, ...],
    profile: BigramProfile,
) -> tuple[
    list[tuple[str, str | None, bytes, str]],
    list[tuple[float, str, str | None, bytes, str]],
]:
    """Flatten candidate model variants for pruned scoring.

    Returns ``(mb_entries, sb_entries)`` where multi-byte entries are
    ``(enc, lang, table, key)`` and single-byte entries are
    ``(upper_bound, enc, lang, table, key)`` sorted by descending bound.
    The upper bound multiplies each lead byte's total profile weight by the
    model's maximum weight for that lead byte — at most 256 terms versus one
    term per distinct bigram for a full score.
    """
    index = get_enc_index()
    norms = _get_model_norms()
    rowmax = get_rowmax()
    row_freq = profile.row_freq
    nonzero_rows = profile.nonzero_rows
    input_norm = profile.input_norm

    mb_entries: list[tuple[str, str | None, bytes, str]] = []
    sb_entries: list[tuple[float, str, str | None, bytes, str]] = []
    for enc in candidates:
        variants = index.get(enc.name)
        if variants is None:
            continue
        if enc.is_multibyte:
            for lang, table, key in variants:
                mb_entries.append((enc.name, lang, table, key))
            continue
        for lang, table, key in variants:
            rm = rowmax[key]
            ub_dot = 0
            for b1 in nonzero_rows:
                ub_dot += rm[b1] * row_freq[b1]
            ub = ub_dot / (norms[key] * input_norm)
            sb_entries.append((ub, enc.name, lang, table, key))
    sb_entries.sort(key=lambda e: e[0], reverse=True)
    return mb_entries, sb_entries


def _score_pruned(
    candidates: tuple[EncodingInfo, ...],
    profile: BigramProfile,
) -> list[tuple[str, float, str | None]]:
    """Score candidates, skipping single-byte variants that provably cannot matter.

    Multi-byte variants are always scored fully — the orchestrator may later
    boost their confidence based on structural coverage, so no raw-score
    bound can rule them out.  Single-byte variants are scored in descending
    upper-bound order (see :func:`_split_variants`) and skipped once their
    bound falls more than ``_PRUNE_MARGIN`` below the running second-best
    encoding score: such variants can affect neither the winner, nor
    position 1, nor any candidate within the confusion band of the top
    score.

    Encodings that ``postprocess_results`` inspects regardless of rank
    (the common Western Latin trio for niche-Latin demotion, KOI8-T for the
    KOI8-R promotion) are force-scored when their trigger could fire, so the
    pruned result list drives postprocessing exactly like the full list.

    Returns (enc, score, lang) tuples for encodings scoring above zero, in
    candidate order.
    """
    index = get_enc_index()
    mb_entries, sb_entries = _split_variants(candidates, profile)

    best_score: dict[str, float] = {}
    best_lang: dict[str, str | None] = {}
    # Running top-2 scores across distinct encodings; the pruning threshold
    # trails the second-best so the top two encodings stay exact.
    top1_enc = ""
    top1 = 0.0
    top2 = 0.0

    def record(enc_name: str, s: float, lang: str | None) -> None:
        nonlocal top1_enc, top1, top2
        prev = best_score.get(enc_name, 0.0)
        if s <= prev:
            return
        best_score[enc_name] = s
        best_lang[enc_name] = lang
        if enc_name == top1_enc:
            top1 = s
        elif s > top1:
            top2 = top1
            top1 = s
            top1_enc = enc_name
        elif s > top2:
            top2 = s

    for enc_name, lang, table, key in mb_entries:
        record(enc_name, score_with_profile(profile, table, key), lang)

    for ub, enc_name, lang, table, key in sb_entries:
        if ub < top2 - _PRUNE_MARGIN:
            # Sorted by descending bound and the threshold only rises, so
            # no later entry can matter either.
            break
        record(enc_name, score_with_profile(profile, table, key), lang)

    # Force-score the encodings postprocess_results may look up by name in
    # the tail of the result list, when their trigger condition could fire.
    forced: list[str] = []
    if top1_enc in _DEMOTION_CANDIDATES:
        forced.extend(_COMMON_LATIN_ENCODINGS)
    if top1_enc == "koi8-r":
        forced.append("koi8-t")
    if forced:
        for enc in candidates:
            if enc.name not in forced:
                continue
            # Score every variant: a partially-pruned encoding may otherwise
            # carry an understated best score into the demotion comparison.
            for lang, table, key in index.get(enc.name, []):
                record(enc.name, score_with_profile(profile, table, key), lang)

    return [
        (enc.name, best_score[enc.name], best_lang[enc.name])
        for enc in candidates
        if best_score.get(enc.name, 0.0) > 0.0
    ]


def score_candidates(
    data: bytes,
    candidates: tuple[EncodingInfo, ...],
    *,
    full_ranking: bool = False,
) -> list[DetectionResult]:
    """Score all candidates and return results sorted by confidence descending.

    :param data: The raw byte data to score.
    :param candidates: Encoding candidates to evaluate.
    :param full_ranking: When ``True``, score every candidate fully so the
        returned list is complete (needed by ``detect_all``).  When ``False``
        (the default), single-byte candidates that provably cannot affect the
        top of the ranking may be skipped; the winner, position 1, and all
        candidates within the confusion band of the top score are identical
        to the full ranking.
    :returns: A list of :class:`DetectionResult` sorted by confidence.
    """
    if not data or not candidates:
        return []

    profile = BigramProfile(data)
    if profile.input_norm == 0.0:
        return []

    if full_ranking or len(profile.nonzero) < _MIN_NONZERO_FOR_PRESCREEN:
        scores = _score_all(data, candidates, profile)
    else:
        scores = _score_pruned(candidates, profile)

    scores.sort(key=lambda x: x[1], reverse=True)
    return [
        DetectionResult(encoding=name, confidence=s, language=lang)
        for name, s, lang in scores
    ]

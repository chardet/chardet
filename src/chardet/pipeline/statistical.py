"""Stage 3: Statistical bigram scoring.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import math
import operator

from chardet.models import (
    _GATHER_DOT,
    _KERNEL_COMPILED,
    BigramProfile,
    _get_model_norms,
    _sumprod,
    coverage_with_profile,
    get_enc_index,
    get_rowmax,
    score_with_profile,
)
from chardet.pipeline import DetectionResult
from chardet.pipeline.postprocess import (
    _DEAD_HEAT_EPSILON,
    forced_encodings,
    scoring_floor,
)
from chardet.registry import EncodingInfo

# Below this many distinct bigrams the upper-bound prescreen costs about as
# much as the full dot products it would avoid, so score everything directly.
_MIN_NONZERO_FOR_PRESCREEN = 64


def _coverage_factor(profile: BigramProfile, table: bytes) -> float:
    """Return what one model variant's cosine is multiplied by: coverage to the 1.5.

    The cosine says how well the input matches what the model knows, and
    coverage how much of the input's weight falls on bigrams the model
    could know at all (see :func:`~chardet.models.coverage_with_profile`).
    On held-out text a gentler power fixed fewer short inputs, and a
    steeper one began to cost correct answers: squared, it handed three
    accented letters typed after an English phrase to a Greek model
    (issue #242).

    The factor is at most 1, so a variant's cosine, and every upper bound
    on its cosine, is an upper bound on its scaled score.  The scoring
    loops lean on that to skip the factor, and often the cosine too, for
    a variant that cannot matter.
    """
    if not profile.cov_total:
        return 1.0
    coverage = coverage_with_profile(profile, table)
    return coverage * math.sqrt(coverage)


def _keep_dead_heats(scores: list[float], cosines: list[float]) -> list[float]:
    """Return *scores* with the top's cosine dead heats restored.

    *scores* and *cosines* are parallel: each encoding's best covered
    score, and the cosine of the variant that earned it.  Two encodings
    whose cosines sit within the dead-heat epsilon read the input equally
    well, and coverage can then separate them on a sliver of evidence: in
    an English file with one capital ``É`` the MacRoman model has seen a
    space before an ellipsis and the Windows-1252 one has not seen a
    space before ``É``.  The dead-heat corrections in ``postprocess``
    have better tools for that question than one bigram, so an encoding
    in a cosine dead heat with the top-scoring one is raised to the top's
    score, less whatever its cosine trails the best cosine in the heat by.

    Only an encoding at or above the pruning contract's ``scoring_floor``
    can join.  Below it coverage has separated the two by more than a
    sliver, and the pruned path may not know which variant is the
    encoding's best, so the full and pruned rankings could disagree.

    Nothing is lowered and nothing rises above the top score, so the
    bounds :func:`_score_pruned` relies on still hold.
    """
    top = -1
    top_score = 0.0
    second = 0.0
    for i in range(len(scores)):
        score = scores[i]
        if score > top_score:
            second = top_score
            top_score = score
            top = i
        elif score > second:
            second = score
    if top < 0:
        return scores
    floor = scoring_floor(top_score, second)
    low = cosines[top] - _DEAD_HEAT_EPSILON
    high = cosines[top] + _DEAD_HEAT_EPSILON
    lead = cosines[top]
    heat: list[int] = []
    for i in range(len(scores)):
        if i != top and scores[i] >= floor and low <= cosines[i] <= high:
            heat.append(i)
            lead = max(lead, cosines[i])
    if not heat:
        return scores
    kept = list(scores)
    for i in heat:
        kept[i] = max(kept[i], top_score - (lead - cosines[i]))
    return kept


def _score_all(
    candidates: tuple[EncodingInfo, ...],
    profile: BigramProfile,
) -> list[tuple[str, float, str | None]]:
    """Score every candidate fully (no pruning).  Returns (enc, score, lang).

    An encoding takes the score and language of its best variant; on an
    exact tie the variant that comes first in index order wins.
    """
    index = get_enc_index()
    names: list[str] = []
    scores: list[float] = []
    cosines: list[float] = []
    langs: list[str | None] = []
    for enc in candidates:
        best = 0.0
        best_cosine = 0.0
        best_lang: str | None = None
        for lang, table, key in index.get(enc.name, ()):
            cosine = score_with_profile(profile, table, key)
            if cosine <= best:
                # Scaled, it can only be lower: not this encoding's best.
                continue
            s = cosine * _coverage_factor(profile, table)
            if s > best:
                best = s
                best_cosine = cosine
                best_lang = lang
        if best > 0.0:
            names.append(enc.name)
            scores.append(best)
            cosines.append(best_cosine)
            langs.append(best_lang)
    return list(zip(names, _keep_dead_heats(scores, cosines), langs, strict=True))


def _split_variants(
    candidates: tuple[EncodingInfo, ...],
    profile: BigramProfile,
) -> tuple[
    list[tuple[str, str | None, bytes, str, int]],
    list[tuple[float, int, str, str | None, bytes, str]],
]:
    """Flatten candidate model variants for pruned scoring.

    Returns ``(mb_entries, sb_entries)`` where multi-byte entries are
    ``(enc, lang, table, key, variant_index)`` and single-byte entries are
    ``(upper_bound, variant_index, enc, lang, table, key)`` sorted by
    descending bound.  The upper bound multiplies each lead byte's total
    profile weight by the model's maximum weight for that lead byte — at
    most 256 terms versus one term per distinct bigram for a full score.
    ``variant_index`` is the variant's position in the encoding index, so
    exact score ties resolve to the same variant the full path keeps.
    """
    index = get_enc_index()
    norms = _get_model_norms()
    rowmax = get_rowmax()
    row_freq = profile.row_freq
    nonzero_rows = profile.nonzero_rows
    input_norm = profile.input_norm
    # Reuse the gather and weights across every model's row-bound dot
    # product. Keep the compiled and JIT paths on their native loops.
    gather_rows: operator.itemgetter[tuple[int, ...]] | None = None
    row_values: tuple[int, ...] = ()
    if (
        _GATHER_DOT
        and not _KERNEL_COMPILED
        and _sumprod is not None
        and type(profile) is BigramProfile
        and type(nonzero_rows) is list
        and type(row_freq) is list
        and len(nonzero_rows) > 1
        and set(map(type, nonzero_rows)) == {int}
    ):
        gather_rows = operator.itemgetter(*nonzero_rows)
        row_values = gather_rows(row_freq)
        if any(type(value) is not int for value in row_values):
            gather_rows = None

    mb_entries: list[tuple[str, str | None, bytes, str, int]] = []
    sb_entries: list[tuple[float, int, str, str | None, bytes, str]] = []
    for enc in candidates:
        variants = index.get(enc.name)
        if variants is None:
            continue
        if enc.is_multibyte_cjk:
            for vi, (lang, table, key) in enumerate(variants):
                mb_entries.append((enc.name, lang, table, key, vi))
            continue
        for vi, (lang, table, key) in enumerate(variants):
            rm = rowmax[key]
            # Declared because _sumprod returns Any: inferred from that
            # assignment, ub_dot would make mypyc box every step of the loop
            # below, which the compiled build runs (about 19% slower overall).
            ub_dot: int
            if gather_rows is not None and _sumprod is not None and type(rm) is bytes:
                ub_dot = _sumprod(gather_rows(rm), row_values)
            else:
                ub_dot = 0
                for b1 in nonzero_rows:
                    ub_dot += rm[b1] * row_freq[b1]
            model_norm = norms.get(key)
            if model_norm is None:
                # Unknown norm: cannot bound the score, so never skip.
                ub = float("inf")
            elif model_norm > 0.0:
                ub = ub_dot / (model_norm * input_norm)
            else:
                # Zero norm: score_with_profile returns 0.0 for this model,
                # so bound it at 0.0 instead of dividing by zero.
                ub = 0.0
            sb_entries.append((ub, vi, enc.name, lang, table, key))
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
    bound falls below the pruning contract's ``scoring_floor``: such
    variants can affect neither the winner, nor position 1, nor any
    candidate a rank correction can examine.

    Encodings that ``postprocess_results`` inspects regardless of rank
    (the common Western Latin trio for niche-Latin demotion, KOI8-T for the
    KOI8-R promotion) are force-scored when their trigger could fire.
    Because confusion resolution can promote position 1 or any candidate
    within the band into position 0 before those triggers are evaluated,
    the trigger check covers every encoding near the top, not just the
    statistical winner.

    Returns (enc, score, lang) tuples for encodings scoring above zero, in
    candidate order.
    """
    index = get_enc_index()
    mb_entries, sb_entries = _split_variants(candidates, profile)

    best_score: dict[str, float] = {}
    best_lang: dict[str, str | None] = {}
    best_vi: dict[str, int] = {}
    best_cosine: dict[str, float] = {}
    # Running top-2 scores across distinct encodings; the pruning threshold
    # trails the second-best so the top two encodings stay exact.
    top1_enc = ""
    top1 = 0.0
    top2 = 0.0

    def record(
        enc_name: str, s: float, cosine: float, lang: str | None, vi: int
    ) -> None:
        nonlocal top1_enc, top1, top2
        prev = best_score.get(enc_name)
        if prev is not None and (s < prev or (s == prev and vi >= best_vi[enc_name])):
            # On exact ties keep the variant that comes first in index
            # order, matching _score_all on the full path.
            return
        best_score[enc_name] = s
        best_cosine[enc_name] = cosine
        best_lang[enc_name] = lang
        best_vi[enc_name] = vi
        if enc_name == top1_enc:
            top1 = s
        elif s > top1:
            top2 = top1
            top1 = s
            top1_enc = enc_name
        elif s > top2:
            top2 = s

    for enc_name, lang, table, key, vi in mb_entries:
        cosine = score_with_profile(profile, table, key)
        if cosine > 0.0:
            factor = _coverage_factor(profile, table)
            record(enc_name, cosine * factor, cosine, lang, vi)

    for ub, vi, enc_name, lang, table, key in sb_entries:
        # The floor below which no rank correction can examine a candidate;
        # everything above it must be scored exactly or detect() would
        # diverge from the unpruned full ranking.
        threshold = scoring_floor(top1, top2)
        if ub < threshold:
            # Sorted by descending bound and the threshold only rises, so
            # no later entry can matter either.
            break
        # A variant matters only if its score reaches the floor and is at
        # least its encoding's best so far.  Its bound and then its cosine
        # each cap that score, so either one falling short settles it: the
        # contract lets a score under the floor go missing, and a variant
        # that is not its encoding's best changes nothing.
        bar = max(threshold, best_score.get(enc_name, 0.0))
        if ub < bar:
            continue
        cosine = score_with_profile(profile, table, key)
        if cosine >= bar:
            factor = _coverage_factor(profile, table)
            record(enc_name, cosine * factor, cosine, lang, vi)

    # Force-score the encodings the corrections look up by name, when their
    # trigger could fire.  The trigger scan covers everything at or above
    # the contract floor, because confusion resolution may promote any of
    # those candidates to the top before postprocess evaluates its own
    # trigger conditions.
    trigger_floor = scoring_floor(top1, top2)
    forced = forced_encodings([e for e, s in best_score.items() if s >= trigger_floor])
    for enc in candidates if forced else ():
        if enc.name not in forced:
            continue
        # Score every variant: a partially-pruned encoding may otherwise
        # carry an understated best score into the demotion comparison.
        for vi, (lang, table, key) in enumerate(index.get(enc.name, [])):
            cosine = score_with_profile(profile, table, key)
            if cosine > 0.0 and cosine >= best_score.get(enc.name, 0.0):
                factor = _coverage_factor(profile, table)
                record(enc.name, cosine * factor, cosine, lang, vi)

    names = [enc.name for enc in candidates if best_score.get(enc.name, 0.0) > 0.0]
    kept = _keep_dead_heats(
        [best_score[name] for name in names], [best_cosine[name] for name in names]
    )
    return [(name, kept[i], best_lang[name]) for i, name in enumerate(names)]


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
        scores = _score_all(candidates, profile)
    else:
        scores = _score_pruned(candidates, profile)

    scores.sort(key=lambda x: x[1], reverse=True)
    return [
        DetectionResult(encoding=name, confidence=s, language=lang)
        for name, s, lang in scores
    ]

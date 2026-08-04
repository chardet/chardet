# tests/test_statistical.py
from __future__ import annotations

import pytest

from chardet.enums import EncodingEra
from chardet.models import get_enc_index
from chardet.pipeline import DetectionResult
from chardet.pipeline.statistical import score_candidates
from chardet.registry import get_candidates


def test_score_candidates_returns_sorted_results():
    data = "Héllo wörld".encode("windows-1252")
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    results = score_candidates(data, candidates)
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)


def test_score_candidates_returns_detection_results():
    data = b"Hello world"
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    results = score_candidates(data, candidates)
    for r in results:
        assert isinstance(r, DetectionResult)


def test_score_candidates_empty_data():
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    results = score_candidates(b"", candidates)
    assert len(results) == 0


def test_score_candidates_empty_candidates():
    results = score_candidates(b"Hello", ())
    assert len(results) == 0


def test_score_candidates_small_set_no_pool():
    candidates = tuple(
        e for e in get_candidates(EncodingEra.MODERN_WEB) if e.name == "utf-8"
    )
    results = score_candidates(b"Hello", candidates)
    assert len(results) <= len(candidates)


def test_score_candidates_no_matching_model():
    """Candidates with no statistical model should return an empty list."""
    # Use an encoding that definitely has no bigram model by filtering to
    # one that is not in the model index.  Structural encodings (ASCII,
    # UTF-*) are detected earlier in the pipeline and never reach statistical
    # scoring, but we can still test that score_candidates handles them.
    index = get_enc_index()
    no_model = [e for e in get_candidates(EncodingEra.ALL) if e.name not in index]
    if not no_model:
        pytest.skip("All candidates have models — cannot test no-model path")
    candidates = (no_model[0],)
    data = b"\xc1\xc2\xc3\xc4\xc5" * 10
    results = score_candidates(data, candidates)
    assert results == []


def test_correct_encoding_scores_highest():
    text = "Привет мир, как дела? Это тестовый текст на русском языке.".encode(
        "windows-1251"
    )
    candidates = get_candidates(EncodingEra.MODERN_WEB)
    results = score_candidates(text, candidates)
    assert len(results) > 0
    # windows-1251 should be among the top results
    top_names = [r.encoding for r in results[:3]]
    assert "cp1251" in top_names


# ---------------------------------------------------------------------------
# Upper-bound pruning
# ---------------------------------------------------------------------------

_PRUNING_SAMPLES = [
    "Все счастливые семьи похожи друг на друга, каждая несчастливая семья "
    "несчастлива по-своему. Все смешалось в доме Облонских.".encode("windows-1251"),
    "Héllo wörld café résumé naïve — l'élève français è già qui. ".encode(
        "windows-1252"
    )
    * 8,
    "これはテストです。日本語の文章を検出するためのサンプルテキストです。".encode(
        "cp932"
    )
    * 4,
    "中文编码检测测试样本，这是一段用于测试的中文文字。".encode("gb18030") * 4,
    "한국어 인코딩 감지 테스트를 위한 샘플 텍스트입니다.".encode("cp949") * 4,
]


# Pruned scoring guarantees exact scores for the winner, position 1, and
# everything within the confusion band of the top score; matches
# statistical._PRUNE_MARGIN's guarantee (confusion band = 0.005).
_EXACT_BAND = 0.005


@pytest.mark.parametrize("data", _PRUNING_SAMPLES, ids=range(len(_PRUNING_SAMPLES)))
def test_pruned_matches_full_ranking_at_top(data: bytes):
    """Pruned scoring must return the same winner and runner-up as full scoring.

    Pruning may drop tail results, and encodings whose variants were partly
    skipped may report an understated tail score — but the winner, position
    1, and everything within the confusion band of the top score must be
    identical to the full ranking, and no pruned score may ever exceed its
    full-ranking counterpart.
    """
    candidates = get_candidates(EncodingEra.ALL)
    pruned = score_candidates(data, candidates)
    full = score_candidates(data, candidates, full_ranking=True)

    assert pruned, "pruned scoring returned no results"
    for i in range(min(2, len(full))):
        assert pruned[i].encoding == full[i].encoding
        assert pruned[i].confidence == pytest.approx(full[i].confidence, abs=1e-12)
        assert pruned[i].language == full[i].language

    full_by_enc = {r.encoding: r for r in full}
    top_conf = full[0].confidence
    for r in pruned:
        true_conf = full_by_enc[r.encoding].confidence
        # Never overstated (would corrupt the ranking) ...
        assert r.confidence <= true_conf + 1e-12
        # ... and exact for anything the confusion band can examine.
        if true_conf >= top_conf - _EXACT_BAND:
            assert r.confidence == pytest.approx(true_conf, abs=1e-12)

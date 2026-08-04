# tests/test_statistical.py
from __future__ import annotations

import pytest

from chardet.enums import EncodingEra
from chardet.models import BigramProfile, get_enc_index
from chardet.pipeline import DetectionResult

# Pruned scoring guarantees exact scores for the winner, position 1, and
# everything within the confusion band of the top score — the same band
# resolve_confusion_groups uses.
from chardet.pipeline.confusion import _CONFUSION_BAND as _EXACT_BAND
from chardet.pipeline.statistical import (
    _MIN_NONZERO_FOR_PRESCREEN,
    score_candidates,
)
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

# Each sample must produce at least _MIN_NONZERO_FOR_PRESCREEN distinct
# bigrams or score_candidates takes the unpruned path for it and the
# pruned-vs-full comparison is vacuous; test_pruning_samples_engage_pruning
# enforces that.
_PRUNING_SAMPLES = [
    "Все счастливые семьи похожи друг на друга, каждая несчастливая семья "
    "несчастлива по-своему. Все смешалось в доме Облонских. Жена узнала, "
    "что муж был в связи с бывшею в их доме француженкою-гувернанткой.".encode(
        "windows-1251"
    ),
    "Héllo wörld café résumé naïve — l'élève français è déjà qui. Der "
    "große Bär läuft über die Straße; ¡el niño español comió jamón añejo "
    "ayer! À côté du fleuve, l'œuvre était déjà finie: ação, coração, "
    "pingüim, saudação, señor, jalapeño, øre, Åse, æble, þing, smörgås, "
    "crème brûlée.".encode("windows-1252"),
    "これは日本語の文章を検出するための試験用サンプルです。吾輩は猫である。"
    "名前はまだ無い。どこで生れたかとんと見当がつかぬ。何でも薄暗いじめじめ"
    "した所でニャーニャー泣いていた事だけは記憶している。".encode("cp932"),
    "中文编码检测测试样本，这是一段用于测试的中文文字。北冥有鱼，其名为鲲。"
    "鲲之大，不知其几千里也；化而为鸟，其名为鹏。鹏之背，不知其几千里也。"
    "怒而飞，其翼若垂天之云。".encode("gb18030"),
    "한국어 인코딩 감지 테스트를 위한 샘플 텍스트입니다. 나 보기가 역겨워 "
    "가실 때에는 말없이 고이 보내 드리우리다. 영변에 약산 진달래꽃 아름 "
    "따다 가실 길에 뿌리우리다.".encode("cp949"),
]


def test_pruning_samples_engage_pruning():
    """Every sample must be large enough for the pruned path to run."""
    for i, data in enumerate(_PRUNING_SAMPLES):
        nonzero = len(BigramProfile(data).nonzero)
        assert nonzero >= _MIN_NONZERO_FOR_PRESCREEN, (
            f"sample {i}: {nonzero} distinct bigrams — pruned path not engaged"
        )


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

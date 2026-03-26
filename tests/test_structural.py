"""Tests for Stage 2b: Multi-byte structural probing."""

from __future__ import annotations

import pytest

from chardet.pipeline import PipelineContext
from chardet.pipeline.structural import (
    _analyze_big5,
    _analyze_big5hkscs,
    _analyze_cp932,
    _analyze_cp949,
    _analyze_euc_kr,
    _analyze_shift_jis,
    compute_lead_byte_diversity,
    compute_multibyte_byte_coverage,
    compute_structural_score,
)
from chardet.registry import REGISTRY


@pytest.fixture
def pipe_ctx() -> PipelineContext:
    return PipelineContext()


def test_shift_jis_scores_high_on_shift_jis_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("shift_jis")
    score = compute_structural_score(data, REGISTRY["shift_jis_2004"], pipe_ctx)
    assert score > 0.7


def test_euc_jp_scores_high_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("euc-jp")
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score > 0.7


def test_shift_jis_scores_low_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界".encode("euc-jp")
    euc_score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    sjis_score = compute_structural_score(data, REGISTRY["shift_jis_2004"], pipe_ctx)
    assert euc_score > sjis_score


def test_euc_kr_scores_high_on_korean_data(pipe_ctx: PipelineContext) -> None:
    data = "안녕하세요".encode("EUC-KR")
    score = compute_structural_score(data, REGISTRY["euc_kr"], pipe_ctx)
    assert score > 0.7


def test_gb18030_scores_high_on_chinese_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界".encode("GB18030")
    score = compute_structural_score(data, REGISTRY["gb18030"], pipe_ctx)
    assert score > 0.7


def test_big5_scores_high_on_big5_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界".encode("big5")
    score = compute_structural_score(data, REGISTRY["big5hkscs"], pipe_ctx)
    assert score > 0.7


def test_big5_trailing_lead_byte() -> None:
    """Big5 data ending with a lone lead byte should not crash."""
    # 你好 in Big5 = A740 A861, then append a lone lead byte 0xA5
    data = "你好".encode("big5") + b"\xa5"
    ratio, mb, _diversity = _analyze_big5(data)
    assert ratio > 0.0
    assert mb > 0


def test_single_byte_encoding_returns_zero(pipe_ctx: PipelineContext) -> None:
    data = b"Hello world"
    score = compute_structural_score(data, REGISTRY["iso8859-1"], pipe_ctx)
    assert score == 0.0


def test_empty_data_returns_zero(pipe_ctx: PipelineContext) -> None:
    score = compute_structural_score(b"", REGISTRY["shift_jis_2004"], pipe_ctx)
    assert score == 0.0


def test_big5hkscs_scores_high_on_big5_data(pipe_ctx: PipelineContext) -> None:
    data = "你好世界測試資料".encode("Big5-HKSCS")
    score = compute_structural_score(data, REGISTRY["big5hkscs"], pipe_ctx)
    assert score > 0.7


def test_euc_jis_2004_scores_high_on_euc_jp_data(pipe_ctx: PipelineContext) -> None:
    data = "こんにちは世界テスト".encode("EUC-JIS-2004")
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score > 0.7


def test_shift_jis_2004_scores_high_on_shift_jis_data(
    pipe_ctx: PipelineContext,
) -> None:
    data = "こんにちは世界テスト".encode("Shift-JIS-2004")
    score = compute_structural_score(data, REGISTRY["shift_jis_2004"], pipe_ctx)
    assert score > 0.7


def test_euc_jp_ss2_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 (0x8E) with invalid trail byte should not count as valid."""
    data = b"\x8e\x20"
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score == 0.0


def test_euc_jp_ss3_valid(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS3 (0x8F) with valid 3-byte JIS X 0212 sequence."""
    data = b"\x8f\xa1\xa1" * 5
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score > 0.0


def test_euc_jp_ss3_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS3 (0x8F) with invalid trail bytes should not count as valid."""
    data = b"\x8f\xa1\x20"
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score == 0.0


def test_multibyte_byte_coverage_all_ascii(pipe_ctx: PipelineContext) -> None:
    """All-ASCII data should return 0.0 coverage for a multibyte encoding."""
    data = b"Hello world plain ASCII"
    coverage = compute_multibyte_byte_coverage(
        data, REGISTRY["shift_jis_2004"], pipe_ctx, non_ascii_count=0
    )
    assert coverage == 0.0


def test_lead_byte_diversity_empty_data(pipe_ctx: PipelineContext) -> None:
    """Empty data should return 0 diversity."""
    diversity = compute_lead_byte_diversity(b"", REGISTRY["shift_jis_2004"], pipe_ctx)
    assert diversity == 0


def test_coverage_no_analyzer_returns_zero(pipe_ctx: PipelineContext) -> None:
    """An escape-protocol multibyte encoding with no analyzer returns 0.0."""
    coverage = compute_multibyte_byte_coverage(
        b"\x80\x81\x82", REGISTRY["hz"], pipe_ctx, non_ascii_count=3
    )
    assert coverage == 0.0


def test_diversity_no_analyzer_returns_256(pipe_ctx: PipelineContext) -> None:
    """An escape-protocol multibyte encoding with no analyzer returns 256."""
    diversity = compute_lead_byte_diversity(b"\x80\x81", REGISTRY["hz"], pipe_ctx)
    assert diversity == 256


def test_coverage_single_byte_encoding_returns_zero(pipe_ctx: PipelineContext) -> None:
    """A single-byte encoding should return 0.0 coverage."""
    coverage = compute_multibyte_byte_coverage(
        b"\xc0\xc1\xc2", REGISTRY["iso8859-1"], pipe_ctx, non_ascii_count=3
    )
    assert coverage == 0.0


def test_euc_jp_ss2_valid_sequence(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 (0x8E) with valid trail byte (0xA1-0xDF) should score > 0."""
    # SS2 sequences: 0x8E followed by a byte in 0xA1-0xDF (half-width katakana)
    data = b"\x8e\xa1\x8e\xb0\x8e\xdf" * 3
    score = compute_structural_score(data, REGISTRY["euc_jis_2004"], pipe_ctx)
    assert score == 1.0  # all lead bytes have valid trails


def test_euc_jp_ss2_coverage(pipe_ctx: PipelineContext) -> None:
    """EUC-JP SS2 valid sequences should contribute to multibyte byte coverage."""
    data = b"\x8e\xa1\x8e\xb0\x8e\xdf"
    coverage = compute_multibyte_byte_coverage(
        data, REGISTRY["euc_jis_2004"], pipe_ctx, non_ascii_count=6
    )
    # 6 bytes total, all are non-ASCII or SS2 pairs: mb_bytes = 6 (2 per pair * 3)
    # non_ascii bytes: 0x8e, 0xa1, 0x8e, 0xb0, 0x8e, 0xdf = 6
    assert coverage == 1.0


def test_johab_lead_byte_invalid_trail(pipe_ctx: PipelineContext) -> None:
    """Johab lead byte with an invalid trail byte should fall through (i += 1)."""
    # Lead byte 0x84 (valid Johab lead) followed by 0x20 (not in 0x31-0x7E or 0x91-0xFE)
    # This should hit the fallthrough path at line 276
    data = b"\x84\x20\x84\x0f\x84\x7f"
    score = compute_structural_score(data, REGISTRY["johab"], pipe_ctx)
    assert score == 0.0  # all trails are invalid


def test_johab_lead_byte_at_end_of_data(pipe_ctx: PipelineContext) -> None:
    """Johab lead byte at the very end of data should fall through."""
    # Lead byte 0x84 with no trail byte available
    data = b"\x84"
    score = compute_structural_score(data, REGISTRY["johab"], pipe_ctx)
    assert score == 0.0


def test_cp932_recognizes_extended_lead_bytes() -> None:
    """CP932 lead bytes 0xF0-0xFC should be recognized by _analyze_cp932."""
    # 3 pairs using CP932-extended lead bytes with valid trail bytes
    data = b"\xf0\x40\xf5\x80\xfc\x40"
    ratio, mb_bytes, diversity = _analyze_cp932(data)
    assert ratio == 1.0
    assert diversity == 3
    # 0xF0 lead=1 mb, 0x40 trail<0x80=0 mb -> 1
    # 0xF5 lead=1 mb, 0x80 trail>0x7F=1 mb -> 2
    # 0xFC lead=1 mb, 0x40 trail<0x80=0 mb -> 1
    assert mb_bytes == 4


def test_shift_jis_does_not_recognize_cp932_extended_leads() -> None:
    """Shift_JIS analyzer should NOT recognize lead bytes 0xF0-0xFC."""
    data = b"\xf0\x40\xf5\x80\xfc\x40"
    ratio, mb_bytes, diversity = _analyze_shift_jis(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_cp932_half_width_katakana_not_lead_bytes() -> None:
    """CP932 half-width katakana (0xA1-0xDF) are single bytes, not lead bytes."""
    # Pure half-width katakana — no valid multibyte pairs expected
    data = b"\xa1\xa2\xa3\xb0\xdf"
    ratio, mb_bytes, diversity = _analyze_cp932(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_cp932_mb_bytes_low_trail() -> None:
    """Trail byte < 0x80 counts 1 mb_byte (lead only); >= 0x80 counts 2."""
    # One pair: lead 0xF0, trail 0x40 (< 0x80) -> mb_bytes = 1
    low_trail = b"\xf0\x40"
    _, mb_low, _ = _analyze_cp932(low_trail)
    assert mb_low == 1

    # One pair: lead 0xF0, trail 0x80 (>= 0x80) -> mb_bytes = 2
    high_trail = b"\xf0\x80"
    _, mb_high, _ = _analyze_cp932(high_trail)
    assert mb_high == 2


def test_cp932_standard_range_still_works() -> None:
    """Standard Shift_JIS range bytes work in both analyzers."""
    data = b"\x81\x40\x9f\x7e\xe0\x80"
    sjis_ratio, _, _ = _analyze_shift_jis(data)
    cp932_ratio, _, _ = _analyze_cp932(data)
    assert sjis_ratio == 1.0
    assert cp932_ratio == 1.0


def test_cp949_recognizes_uhc_extension_bytes() -> None:
    """CP949 lead bytes 0x81-0xA0 with ASCII letter trails should be recognized."""
    # UHC extension: lead 0x81 + trail 0x41 (ASCII 'A'), lead 0x90 + trail 0x61 ('a')
    data = b"\x81\x41\x90\x61\xa0\x5a"
    ratio, mb_bytes, diversity = _analyze_cp949(data)
    assert ratio == 1.0
    assert diversity == 3
    # 0x81>0x7F=1, 0x41<0x80=0 -> 1; 0x90>0x7F=1, 0x61<0x80=0 -> 1; 0xA0>0x7F=1, 0x5A<0x80=0 -> 1
    assert mb_bytes == 3


def test_euc_kr_does_not_recognize_uhc_extension() -> None:
    """EUC-KR analyzer should NOT recognize lead bytes 0x81-0xA0 or ASCII trails."""
    data = b"\x81\x41\x90\x61\xa0\x5a"
    ratio, mb_bytes, diversity = _analyze_euc_kr(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_cp949_skips_0xc9_lead_byte() -> None:
    """0xC9 is not a valid CP949/UHC lead byte."""
    data = b"\xc9\xa1"
    ratio, mb_bytes, diversity = _analyze_cp949(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_cp949_standard_euc_kr_range_still_works() -> None:
    """Standard EUC-KR range bytes work in both analyzers."""
    data = b"\xa1\xa1\xb0\xfe\xfd\xa1"
    euc_ratio, _, _ = _analyze_euc_kr(data)
    cp949_ratio, _, _ = _analyze_cp949(data)
    assert euc_ratio == 1.0
    assert cp949_ratio == 1.0


def test_cp949_mb_bytes_ascii_trail() -> None:
    """Trail byte in ASCII range counts 1 mb_byte (lead only); high trail counts 2."""
    # Lead 0x81 + trail 0x41 (ASCII) -> mb_bytes = 1
    ascii_trail = b"\x81\x41"
    _, mb_low, _ = _analyze_cp949(ascii_trail)
    assert mb_low == 1

    # Lead 0x81 + trail 0xA1 (high byte) -> mb_bytes = 2
    high_trail = b"\x81\xa1"
    _, mb_high, _ = _analyze_cp949(high_trail)
    assert mb_high == 2


def test_big5hkscs_recognizes_extended_lead_bytes() -> None:
    """Big5-HKSCS lead bytes 0x87-0xA0 and 0xFA-0xFE should be recognized."""
    # HKSCS extension: leads below Big5's 0xA1 floor and above 0xF9 ceiling
    data = b"\x87\x40\x90\xa1\xfa\x7e\xfe\xfe"
    ratio, mb_bytes, diversity = _analyze_big5hkscs(data)
    assert ratio == 1.0
    assert diversity == 4
    # 0x87+0x40: lead=1, trail<0x80=0 -> 1
    # 0x90+0xA1: lead=1, trail>0x7F=1 -> 2
    # 0xFA+0x7E: lead=1, trail<0x80=0 -> 1
    # 0xFE+0xFE: lead=1, trail>0x7F=1 -> 2
    assert mb_bytes == 6


def test_big5_does_not_recognize_hkscs_extension() -> None:
    """Big5 analyzer should NOT recognize lead bytes 0x87-0xA0 or 0xFA-0xFE."""
    # Use only HKSCS-extended lead bytes that are outside Big5's 0xA1-0xF9 range,
    # with ASCII trail bytes so skipped leads don't accidentally form Big5 pairs.
    data = b"\x87\x41\x90\x42\xfa\x43\xfe\x44"
    ratio, mb_bytes, diversity = _analyze_big5(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_big5hkscs_standard_big5_range_still_works() -> None:
    """Standard Big5 range bytes work in both analyzers."""
    data = b"\xa1\x40\xc0\x7e\xf9\xfe"
    big5_ratio, _, _ = _analyze_big5(data)
    hkscs_ratio, _, _ = _analyze_big5hkscs(data)
    assert big5_ratio == 1.0
    assert hkscs_ratio == 1.0


def test_big5hkscs_mb_bytes_low_trail() -> None:
    """Trail byte < 0x80 counts 1 mb_byte (lead only); >= 0x80 counts 2."""
    # Lead 0x87 + trail 0x40 -> mb_bytes = 1
    low_trail = b"\x87\x40"
    _, mb_low, _ = _analyze_big5hkscs(low_trail)
    assert mb_low == 1

    # Lead 0x87 + trail 0xA1 -> mb_bytes = 2
    high_trail = b"\x87\xa1"
    _, mb_high, _ = _analyze_big5hkscs(high_trail)
    assert mb_high == 2


# ---------------------------------------------------------------------------
# Lead byte at end of data (fallthrough coverage)
# ---------------------------------------------------------------------------


def test_cp932_lead_byte_at_end_of_data() -> None:
    """CP932 lead byte at the very end of data should fall through."""
    data = b"\xf0"
    ratio, mb_bytes, diversity = _analyze_cp932(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_cp949_lead_byte_at_end_of_data() -> None:
    """CP949 lead byte at the very end of data should fall through."""
    data = b"\x81"
    ratio, mb_bytes, diversity = _analyze_cp949(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0


def test_big5hkscs_lead_byte_at_end_of_data() -> None:
    """Big5-HKSCS lead byte at the very end of data should fall through."""
    data = b"\x87"
    ratio, mb_bytes, diversity = _analyze_big5hkscs(data)
    assert ratio == 0.0
    assert mb_bytes == 0
    assert diversity == 0

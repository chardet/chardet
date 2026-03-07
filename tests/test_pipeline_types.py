# tests/test_pipeline_types.py
from __future__ import annotations

import pytest

from chardet.pipeline import DetectionResult, PipelineContext


def test_detection_result_fields():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language="en")
    assert r.encoding == "UTF-8"
    assert r.confidence == 0.99
    assert r.language == "en"


def test_detection_result_to_dict():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language=None)
    d = r.to_dict()
    assert d == {"encoding": "UTF-8", "confidence": 0.99, "language": None}


def test_detection_result_none():
    r = DetectionResult(encoding=None, confidence=0.0, language=None)
    assert r.to_dict() == {"encoding": None, "confidence": 0.0, "language": None}


def test_detection_result_is_frozen():
    import dataclasses

    r = DetectionResult(encoding="UTF-8", confidence=0.99, language=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.encoding = "ASCII"


def test_pipeline_context_defaults():
    ctx = PipelineContext()
    assert ctx.analysis_cache == {}
    assert ctx.non_ascii_count is None
    assert ctx.mb_scores == {}


def test_pipeline_context_is_mutable():
    ctx = PipelineContext()
    ctx.analysis_cache["utf-8"] = (0.9, 10, 5)
    ctx.non_ascii_count = 42
    ctx.mb_scores["shift_jis"] = 0.85
    assert ctx.analysis_cache["utf-8"] == (0.9, 10, 5)
    assert ctx.non_ascii_count == 42
    assert ctx.mb_scores["shift_jis"] == 0.85


def test_pipeline_context_mb_coverage():
    ctx = PipelineContext()
    assert ctx.mb_coverage == {}
    ctx.mb_coverage["shift_jis"] = 0.95
    assert ctx.mb_coverage["shift_jis"] == 0.95

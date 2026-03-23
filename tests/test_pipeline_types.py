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
    assert d == {
        "encoding": "UTF-8",
        "confidence": 0.99,
        "language": None,
        "mime_type": None,
    }


def test_detection_result_none():
    r = DetectionResult(encoding=None, confidence=0.0, language=None)
    assert r.to_dict() == {
        "encoding": None,
        "confidence": 0.0,
        "language": None,
        "mime_type": None,
    }


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


def test_pipeline_context_is_not_frozen():
    """PipelineContext must not be frozen — pipeline stages mutate it."""
    assert not PipelineContext.__dataclass_params__.frozen
    ctx = PipelineContext()
    ctx.non_ascii_count = 42
    assert ctx.non_ascii_count == 42


def test_pipeline_context_mb_coverage():
    ctx = PipelineContext()
    assert ctx.mb_coverage == {}
    ctx.mb_coverage["shift_jis"] = 0.95
    assert ctx.mb_coverage["shift_jis"] == 0.95


def test_detection_result_mime_type_default():
    r = DetectionResult(encoding="UTF-8", confidence=0.99, language="en")
    assert r.mime_type is None


def test_detection_result_mime_type_explicit():
    r = DetectionResult(
        encoding=None, confidence=1.0, language=None, mime_type="image/png"
    )
    assert r.mime_type == "image/png"


def test_detection_result_to_dict_includes_mime_type():
    r = DetectionResult(
        encoding="UTF-8", confidence=0.99, language=None, mime_type="text/plain"
    )
    d = r.to_dict()
    assert d == {
        "encoding": "UTF-8",
        "confidence": 0.99,
        "language": None,
        "mime_type": "text/plain",
    }

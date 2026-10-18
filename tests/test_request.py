# tests/test_request.py
"""Tests for :class:`chardet._request.DetectionRequest`."""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import patch

import pytest

import chardet
from chardet import UniversalDetector, output_names
from chardet._request import DetectionRequest
from chardet.enums import EncodingEra
from chardet.pipeline import DetectionResult, orchestrator

_GREEK = "Καλημέρα κόσμε, αυτό είναι ένα δοκιμαστικό κείμενο στα ελληνικά.".encode(
    "iso8859-7"
)
_JAPANESE = "日本語のテキストです。文字コードを判定します。".encode("euc_jp")
_FRENCH = "Le café était fermé, alors nous sommes allés à la gare.".encode("cp1252")

_INPUTS = {
    "greek": _GREEK,
    "japanese": _JAPANESE,
    "french": _FRENCH,
    "ascii": b"Hello, world!",
    "empty": b"",
    "binary": b"\x00\x01\x02\x03" * 20,
}

_OPTIONS: dict[str, dict[str, Any]] = {
    "defaults": {},
    "superset": {"prefer_superset": True},
    "raw-names": {"compat_names": False},
    "superset-raw": {"prefer_superset": True, "compat_names": False},
    "include": {"include_encodings": ["iso-8859-7", "utf-8", "euc-jp"]},
    "exclude-superset": {
        "prefer_superset": True,
        "exclude_encodings": ["windows-1253"],
    },
    "small-window": {"max_bytes": 16},
    "modern-era": {"encoding_era": EncodingEra.MODERN_WEB},
}


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


def test_resolve_defaults_match_the_dataclass_defaults():
    assert DetectionRequest.resolve() == DetectionRequest()


def test_resolve_canonicalizes_encoding_names():
    request = DetectionRequest.resolve(
        include_encodings=["UTF-8", "latin-1"],
        exclude_encodings=["Shift_JIS"],
        no_match_encoding="windows-1252",
        empty_input_encoding="ASCII",
    )
    assert request.include_encodings == frozenset({"utf-8", "iso8859-1"})
    assert request.exclude_encodings == frozenset({"shift_jis_2004"})
    assert request.no_match_encoding == "cp1252"
    assert request.empty_input_encoding == "ascii"


@pytest.mark.parametrize("max_bytes", [0, -1, True, 1.5])
def test_resolve_rejects_bad_max_bytes(max_bytes: float):
    with pytest.raises(ValueError, match="max_bytes"):
        DetectionRequest.resolve(max_bytes=max_bytes)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"include_encodings": ["not-a-codec"]},
        {"exclude_encodings": ["not-a-codec"]},
        {"include_encodings": []},
        {"no_match_encoding": "not-a-codec"},
        {"empty_input_encoding": "not-a-codec"},
    ],
)
def test_resolve_rejects_bad_encoding_options(kwargs: dict[str, Any]):
    with pytest.raises(ValueError, match="encoding"):
        DetectionRequest.resolve(**kwargs)


def test_resolve_folds_should_rename_legacy_into_prefer_superset():
    with pytest.warns(DeprecationWarning, match="should_rename_legacy"):
        request = DetectionRequest.resolve(should_rename_legacy=True)
    assert request.prefer_superset


def test_resolve_warns_about_chunk_size():
    with pytest.warns(DeprecationWarning, match="chunk_size"):
        DetectionRequest.resolve(chunk_size=1024)


# ---------------------------------------------------------------------------
# run + render against the public adapters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("options", _OPTIONS.values(), ids=_OPTIONS.keys())
@pytest.mark.parametrize("data", _INPUTS.values(), ids=_INPUTS.keys())
def test_run_and_render_match_detect(data: bytes, options: dict[str, Any]):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        request = DetectionRequest.resolve(**options)
        window = data[: request.max_bytes]
        rendered = request.render(request.run(data), window)
        assert rendered == [chardet.detect(data, **options)]

        ranking = request.run(data, full_ranking=True)
        assert request.render(ranking, window, all_results=True) == (
            chardet.detect_all(data, **options)
        )
        assert request.render(
            ranking, window, all_results=True, ignore_threshold=True
        ) == chardet.detect_all(data, ignore_threshold=True, **options)


@pytest.mark.parametrize("options", _OPTIONS.values(), ids=_OPTIONS.keys())
@pytest.mark.parametrize("data", _INPUTS.values(), ids=_INPUTS.keys())
def test_run_and_render_match_universal_detector(data: bytes, options: dict[str, Any]):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        request = DetectionRequest.resolve(**options)
        window = data[: request.max_bytes]
        expected = request.render(
            request.run(window, input_truncated=len(data) > len(window)), window
        )[0]
        detector = UniversalDetector(**options)
        detector.feed(data)
        assert detector.close() == expected
    assert detector.result == expected


def test_universal_detector_result_is_a_fresh_copy():
    detector = UniversalDetector()
    detector.feed(_GREEK)
    first = detector.close()
    first["encoding"] = "mutated"
    assert detector.result["encoding"] == "ISO-8859-7"
    assert detector.result is not detector.result


def test_render_lists_each_name_once():
    """Two candidates remapped onto one superset name keep the first."""
    request = DetectionRequest(prefer_superset=True)
    results = [
        DetectionResult("iso8859-7", 0.6, "el", "text/plain"),
        DetectionResult("cp1253", 0.5, "el", "text/plain"),
        DetectionResult("iso8859-1", 0.1, "en", "text/plain"),
    ]
    rendered = request.render(results, b"abc", all_results=True)
    assert [d["encoding"] for d in rendered] == ["Windows-1253"]
    rendered = request.render(results, b"abc", all_results=True, ignore_threshold=True)
    assert [(d["encoding"], d["confidence"]) for d in rendered] == [
        ("Windows-1253", 0.6),
        ("Windows-1252", 0.1),
    ]


def test_render_keeps_low_confidence_results_when_nothing_clears_the_threshold():
    request = DetectionRequest()
    results = [DetectionResult("cp1252", 0.1, None, "text/plain")]
    rendered = request.render(results, b"abc", all_results=True)
    assert [d["encoding"] for d in rendered] == ["Windows-1252"]


# ---------------------------------------------------------------------------
# Whole-window decodes at the public edge
# ---------------------------------------------------------------------------


@pytest.fixture
def window_decodes() -> Iterator[list[str]]:
    """Record every decode the output-name transforms run.

    ``_request``, ``output_names`` and ``_utils`` are interpreted on every
    build, so the patch is observed on compiled builds too.
    """
    calls: list[str] = []
    tolerant = output_names.decodes_without_error
    strict = output_names.decodes_completely

    def count_tolerant(data: bytes, encoding: str) -> bool:
        calls.append(encoding)
        return tolerant(data, encoding)

    def count_strict(data: bytes, encoding: str) -> bool:
        calls.append(encoding)
        return strict(data, encoding)

    with (
        patch.object(output_names, "decodes_without_error", count_tolerant),
        patch.object(output_names, "decodes_completely", count_strict),
    ):
        yield calls


@pytest.mark.parametrize(
    ("encoding", "window", "options", "expected_decodes"),
    [
        # Measured on 7.7.0 main: detect() pays nothing for a name whose
        # display codec is its own, one decode for a display name that is
        # narrower, and one for a superset remap.  No result pays two: no
        # name is both remappable and narrowed.
        ("cp1252", _FRENCH, {}, []),
        ("cp1252", _FRENCH, {"prefer_superset": True}, []),
        ("iso8859-1", b"caf\xe9", {}, []),
        ("iso8859-1", b"caf\xe9", {"prefer_superset": True}, ["cp1252"]),
        ("euc_jis_2004", _JAPANESE, {}, ["EUC-JP"]),
        ("euc_jis_2004", _JAPANESE, {"prefer_superset": True}, ["EUC-JP"]),
        ("euc_jis_2004", _JAPANESE, {"compat_names": False}, []),
        ("euc_kr", "한국어".encode("euc_kr"), {"prefer_superset": True}, ["cp949"]),
    ],
)
def test_render_decode_budget(
    window_decodes: list[str],
    encoding: str,
    window: bytes,
    options: dict[str, Any],
    expected_decodes: list[str],
):
    request = DetectionRequest.resolve(**options)
    request.render([DetectionResult(encoding, 0.9, None, "text/plain")], window)
    assert window_decodes == expected_decodes


def test_render_all_results_decodes_once_per_result_at_most(
    window_decodes: list[str],
):
    request = DetectionRequest(prefer_superset=True)
    results = [
        DetectionResult("iso8859-7", 0.6, "el", "text/plain"),
        DetectionResult("cp1253", 0.5, "el", "text/plain"),
        DetectionResult("euc_jis_2004", 0.4, "ja", "text/plain"),
    ]
    request.render(results, _GREEK, all_results=True)
    assert window_decodes == ["cp1253", "EUC-JP"]


def test_universal_detector_renders_once_per_close(window_decodes: list[str]):
    """``result`` copies the rendered dict instead of re-checking the buffer."""
    detector = UniversalDetector()
    detector.feed(_JAPANESE)
    detector.close()
    for _ in range(3):
        assert detector.result["encoding"] == "EUC-JP"
    assert window_decodes == ["EUC-JP"]


# ---------------------------------------------------------------------------
# Warnings point at the caller's line
# ---------------------------------------------------------------------------


def _warning_files(category: type[Warning], call: Callable[[], object]) -> list[str]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        call()
    return [w.filename for w in caught if issubclass(w.category, category)]


def _close_detector(include_encodings: list[str]) -> None:
    detector = UniversalDetector(include_encodings=include_encodings)
    detector.feed(b"\x80\x81")
    detector.close()


@pytest.mark.parametrize(
    "call",
    [
        lambda: chardet.detect(b"abc", chunk_size=1024),
        lambda: chardet.detect_all(b"abc", chunk_size=1024),
        lambda: chardet.detect(b"abc", should_rename_legacy=True),
        lambda: chardet.detect_all(b"abc", should_rename_legacy=True),
        lambda: UniversalDetector(should_rename_legacy=True),
    ],
    ids=[
        "detect-chunk_size",
        "detect_all-chunk_size",
        "detect-should_rename_legacy",
        "detect_all-should_rename_legacy",
        "UniversalDetector-should_rename_legacy",
    ],
)
def test_deprecation_warnings_point_at_the_caller(call: Callable[[], object]):
    assert _warning_files(DeprecationWarning, call) == [__file__]


@pytest.mark.skipif(
    orchestrator.__file__.endswith((".so", ".pyd")),
    reason="compiled pipeline functions add no Python frames to count",
)
@pytest.mark.parametrize(
    "call",
    [
        lambda: chardet.detect(b"\x80\x81", include_encodings=["ascii"]),
        lambda: chardet.detect_all(b"\x80\x81", include_encodings=["ascii"]),
        lambda: _close_detector(include_encodings=["ascii"]),
        lambda: chardet.detect(b"", include_encodings=["ascii"]),
    ],
    ids=["detect", "detect_all", "UniversalDetector.close", "detect-empty"],
)
def test_fallback_warning_points_at_the_caller(call: Callable[[], object]):
    assert _warning_files(UserWarning, call) == [__file__]

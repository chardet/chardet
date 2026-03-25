# tests/test_benchmark.py
"""Performance regression tests.

Default-tier tests (ratio, scaling) run with the normal test suite and are
hardware-independent.  Benchmark-tier tests (absolute thresholds) run only
with ``pytest -m benchmark``.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from pathlib import Path

import pytest

import chardet
from chardet.models import _load_models_data, get_enc_index
from chardet.pipeline.confusion import load_confusion_data
from chardet.registry import get_candidates, lookup_encoding

# ---------------------------------------------------------------------------
# Test data — hardcoded byte literals, no external dependencies
# ---------------------------------------------------------------------------

# ~532 bytes of Tolstoy (Anna Karenina) encoded as windows-1251.
# Routes through the full pipeline to statistical scoring.
CYRILLIC_WIN1251 = (
    b"\xc2\xf1\xe5 \xf1\xf7\xe0\xf1\xf2\xeb\xe8\xe2\xfb\xe5 \xf1\xe5\xec"
    b"\xfc\xe8 \xef\xee\xf5\xee\xe6\xe8 \xe4\xf0\xf3\xe3 \xed\xe0 \xe4\xf0"
    b"\xf3\xe3\xe0, \xea\xe0\xe6\xe4\xe0\xff \xed\xe5\xf1\xf7\xe0\xf1\xf2"
    b"\xeb\xe8\xe2\xe0\xff \xf1\xe5\xec\xfc\xff \xed\xe5\xf1\xf7\xe0\xf1"
    b"\xf2\xeb\xe8\xe2\xe0 \xef\xee-\xf1\xe2\xee\xe5\xec\xf3. \xc2\xf1\xe5"
    b" \xf1\xec\xe5\xf8\xe0\xeb\xee\xf1\xfc \xe2 \xe4\xee\xec\xe5 \xce\xe1"
    b"\xeb\xee\xed\xf1\xea\xe8\xf5. \xc6\xe5\xed\xe0 \xf3\xe7\xed\xe0\xeb"
    b"\xe0, \xf7\xf2\xee \xec\xf3\xe6 \xe1\xfb\xeb \xe2 \xf1\xe2\xff\xe7"
    b"\xe8 \xf1 \xe1\xfb\xe2\xf8\xe5\xfe \xe2 \xe8\xf5 \xe4\xee\xec\xe5"
    b" \xf4\xf0\xe0\xed\xf6\xf3\xe6\xe5\xed\xea\xee\xfe-\xe3\xf3\xe2\xe5"
    b"\xf0\xed\xe0\xed\xf2\xea\xee\xe9, \xe8 \xee\xe1\xfa\xff\xe2\xe8\xeb"
    b"\xe0 \xec\xf3\xe6\xf3, \xf7\xf2\xee \xed\xe5 \xec\xee\xe6\xe5\xf2"
    b" \xe6\xe8\xf2\xfc \xf1 \xed\xe8\xec \xe2 \xee\xe4\xed\xee\xec \xe4"
    b"\xee\xec\xe5. \xcf\xee\xeb\xee\xe6\xe5\xed\xe8\xe5 \xfd\xf2\xee \xef"
    b"\xf0\xee\xe4\xee\xeb\xe6\xe0\xeb\xee\xf1\xfc \xf3\xe6\xe5 \xf2\xf0"
    b"\xe5\xf2\xe8\xe9 \xe4\xe5\xed\xfc \xe8 \xf7\xf3\xe2\xf1\xf2\xe2\xee"
    b"\xe2\xe0\xeb\xee\xf1\xfc \xe8 \xf1\xe0\xec\xe8\xec\xe8 \xf1\xf3\xef"
    b"\xf0\xf3\xe3\xe0\xec\xe8, \xe8 \xe2\xf1\xe5\xec\xe8 \xf7\xeb\xe5\xed"
    b"\xe0\xec\xe8 \xf1\xe5\xec\xfc\xe8, \xe8 \xe4\xee\xec\xee\xf7\xe0\xe4"
    b"\xf6\xe0\xec\xe8. \xc2\xf1\xe5 \xf7\xeb\xe5\xed\xfb \xf1\xe5\xec\xfc"
    b"\xe8 \xe8 \xe4\xee\xec\xee\xf7\xe0\xe4\xf6\xfb \xf7\xf3\xe2\xf1\xf2"
    b"\xe2\xee\xe2\xe0\xeb\xe8, \xf7\xf2\xee \xed\xe5\xf2 \xf1\xec\xfb\xf1"
    b"\xeb\xe0 \xe2 \xe8\xf5 \xf1\xee\xe6\xe8\xf2\xe5\xeb\xfc\xf1\xf2\xe2"
    b"\xe5 \xe8 \xf7\xf2\xee \xed\xe0 \xea\xe0\xe6\xe4\xee\xec \xef\xee\xf1"
    b"\xf2\xee\xff\xeb\xee\xec \xe4\xe2\xee\xf0\xe5 \xf1\xeb\xf3\xf7\xe0"
    b"\xe9\xed\xee \xf1\xee\xf8\xe5\xe4\xf8\xe8\xe5\xf1\xff \xeb\xfe\xe4"
    b"\xe8 \xe1\xee\xeb\xe5\xe5 \xf1\xe2\xff\xe7\xe0\xed\xfb \xec\xe5\xe6"
    b"\xe4\xf3 \xf1\xee\xe1\xee\xe9."
)

ASCII_DATA = b"Hello world, this is a plain ASCII text." * 100
BOM_DATA = b"\xef\xbb\xbfHello world" * 100
UTF8_DATA = "H\u00e9llo w\u00f6rld caf\u00e9 r\u00e9sum\u00e9 na\u00efve".encode() * 100
MARKUP_DATA = b'<html><head><meta charset="windows-1252"></head>' + b"x" * 500

# ISO-2022-JP: ESC $ B switches to JIS X 0208, ESC ( B switches back to ASCII.
# Content is "これはテストです" repeated.
ESCAPE_ISO2022JP = b"\x1b$B$3$l$O%F%9%H$G$9\x1b(B" * 10

# UTF-16-LE without BOM — null-byte interleaving triggers stage 1a+.
UTF16LE_NOBOM = (
    "Hello world, this is a test of UTF-16 encoding detection.".encode("utf-16-le") * 10
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ITERS_RATIO = 200
_ITERS_SCALING = 100
_ITERS_THRESHOLD = 200


def _median_time(func: Callable[[], object], n: int) -> float:
    """Run *func* n times and return the median elapsed time in seconds."""
    times = []
    for _ in range(n):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def _clear_all_caches():
    """Clear all functools.cache-decorated functions to simulate cold start."""
    _load_models_data.cache_clear()
    get_enc_index.cache_clear()
    get_candidates.cache_clear()
    lookup_encoding.cache_clear()
    load_confusion_data.cache_clear()


def _make_scaled_input(base: bytes, target_bytes: int) -> bytes:
    """Repeat *base* to reach at least *target_bytes*.

    Returns a whole number of repetitions (no mid-sequence truncation) so
    that multi-byte encodings like UTF-8 are not broken by a partial
    character at the end.
    """
    repeats = max(1, target_bytes // len(base))
    return base * repeats


# ---------------------------------------------------------------------------
# Layer 1: Ratio tests (default tier — hardware-independent)
# ---------------------------------------------------------------------------

# mypyc widens the gap between fast-path and statistical detection;
# pure Python still needs headroom so use a lower threshold.
_HAS_MYPYC = any(Path(chardet.__file__).parent.rglob("*.so")) or any(
    Path(chardet.__file__).parent.rglob("*.pyd")
)
_MIN_SPEEDUP = 3 if _HAS_MYPYC else 1.5


@pytest.mark.parametrize(
    ("label", "fast_data"),
    [
        ("BOM", BOM_DATA),
        ("UTF-16", UTF16LE_NOBOM),
        ("Escape", ESCAPE_ISO2022JP),
        ("Markup", MARKUP_DATA),
        ("ASCII", ASCII_DATA),
        ("UTF-8", UTF8_DATA),
    ],
    ids=["BOM", "UTF-16", "Escape", "Markup", "ASCII", "UTF-8"],
)
def test_ratio_fast_vs_statistical(label: str, fast_data: bytes):
    fast = _median_time(lambda: chardet.detect(fast_data), _ITERS_RATIO)
    slow = _median_time(lambda: chardet.detect(CYRILLIC_WIN1251), _ITERS_RATIO)
    ratio = slow / fast
    assert ratio >= _MIN_SPEEDUP, (
        f"{label} not fast enough vs statistical: {ratio:.1f}x (need {_MIN_SPEEDUP}x)"
    )


def test_ratio_detect_vs_detect_all():
    fast = _median_time(lambda: chardet.detect(CYRILLIC_WIN1251), _ITERS_RATIO)
    slow = _median_time(lambda: chardet.detect_all(CYRILLIC_WIN1251), _ITERS_RATIO)
    ratio = slow / fast
    # detect_all has some overhead but should not be dramatically slower.
    # Use a generous upper bound: detect_all should be no more than 5x slower.
    assert ratio < 5, f"detect_all too slow vs detect: {ratio:.1f}x (max 5x)"


def test_ratio_cold_vs_warm_model_loading():
    # Ensure models are loaded first (warm state)
    chardet.detect(CYRILLIC_WIN1251)

    # Measure warm median
    warm = _median_time(lambda: chardet.detect(CYRILLIC_WIN1251), _ITERS_RATIO)

    # Clear all caches to simulate cold start
    _clear_all_caches()

    # Measure single cold call
    start = time.perf_counter()
    chardet.detect(CYRILLIC_WIN1251)
    cold = time.perf_counter() - start

    ratio = cold / warm
    assert ratio < 30, f"Cold start too slow vs warm: {ratio:.1f}x (max 30x)"


# ---------------------------------------------------------------------------
# Layer 2: Scaling tests (default tier — hardware-independent)
# ---------------------------------------------------------------------------

_SCALING_SIZES = [1024, 2048, 4096, 8192]
_MAX_SCALING_RATIO = 3.0  # time(2N)/time(N) must be below this


def test_scaling_statistical():
    times = {}
    for size in _SCALING_SIZES:
        data = _make_scaled_input(CYRILLIC_WIN1251, size)
        times[size] = _median_time(lambda d=data: chardet.detect(d), _ITERS_SCALING)

    for i in range(len(_SCALING_SIZES) - 1):
        small = _SCALING_SIZES[i]
        large = _SCALING_SIZES[i + 1]
        ratio = times[large] / times[small]
        assert ratio < _MAX_SCALING_RATIO, (
            f"Statistical scaling {small}->{large}: {ratio:.2f}x "
            f"(max {_MAX_SCALING_RATIO}x)"
        )


def test_scaling_utf8():
    times = {}
    for size in _SCALING_SIZES:
        data = _make_scaled_input(UTF8_DATA, size)
        times[size] = _median_time(lambda d=data: chardet.detect(d), _ITERS_SCALING)

    for i in range(len(_SCALING_SIZES) - 1):
        small = _SCALING_SIZES[i]
        large = _SCALING_SIZES[i + 1]
        ratio = times[large] / times[small]
        assert ratio < _MAX_SCALING_RATIO, (
            f"UTF-8 scaling {small}->{large}: {ratio:.2f}x (max {_MAX_SCALING_RATIO}x)"
        )


# ---------------------------------------------------------------------------
# Layer 3: Absolute threshold tests (benchmark tier — -m benchmark only)
#
# Thresholds are initial estimates and should be tuned after first run.
# ---------------------------------------------------------------------------

pytestmark_benchmark = pytest.mark.benchmark


@pytestmark_benchmark
def test_threshold_statistical():
    median_s = _median_time(lambda: chardet.detect(CYRILLIC_WIN1251), _ITERS_THRESHOLD)
    median_ms = median_s * 1000
    assert median_ms < 5, f"Statistical detection too slow: {median_ms:.2f}ms"


@pytestmark_benchmark
def test_threshold_ascii():
    median_s = _median_time(lambda: chardet.detect(ASCII_DATA), _ITERS_THRESHOLD)
    median_ms = median_s * 1000
    assert median_ms < 2, f"ASCII detection too slow: {median_ms:.2f}ms"


@pytestmark_benchmark
def test_threshold_bom():
    median_s = _median_time(lambda: chardet.detect(BOM_DATA), _ITERS_THRESHOLD)
    median_ms = median_s * 1000
    assert median_ms < 2, f"BOM detection too slow: {median_ms:.2f}ms"


@pytestmark_benchmark
def test_threshold_utf8():
    median_s = _median_time(lambda: chardet.detect(UTF8_DATA), _ITERS_THRESHOLD)
    median_ms = median_s * 1000
    assert median_ms < 2, f"UTF-8 detection too slow: {median_ms:.2f}ms"


@pytestmark_benchmark
def test_threshold_cold_model_load():
    # Warm up first
    chardet.detect(CYRILLIC_WIN1251)
    _clear_all_caches()

    start = time.perf_counter()
    chardet.detect(CYRILLIC_WIN1251)
    cold_ms = (time.perf_counter() - start) * 1000
    assert cold_ms < 100, f"Cold model load too slow: {cold_ms:.2f}ms"


@pytestmark_benchmark
def test_threshold_detect_all():
    median_s = _median_time(
        lambda: chardet.detect_all(CYRILLIC_WIN1251), _ITERS_THRESHOLD
    )
    median_ms = median_s * 1000
    assert median_ms < 5, f"detect_all too slow: {median_ms:.2f}ms"

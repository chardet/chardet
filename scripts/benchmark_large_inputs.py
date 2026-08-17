#!/usr/bin/env python
"""Benchmark detection latency on large inputs with ``max_bytes=len(data)``.

Synthetic single-encoding buffers at several sizes, timed with the full
examination window (no default cap).  If charset-normalizer is importable it
is measured too, **interleaved** trial by trial with chardet — thermal drift
makes back-to-back blocks lie by ~25%, so only interleaved A/B numbers are
comparable.

Run against the working tree::

    uv run python scripts/benchmark_large_inputs.py

Run against a compiled wheel plus charset-normalizer (the configuration a
PyPI user actually gets)::

    uv run python scripts/benchmark_large_inputs.py --build-compiled
    uv run --no-project --with <printed wheel path> --with charset-normalizer \\
        python scripts/benchmark_large_inputs.py
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SIZES_MIB = (1, 32, 272)

# (label, text, codec) — text repeats to fill each size.
CORPORA = (
    (
        "utf-8",
        "Le cœur a ses raisons que la raison ne connaît point. Être ou ne "
        "pas être, telle est la question. Ça alors! ",
        "utf-8",
    ),
    (
        "cp1252",
        "Le cœur a ses raisons que la raison ne connaît point. Être ou ne "
        "pas être, telle est la question. Ça alors! ",
        "cp1252",
    ),
    (
        "shift_jis",
        "吾輩は猫である。名前はまだ無い。どこで生れたかとんと見当がつかぬ。",
        "shift_jis",
    ),
)


def _build(text: str, codec: str, size_mib: int) -> bytes:
    chunk = text.encode(codec)
    return chunk * (size_mib * 1024 * 1024 // len(chunk))


def _detectors() -> dict[str, Callable[[bytes], str | None]]:
    import chardet  # noqa: PLC0415

    detectors: dict[str, Callable[[bytes], str | None]] = {}

    def _chardet(data: bytes) -> str | None:
        return chardet.detect(data, max_bytes=len(data))["encoding"]

    detectors[f"chardet {chardet.__version__}"] = _chardet

    try:
        import charset_normalizer  # noqa: PLC0415
    except ImportError:
        print("note: charset-normalizer not importable, measuring chardet only")
    else:

        def _normalizer(data: bytes) -> str | None:
            return charset_normalizer.detect(data)["encoding"]

        detectors[f"charset-normalizer {charset_normalizer.__version__}"] = _normalizer

    return detectors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        metavar="N",
        help="Interleaved rounds per cell (default: 5); the median is reported",
    )
    parser.add_argument(
        "--build-compiled",
        action="store_true",
        help="Build the compiled wheel into dist/ and print the run command",
    )
    args = parser.parse_args()

    if args.build_compiled:
        import tempfile  # noqa: PLC0415

        from detector_env import build_compiled_wheel  # noqa: PLC0415

        root = Path(__file__).resolve().parent.parent
        # A fresh directory: build_compiled_wheel returns "the" wheel it
        # finds in out_dir, so a populated dist/ would hand back a stale one.
        out_dir = Path(tempfile.mkdtemp(prefix="chardet-large-bench-"))
        wheel = build_compiled_wheel(root, out_dir)
        print(f"Built: {wheel}")
        print(
            "Run:\n  uv run --no-project"
            f" --with {wheel} --with charset-normalizer"
            f" python {Path(__file__).resolve()}"
        )
        return

    detectors = _detectors()
    # Warm up model loads and import costs outside the timed region.
    for detect in detectors.values():
        detect(b"warmup bytes: h\xc3\xa9llo")

    for label, text, codec in CORPORA:
        for size_mib in SIZES_MIB:
            data = _build(text, codec, size_mib)
            timings: dict[str, list[float]] = {name: [] for name in detectors}
            verdicts: dict[str, str | None] = {}
            for _ in range(args.rounds):
                # Interleave detectors within each round.
                for name, detect in detectors.items():
                    t0 = time.perf_counter()
                    verdicts[name] = detect(data)
                    timings[name].append(time.perf_counter() - t0)
            del data
            for name in detectors:
                median = statistics.median(timings[name])
                print(
                    f"{label:>10} {size_mib:>4} MiB  {name:<28} "
                    f"{median * 1000:>9.1f} ms  -> {verdicts[name]}"
                )


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Benchmark a single encoding detector: timing and accuracy.

NO tracemalloc — import times and detection times are measured cleanly
with ``time.perf_counter()`` only.

Can be run standalone for human-readable output, or with ``--json-only`` for
machine-readable JSON (used by ``compare_detectors.py``).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark a single encoding detector (timing only).",
    )
    parser.add_argument(
        "--detector",
        choices=["chardet", "charset-normalizer", "cchardet"],
        default="chardet",
        help="Detector library to benchmark (default: chardet)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("tests/data"),
        help="Path to test data directory (default: tests/data)",
    )
    parser.add_argument(
        "--encoding-era",
        choices=["all", "modern_web", "none"],
        default="all",
        help=(
            "Encoding era for chardet.detect(): "
            "'all' (default) for EncodingEra.ALL, "
            "'modern_web' for EncodingEra.MODERN_WEB, "
            "'none' to omit (for chardet < 6.0)"
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        default=False,
        help="Print only JSON output (for consumption by other scripts)",
    )
    parser.add_argument(
        "--pure",
        action="store_true",
        default=False,
        help="Abort if mypyc .so/.pyd files are present (ensure pure-Python measurement)",
    )
    args = parser.parse_args()

    if args.pure and args.detector == "chardet":
        from utils import abort_if_mypyc_compiled

        abort_if_mypyc_compiled()

    data_dir: Path = args.data_dir.resolve()
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    from utils import collect_test_files

    test_files = collect_test_files(data_dir)
    if not test_files:
        print("ERROR: no test files found!", file=sys.stderr)
        sys.exit(1)

    # Pre-read all file data so I/O doesn't affect timing
    all_data = [(enc, lang, fp, fp.read_bytes()) for enc, lang, fp in test_files]

    # Import detector and build detect function — timed with perf_counter only
    if args.detector == "chardet" and args.encoding_era != "none":
        t0 = time.perf_counter()
        import chardet
        from chardet.enums import EncodingEra

        import_time = time.perf_counter() - t0
        era = EncodingEra.ALL if args.encoding_era == "all" else EncodingEra.MODERN_WEB

        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = chardet.detect(data, encoding_era=era)
            return r["encoding"], r["language"]

    elif args.detector == "chardet":
        t0 = time.perf_counter()
        import chardet

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = chardet.detect(data)
            return r["encoding"], r["language"]

    elif args.detector == "cchardet":
        t0 = time.perf_counter()
        import cchardet

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            return cchardet.detect(data)["encoding"], None

    else:
        t0 = time.perf_counter()
        import charset_normalizer

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = charset_normalizer.detect(data)
            return r["encoding"], r["language"]

    # Warm-up: first detect() call triggers lazy initialization (model loading,
    # norm computation, etc.).  Time it separately so compare_detectors.py can
    # report it as "1st detect".
    t_warmup = time.perf_counter()
    detect(b"Hello, world!")
    first_detect_time = time.perf_counter() - t_warmup

    # Run detection over all files, collect per-file times + results
    file_times: list[float] = []
    t_total_start = time.perf_counter()
    for enc, lang, fp, data in all_data:
        ft0 = time.perf_counter()
        detected, detected_language = detect(data)
        file_elapsed = time.perf_counter() - ft0
        file_times.append(file_elapsed)

        if args.json_only:
            print(
                json.dumps(
                    {
                        "expected": enc,
                        "language": lang,
                        "path": str(fp),
                        "detected": detected,
                        "detected_language": detected_language,
                        "elapsed": file_elapsed,
                    }
                )
            )
    total_elapsed = time.perf_counter() - t_total_start

    if args.json_only:
        # Summary line (last)
        print(
            json.dumps(
                {
                    "__timing__": total_elapsed,
                    "import_time": import_time,
                    "first_detect_time": first_detect_time,
                }
            )
        )
    else:
        # Human-readable summary
        total_ms = sum(file_times) * 1000
        mean_ms = statistics.mean(file_times) * 1000 if file_times else 0.0
        median_ms = statistics.median(file_times) * 1000 if file_times else 0.0
        if len(file_times) >= 20:
            q = statistics.quantiles(file_times, n=20)
            p90_ms = q[17] * 1000
            p95_ms = q[18] * 1000
        else:
            p90_ms = p95_ms = 0.0

        print(f"Detector: {args.detector}")
        if args.detector == "chardet":
            print(f"  encoding_era: {args.encoding_era}")
        print(f"  Files:        {len(all_data)}")
        print()
        print("Timing:")
        print(f"  Import:       {import_time:.3f}s")
        print(f"  1st detect:   {first_detect_time:.3f}s")
        print(f"  Detection:    {total_ms:.0f}ms total")
        print(
            f"  Per-file:     mean={mean_ms:.2f}ms  median={median_ms:.2f}ms"
            f"  p90={p90_ms:.2f}ms  p95={p95_ms:.2f}ms"
        )


if __name__ == "__main__":
    main()

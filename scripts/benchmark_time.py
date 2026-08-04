#!/usr/bin/env python
"""Benchmark a single encoding detector: timing and accuracy.

NO tracemalloc — import times and detection times are measured cleanly
with ``time.perf_counter()`` only.

Can be run standalone for human-readable output, or with ``--json-only`` for
machine-readable JSON (used by ``compare_detectors.py``).
"""

from __future__ import annotations

import concurrent.futures
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from utils import build_benchmark_parser, load_benchmark_data  # noqa: PLC0415

    parser = build_benchmark_parser(
        "Benchmark a single encoding detector (timing only)."
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        metavar="N",
        help="Number of detection threads (default: 1, no threading overhead)",
    )
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be >= 1")
    all_data = load_benchmark_data(args)

    # Import detector and build detect function — timed with perf_counter only
    if args.detector == "chardet" and args.encoding_era != "none":
        t0 = time.perf_counter()
        import chardet  # noqa: PLC0415
        from chardet.enums import EncodingEra  # noqa: PLC0415

        import_time = time.perf_counter() - t0
        era = EncodingEra.ALL if args.encoding_era == "all" else EncodingEra.MODERN_WEB

        # Use should_rename_legacy for backward compat with older chardet
        # versions in compare_detectors (prefer_superset doesn't exist in 7.0.1).
        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = chardet.detect(data, encoding_era=era, should_rename_legacy=True)
            return r["encoding"], r["language"]

    elif args.detector == "chardet":
        # Old chardet (< 6.0) — no encoding_era support.
        # Try should_rename_legacy (5.x+), fall back to plain detect (3.x/4.x).
        t0 = time.perf_counter()
        import chardet  # noqa: PLC0415

        import_time = time.perf_counter() - t0

        import inspect  # noqa: PLC0415

        _has_rename = (
            "should_rename_legacy" in inspect.signature(chardet.detect).parameters
        )

        def detect(data: bytes) -> tuple[str | None, str | None]:
            if _has_rename:
                r = chardet.detect(data, should_rename_legacy=True)
            else:
                r = chardet.detect(data)
            if r is None:
                return None, None
            return r["encoding"], r.get("language")

    elif args.detector == "charade":
        t0 = time.perf_counter()
        import charade  # noqa: PLC0415

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = charade.detect(data)
            if r is None:
                return None, None
            return r["encoding"], r.get("language")

    elif args.detector == "cchardet":
        t0 = time.perf_counter()
        import cchardet  # noqa: PLC0415

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            return cchardet.detect(data)["encoding"], None

    else:
        t0 = time.perf_counter()
        import charset_normalizer  # noqa: PLC0415

        import_time = time.perf_counter() - t0

        def detect(data: bytes) -> tuple[str | None, str | None]:
            r = charset_normalizer.detect(data)
            return r["encoding"], r["language"]

    # Warm-up: first detect() call may trigger lazy initialization.
    # Time it separately so compare_detectors.py can report it as "1st detect".
    t_warmup = time.perf_counter()
    detect(b"Hello, world!")
    first_detect_time = time.perf_counter() - t_warmup

    # Run detection over all files, collect per-file times + results
    file_times: list[float] = []

    if args.threads > 1:
        # Multi-threaded path: distribute detect() calls across threads
        def _detect_one(
            item: tuple[str | None, str | None, Path, bytes],
        ) -> tuple[str | None, str | None, Path, str | None, str | None, float]:
            enc, lang, fp, data = item
            ft0 = time.perf_counter()
            detected, detected_language = detect(data)
            file_elapsed = time.perf_counter() - ft0
            return enc, lang, fp, detected, detected_language, file_elapsed

        results_for_json: list[dict] = []
        t_total_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.threads
        ) as executor:
            for (
                enc,
                lang,
                fp,
                detected,
                detected_language,
                file_elapsed,
            ) in executor.map(_detect_one, all_data):
                file_times.append(file_elapsed)
                if args.json_only:
                    results_for_json.append(
                        {
                            "expected": enc,
                            "language": lang,
                            "path": str(fp),
                            "detected": detected,
                            "detected_language": detected_language,
                            "elapsed": file_elapsed,
                        }
                    )
        total_elapsed = time.perf_counter() - t_total_start

        # Print buffered JSON results (preserves file order)
        for obj in results_for_json:
            print(json.dumps(obj))
    else:
        # Single-threaded path: no executor overhead
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
                    "threads": args.threads,
                }
            )
        )
    else:
        # Human-readable summary
        total_ms = sum(file_times) * 1000
        mean_ms = statistics.mean(file_times) * 1000 if file_times else 0.0
        median_ms = statistics.median(file_times) * 1000 if file_times else 0.0
        from utils import percentiles  # noqa: PLC0415

        pct = percentiles(file_times, (90, 95))
        p90_ms = pct[90] * 1000
        p95_ms = pct[95] * 1000

        print(f"Detector: {args.detector}")
        if args.detector == "chardet":
            print(f"  encoding_era: {args.encoding_era}")
        print(f"  Files:        {len(all_data)}")
        print(f"  Threads:      {args.threads}")
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

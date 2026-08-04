#!/usr/bin/env python
"""Benchmark a single encoding detector: memory usage only.

Uses ``tracemalloc`` (started early) and RSS via ``resource.getrusage``.

Can be run standalone for human-readable output, or with ``--json-only`` for
machine-readable JSON (used by ``compare_detectors.py``).
"""

from __future__ import annotations

import json
import platform
import sys
import tracemalloc
from pathlib import Path
from statistics import mean

try:
    import resource

    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import format_bytes as _format_bytes
from utils import percentiles

# Start tracemalloc as early as possible to capture baseline accurately.
tracemalloc.start()


def main() -> None:
    from utils import build_benchmark_parser, load_benchmark_data  # noqa: PLC0415

    parser = build_benchmark_parser(
        "Benchmark a single encoding detector (memory only)."
    )
    args = parser.parse_args()
    all_data = load_benchmark_data(args)

    # Baseline: utils + file data loaded, detector library NOT yet imported
    baseline_current, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    rss_before = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if _HAS_RESOURCE else 0
    )

    # Import detector and build detect function
    if args.detector == "chardet" and args.encoding_era != "none":
        import chardet  # noqa: PLC0415
        from chardet.enums import EncodingEra  # noqa: PLC0415

        after_import, _ = tracemalloc.get_traced_memory()
        era = EncodingEra.ALL if args.encoding_era == "all" else EncodingEra.MODERN_WEB

        def detect(data: bytes) -> str | None:
            return chardet.detect(data, encoding_era=era)["encoding"]

    elif args.detector == "chardet":
        import chardet  # noqa: PLC0415

        after_import, _ = tracemalloc.get_traced_memory()

        def detect(data: bytes) -> str | None:
            return chardet.detect(data)["encoding"]

    elif args.detector == "cchardet":
        import cchardet  # noqa: PLC0415

        after_import, _ = tracemalloc.get_traced_memory()

        def detect(data: bytes) -> str | None:
            return cchardet.detect(data)["encoding"]

    else:
        from charset_normalizer import from_bytes  # noqa: PLC0415

        after_import, _ = tracemalloc.get_traced_memory()

        def detect(data: bytes) -> str | None:
            r = from_bytes(data)
            best = r.best()
            return best.encoding if best else None

    # Capture the import phase's high-water mark before any reset erases it:
    # transient allocations during import must stay in the run-wide peak.
    _, import_phase_peak = tracemalloc.get_traced_memory()

    # Warm up lazy initialization (model loading etc.) with a sample that
    # reaches statistical scoring, so the per-detection peaks below measure
    # steady-state calls instead of bundling the one-time load into the
    # first file's sample.  The warmup's own peak is reported separately.
    tracemalloc.reset_peak()
    warm_before, _ = tracemalloc.get_traced_memory()
    detect(
        b"\xc2\xf1\xe5 \xf1\xf7\xe0\xf1\xf2\xeb\xe8\xe2\xfb\xe5 \xf1\xe5\xec"
        b"\xfc\xe8 \xef\xee\xf5\xee\xe6\xe8 \xe4\xf0\xf3\xe3 \xed\xe0 \xe4"
        b"\xf0\xf3\xe3\xe0"
    )
    _, warm_peak = tracemalloc.get_traced_memory()
    first_detect_peak = warm_peak - warm_before

    # Run detection over all files (slow under tracemalloc, but needed for peak).
    # Peak is reset per file so each detection's own high-water mark can be
    # recorded, which is what the memory-percentile table is built from. The
    # run-wide peak starts from the import and warmup phases' high-water
    # marks (per-file resets would otherwise erase them) and is then the max
    # of the per-file absolute peaks.
    traced_peak = max(import_phase_peak, warm_peak)
    file_peaks: list[int] = []
    for _enc, _lang, _fp, data in all_data:
        tracemalloc.reset_peak()
        current_before, _ = tracemalloc.get_traced_memory()
        detect(data)
        _, peak_after = tracemalloc.get_traced_memory()
        file_peaks.append(peak_after - current_before)
        traced_peak = max(traced_peak, peak_after)

    tracemalloc.stop()

    rss_after = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if _HAS_RESOURCE else 0
    )
    # macOS reports ru_maxrss in bytes; Linux in KiB
    if _HAS_RESOURCE and platform.system() != "Darwin":
        rss_before *= 1024
        rss_after *= 1024

    traced_import = after_import - baseline_current
    traced_peak_delta = traced_peak - baseline_current

    if args.json_only:
        print(
            json.dumps(
                {
                    "traced_import": traced_import,
                    "traced_peak": traced_peak_delta,
                    "first_detect_peak": first_detect_peak,
                    "rss_before": rss_before,
                    "rss_after": rss_after,
                    "file_peaks": file_peaks,
                }
            )
        )
    else:
        print(f"Detector: {args.detector}")
        if args.detector == "chardet":
            print(f"  encoding_era: {args.encoding_era}")
        print(f"  Files:        {len(all_data)}")
        print()
        print("Memory:")
        print(f"  Traced import:   {_format_bytes(traced_import)}")
        print(f"  Traced peak:     {_format_bytes(traced_peak_delta)}")
        print(f"  1st detect peak: {_format_bytes(first_detect_peak)}")
        print(f"  RSS before:      {_format_bytes(rss_before)}")
        print(f"  RSS after:       {_format_bytes(rss_after)}")
        if file_peaks:
            pct = percentiles(file_peaks, (50, 90, 95, 99))
            print()
            print("Peak memory per detection (steady-state, after warmup):")
            print(f"  mean:   {_format_bytes(int(mean(file_peaks)))}")
            for label, p in (("median", 50), ("p90", 90), ("p95", 95), ("p99", 99)):
                print(f"  {label + ':':<8}{_format_bytes(int(pct[p]))}")
            print(f"  max:    {_format_bytes(max(file_peaks))}")


if __name__ == "__main__":
    main()

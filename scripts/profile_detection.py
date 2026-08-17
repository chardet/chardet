#!/usr/bin/env python
"""Profile chardet detection on the full test suite.

Three modes:

1. **Aggregate** (default): cProfile over all files, showing top functions
   by cumulative and self time.

2. **Per-file** (``--slow N``): time each ``detect()`` call individually,
   then show the N slowest files with per-stage breakdowns so you can see
   *which* files are expensive and *where* the time goes.

3. **mypyc** (``--mypyc``): build the shipped compiled configuration
   (mypyc + Cython kernel), install it in a temporary venv, and re-run
   the profiling there.  Combines with ``--slow N`` for per-file timing
   of compiled code.
"""

from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from detector_env import build_compiled_wheel
from utils import collect_test_files

import chardet
from chardet._utils import DEFAULT_MAX_BYTES, EVIDENCE_CAP_BYTES
from chardet.enums import EncodingEra
from chardet.pipeline import PipelineContext
from chardet.pipeline.ascii import detect_ascii
from chardet.pipeline.binary import is_binary
from chardet.pipeline.bom import detect_bom
from chardet.pipeline.confusion import resolve_confusion_groups
from chardet.pipeline.escape import detect_escape_encoding
from chardet.pipeline.magic import detect_magic
from chardet.pipeline.markup import detect_markup_charset
from chardet.pipeline.statistical import score_candidates
from chardet.pipeline.structural import compute_structural_score
from chardet.pipeline.utf8 import detect_utf8
from chardet.pipeline.utf1632 import detect_utf1632_patterns
from chardet.pipeline.validity import filter_by_validity
from chardet.registry import get_candidates


def _print_build_info() -> None:
    """Print which chardet build is loaded."""
    chardet_path = Path(chardet.__file__).resolve().parent
    has_so = any(chardet_path.rglob("*.so")) or any(chardet_path.rglob("*.pyd"))
    build = "mypyc" if has_so else "pure"
    print(f"  chardet {chardet.__version__} ({build}) from {chardet_path}\n")


def run_all_detections(data_dir: Path) -> None:
    test_files = collect_test_files(data_dir)
    for _enc, _lang, filepath in test_files:
        data = filepath.read_bytes()
        chardet.detect(data, encoding_era=EncodingEra.ALL)


def run_per_file_timing(data_dir: Path, slow_count: int) -> None:
    """Time each detection individually and report the slowest files."""
    test_files = collect_test_files(data_dir)

    # Warm up (first detect triggers lazy model loading)
    if test_files:
        warmup_data = test_files[0][2].read_bytes()
        chardet.detect(warmup_data, encoding_era=EncodingEra.ALL)

    results: list[tuple[float, str, str, str | None, int, dict[str, float]]] = []

    candidates = get_candidates(EncodingEra.ALL, None, None)

    for enc, lang, filepath in test_files:
        data = filepath.read_bytes()
        data_truncated = data[:DEFAULT_MAX_BYTES]
        file_label = f"{enc}-{lang}/{filepath.name}"
        stages: dict[str, float] = {}

        t_total_start = time.perf_counter()

        # BOM
        t0 = time.perf_counter()
        bom_result = detect_bom(data_truncated)
        stages["bom"] = time.perf_counter() - t0
        if bom_result is not None:
            stages["exit_stage"] = "bom"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # UTF-16/32
        t0 = time.perf_counter()
        utf1632_result = detect_utf1632_patterns(data_truncated)
        stages["utf1632"] = time.perf_counter() - t0
        if utf1632_result is not None:
            stages["exit_stage"] = "utf1632"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # Escape
        t0 = time.perf_counter()
        escape_result = detect_escape_encoding(data_truncated)
        stages["escape"] = time.perf_counter() - t0
        if escape_result is not None and escape_result.encoding is not None:
            stages["exit_stage"] = "escape"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # Magic
        t0 = time.perf_counter()
        magic_result = detect_magic(data_truncated)
        stages["magic"] = time.perf_counter() - t0
        if magic_result is not None:
            stages["exit_stage"] = "magic"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # UTF-8 precheck
        t0 = time.perf_counter()
        utf8_precheck = detect_utf8(data_truncated)
        stages["utf8"] = time.perf_counter() - t0

        # ASCII precheck
        t0 = time.perf_counter()
        ascii_precheck = detect_ascii(data_truncated)
        stages["ascii"] = time.perf_counter() - t0

        # Binary
        t0 = time.perf_counter()
        binary = (
            utf8_precheck is None
            and ascii_precheck is None
            and is_binary(data_truncated)
        )
        stages["binary"] = time.perf_counter() - t0
        if binary:
            stages["exit_stage"] = "binary"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # Markup
        t0 = time.perf_counter()
        markup_result = detect_markup_charset(data_truncated)
        stages["markup"] = time.perf_counter() - t0
        if markup_result is not None:
            stages["exit_stage"] = "markup"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # ASCII / UTF-8 return
        if ascii_precheck is not None:
            stages["exit_stage"] = "ascii"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue
        if utf8_precheck is not None:
            stages["exit_stage"] = "utf8"
            t_total = time.perf_counter() - t_total_start
            results.append(
                (t_total, file_label, enc or "None", None, len(data), stages)
            )
            continue

        # Everything below the exhaustive checks converges on the evidence
        # cap (ADR-0006).  The orchestrator slices once and feeds that view
        # to all of them, so this replica must too --- profiling the full
        # window here would report costs the shipping pipeline never pays.
        evidence = data_truncated[:EVIDENCE_CAP_BYTES]

        # Validity filtering
        t0 = time.perf_counter()
        valid_candidates = filter_by_validity(evidence, candidates)
        stages["validity"] = time.perf_counter() - t0

        # Structural scoring (for multibyte candidates)
        t0 = time.perf_counter()
        for enc_info in valid_candidates:
            if enc_info.is_multibyte:
                ctx = PipelineContext()
                compute_structural_score(evidence, enc_info, ctx)
        stages["structural"] = time.perf_counter() - t0

        # Statistical scoring
        t0 = time.perf_counter()
        stat_results = list(score_candidates(evidence, tuple(valid_candidates)))
        stages["statistical"] = time.perf_counter() - t0

        # Confusion resolution
        t0 = time.perf_counter()
        if stat_results:
            resolve_confusion_groups(evidence, stat_results)
        stages["confusion"] = time.perf_counter() - t0

        # Full detect for the actual result
        detected = chardet.detect(data, encoding_era=EncodingEra.ALL)
        stages["exit_stage"] = "statistical"
        stages["detected"] = detected.get("encoding") or "None"

        t_total = time.perf_counter() - t_total_start
        results.append(
            (
                t_total,
                file_label,
                enc or "None",
                detected.get("encoding"),
                len(data),
                stages,
            )
        )

    # Sort by total time descending
    results.sort(key=lambda x: x[0], reverse=True)

    # Summary stats
    times = [r[0] for r in results]
    total = sum(times)
    times_sorted = sorted(times)
    n = len(times_sorted)
    p90 = times_sorted[int(n * 0.90)] if n else 0
    p95 = times_sorted[int(n * 0.95)] if n else 0
    p99 = times_sorted[int(n * 0.99)] if n else 0

    print("=" * 100)
    print("TIMING DISTRIBUTION")
    print("=" * 100)
    print(f"  Files: {n}")
    print(f"  Total: {total * 1000:.1f}ms")
    print(f"  Mean:  {(total / n) * 1000:.2f}ms" if n else "  Mean:  N/A")
    print(f"  p90:   {p90 * 1000:.2f}ms")
    print(f"  p95:   {p95 * 1000:.2f}ms")
    print(f"  p99:   {p99 * 1000:.2f}ms")
    print(f"  Max:   {times_sorted[-1] * 1000:.2f}ms" if n else "  Max:   N/A")
    print()

    # Exit stage distribution
    exit_stages: dict[str, int] = {}
    for _, _, _, _, _, stages in results:
        stage = stages.get("exit_stage", "unknown")
        exit_stages[stage] = exit_stages.get(stage, 0) + 1
    print("=" * 100)
    print("EXIT STAGE DISTRIBUTION")
    print("=" * 100)
    for stage, count in sorted(exit_stages.items(), key=lambda x: -x[1]):
        print(f"  {stage:<15s} {count:>5d}  ({count / n * 100:.1f}%)")
    print()

    # Slowest files
    print("=" * 100)
    print(f"SLOWEST {slow_count} FILES")
    print("=" * 100)
    for i, (t_total, label, expected, _detected, size, stages) in enumerate(
        results[:slow_count]
    ):
        print(f"\n  #{i + 1}: {label}")
        print(
            f"       Total: {t_total * 1000:.2f}ms  |  Size: {size:,} bytes"
            f"  |  Expected: {expected}  |  Exit: {stages.get('exit_stage', '?')}"
        )
        # Show per-stage times, skipping near-zero
        stage_parts = []
        for stage_name in [
            "bom",
            "utf1632",
            "escape",
            "magic",
            "utf8",
            "ascii",
            "binary",
            "markup",
            "validity",
            "structural",
            "statistical",
            "confusion",
        ]:
            if stage_name in stages:
                ms = stages[stage_name] * 1000
                if ms >= 0.01:
                    stage_parts.append(f"{stage_name}={ms:.2f}ms")
        print(f"       Stages: {', '.join(stage_parts)}")


def _reexec_in_mypyc_venv() -> int:
    """Build a compiled wheel, create a temp venv, and re-run this script there.

    The script and ``utils.py`` are copied to a temp directory outside the
    project tree so the venv Python imports the mypyc-compiled chardet
    from site-packages rather than the editable source install.
    """
    project_root = Path(__file__).resolve().parent.parent
    scripts_dir = project_root / "scripts"
    wheel_dir = Path(tempfile.mkdtemp(prefix="chardet-profile-mypyc-"))
    venv_dir = Path(tempfile.mkdtemp(prefix="chardet-profile-venv-"))
    run_dir = Path(tempfile.mkdtemp(prefix="chardet-profile-run-"))

    try:
        # Build the shipped compiled configuration (mypyc + Cython kernel);
        # the in-place artifact sweep happens inside the helper.
        try:
            wheel = build_compiled_wheel(project_root, wheel_dir)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"  Built: {wheel.name}")

        # Create venv and install
        print("Creating venv ...")
        subprocess.run(["uv", "venv", str(venv_dir)], check=True)
        venv_python = str(venv_dir / "bin" / "python")
        subprocess.run(
            ["uv", "pip", "install", "--python", venv_python, str(wheel)],
            check=True,
        )

        # Copy this script and utils.py to a temp dir outside the project
        # tree so the child process doesn't pick up the source chardet.
        shutil.copy2(Path(__file__).resolve(), run_dir / "profile_detection.py")
        shutil.copy2(scripts_dir / "utils.py", run_dir / "utils.py")
        shutil.copy2(scripts_dir / "detector_env.py", run_dir / "detector_env.py")

        # Re-exec in the venv, forwarding all args except --mypyc
        forwarded = [a for a in sys.argv[1:] if a != "--mypyc"]
        # Pass data dir explicitly since the script is no longer in scripts/
        child_script = str(run_dir / "profile_detection.py")
        print(f"\nRe-running with mypyc-compiled chardet (python={venv_python})\n")
        sys.stdout.flush()
        result = subprocess.run(
            [
                venv_python,
                child_script,
                "--data-dir",
                str(project_root / "tests" / "data"),
                *forwarded,
            ],
            check=False,
            env={
                **os.environ,
                "VIRTUAL_ENV": str(venv_dir),
                "PATH": f"{venv_dir / 'bin'}:{os.environ.get('PATH', '')}",
            },
        )
        return result.returncode
    finally:
        shutil.rmtree(wheel_dir, ignore_errors=True)
        shutil.rmtree(venv_dir, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--slow",
        type=int,
        default=0,
        metavar="N",
        help="Show the N slowest files with per-stage timing (skips cProfile)",
    )
    parser.add_argument(
        "--mypyc",
        action="store_true",
        help="Build the shipped compiled configuration (mypyc + Cython "
        "kernel) and profile inside a temp venv",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Path to test data directory (default: tests/data/ relative to project root)",
    )
    args = parser.parse_args()

    if args.mypyc:
        sys.exit(_reexec_in_mypyc_venv())

    data_dir = (
        args.data_dir or Path(__file__).resolve().parent.parent / "tests" / "data"
    )

    _print_build_info()

    if args.slow > 0:
        run_per_file_timing(data_dir, args.slow)
    else:
        profiler = cProfile.Profile()
        profiler.enable()
        run_all_detections(data_dir)
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative")
        print("=" * 80)
        print("TOP 40 BY CUMULATIVE TIME")
        print("=" * 80)
        stats.print_stats(40)

        print("=" * 80)
        print("TOP 40 BY TOTAL (SELF) TIME")
        print("=" * 80)
        stats.sort_stats("tottime")
        stats.print_stats(40)


if __name__ == "__main__":
    main()

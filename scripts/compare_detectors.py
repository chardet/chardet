#!/usr/bin/env python
"""Compare chardet vs other detectors on the chardet test suite.

Includes:
- Rich per-encoding comparison with directional equivalences and winner column
- Pairwise win/loss/tie breakdowns per opponent
- Memory usage comparison (peak traced allocations)
- Result caching for faster repeat runs
- 3x median timing for stable measurements

All detectors — including chardet — run in isolated temporary venvs
created with ``uv`` for fair, consistent measurement.  Use ``--pure`` to
guarantee the chardet venv contains no mypyc extensions.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import collect_test_files, normalize_language
from utils import format_bytes as _format_bytes
from utils import percentiles as _percentiles

from chardet.evaluation import (
    BIDIRECTIONAL_GROUPS,
    SUPERSETS,
    is_correct,
    is_equivalent_detection,
    is_exact_match,
)
from chardet.registry import REGISTRY, lookup_encoding

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CHAR_DATASET_URL = "https://github.com/Ousret/char-dataset.git"
_CHAR_DATASET_DIR = _PROJECT_ROOT / ".char-dataset"

# Per-file detection result: (expected_enc, expected_lang, path, detected_enc, detected_lang)
_DetectionRow = tuple[str, str, str, str | None, str | None]


def _norm_hash(data: bytes) -> str:
    """SHA-256 hash after normalizing line endings to LF."""
    return hashlib.sha256(
        data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    ).hexdigest()


def _ensure_char_dataset() -> Path:
    """Clone or update charset-normalizer's char-dataset."""
    if _CHAR_DATASET_DIR.is_dir():
        subprocess.run(
            ["git", "-C", str(_CHAR_DATASET_DIR), "pull", "--ff-only"],
            check=True,
            capture_output=True,
        )
    else:
        print(f"Cloning char-dataset to {_CHAR_DATASET_DIR} ...")
        subprocess.run(
            ["git", "clone", "--depth=1", _CHAR_DATASET_URL, str(_CHAR_DATASET_DIR)],
            check=True,
            capture_output=True,
        )
    return _CHAR_DATASET_DIR


def _compute_cn_dataset_overlap(
    test_files: list[tuple[str | None, str | None, Path]],
) -> list[tuple[str | None, str | None, Path]]:
    """Filter test_files to only those also present in char-dataset.

    Matches by content hash after normalizing line endings (some files
    differ only in CR/LF vs LF).
    """
    cn_dir = _ensure_char_dataset()

    # Build set of normalized hashes from char-dataset
    cn_hashes: set[str] = set()
    for subdir in cn_dir.iterdir():
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue
        for f in subdir.iterdir():
            if f.is_file() and f.name != "README.md":
                cn_hashes.add(_norm_hash(f.read_bytes()))

    # Filter test_files to those whose content matches
    return [
        (enc, lang, fp)
        for enc, lang, fp in test_files
        if _norm_hash(fp.read_bytes()) in cn_hashes
    ]


@dataclass(slots=True)
class _TimingResult:
    """Aggregated timing data from a single or multi-run benchmark."""

    results: list[_DetectionRow]
    elapsed: float
    file_times: list[float]
    import_time: float
    first_detect_time: float


# ---------------------------------------------------------------------------
# Cache infrastructure
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _compute_benchmark_hash() -> str:
    """SHA-256 (first 12 hex chars) of benchmark-related source files + test data.

    Includes the git commit hash of the test-data submodule so that adding,
    removing, or modifying test files invalidates cached results.
    """
    scripts_dir = _PROJECT_ROOT / "scripts"
    equiv_path = _PROJECT_ROOT / "src" / "chardet" / "equivalences.py"
    paths = [
        scripts_dir / "benchmark_time.py",
        scripts_dir / "benchmark_memory.py",
        scripts_dir / "utils.py",
        equiv_path,
    ]
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    # Include test-data commit hash (changes when files are added/modified)
    data_dir = _PROJECT_ROOT / "tests" / "data"
    if data_dir.is_dir():
        with contextlib.suppress(FileNotFoundError):
            result = subprocess.run(
                ["git", "-C", str(data_dir), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                h.update(result.stdout.strip().encode())
    return h.hexdigest()[:12]


def _get_cache_dir() -> Path:
    """Return the ``.benchmark_results/`` directory, creating it if needed."""
    cache_dir = _PROJECT_ROOT / ".benchmark_results"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def _clean_inplace_mypyc_artifacts(project_root: Path) -> list[Path]:
    """Delete compiled extensions the mypyc build hook leaves in ``src/``.

    hatch-mypyc compiles in place, so building a wheel with ``--mypyc``
    leaves ``.so``/``.pyd`` files sitting next to the ``.py`` sources they
    were built from.  Python imports an extension in preference to the
    module beside it, so anything run from the source tree afterwards
    silently gets the compiled build: a later source edit appears to do
    nothing, a ``--pure`` measurement is not pure, and the files are
    gitignored so ``git status`` stays clean while it happens.

    The wheel already contains its own copies, so removing them here
    costs nothing.  Returns the paths removed, for logging.
    """
    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return []
    removed: list[Path] = []
    for pattern in ("*.so", "*.pyd"):
        for path in sorted(src_dir.rglob(pattern)):
            path.unlink()
            removed.append(path)
    return removed


def _cache_filename(  # noqa: PLR0913
    detector_name: str,
    detector_version: str,
    benchmark_hash: str,
    python_tag: str,
    build_tag: str,
    kind: str,
    *,
    threads: int = 1,
) -> str:
    """Build a cache filename like ``chardet_7.0.1_a1b2c3_cpython3.11_mypyc_time.json``.

    When *threads* > 1, a ``{N}threads`` segment is inserted before *kind*:
    ``chardet_7.0.1_a1b2c3_cpython3.11_mypyc_4threads_time.json``.

    The ``--cn-dataset`` flag does not affect the cache key because the
    benchmark subprocess always runs on all files — the cn-dataset filter
    is applied when aggregating results, not when detecting.

    *detector_name* should be the package name (e.g. ``"chardet"``,
    ``"charset-normalizer"``), **not** the display label.
    """
    safe_name = detector_name.replace(" ", "-").replace("/", "-")
    threads_seg = f"_{threads}threads" if threads > 1 else ""
    return f"{safe_name}_{detector_version}_{benchmark_hash}_{python_tag}_{build_tag}{threads_seg}_{kind}.json"


def _load_cached(cache_dir: Path, filename: str) -> dict | None:
    """Load a cached JSON result, or return ``None`` on miss."""
    path = cache_dir / filename
    if not path.is_file():
        return None
    with path.open() as f:
        return json.load(f)


def _save_cache(cache_dir: Path, filename: str, data: dict) -> None:
    """Save a result dict as JSON to the cache directory."""
    path = cache_dir / filename
    with path.open("w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Version & Python info detection
# ---------------------------------------------------------------------------


def _get_detector_version(python_executable: str, detector_type: str) -> str:
    """Query the detector's ``__version__`` from the venv."""
    module = {
        "chardet": "chardet",
        "charset-normalizer": "charset_normalizer",
        "cchardet": "cchardet",
        "charade": "charade",
    }[detector_type]
    script = f"import {module}; print({module}.__version__)"
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    tmp = Path(tmp_path)
    try:
        os.close(fd)
        tmp.write_text(script)
        result = subprocess.run(
            [python_executable, str(tmp)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"
    finally:
        tmp.unlink(missing_ok=True)


def _get_python_tag(python_executable: str) -> str:
    """Return a tag like ``cpython3.11`` or ``pypy3.10`` from the venv Python."""
    script = (
        "import platform, sys, sysconfig; "
        "abi = sysconfig.get_config_var('ABIFLAGS') or ''; "
        "t = 't' if 't' in abi else ''; "
        "print(f'{platform.python_implementation().lower()}{sys.version_info.major}.{sys.version_info.minor}{t}')"
    )
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    tmp = Path(tmp_path)
    try:
        os.close(fd)
        tmp.write_text(script)
        result = subprocess.run(
            [python_executable, str(tmp)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"
    finally:
        tmp.unlink(missing_ok=True)


def _get_build_tag(python_executable: str, detector_type: str) -> str:
    """Return ``"mypyc"`` if the detector has native .so/.pyd extensions, else ``"pure"``."""
    module = {
        "chardet": "chardet",
        "charset-normalizer": "charset_normalizer",
        "cchardet": "cchardet",
        "charade": "charade",
    }[detector_type]
    # Look for .so/.pyd files under the package directory
    script = (
        f"import {module}, pathlib; "
        f"pkg = pathlib.Path({module}.__file__).parent; "
        f"exts = [p for p in pkg.rglob('*') if p.suffix in ('.so', '.pyd') and p.is_file()]; "
        f"print('mypyc' if exts else 'pure')"
    )
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    tmp = Path(tmp_path)
    try:
        os.close(fd)
        tmp.write_text(script)
        result = subprocess.run(
            [python_executable, str(tmp)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"
    finally:
        tmp.unlink(missing_ok=True)


def _resolve_version_without_venv(
    detector_type: str,
    pip_args: list[str],
    project_root: str,
) -> str:
    """Resolve a detector's version without creating a venv.

    - Local chardet (pip_args is [project_root]): query via ``uv run python``.
    - Pinned chardet (pip_args like ["chardet==6.0.0"]): parse from arg.
    - charset-normalizer / cchardet: ``uv pip compile --no-deps``.
    """
    # Pinned version: extract from "package==X.Y.Z"
    if len(pip_args) == 1 and "==" in pip_args[0]:
        return pip_args[0].split("==", 1)[1]

    # Local chardet: query the existing dev install
    if detector_type == "chardet" and Path(project_root).is_dir():
        fd, tmp_path = tempfile.mkstemp(suffix=".py")
        tmp = Path(tmp_path)
        try:
            os.close(fd)
            tmp.write_text("import chardet; print(chardet.__version__)")
            result = subprocess.run(
                ["uv", "run", "python", str(tmp)],
                capture_output=True,
                text=True,
                check=True,
                cwd=project_root,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"
        finally:
            tmp.unlink(missing_ok=True)

    # PyPI package: resolve via uv pip compile
    pkg_name = {
        "charset-normalizer": "charset-normalizer",
        "cchardet": "faust-cchardet",
        "chardet": "chardet",
        "charade": "charade",
    }.get(detector_type, detector_type)
    with contextlib.suppress(subprocess.CalledProcessError):
        result = subprocess.run(
            ["uv", "pip", "compile", "--no-deps", "-"],
            input=pkg_name,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "==" in line:
                return line.split("==", 1)[1]
    return "unknown"


def _predict_build_tag(
    detector_type: str,
    *,
    pure: bool,
    mypyc: bool,
    python_impl: str = "cpython",
) -> str:
    """Predict the build tag without creating a venv.

    - ``--pure`` -> ``"pure"`` for all detectors.
    - ``--mypyc`` -> ``"mypyc"`` for chardet.
    - Default: chardet checks ``HATCH_BUILD_HOOK_ENABLE_MYPYC`` env var;
      charset-normalizer and cchardet ship compiled wheels on CPython
      -> ``"mypyc"``, ``"pure"`` on PyPy.
    """
    if pure:
        return "pure"
    if detector_type == "charade":
        return "pure"
    if mypyc:
        return "mypyc"
    if detector_type == "chardet":
        if os.environ.get("HATCH_BUILD_HOOK_ENABLE_MYPYC", "").lower() in (
            "true",
            "1",
            "yes",
        ):
            return "mypyc"
        return "pure"
    # charset-normalizer and cchardet ship compiled extensions on CPython
    if python_impl == "cpython":
        return "mypyc"
    return "pure"


def _resolve_python_tag_without_venv(python_version: str | None) -> str:
    """Derive a python tag like ``cpython3.12`` without creating a venv.

    If *python_version* is ``None``, uses the current interpreter.
    Otherwise parses the ``--python`` argument (e.g. ``"3.11"``,
    ``"pypy3.10"``).
    """
    if python_version is None:
        import platform as _platform  # noqa: PLC0415

        impl = _platform.python_implementation().lower()
        return f"{impl}{sys.version_info.major}.{sys.version_info.minor}"

    # Parse --python arg: "pypy3.10" or "3.11"
    pv = python_version.lower()
    if pv.startswith("pypy"):
        return pv  # already "pypy3.10"
    if pv.startswith("cpython"):
        return pv  # already "cpython3.11"
    # Bare version like "3.11" -> "cpython3.11"
    return f"cpython{pv}"


def _has_full_cache(  # noqa: PLR0913
    cache_dir: Path,
    detector_type: str,
    version: str,
    benchmark_hash: str,
    python_tag: str,
    build_tag: str,
    *,
    skip_memory: bool = True,
    threads: int = 1,
) -> bool:
    """Return ``True`` if all required cache files exist."""
    kinds = ("time",) if skip_memory else ("time", "memory")
    for kind in kinds:
        # Memory benchmarks are always single-threaded; only timing caches
        # include the thread count.
        t = threads if kind == "time" else 1
        fname = _cache_filename(
            detector_type,
            version,
            benchmark_hash,
            python_tag,
            build_tag,
            kind,
            threads=t,
        )
        if not (cache_dir / fname).is_file():
            return False
    return True


# ---------------------------------------------------------------------------
# Venv management for isolated detectors
# ---------------------------------------------------------------------------


def _create_detector_venv(
    label: str,
    pip_args: list[str],
    *,
    python_version: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Create a temporary venv with a detector package installed.

    Parameters
    ----------
    label : str
        Human-readable label used for the temp dir prefix and log messages.
    pip_args : list[str]
        Arguments passed directly to ``uv pip install --python <venv_python>``.
    python_version : str | None
        Python version to pass to ``uv venv --python``.  When ``None``,
        uses ``sys.executable``.
    env : dict[str, str] | None
        Environment variables for the pip install step.  ``None`` inherits the
        parent process environment.

    Returns
    -------
    tuple[Path, Path]
        ``(venv_dir, python_executable)``

    """
    safe_prefix = label.replace(" ", "-").replace("/", "-")
    venv_dir = Path(tempfile.mkdtemp(prefix=f"{safe_prefix}-"))
    python_spec = python_version or sys.executable
    print(f"  Creating venv for {label} at {venv_dir} ...")
    subprocess.run(
        ["uv", "venv", "--python", python_spec, str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    venv_python = venv_dir / "bin" / "python"
    print(f"  Installing {label} ...")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_python), *pip_args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return venv_dir, venv_python


def _cleanup_venv(venv_dir: Path) -> None:
    """Remove a temporary venv directory."""
    shutil.rmtree(venv_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Subprocess detection (for isolated detector versions)
# ---------------------------------------------------------------------------


def _run_timing_subprocess(  # noqa: PLR0913
    python_executable: str,
    data_dir: str,
    *,
    detector_type: str = "chardet",
    encoding_era: str = "all",
    pure: bool = False,
    threads: int = 1,
) -> _TimingResult:
    """Run detection timing in an isolated subprocess via ``benchmark_time.py``.

    Parameters
    ----------
    python_executable : str
        Path to the Python interpreter in the target venv.
    data_dir : str
        Path to the test data directory.
    detector_type : str
        One of ``"chardet"``, ``"charset-normalizer"``, ``"cchardet"``, or ``"charade"``.
    encoding_era : str
        For ``"chardet"`` only -- ``"all"``, ``"modern_web"``, or ``"none"``.
    pure : bool
        Abort if mypyc .so/.pyd files are found (chardet only).
    threads : int
        Number of detection threads to pass to ``benchmark_time.py``.

    Returns
    -------
    _TimingResult
        Aggregated timing data including per-file results, elapsed time,
        per-file durations, import time, and first-detect time.

    """
    benchmark_script = str(Path(__file__).resolve().parent / "benchmark_time.py")
    cmd = [
        python_executable,
        benchmark_script,
        "--detector",
        detector_type,
        "--data-dir",
        data_dir,
        "--json-only",
    ]
    cmd.extend(["--encoding-era", encoding_era])
    if pure:
        cmd.append("--pure")
    if threads > 1:
        cmd.extend(["--threads", str(threads)])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(
            f"  WARNING: subprocess detection failed:\n  {result.stderr.strip()}",
            file=sys.stderr,
        )
        return _TimingResult([], 0.0, [], 0.0, 0.0)

    results: list[_DetectionRow] = []
    file_times: list[float] = []
    timing = 0.0
    import_time = 0.0
    first_detect_time = 0.0
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        obj = json.loads(line)
        if "__timing__" in obj:
            timing = obj["__timing__"]
            import_time = obj["import_time"]
            first_detect_time = obj.get("first_detect_time", 0.0)
        else:
            results.append(
                (
                    obj["expected"],
                    obj["language"],
                    obj["path"],
                    obj["detected"],
                    obj.get("detected_language"),
                )
            )
            file_times.append(obj["elapsed"])
    return _TimingResult(results, timing, file_times, import_time, first_detect_time)


def _is_cjk_encoding(name: str | None) -> bool:
    """Whether *name* is a legacy CJK multi-byte encoding.

    Every ``is_multibyte`` entry in the registry is CJK (Big5, GB, EUC,
    Shift_JIS, ISO-2022, Johab), so that flag is the classifier. UTF-8/16/32
    are excluded: they carry CJK text but skip the expensive disambiguation
    path, which is what this split is meant to isolate.
    """
    if not name:
        return False
    canonical = lookup_encoding(name)
    info = REGISTRY.get(canonical) if canonical else None
    return bool(info and info.is_multibyte)


# ---------------------------------------------------------------------------
# 3x median timing
# ---------------------------------------------------------------------------


def _run_timing_with_median(  # noqa: PLR0913
    python_executable: str,
    data_dir: str,
    *,
    detector_type: str = "chardet",
    encoding_era: str = "all",
    pure: bool = False,
    num_runs: int = 3,
    threads: int = 1,
) -> _TimingResult:
    """Run timing ``num_runs`` times and return median-aggregated results.

    Detection results (accuracy data) come from the first run.
    Total time, import time, first-detect time, and per-file times are the
    element-wise medians.
    """
    all_totals: list[float] = []
    all_import_times: list[float] = []
    all_first_detect_times: list[float] = []
    all_file_times: list[list[float]] = []
    first_results: list[_DetectionRow] = []

    for i in range(num_runs):
        run = _run_timing_subprocess(
            python_executable,
            data_dir,
            detector_type=detector_type,
            encoding_era=encoding_era,
            pure=pure,
            threads=threads,
        )
        if i == 0:
            first_results = run.results
        all_totals.append(run.elapsed)
        all_import_times.append(run.import_time)
        all_first_detect_times.append(run.first_detect_time)
        all_file_times.append(run.file_times)

    if not all_totals:
        return _TimingResult([], 0.0, [], 0.0, 0.0)

    median_total = statistics.median(all_totals)
    median_import = statistics.median(all_import_times)
    median_first_detect = statistics.median(all_first_detect_times)

    # Element-wise median of per-file times
    if all_file_times and all_file_times[0]:
        n_files = len(all_file_times[0])
        median_file_times = [
            statistics.median(run[j] for run in all_file_times if j < len(run))
            for j in range(n_files)
        ]
    else:
        median_file_times = []

    return _TimingResult(
        first_results,
        median_total,
        median_file_times,
        median_import,
        median_first_detect,
    )


# ---------------------------------------------------------------------------
# Subprocess-isolated measurement (memory + import time)
# ---------------------------------------------------------------------------


def _measure_memory_subprocess(
    detector: str,
    data_dir: str,
    *,
    python_executable: str,
    encoding_era: str = "all",
    pure: bool = False,
) -> dict[str, int]:
    """Measure memory by running ``benchmark_memory.py`` in a subprocess."""
    benchmark_script = str(Path(__file__).resolve().parent / "benchmark_memory.py")
    cmd = [
        python_executable,
        benchmark_script,
        "--detector",
        detector,
        "--data-dir",
        data_dir,
        "--json-only",
    ]
    cmd.extend(["--encoding-era", encoding_era])
    if pure:
        cmd.append("--pure")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"  WARNING: {detector} memory benchmark failed:", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        return {
            "traced_import": 0,
            "traced_peak": 0,
            "rss_before": 0,
            "rss_after": 0,
            "file_peaks": [],
        }
    return json.loads(result.stdout.strip().split("\n")[0])


# ---------------------------------------------------------------------------
# Result recording helper
# ---------------------------------------------------------------------------


def _record_result(  # noqa: PLR0913
    detector_stats: dict,
    expected_encoding: str | None,
    expected_language: str | None,
    filepath: Path,
    detected: str | None,
    detected_language: str | None,
) -> None:
    """Update a detector's stats dict with one detection result."""
    detector_stats["total"] += 1
    detector_stats["per_enc"][expected_encoding]["total"] += 1
    if is_exact_match(expected_encoding, detected):
        detector_stats["strict_correct"] += 1
    if is_correct(expected_encoding, detected) or (
        detected is not None
        and is_equivalent_detection(filepath.read_bytes(), expected_encoding, detected)
    ):
        detector_stats["correct"] += 1
        detector_stats["per_enc"][expected_encoding]["correct"] += 1
    else:
        detector_stats["failures"].append(
            f"  {filepath.parent.name}/{filepath.name}: "
            f"expected={expected_encoding}, got={detected}"
        )

    # Language tracking (independent of encoding accuracy)
    # Skip for binary files (expected_language is None).
    if expected_language is None:
        return
    detector_stats["lang_total"] += 1
    detector_stats["per_enc"][expected_encoding]["lang_total"] += 1
    normalized = normalize_language(detected_language)
    if normalized is not None and normalized == expected_language.lower():
        detector_stats["lang_correct"] += 1
        detector_stats["per_enc"][expected_encoding]["lang_correct"] += 1
    else:
        detector_stats["lang_failures"].append(
            f"  {filepath.parent.name}/{filepath.name}: "
            f"expected={expected_language}, got={detected_language}"
        )


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------


def run_comparison(  # noqa: PLR0913
    data_dir: Path,
    detectors: list[tuple[str, str, str, str]],
    *,
    pure: bool = False,
    detector_versions: dict[str, str] | None = None,
    python_tags: dict[str, str] | None = None,
    build_tags: dict[str, str] | None = None,
    use_cache: bool = True,
    benchmark_hash: str = "",
    memory: bool = False,
    threads: int = 1,
    cn_dataset: bool = False,
) -> None:
    """Run accuracy and performance comparison across detectors.

    Parameters
    ----------
    data_dir : Path
        Path to the test data directory.
    detectors : list[tuple[str, str, str, str]]
        Each tuple is ``(label, detector_type, python_executable, encoding_era)``.
    pure : bool
        Propagate ``--pure`` to chardet subprocess scripts.
    detector_versions : dict[str, str] | None
        Mapping of label -> version string for cache keys.
    python_tags : dict[str, str] | None
        Mapping of label -> python tag (e.g. ``cpython3.11``) for cache keys.
    build_tags : dict[str, str] | None
        Mapping of label -> build tag (``"mypyc"`` or ``"pure"``) for cache keys.
    use_cache : bool
        Whether to use cached results.
    benchmark_hash : str
        Hash of benchmark source files for cache invalidation.
    memory : bool
        Run memory benchmarks when ``True``.
    threads : int
        Number of detection threads to pass to ``benchmark_time.py``.

    """
    if detector_versions is None:
        detector_versions = {}
    if python_tags is None:
        python_tags = {}
    if build_tags is None:
        build_tags = {}

    test_files = collect_test_files(data_dir)
    if not test_files:
        print("ERROR: No test files found!")
        sys.exit(1)

    if cn_dataset:
        full_count = len(test_files)
        test_files = _compute_cn_dataset_overlap(test_files)
        print(
            f"Filtered to {len(test_files)}/{full_count} files overlapping with char-dataset"
        )

    detector_labels = [label for label, *_ in detectors]

    print(f"Found {len(test_files)} test files")
    print(f"Detectors: {', '.join(detector_labels)}")
    if threads > 1:
        print(f"Threads: {threads}")
    print()
    print("Equivalences used:")
    print("  Superset relationships (detected superset of expected is correct):")
    for subset, supersets in SUPERSETS.items():
        print(f"    {subset} -> {', '.join(sorted(supersets))}")
    print("  Bidirectional groups (byte-order variants):")
    for group in BIDIRECTIONAL_GROUPS:
        print(f"    {' = '.join(group)}")
    print("  Decoded-output equivalence (base-letter matching after NFKD")
    print("    normalization and currency/euro symbol equivalence)")
    print()

    # Initialize per-detector stats
    stats: dict[str, dict] = {}
    for label in detector_labels:
        stats[label] = {
            "correct": 0,
            "strict_correct": 0,
            "total": 0,
            "lang_correct": 0,
            "lang_total": 0,
            "per_enc": defaultdict(
                lambda: {
                    "correct": 0,
                    "total": 0,
                    "lang_correct": 0,
                    "lang_total": 0,
                }
            ),
            "failures": [],
            "lang_failures": [],
            "time": 0.0,
            "file_times": [],
            "cjk_file_times": [],
            "non_cjk_file_times": [],
        }

    data_dir_str = str(data_dir)
    cache_dir = _get_cache_dir() if use_cache else None

    # Build a set of allowed file suffixes for filtering (used with --cn-dataset).
    # Uses "encoding-dir/filename" rather than full paths because cached results
    # may use a different base path (symlink vs resolved).
    allowed_suffixes: frozenset[str] | None = None
    if cn_dataset:
        allowed_suffixes = frozenset(
            f"{fp.parent.name}/{fp.name}" for _, _, fp in test_files
        )

    # --- Parallel timing benchmarks ---
    import_times: dict[str, float] = {}
    first_detect_times: dict[str, float] = {}

    def _run_timing_for_detector(
        label: str, detector_type: str, python_exe: str, era: str
    ) -> tuple[str, _TimingResult]:
        version = detector_versions.get(label, "unknown")
        py_tag = python_tags.get(label, "unknown")
        b_tag = build_tags.get(label, "unknown")

        # Check cache
        if cache_dir is not None:
            fname = _cache_filename(
                detector_type,
                version,
                benchmark_hash,
                py_tag,
                b_tag,
                "time",
                threads=threads,
            )
            cached = _load_cached(cache_dir, fname)
            if cached is not None:
                print(f"  Using cached timing results for {label}")
                return label, _TimingResult(
                    results=[tuple(r) for r in cached["results"]],
                    elapsed=cached["total"],
                    file_times=cached["file_times"],
                    import_time=cached["import_time"],
                    first_detect_time=cached.get("first_detect_time", 0.0),
                )

        # Old chardet (major < 7) gets 1 run (too slow for 3x)
        num_runs = 3
        if detector_type == "chardet" and version != "unknown":
            with contextlib.suppress(ValueError):
                if int(version.split(".")[0]) < 7:
                    num_runs = 1

        is_pure = pure and detector_type == "chardet"
        print(f"  Running {num_runs}x timing for {label} ...")
        timing = _run_timing_with_median(
            python_exe,
            data_dir_str,
            detector_type=detector_type,
            encoding_era=era,
            pure=is_pure,
            num_runs=num_runs,
            threads=threads,
        )

        # Save to cache
        if cache_dir is not None:
            fname = _cache_filename(
                detector_type,
                version,
                benchmark_hash,
                py_tag,
                b_tag,
                "time",
                threads=threads,
            )
            _save_cache(
                cache_dir,
                fname,
                {
                    "results": timing.results,
                    "total": timing.elapsed,
                    "file_times": timing.file_times,
                    "import_time": timing.import_time,
                    "first_detect_time": timing.first_detect_time,
                },
            )

        return label, timing

    max_workers = max(1, (os.cpu_count() or 2) // 2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_timing_for_detector, label, detector_type, python_exe, era
            ): label
            for label, detector_type, python_exe, era in detectors
        }
        for future in concurrent.futures.as_completed(futures):
            label, timing = future.result()
            stats[label]["time"] = timing.elapsed
            import_times[label] = timing.import_time
            first_detect_times[label] = timing.first_detect_time
            filtered_file_times: list[float] = []
            cjk_times: list[float] = []
            non_cjk_times: list[float] = []
            for i, (expected, exp_lang, path_str, detected, det_lang) in enumerate(
                timing.results
            ):
                if allowed_suffixes is not None:
                    p = Path(path_str)
                    suffix = f"{p.parent.name}/{p.name}"
                    if suffix not in allowed_suffixes:
                        continue
                if i < len(timing.file_times):
                    filtered_file_times.append(timing.file_times[i])
                    bucket = cjk_times if _is_cjk_encoding(expected) else non_cjk_times
                    bucket.append(timing.file_times[i])
                _record_result(
                    stats[label],
                    expected,
                    exp_lang,
                    Path(path_str),
                    detected,
                    det_lang,
                )
            stats[label]["file_times"] = filtered_file_times
            stats[label]["cjk_file_times"] = cjk_times
            stats[label]["non_cjk_file_times"] = non_cjk_times

    total = stats[detectors[0][0]]["total"]

    # --- Sequential memory benchmarks (with caching) ---
    memory_results: dict[str, dict] = {}
    if not memory:
        print("Skipping memory benchmarks (pass --memory to include)")
    else:
        print("Measuring memory (isolated subprocesses)...")
    for label, detector_type, python_exe, era in detectors:
        if not memory:
            continue
        version = detector_versions.get(label, "unknown")
        py_tag = python_tags.get(label, "unknown")
        b_tag = build_tags.get(label, "unknown")

        # Check cache
        if cache_dir is not None:
            fname = _cache_filename(
                detector_type, version, benchmark_hash, py_tag, b_tag, "memory"
            )
            cached = _load_cached(cache_dir, fname)
            if cached is not None:
                print(f"  Using cached memory results for {label}")
                memory_results[label] = cached
                continue

        print(f"  Measuring memory for {label} ...")
        memory_results[label] = _measure_memory_subprocess(
            detector_type,
            data_dir_str,
            python_executable=python_exe,
            encoding_era=era,
            pure=pure and detector_type == "chardet",
        )

        # Save to cache
        if cache_dir is not None:
            fname = _cache_filename(
                detector_type, version, benchmark_hash, py_tag, b_tag, "memory"
            )
            _save_cache(cache_dir, fname, memory_results[label])

    # ===================================================================
    # Report
    # ===================================================================

    # -- Overall accuracy --
    print()
    print("=" * 100)
    print("OVERALL ACCURACY (directional equivalences)")
    print("=" * 100)
    max_label = max(len(label) for label in detector_labels)
    for label in detector_labels:
        s = stats[label]
        enc_acc = s["correct"] / total if total else 0
        lang_acc = s["lang_correct"] / s["lang_total"] if s["lang_total"] else 0
        print(
            f"  {label + ':':<{max_label + 1}} "
            f"{s['correct']:>4}/{total} = {enc_acc:.1%} encoding  "
            f"{s['lang_correct']:>4}/{s['lang_total']} = {lang_acc:.1%} language  "
            f"(detection: {s['time']:.2f}s)"
        )

    # -- CJK vs non-CJK latency --
    if any(stats[x]["cjk_file_times"] for x in detector_labels):
        print()
        print("=" * 100)
        print("LATENCY BY SCRIPT FAMILY (per-file, detection-only, milliseconds)")
        print("=" * 100)
        print(
            f"  {'':>{max_label}}  {'group':>9}  {'files':>6}  {'mean':>9}  "
            f"{'median':>9}  {'p95':>9}  {'p99':>9}  {'max':>9}"
        )
        print(
            f"  {'-' * max_label}  {'-' * 9}  {'-' * 6}  {'-' * 9}  "
            f"{'-' * 9}  {'-' * 9}  {'-' * 9}  {'-' * 9}"
        )
        for label in detector_labels:
            for group, key in (
                ("CJK", "cjk_file_times"),
                ("non-CJK", "non_cjk_file_times"),
            ):
                ft = stats[label][key]
                if not ft:
                    continue
                pct = _percentiles(ft, (50, 95, 99))
                print(
                    f"  {label:<{max_label}}  {group:>9}  {len(ft):>6}  "
                    f"{statistics.mean(ft) * 1000:>8.2f}ms  "
                    f"{pct[50] * 1000:>8.2f}ms  {pct[95] * 1000:>8.2f}ms  "
                    f"{pct[99] * 1000:>8.2f}ms  {max(ft) * 1000:>8.2f}ms"
                )
        print()
        print("  CJK = expected encoding is a legacy CJK multi-byte encoding")
        print("        (Big5, GB, EUC, Shift_JIS, ISO-2022, Johab). UTF-8/16/32")
        print("        count as non-CJK even when the text is CJK, since they")
        print("        skip the multi-byte disambiguation path.")
        print()

    # -- Strict vs lenient scoring --
    print()
    print("=" * 100)
    print("STRICT vs LENIENT ENCODING ACCURACY")
    print("=" * 100)
    print(f"  {'':>{max_label}}  {'lenient':>16}  {'strict':>16}  {'concession':>16}")
    print(f"  {'-' * max_label}  {'-' * 16}  {'-' * 16}  {'-' * 16}")
    for label in detector_labels:
        s = stats[label]
        lenient = s["correct"]
        strict = s["strict_correct"]
        lenient_pct = lenient / total if total else 0
        strict_pct = strict / total if total else 0
        gap_pp = (lenient_pct - strict_pct) * 100
        print(
            f"  {label:<{max_label}}  "
            f"{f'{lenient} ({lenient_pct:.1%})':>16}  "
            f"{f'{strict} ({strict_pct:.1%})':>16}  "
            f"{f'+{lenient - strict} (+{gap_pp:.1f}pp)':>16}"
        )
    print()
    print("  lenient    = supersets, byte-order variants, and decoded-output")
    print("               equivalence all credited (the default scoring)")
    print("  strict     = exact encoding match only, after alias normalization")
    print("  concession = files a detector wins only under lenient scoring")
    print()

    # -- Detection runtime distribution --
    print()
    print("=" * 100)
    print("DETECTION RUNTIME DISTRIBUTION (per-file, detection-only, milliseconds)")
    print("=" * 100)
    print(
        f"  {'':>{max_label}}  {'total':>10}  {'mean':>10}  "
        f"{'median':>10}  {'p90':>10}  {'p95':>10}  {'p99':>10}  {'max':>10}"
    )
    print(
        f"  {'-' * max_label}  {'-' * 10}  {'-' * 10}  "
        f"{'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 10}"
    )
    for label in detector_labels:
        ft = stats[label]["file_times"]
        if ft:
            total_ms = sum(ft) * 1000
            mean_ms = statistics.mean(ft) * 1000
            median_ms = statistics.median(ft) * 1000
            max_ms = max(ft) * 1000
            pct = _percentiles(ft, (90, 95, 99))
            p90_ms = pct[90] * 1000
            p95_ms = pct[95] * 1000
            p99_ms = pct[99] * 1000
        else:
            total_ms = mean_ms = median_ms = 0.0
            p90_ms = p95_ms = p99_ms = max_ms = 0.0
        print(
            f"  {label:<{max_label}} "
            f"{total_ms:>9.0f}ms "
            f"{mean_ms:>9.2f}ms "
            f"{median_ms:>9.2f}ms "
            f"{p90_ms:>9.2f}ms "
            f"{p95_ms:>9.2f}ms "
            f"{p99_ms:>9.2f}ms "
            f"{max_ms:>9.2f}ms"
        )

    # -- Startup & memory --
    section_title = "STARTUP & MEMORY" if memory else "STARTUP"
    print()
    print("=" * 100)
    print(f"{section_title} (isolated subprocesses)")
    print("=" * 100)
    header = (
        f"  {'':>{max_label}}  {'import (ms)':>12}  {'1st detect (ms)':>16}  "
        f"{'time to 1st result (ms)':>24}"
    )
    sep = f"  {'-' * max_label}  {'-' * 12}  {'-' * 16}  {'-' * 24}"
    if memory:
        header += (
            f"  {'traced import':>14} {'traced peak':>14}  "
            f"{'RSS before':>12} {'RSS after':>12}"
        )
        sep += f"  {'-' * 14} {'-' * 14}  {'-' * 12} {'-' * 12}"
    print(header)
    print(sep)
    for label in detector_labels:
        first_detect = first_detect_times.get(label, 0.0)
        row = (
            f"  {label:<{max_label}} "
            f"{import_times[label] * 1000:>11.1f}ms  "
            f"{first_detect * 1000:>15.1f}ms  "
            f"{(import_times[label] + first_detect) * 1000:>23.1f}ms"
        )
        if memory:
            sub = memory_results[label]
            row += (
                f"  {_format_bytes(sub['traced_import']):>14} "
                f"{_format_bytes(sub['traced_peak']):>14}  "
                f"{_format_bytes(sub['rss_before']):>12} "
                f"{_format_bytes(sub['rss_after']):>12}"
            )
        print(row)
    print()
    if memory:
        print("  traced = tracemalloc (CPython allocations only)")
        print(
            "  RSS    = resident set size"
            " (all memory incl. C extensions; shared baseline)"
        )
    print("  1st detect = time for first file detection (includes lazy initialization)")
    print("  time to 1st result = import + 1st detect")
    print()

    # -- Per-detection memory distribution --
    if memory and any(memory_results[x].get("file_peaks") for x in detector_labels):
        print("=" * 100)
        print("PEAK MEMORY PER DETECTION (per-file, detection-only)")
        print("=" * 100)
        print(
            f"  {'':>{max_label}}  {'mean':>12}  {'median':>12}  "
            f"{'p90':>12}  {'p95':>12}  {'p99':>12}  {'max':>12}"
        )
        print(
            f"  {'-' * max_label}  {'-' * 12}  {'-' * 12}  "
            f"{'-' * 12}  {'-' * 12}  {'-' * 12}  {'-' * 12}"
        )
        for label in detector_labels:
            peaks = memory_results[label].get("file_peaks") or []
            if peaks:
                pct = _percentiles(peaks, (50, 90, 95, 99))
                cells = [
                    int(statistics.mean(peaks)),
                    int(pct[50]),
                    int(pct[90]),
                    int(pct[95]),
                    int(pct[99]),
                    max(peaks),
                ]
                row = f"  {label:<{max_label}}  " + "  ".join(
                    f"{_format_bytes(c):>12}" for c in cells
                )
            else:
                row = f"  {label:<{max_label}}  " + "  ".join(
                    f"{'---':>12}" for _ in range(6)
                )
            print(row)
        print()
        print("  Peak CPython allocations during a single detect() call, above the")
        print("  memory already resident when that call started. C-extension")
        print("  allocations (e.g. cchardet) are invisible to tracemalloc.")
        print()

    # -- Per-encoding table --
    all_encodings = sorted(
        {enc for label in detector_labels for enc in stats[label]["per_enc"]},
        key=lambda x: x or "",
    )
    col_w = max(18, *(len(label) + 2 for label in detector_labels))

    print("=" * 100)
    print("PER-ENCODING ACCURACY (directional)")
    print("=" * 100)

    header = f"  {'Encoding':<25} {'Files':>5}"
    for label in detector_labels:
        header += f"  {label:>{col_w}}"
    header += f"  {'Best':>{col_w}}"
    print(header)
    sep = f"  {'-' * 25} {'-' * 5}"
    for _ in detector_labels:
        sep += f"  {'-' * col_w}"
    sep += f"  {'-' * col_w}"
    print(sep)

    # Pairwise comparison data (each other detector vs the reference detector)
    ref_label = detector_labels[0]
    pairwise: dict[str, dict[str, list]] = {}
    for label in detector_labels[1:]:
        pairwise[label] = {"ref_wins": [], "other_wins": [], "ties": []}

    for enc in all_encodings:
        t_enc = stats[ref_label]["per_enc"][enc]["total"]
        if t_enc == 0:
            continue

        enc_display = "None" if enc is None else enc
        row = f"  {enc_display:<25} {t_enc:>5}"
        best_acc = -1.0
        best_label = ""
        tied = False

        for label in detector_labels:
            s = stats[label]["per_enc"][enc]
            acc = s["correct"] / t_enc if t_enc else 0
            row += f"  {s['correct']:>{col_w - 12}}/{t_enc} = {acc:>6.1%} "
            if acc > best_acc:
                best_acc = acc
                best_label = label
                tied = False
            elif acc == best_acc:
                tied = True

        winner = "TIE" if tied else best_label
        row += f"  {winner:>{col_w}}"
        print(row)

        # Record pairwise data
        ref_acc = stats[ref_label]["per_enc"][enc]["correct"] / t_enc if t_enc else 0
        for label in detector_labels[1:]:
            other_acc = stats[label]["per_enc"][enc]["correct"] / t_enc if t_enc else 0
            if ref_acc > other_acc:
                pairwise[label]["ref_wins"].append((enc, ref_acc, other_acc, t_enc))
            elif other_acc > ref_acc:
                pairwise[label]["other_wins"].append((enc, other_acc, ref_acc, t_enc))
            else:
                pairwise[label]["ties"].append((enc, ref_acc, t_enc))

    # -- Per-encoding language accuracy --
    print()
    print("=" * 100)
    print("PER-ENCODING LANGUAGE ACCURACY")
    print("=" * 100)

    header = f"  {'Encoding':<25} {'Files':>5}"
    for label in detector_labels:
        header += f"  {label:>{col_w}}"
    print(header)
    sep = f"  {'-' * 25} {'-' * 5}"
    for _ in detector_labels:
        sep += f"  {'-' * col_w}"
    print(sep)

    for enc in all_encodings:
        t_enc = stats[ref_label]["per_enc"][enc]["lang_total"]
        if t_enc == 0:
            continue

        enc_display = "None" if enc is None else enc
        row = f"  {enc_display:<25} {t_enc:>5}"
        for label in detector_labels:
            s = stats[label]["per_enc"][enc]
            lang_c = s["lang_correct"]
            acc = lang_c / t_enc if t_enc else 0
            row += f"  {lang_c:>{col_w - 12}}/{t_enc} = {acc:>6.1%} "
        print(row)

    # -- Pairwise comparisons vs reference detector --
    for label in detector_labels[1:]:
        pw = pairwise[label]

        print()
        print("=" * 100)
        print(f"PAIRWISE: {ref_label} vs {label}")
        print("=" * 100)

        rw = sorted(pw["ref_wins"], key=lambda x: x[1] - x[2], reverse=True)
        print(f"\n  {ref_label} wins ({len(rw)} encodings):")
        for enc, r_acc, o_acc, t_enc in rw:
            enc_display = "None" if enc is None else enc
            diff = r_acc - o_acc
            print(
                f"    {enc_display:<25} {ref_label}={r_acc:>6.1%}  "
                f"{label}={o_acc:>6.1%}  delta={diff:>+6.1%}  ({t_enc} files)"
            )

        ow = sorted(pw["other_wins"], key=lambda x: x[1] - x[2], reverse=True)
        print(f"\n  {label} wins ({len(ow)} encodings):")
        for enc, o_acc, r_acc, t_enc in ow:
            enc_display = "None" if enc is None else enc
            diff = o_acc - r_acc
            print(
                f"    {enc_display:<25} {label}={o_acc:>6.1%}  "
                f"{ref_label}={r_acc:>6.1%}  delta={diff:>+6.1%}  ({t_enc} files)"
            )

        ti = pw["ties"]
        print(f"\n  Tied ({len(ti)} encodings):")
        for enc, acc, t_enc in ti:
            enc_display = "None" if enc is None else enc
            print(f"    {enc_display:<25} both={acc:>6.1%}  ({t_enc} files)")

    # -- Failure details --
    for label in detector_labels:
        failures = stats[label]["failures"]
        print()
        print("=" * 100)
        print(f"{label.upper()} FAILURES ({len(failures)} total)")
        print("=" * 100)
        for f in failures[:80]:
            print(f)
        if len(failures) > 80:
            print(f"  ... and {len(failures) - 80} more")

    # -- Language failure details --
    for label in detector_labels:
        lang_failures = stats[label]["lang_failures"]
        # Skip detectors that never detected any language (e.g., charset-normalizer)
        if (
            lang_failures
            and stats[label]["lang_correct"] == 0
            and stats[label]["lang_total"] > 0
        ):
            print()
            print("=" * 100)
            print(
                f"{label.upper()} LANGUAGE FAILURES (all {len(lang_failures)} — detector does not report language)"
            )
            print("=" * 100)
            continue
        print()
        print("=" * 100)
        print(f"{label.upper()} LANGUAGE FAILURES ({len(lang_failures)} total)")
        print("=" * 100)
        for f in lang_failures[:80]:
            print(f)
        if len(lang_failures) > 80:
            print(f"  ... and {len(lang_failures) - 80} more")


# ---------------------------------------------------------------------------
# Per-python-version runner
# ---------------------------------------------------------------------------

# Type alias for venv specs: (label, pip_args, env, detector_type, python_version)
_VenvSpec = tuple[str, list[str], dict[str, str] | None, str, str | None]


def _run_for_python_version(  # noqa: PLR0913
    args: argparse.Namespace,
    python_version: str | None,
    data_dir: Path,
    project_root: str,
    benchmark_hash: str,
    use_cache: bool,  # noqa: FBT001
) -> None:
    """Run the full comparison for a single Python version."""
    # --pure: strip the mypyc build hook env var so the chardet venv is
    # guaranteed to be pure Python even if the caller has it set.
    # --mypyc: build a mypyc wheel locally first, then install it.
    install_env: dict[str, str] | None = None
    mypyc_wheel_dir: Path | None = None
    chardet_pip_args: list[str] = [project_root]
    if args.pure:
        install_env = {
            k: v for k, v in os.environ.items() if k != "HATCH_BUILD_HOOK_ENABLE_MYPYC"
        }
    elif args.mypyc:
        # Build a mypyc-compiled wheel so the venv gets compiled extensions.
        # Passing HATCH_BUILD_HOOK_ENABLE_MYPYC via env to `uv pip install`
        # doesn't reliably trigger the build hook, so we build explicitly.
        mypyc_wheel_dir = Path(tempfile.mkdtemp(prefix="chardet-mypyc-wheel-"))
        print("Building mypyc wheel for local chardet ...")
        build_cmd = [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(mypyc_wheel_dir),
            project_root,
        ]
        if python_version:
            build_cmd.extend(["--python", python_version])
        try:
            subprocess.run(
                build_cmd,
                check=True,
                # Both hooks: mypyc for the pipeline modules, the custom hook
                # for the Cython scoring kernel.  Enabling only the first
                # builds a wheel that runs the packed buffers through the
                # interpreter, which benchmarks ~30% slower than this one.
                env={
                    **os.environ,
                    "HATCH_BUILD_HOOK_ENABLE_MYPYC": "true",
                    "HATCH_BUILD_HOOK_ENABLE_CUSTOM": "true",
                },
            )
        finally:
            stale = _clean_inplace_mypyc_artifacts(Path(project_root))
            if stale:
                print(
                    f"  Removed {len(stale)} in-place mypyc artifact(s) "
                    f"from {Path(project_root) / 'src'}"
                )
        wheels = list(mypyc_wheel_dir.glob("*.whl"))
        if not wheels:
            print("ERROR: mypyc wheel build produced no .whl file", file=sys.stderr)
            sys.exit(1)
        chardet_pip_args = [str(wheels[0])]
        print(f"  Built: {wheels[0].name}")

    # Build venv specs: (label, pip_args, env, detector_type, python_version)
    venv_specs: list[_VenvSpec] = [
        ("chardet", chardet_pip_args, install_env, "chardet", python_version),
    ]

    for version in args.chardet_version:
        cv_pip_args = [f"chardet=={version}"]
        if args.pure:
            cv_pip_args.extend(["--no-binary", "chardet"])
        venv_specs.append(
            (f"chardet {version}", cv_pip_args, None, "chardet", python_version)
        )

    if args.charset_normalizer:
        # --pure: force pure-Python build via --no-binary
        cn_pip_args = ["charset-normalizer"]
        if args.pure:
            cn_pip_args.extend(["--no-binary", "charset-normalizer"])
        venv_specs.append(
            (
                "charset-normalizer",
                cn_pip_args,
                None,
                "charset-normalizer",
                python_version,
            )
        )

    venv_specs.extend(
        (f"charade {version}", [f"charade=={version}"], None, "charade", python_version)
        for version in args.charade
    )

    if args.cchardet:
        venv_specs.append(
            ("cchardet", ["faust-cchardet"], None, "cchardet", python_version)
        )

    # --- Pre-resolve versions and tags without creating venvs ---
    print("Resolving detector versions ...")
    detector_versions: dict[str, str] = {}
    python_tags: dict[str, str] = {}
    build_tags: dict[str, str] = {}
    detector_type_map: dict[str, str] = {}

    pre_python_tag = _resolve_python_tag_without_venv(python_version)

    for spec in venv_specs:
        label, pip_args, _env, det_type, _pyver = spec
        detector_type_map[label] = det_type
        detector_versions[label] = _resolve_version_without_venv(
            det_type, pip_args, project_root
        )
        python_tags[label] = pre_python_tag
        build_tags[label] = _predict_build_tag(
            det_type,
            pure=args.pure,
            mypyc=args.mypyc,
            python_impl=pre_python_tag.split(".")[0].rstrip("0123456789"),
        )
        print(
            f"  {label}: version={detector_versions[label]}, "
            f"python={python_tags[label]}, build={build_tags[label]}"
        )

    # --- Check cache: partition specs into cached vs needs-venv ---
    cache_dir = _get_cache_dir() if use_cache else None
    uncached_specs: list[_VenvSpec] = []

    for spec in venv_specs:
        label = spec[0]
        det_type = spec[3]
        if cache_dir is not None and _has_full_cache(
            cache_dir,
            det_type,
            detector_versions[label],
            benchmark_hash,
            python_tags[label],
            build_tags[label],
            skip_memory=not args.memory,
            threads=args.threads,
        ):
            print(f"  {label}: full cache hit, skipping venv creation")
        else:
            uncached_specs.append(spec)

    # --- Create venvs only for uncached detectors ---
    venvs: dict[str, tuple[Path, Path]] = {}

    def _create_venv_from_spec(
        spec: _VenvSpec,
    ) -> tuple[str, Path, Path]:
        label, pip_args, env, _det_type, pv = spec
        venv_dir, python_path = _create_detector_venv(
            label, pip_args, python_version=pv, env=env
        )
        return label, venv_dir, python_path

    if uncached_specs:
        print(f"Setting up {len(uncached_specs)} venv(s) ...")
    else:
        print("All detectors fully cached, no venvs needed.")

    try:
        if uncached_specs:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(_create_venv_from_spec, spec): spec
                    for spec in uncached_specs
                }
                for future in concurrent.futures.as_completed(futures):
                    spec = futures[future]
                    label = spec[0]
                    try:
                        label, venv_dir, python_path = future.result()
                        venvs[label] = (venv_dir, python_path)
                    except subprocess.CalledProcessError as exc:
                        print(f"  WARNING: failed to create venv for {label}: {exc}")

            # Update versions/tags from actual venvs (more accurate)
            for label, (_, python_path) in venvs.items():
                det_type = detector_type_map[label]
                py_exe = str(python_path)
                old_version = detector_versions[label]
                detector_versions[label] = _get_detector_version(py_exe, det_type)
                python_tags[label] = _get_python_tag(py_exe)
                build_tags[label] = _get_build_tag(py_exe, det_type)
                if old_version != detector_versions[label]:
                    print(
                        f"  NOTE: {label} pre-resolved version {old_version} "
                        f"differs from venv version {detector_versions[label]}"
                    )
                print(
                    f"  {label}: version={detector_versions[label]}, "
                    f"python={python_tags[label]}, build={build_tags[label]}"
                )

        # Rebuild labels to include package name, version, and build tag
        label_remap: dict[str, str] = {}
        for spec in venv_specs:
            old_label = spec[0]
            det_type = spec[3]
            version = detector_versions.get(old_label, "unknown")
            b_tag = build_tags.get(old_label, "unknown")
            label_remap[old_label] = f"{det_type} {version} ({b_tag})"

        venvs = {label_remap.get(k, k): v for k, v in venvs.items()}
        detector_versions = {
            label_remap.get(k, k): v for k, v in detector_versions.items()
        }
        python_tags = {label_remap.get(k, k): v for k, v in python_tags.items()}
        build_tags = {label_remap.get(k, k): v for k, v in build_tags.items()}

        # Build unified detector list: (label, detector_type, python_exe, encoding_era)
        detectors: list[tuple[str, str, str, str]] = []
        for spec in venv_specs:
            old_label = spec[0]
            det_type = spec[3]
            label = label_remap.get(old_label, old_label)
            # Cached detectors get dummy exe; run_comparison loads from cache.
            # Skip detectors whose venv failed to create and have no cache.
            if label not in venvs:
                cache_dir = _get_cache_dir() if use_cache else None
                if cache_dir is None:
                    print(f"  Skipping {label} (no venv and no cache)")
                    continue
                # Check if there's a cached result we can use
                version = detector_versions.get(label, "unknown")
                fname = _cache_filename(
                    det_type,
                    version,
                    benchmark_hash,
                    pre_python_tag,
                    _predict_build_tag(det_type, pure=args.pure, mypyc=args.mypyc),
                    "time",
                )
                if not _load_cached(cache_dir, fname):
                    print(f"  Skipping {label} (no venv and no cache)")
                    continue
            python_exe = str(venvs[label][1]) if label in venvs else "/dev/null"
            version = detector_versions.get(label, "unknown")
            if det_type == "chardet":
                try:
                    era = "all" if int(version.split(".")[0]) >= 6 else "none"
                except ValueError:
                    era = "all"
            else:
                era = "none"
            detectors.append((label, det_type, python_exe, era))

        run_comparison(
            data_dir,
            detectors,
            pure=args.pure,
            detector_versions=detector_versions,
            python_tags=python_tags,
            build_tags=build_tags,
            use_cache=use_cache,
            benchmark_hash=benchmark_hash,
            memory=args.memory,
            threads=args.threads,
            cn_dataset=args.cn_dataset,
        )
    finally:
        for label, (venv_dir, _) in venvs.items():
            print(f"  Cleaning up venv for {label} ...")
            _cleanup_venv(venv_dir)
        if mypyc_wheel_dir is not None:
            shutil.rmtree(mypyc_wheel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare chardet vs other detectors on the chardet test suite.",
    )
    parser.add_argument(
        "-c",
        "--chardet-version",
        action="append",
        default=[],
        metavar="X.Y.Z",
        help="Chardet version to include (repeatable, e.g. -c 6.0.0 -c 5.2.0)",
    )
    parser.add_argument(
        "--cchardet",
        action="store_true",
        default=False,
        help="Include cchardet (faust-cchardet) in the comparison",
    )
    parser.add_argument(
        "--charade",
        action="append",
        default=[],
        metavar="VERSION",
        help="Charade version to include (repeatable, e.g. --charade 1.0.3)",
    )
    parser.add_argument(
        "--cn",
        "--charset-normalizer",
        action="store_true",
        default=False,
        dest="charset_normalizer",
        help="Include charset-normalizer in the comparison",
    )
    parser.add_argument(
        "--python",
        action="append",
        default=[],
        metavar="VERSION",
        help=(
            "Python version to pass to 'uv venv --python' (e.g. 3.11, pypy3.10). "
            "Repeatable: --python 3.12 --python 3.13 runs a full comparison for each."
        ),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Force re-run, ignoring cached results",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        default=False,
        help="Include memory benchmarks (slow, only needed for release notes)",
    )
    parser.add_argument(
        "--pure",
        action="store_true",
        default=False,
        help=(
            "Ensure detectors are pure Python (strips HATCH_BUILD_HOOK_ENABLE_MYPYC, "
            "propagates --pure to subprocesses to abort if .so/.pyd files are found)"
        ),
    )
    parser.add_argument(
        "--mypyc",
        action="store_true",
        default=False,
        help=(
            "Forces mypyc versions of chardet and charset-normalizer"
            " (sets HATCH_BUILD_HOOK_ENABLE_MYPYC=true)"
        ),
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        metavar="N",
        help="Number of detection threads for benchmark_time.py (default: 1)",
    )
    parser.add_argument(
        "--cn-dataset",
        action="store_true",
        default=False,
        help=(
            "Restrict to the ~472 files that overlap with charset-normalizer's "
            "char-dataset (github.com/Ousret/char-dataset)"
        ),
    )
    args = parser.parse_args()

    if args.pure and args.mypyc:
        parser.error("--pure and --mypyc are mutually exclusive")
    if args.threads < 1:
        parser.error("--threads must be >= 1")

    # Force line-buffered stdout so progress is visible when piped (e.g. tee).
    sys.stdout.reconfigure(line_buffering=True)

    data_dir = Path(__file__).resolve().parent.parent / "tests" / "data"
    if not data_dir.is_dir():
        print(f"ERROR: Test data directory not found: {data_dir}")
        sys.exit(1)

    project_root = str(Path(__file__).resolve().parent.parent)
    benchmark_hash = _compute_benchmark_hash()
    use_cache = not args.no_cache

    # Normalize --python: empty list means "current interpreter" (single run).
    python_versions: list[str | None] = args.python or [None]
    multi = len(python_versions) > 1

    for i, python_version in enumerate(python_versions):
        if multi:
            tag = python_version or "default"
            print(f"\n{'=' * 72}")
            print(f"  Python: {tag}  ({i + 1}/{len(python_versions)})")
            print(f"{'=' * 72}\n")

        _run_for_python_version(
            args,
            python_version,
            data_dir,
            project_root,
            benchmark_hash,
            use_cache,
        )

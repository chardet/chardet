#!/usr/bin/env python3
"""Benchmark chardet vs charset-normalizer on charset-normalizer's char-dataset.

Uses 4 scoring tiers to show how methodology affects reported accuracy:

  Tier 1 — Strict:        exact codec-normalized match
  Tier 2 — Equivalences:  Tier 1 OR chardet equivalence rules (supersets, bidirectional)
  Tier 3 — Any candidate: expected encoding appears in any returned candidate
  Tier 4 — Any equiv:     any candidate passes equivalence rules

This allows fair comparison between libraries with different output conventions.
"""

from __future__ import annotations

import argparse
import codecs
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chardet
from chardet.enums import EncodingEra
from chardet.evaluation import is_acceptable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data acquisition
# ---------------------------------------------------------------------------

_CHAR_DATASET_URL = "https://github.com/Ousret/char-dataset.git"
_CHAR_DATASET_DIR = _PROJECT_ROOT / ".char-dataset"
_CACHE_DIR = _PROJECT_ROOT / ".char-dataset-results"


def clone_char_dataset(dest: Path) -> None:
    """Shallow clone char-dataset, or pull if it already exists."""
    if dest.is_dir():
        print(f"Updating char-dataset at {dest} ...")
        subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only"],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        print(f"Cloning char-dataset to {dest} ...")
        subprocess.run(
            ["git", "clone", "--depth=1", _CHAR_DATASET_URL, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )


def _normalize_codec(name: str) -> str:
    """Normalize an encoding name via codecs.lookup().

    Deliberately NOT ``chardet.evaluation.is_exact_match``: Tier 1 referees
    a cross-library comparison, and normalizing through chardet's own
    registry would bias the strict tier toward chardet's naming
    conventions.  The stdlib codec registry is the neutral ground both
    libraries' outputs pass through.
    """
    return codecs.lookup(name).name


def collect_char_dataset_files(dataset_dir: Path) -> list[tuple[str | None, Path]]:
    """Collect (expected_encoding, filepath) pairs from the char-dataset layout.

    The dataset uses subdirectory names as expected encodings.  A special
    ``None`` directory contains binary files for which detection should return
    ``None``.
    """
    files: list[tuple[str | None, Path]] = []
    for subdir in sorted(dataset_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue
        if subdir.name == "None":
            expected: str | None = None
        else:
            try:
                expected = _normalize_codec(subdir.name)
            except LookupError:
                print(
                    f"ERROR: Unknown encoding directory '{subdir.name}' — "
                    f"char-dataset structure may have changed",
                    file=sys.stderr,
                )
                sys.exit(1)
        files.extend(
            (expected, filepath)
            for filepath in sorted(subdir.iterdir())
            if filepath.is_file()
        )
    return files


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DetectionResult:
    """Per-file detection result from one detector."""

    best_encoding: str | None
    best_confidence: float
    all_encodings: list[str]


def _normalize_detected(encoding: str | None) -> str | None:
    """Normalize a detected encoding name via codecs.lookup(), with fallback."""
    if encoding is None:
        return None
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        return encoding.lower()


def run_chardet(files: list[tuple[str | None, Path]]) -> list[DetectionResult]:
    """Run chardet.detect_all() on every file and return per-file results."""
    results: list[DetectionResult] = []
    for _expected, filepath in files:
        data = filepath.read_bytes()
        all_dicts = chardet.detect_all(
            data, encoding_era=EncodingEra.ALL, compat_names=False
        )
        best = all_dicts[0] if all_dicts else {"encoding": None, "confidence": 0.0}
        best_enc = _normalize_detected(best.get("encoding"))
        best_conf = float(best.get("confidence") or 0.0)
        seen: set[str | None] = set()
        all_encs: list[str] = []
        for d in all_dicts:
            n = _normalize_detected(d.get("encoding"))
            if n is not None and n not in seen:
                seen.add(n)
                all_encs.append(n)
        results.append(DetectionResult(best_enc, best_conf, all_encs))
    return results


# ---------------------------------------------------------------------------
# charset-normalizer venv helpers
# ---------------------------------------------------------------------------

_CN_DETECT_SCRIPT = """\
import sys, json
import charset_normalizer

for line in sys.stdin:
    path = line.rstrip("\\n")
    if not path:
        continue
    data = open(path, "rb").read()
    best = charset_normalizer.detect(data)
    best_enc = best.get("encoding")
    best_conf = best.get("confidence") or 0.0

    from_results = charset_normalizer.from_bytes(data)
    all_encs = []
    seen = set()
    for r in from_results:
        enc = r.first().encoding if hasattr(r, "first") else getattr(r, "encoding", None)
        if enc and enc not in seen:
            seen.add(enc)
            all_encs.append(enc)
    if best_enc and best_enc not in seen:
        all_encs.insert(0, best_enc)

    print(json.dumps({"best_encoding": best_enc, "best_confidence": best_conf, "all_encodings": all_encs}))
    sys.stdout.flush()
"""


def create_cn_venv() -> tuple[Path, Path, str]:
    """Create an isolated venv with charset-normalizer installed.

    Returns ``(venv_dir, python_path, version)``.
    """
    venv_dir = Path(tempfile.mkdtemp(prefix="chardet-cn-bench-"))
    print(f"Creating charset-normalizer venv at {venv_dir} ...")
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    python_path = venv_dir / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python_path), "charset-normalizer"],
        check=True,
        capture_output=True,
        text=True,
    )
    # Fetch version
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    tmp = Path(tmp_path)
    try:
        os.close(fd)
        tmp.write_text(
            "import charset_normalizer; print(charset_normalizer.__version__)"
        )
        result = subprocess.run(
            [str(python_path), str(tmp)],
            capture_output=True,
            text=True,
            check=True,
        )
        version = result.stdout.strip()
    except subprocess.CalledProcessError:
        version = "unknown"
    finally:
        tmp.unlink(missing_ok=True)
    return venv_dir, python_path, version


def cleanup_venv(venv_dir: Path) -> None:
    """Remove a temporary venv directory."""
    shutil.rmtree(venv_dir, ignore_errors=True)


def run_charset_normalizer(
    files: list[tuple[str | None, Path]],
    cn_python: Path,
) -> list[DetectionResult]:
    """Run charset-normalizer on every file using an isolated venv.

    The helper script is written to a temp file.  File paths are fed via
    stdin; one JSON result per line is read back.
    """
    fd, script_path = tempfile.mkstemp(suffix=".py")
    script = Path(script_path)
    try:
        os.close(fd)
        script.write_text(_CN_DETECT_SCRIPT)
        file_paths = "\n".join(str(fp) for _, fp in files) + "\n"
        proc = subprocess.run(
            [str(cn_python), str(script)],
            input=file_paths,
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        script.unlink(missing_ok=True)

    results: list[DetectionResult] = []
    for line in proc.stdout.strip().split("\n"):
        if not line:
            continue
        obj = json.loads(line)
        enc = obj.get("best_encoding")
        if enc is not None:
            try:
                enc = codecs.lookup(enc).name
            except LookupError:
                enc = enc.lower()
        conf = float(obj.get("best_confidence") or 0.0)
        all_encs_raw: list[str] = obj.get("all_encodings") or []
        all_encs: list[str] = []
        seen: set[str] = set()
        for e in all_encs_raw:
            try:
                n = codecs.lookup(e).name
            except LookupError:
                n = e.lower()
            if n not in seen:
                seen.add(n)
                all_encs.append(n)
        results.append(DetectionResult(enc, conf, all_encs))
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TierScores:
    """Per-library scoring across all 4 tiers."""

    total: int = 0
    tier1: int = 0
    tier2: int = 0
    tier3: int = 0
    tier4: int = 0
    per_encoding: dict[str, dict[str, int]] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)


def _enc_key(enc: str | None) -> str:
    return enc if enc is not None else "None"


def score_results(
    files: list[tuple[str | None, Path]],
    results: list[DetectionResult],
) -> TierScores:
    """Score detection results at all 4 tiers."""
    scores = TierScores()
    for (expected, filepath), result in zip(files, results, strict=True):
        scores.total += 1
        enc_k = _enc_key(expected)
        if enc_k not in scores.per_encoding:
            scores.per_encoding[enc_k] = {
                "total": 0,
                "tier1": 0,
                "tier2": 0,
                "tier3": 0,
                "tier4": 0,
            }
        scores.per_encoding[enc_k]["total"] += 1

        detected = result.best_encoding
        data_bytes = filepath.read_bytes()

        # Normalize expected for Tier 1 comparison
        norm_expected: str | None
        if expected is None:
            norm_expected = None
        else:
            try:
                norm_expected = codecs.lookup(expected).name
            except LookupError:
                norm_expected = expected.lower()

        # Tier 1: strict exact match
        t1 = norm_expected == detected
        if t1:
            scores.tier1 += 1
            scores.per_encoding[enc_k]["tier1"] += 1

        # Tier 2: Tier 1 OR chardet equivalences
        t2 = t1 or is_acceptable(data_bytes, expected, detected)
        if t2:
            scores.tier2 += 1
            scores.per_encoding[enc_k]["tier2"] += 1

        # Tier 3: expected in any candidate (exact normalized match)
        if norm_expected is None:
            t3 = detected is None
        else:
            t3 = norm_expected in result.all_encodings
        if t3:
            scores.tier3 += 1
            scores.per_encoding[enc_k]["tier3"] += 1

        # Tier 4: any candidate passes equivalences
        if norm_expected is None:
            t4 = detected is None
        else:
            t4 = any(
                is_acceptable(data_bytes, expected, cand)
                for cand in result.all_encodings
            )
        if t4:
            scores.tier4 += 1
            scores.per_encoding[enc_k]["tier4"] += 1

        # Track failures
        if not t2:
            category = "none_result" if detected is None else "wrong_family"
            scores.failures.append(
                {
                    "path": str(filepath),
                    "expected": enc_k,
                    "detected": detected,
                    "confidence": result.best_confidence,
                    "category": category,
                    "tier3": t3,
                    "tier4": t4,
                }
            )

        # Track Tier 1 failures rescued by Tier 2 (superset/equiv detections)
        if not t1 and t2:
            scores.failures.append(
                {
                    "path": str(filepath),
                    "expected": enc_k,
                    "detected": detected,
                    "confidence": result.best_confidence,
                    "category": "superset_rescued",
                    "tier3": t3,
                    "tier4": t4,
                }
            )

    return scores


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def _file_content_hash(filepath: Path) -> str:
    """SHA-256 of the full file contents, first 12 hex chars."""
    return hashlib.sha256(filepath.read_bytes()).hexdigest()[:12]


def _cache_key(cn_version: str, files: list[tuple[str | None, Path]]) -> str:
    """Build a stable cache key from the cn version and file content hashes."""
    h = hashlib.sha256()
    h.update(cn_version.encode())
    for expected, fp in files:
        h.update(f"{expected}:{fp}:{_file_content_hash(fp)}\n".encode())
    return h.hexdigest()[:16]


def save_cn_cache(
    cache_dir: Path,
    cn_version: str,
    files: list[tuple[str | None, Path]],
    results: list[DetectionResult],
) -> None:
    """Save charset-normalizer results to the cache directory."""
    cache_dir.mkdir(exist_ok=True)
    key = _cache_key(cn_version, files)
    cache_path = cache_dir / f"cn_{cn_version}_{key}.json"
    payload = [
        {
            "best_encoding": r.best_encoding,
            "best_confidence": r.best_confidence,
            "all_encodings": r.all_encodings,
        }
        for r in results
    ]
    with cache_path.open("w") as f:
        json.dump(payload, f)
    print(f"  Saved cn cache: {cache_path.name}")


def load_cn_cache(
    cache_dir: Path,
    cn_version: str,
    files: list[tuple[str | None, Path]],
) -> list[DetectionResult] | None:
    """Load cached charset-normalizer results, or return None on miss."""
    key = _cache_key(cn_version, files)
    cache_path = cache_dir / f"cn_{cn_version}_{key}.json"
    if not cache_path.is_file():
        return None
    with cache_path.open() as f:
        payload = json.load(f)
    return [
        DetectionResult(
            best_encoding=item["best_encoding"],
            best_confidence=item["best_confidence"],
            all_encodings=item["all_encodings"],
        )
        for item in payload
    ]


def _resolve_cn_version() -> str:
    """Resolve latest charset-normalizer version via uv pip compile."""
    with contextlib.suppress(subprocess.CalledProcessError):
        result = subprocess.run(
            ["uv", "pip", "compile", "--no-deps", "--python", sys.executable, "-"],
            input="charset-normalizer",
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "==" in line:
                return line.split("==", 1)[1]
    return "unknown"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_summary(
    all_scores: dict[str, TierScores],
    *,
    tier_filter: int | None = None,
) -> None:
    """Print a summary table of tier scores per library."""
    lib_names = list(all_scores.keys())
    if not lib_names:
        return
    total = all_scores[lib_names[0]].total

    tiers = [1, 2, 3, 4]
    if tier_filter is not None:
        tiers = [tier_filter]

    tier_labels = {
        1: "Tier 1 (strict best)",
        2: "Tier 2 (best + equiv)",
        3: "Tier 3 (all candidates)",
        4: "Tier 4 (all + equiv)",
    }

    col_w = max(20, *(len(n) + 2 for n in lib_names))

    print()
    print("=" * 80)
    print("ACCURACY SUMMARY")
    print("=" * 80)
    header = f"  {'':25}"
    for name in lib_names:
        header += f"  {name:>{col_w}}"
    print(header)
    sep = f"  {'-' * 25}"
    for _ in lib_names:
        sep += f"  {'-' * col_w}"
    print(sep)

    for tier in tiers:
        attr = f"tier{tier}"
        row = f"  {tier_labels[tier]:<25}"
        for name in lib_names:
            s = all_scores[name]
            count = getattr(s, attr)
            pct = count / total if total else 0.0
            row += f"  {count:>{col_w - 9}}/{total} = {pct:>6.1%} "
        print(row)

    print(f"  {'Total files':<25}  {total}")


def print_per_encoding(all_scores: dict[str, TierScores]) -> None:
    """Print per-encoding Tier 2 breakdown sorted by failure count."""
    lib_names = list(all_scores.keys())
    if not lib_names:
        return
    ref = all_scores[lib_names[0]]
    all_enc_keys = sorted(
        set(ref.per_encoding.keys()),
        key=lambda k: -(ref.per_encoding[k]["total"] - ref.per_encoding[k]["tier2"]),
    )

    col_w = max(18, *(len(n) + 2 for n in lib_names))

    print()
    print("=" * 80)
    print("PER-ENCODING ACCURACY (Tier 2)")
    print("=" * 80)
    header = f"  {'Encoding':<30} {'Files':>5}"
    for name in lib_names:
        header += f"  {name:>{col_w}}"
    print(header)
    sep = f"  {'-' * 30} {'-' * 5}"
    for _ in lib_names:
        sep += f"  {'-' * col_w}"
    print(sep)

    for enc_k in all_enc_keys:
        enc_info = ref.per_encoding.get(enc_k, {})
        total_enc = enc_info.get("total", 0)
        if total_enc == 0:
            continue
        row = f"  {enc_k:<30} {total_enc:>5}"
        for name in lib_names:
            s = all_scores[name]
            enc_data = s.per_encoding.get(enc_k, {})
            t2 = enc_data.get("tier2", 0)
            pct = t2 / total_enc if total_enc else 0.0
            row += f"  {t2:>{col_w - 9}}/{total_enc} = {pct:>6.1%} "
        print(row)


def print_failures(scores: TierScores, *, label: str) -> None:
    """Print failure details grouped by category."""
    failures = scores.failures
    print()
    print("=" * 80)
    print(f"{label.upper()} FAILURES ({len(failures)} total at Tier 2)")
    print("=" * 80)

    by_cat: dict[str, list[dict]] = {}
    for f in failures:
        cat = f["category"]
        by_cat.setdefault(cat, []).append(f)

    for cat, items in sorted(by_cat.items()):
        print(f"\n  [{cat}] ({len(items)} failures)")
        for item in items[:20]:
            path_short = Path(item["path"]).parent.name + "/" + Path(item["path"]).name
            t3_note = " (in candidates)" if item.get("tier3") else ""
            t4_note = " (equiv in candidates)" if item.get("tier4") else ""
            note = t3_note or t4_note or ""
            print(
                f"    expected={item['expected']}, detected={item['detected']}"
                f" (conf={item['confidence']:.2f})  {path_short}{note}"
            )
        if len(items) > 20:
            print(f"    ... and {len(items) - 20} more")


def print_json_report(all_scores: dict[str, TierScores]) -> None:
    """Print a full JSON report."""
    report: dict = {}
    for name, s in all_scores.items():
        report[name] = {
            "total": s.total,
            "tier1": s.tier1,
            "tier2": s.tier2,
            "tier3": s.tier3,
            "tier4": s.tier4,
            "tier1_pct": s.tier1 / s.total if s.total else 0.0,
            "tier2_pct": s.tier2 / s.total if s.total else 0.0,
            "tier3_pct": s.tier3 / s.total if s.total else 0.0,
            "tier4_pct": s.tier4 / s.total if s.total else 0.0,
            "per_encoding": s.per_encoding,
            "failures": s.failures,
        }
    print(json.dumps(report, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for benchmark_char_dataset.py."""
    parser = argparse.ArgumentParser(
        description="Benchmark chardet vs charset-normalizer on char-dataset.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Force re-run of charset-normalizer, ignoring cached results",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--chardet-only",
        action="store_true",
        default=False,
        help="Run chardet only (skip charset-normalizer)",
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        metavar="N",
        help="Filter summary output to a single tier (1-4)",
    )
    parser.add_argument(
        "--failures",
        action="store_true",
        default=False,
        help="Print detailed failure list",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        metavar="NAME",
        help="Filter per-encoding table to a single encoding",
    )
    args = parser.parse_args()

    # Force line-buffered stdout for visibility when piped
    sys.stdout.reconfigure(line_buffering=True)

    # ---- 1. Data acquisition ----
    clone_char_dataset(_CHAR_DATASET_DIR)
    files = collect_char_dataset_files(_CHAR_DATASET_DIR)
    print(f"Collected {len(files)} test files from char-dataset")

    if args.encoding:
        try:
            enc_filter = codecs.lookup(args.encoding).name
        except LookupError:
            enc_filter = args.encoding.lower()
        files = [(e, p) for e, p in files if e == enc_filter]
        print(f"Filtered to {len(files)} files for encoding '{enc_filter}'")

    if not files:
        print("No files to process. Exiting.")
        sys.exit(1)

    # ---- 2. Run chardet ----
    print("Running chardet ...")
    chardet_results = run_chardet(files)
    chardet_scores = score_results(files, chardet_results)
    all_scores: dict[str, TierScores] = {
        f"chardet {chardet.__version__}": chardet_scores,
    }

    # ---- 3. Run charset-normalizer (optional, with caching) ----
    cn_label: str | None = None
    if not args.chardet_only:
        _CACHE_DIR.mkdir(exist_ok=True)
        use_cache = not args.no_cache

        # Try to resolve cn version without a venv for cache lookup
        cn_version = _resolve_cn_version()
        cn_results: list[DetectionResult] | None = None

        if use_cache:
            cn_results = load_cn_cache(_CACHE_DIR, cn_version, files)
            if cn_results is not None:
                print(f"  Loaded charset-normalizer {cn_version} results from cache")

        if cn_results is None:
            venv_dir: Path | None = None
            try:
                venv_dir, cn_python, cn_version = create_cn_venv()
                print(f"  Running charset-normalizer {cn_version} ...")
                cn_results = run_charset_normalizer(files, cn_python)
                if use_cache:
                    save_cn_cache(_CACHE_DIR, cn_version, files, cn_results)
            except Exception as e:
                print(
                    f"  WARNING: charset-normalizer run failed: {e}",
                    file=sys.stderr,
                )
                print("  Falling back to chardet-only mode.", file=sys.stderr)
                cn_results = None
            finally:
                if venv_dir is not None:
                    cleanup_venv(venv_dir)

        if cn_results is not None:
            cn_label = f"charset-normalizer {cn_version}"
            all_scores[cn_label] = score_results(files, cn_results)

    # ---- 4. Report ----
    if args.json_output:
        print_json_report(all_scores)
        return

    print_summary(all_scores, tier_filter=args.tier)

    if not args.encoding:
        print_per_encoding(all_scores)

    if args.failures:
        for lib_name, scores in all_scores.items():
            print_failures(scores, label=lib_name)


if __name__ == "__main__":
    main()

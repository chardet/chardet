#!/usr/bin/env python3
"""Verify no overlap between training cache and test data.

Loads all cached training articles and test data files, fingerprints both,
and reports any intersection.

Usage:
    uv run python scripts/verify_no_overlap.py
    uv run python scripts/verify_no_overlap.py --test-data-dir tests/data --cache-dir data/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from data_sources import TEXT_SOURCES, hash_exclusion_set
from exclusions import build_exclusion_set, overlaps_exclusions


def check_overlap(
    test_data_dir: Path,
    cache_dir: Path,
) -> list[str]:
    """Check for overlapping content between training cache and test data.

    Returns the paths of training articles that reproduce a test file.
    """
    test_index = build_exclusion_set(test_data_dir)
    if not test_index:
        return []

    overlaps: list[str] = []

    for source in TEXT_SOURCES:
        source_dir = cache_dir / source
        if not source_dir.is_dir():
            continue
        for lang_dir in sorted(source_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            for article_file in sorted(lang_dir.iterdir()):
                if article_file.suffix != ".txt":
                    continue
                text = article_file.read_text(encoding="utf-8")
                if overlaps_exclusions(text, test_index):
                    rel_path = f"{source}/{lang_dir.name}/{article_file.name}"
                    overlaps.append(rel_path)

    return overlaps


def _read_metadata_field(metadata_path: Path, field: str) -> str | None:
    """Read a top-level quoted string field from the training metadata."""
    if not metadata_path.is_file():
        return None
    prefix = f"{field}:"
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip('"')
        if line.startswith("models:"):
            break
    return None


def _git(test_data_dir: Path, *args: str) -> str | None:
    """Run a git command in *test_data_dir*, or None on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(test_data_dir), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _differing_test_files(test_data_dir: Path, commit: str) -> list[str] | None:
    """List test files that differ from *commit*, or None if git cannot say.

    Untracked files are included: a test file that was added but not yet
    committed is the most likely cause of a provenance mismatch, and
    ``git diff`` alone would report nothing and leave the warning with no
    files to name.
    """
    toplevel = _git(test_data_dir, "rev-parse", "--show-toplevel")
    if toplevel is None or Path(toplevel.strip()).resolve() != test_data_dir.resolve():
        return None
    diff = _git(test_data_dir, "diff", "--name-only", commit)
    if diff is None:
        return None
    untracked = _git(test_data_dir, "ls-files", "--others", "--exclude-standard") or ""
    names = {line for line in diff.splitlines() if line.strip()}
    names.update(line for line in untracked.splitlines() if line.strip())
    return sorted(names)


def report_training_provenance(test_data_dir: Path, metadata_path: Path) -> bool:
    """Report whether every test file today was excluded from training.

    The overlap scan above compares the *current* article cache against
    test data, which cannot see the one contamination direction that
    matters here: a test file created from a corpus article, with the
    source article then removed from the cache, leaves the scan clean
    while the shipped models were still trained on that text.  Comparing
    the set of test files excluded at training time against today's
    closes that gap.

    ``train.py`` records provenance only when *every* model in models.bin
    was built from a corpus with one exclusion set removed, so a match
    here means today's entire test set was kept out of training.  An
    absent record means unverifiable, never verified.

    :returns: ``True`` only when provenance is recorded *and* matches.
    """
    recorded_hash = _read_metadata_field(metadata_path, "exclusion_set_hash")
    if recorded_hash is None:
        print(
            "UNVERIFIED: the training metadata records no exclusion set, so "
            "whether today's test files were all excluded from training "
            "cannot be determined.  A retrain covering every model (or one "
            "whose reused counts all carry the same record) sets it."
        )
        return False

    current_hash = hash_exclusion_set(build_exclusion_set(test_data_dir))
    if current_hash == recorded_hash:
        print(
            "VERIFIED: every model was trained with today's entire test set "
            "excluded from its corpus."
        )
        return True

    print()
    print("WARNING: today's test set is not the one that was excluded during training.")
    commit = _read_metadata_field(metadata_path, "test_data_commit")
    differing = _differing_test_files(test_data_dir, commit) if commit else None
    if differing:
        print(f"  {len(differing)} file(s) differ from {commit[:12]}:")
        for name in differing[:20]:
            print(f"    {name}")
        if len(differing) > 20:
            print(f"    ... and {len(differing) - 20} more")
        print(
            "  (This compares two states, so the list also covers files "
            "removed since training if this checkout is the older one.)"
        )
    elif commit is None:
        print("  No test-data commit was recorded, so the files cannot be listed.")
    else:
        print(f"  Cannot list files: {test_data_dir} is not a git checkout.")
    print(
        "  A test file added after training may have been trained on, which "
        "the scan above cannot detect once its source article is gone from "
        "the cache.  Retrain every encoding whose languages include theirs "
        "before trusting accuracy numbers."
    )
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify no overlap between training cache and test data",
    )
    parser.add_argument(
        "--test-data-dir",
        default="tests/data/",
        help="Path to test data directory",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/",
        help="Path to training data cache directory",
    )
    parser.add_argument(
        "--metadata",
        default="src/chardet/models/training_metadata.yaml",
        help="Path to the training metadata written alongside models.bin",
    )
    args = parser.parse_args()

    test_data_path = Path(args.test_data_dir)
    if test_data_path.is_symlink():
        test_data_path = test_data_path.resolve()

    cache_path = Path(args.cache_dir)

    if not test_data_path.is_dir():
        print(f"ERROR: test data dir not found: {test_data_path}", file=sys.stderr)
        sys.exit(1)

    if not cache_path.is_dir():
        print(f"ERROR: cache dir not found: {cache_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Test data: {test_data_path}")
    print(f"Cache dir: {cache_path}")
    print()

    overlaps = check_overlap(test_data_path, cache_path)

    if overlaps:
        print(f"FAIL: Found {len(overlaps)} overlapping articles:")
        for path in overlaps:
            print(f"  {path}")
        sys.exit(1)

    print("PASS: No overlap detected between training cache and test data.")
    # Advisory, not a failure: test data legitimately grows between
    # retrains, and exiting non-zero on every benign addition would train
    # readers to ignore the warning.  The overlap scan above stays the
    # hard gate.
    metadata_path = Path(args.metadata)
    if not metadata_path.is_file():
        # A mistyped --metadata must not read as "nothing to verify".
        print(f"ERROR: training metadata not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)
    report_training_provenance(test_data_path, metadata_path)
    sys.exit(0)


if __name__ == "__main__":
    main()

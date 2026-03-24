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
import sys
from pathlib import Path

from exclusions import build_exclusion_set, fingerprint_text


def check_overlap(
    test_data_dir: Path,
    cache_dir: Path,
) -> list[tuple[str, str]]:
    """Check for overlapping content between training cache and test data.

    Returns list of (training_file, fingerprint) tuples for overlapping articles.
    """
    test_fingerprints = build_exclusion_set(test_data_dir)
    if not test_fingerprints:
        return []

    overlaps: list[tuple[str, str]] = []

    for source in ("culturax", "madlad400", "wikipedia"):
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
                fp = fingerprint_text(text)
                if fp in test_fingerprints:
                    rel_path = f"{source}/{lang_dir.name}/{article_file.name}"
                    overlaps.append((rel_path, fp))

    return overlaps


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
        for path, fp in overlaps:
            print(f"  {path} (fingerprint: {fp[:16]}...)")
        sys.exit(1)
    else:
        print("PASS: No overlap detected between training cache and test data.")
        sys.exit(0)


if __name__ == "__main__":
    main()

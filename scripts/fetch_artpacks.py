#!/usr/bin/env python3
"""Fetch and prepare the ANSI artpack corpus for the zxx/cp437 art model.

Pulls extracted artpacks from the 16colo.rs archive (which provides rsync
access specifically for mirroring), keeps only text-mode art files, strips
ANSI escape sequences and SAUCE metadata, and caches the cp437-decoded
results as training articles under ``data/artpacks/zxx/``.

The model trained from this corpus is a statistical byte-bigram summary —
bigrams on art are not art; no artwork is redistributed and none can be
reconstructed from the model.

Usage:
    uv run python scripts/fetch_artpacks.py
    uv run python scripts/fetch_artpacks.py --years 1994 1995 --max-samples 5000
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from data_sources import save_article
from exclusions import build_exclusion_set, content_hash, overlaps_exclusions

RSYNC_MODULE = "rsync://16colo.rs/pack"

# Text-mode art formats.  .ans carries ANSI escape codes (stripped below);
# .asc/.nfo/.diz/.txt are plain cp437 text.  Binary formats (.rip, .xb,
# images, executables) are never transferred.
_ART_EXTENSIONS = ("ans", "asc", "nfo", "diz", "txt")

# The classic ANSI-scene era, matching the vintage of the wild artpacks in
# the test suite.
_DEFAULT_YEARS = ("1993", "1994", "1995", "1996", "1997")

# ANSI CSI escape sequences (colors, cursor movement).
_ANSI_ESCAPE_RE = re.compile(rb"\x1b\[[0-9;?=]*[@-~]")

# Control bytes to remove after escape stripping — everything below 0x20
# except \t \r \n.  cp437 maps these to glyphs, but in files they are
# control codes, not art.
_CONTROL_DELETE = bytes(b for b in range(0x20) if b not in (0x09, 0x0A, 0x0D))

# Minimum decoded length for a usable training article.
_MIN_CHARS = 200

# Minimum fraction of high bytes: articles below this are plain prose, which
# the ordinary language models already cover.  The art model should learn
# art, not English NFO text.
_MIN_HIGH_FRACTION = 0.05


def rsync_year(year: str, raw_dir: Path) -> None:
    """Mirror one year's text-mode art files into ``raw_dir/<year>``."""
    dest = raw_dir / year
    dest.mkdir(parents=True, exist_ok=True)
    includes: list[str] = ["--include=*/"]
    for ext in _ART_EXTENSIONS:
        includes.append(f"--include=*.{ext}")
        includes.append(f"--include=*.{ext.upper()}")
    cmd = [
        "rsync",
        "--no-motd",
        "-rt",
        "--prune-empty-dirs",
        *includes,
        "--exclude=*",
        f"{RSYNC_MODULE}/{year}/",
        str(dest),
    ]
    print(f"  rsync {year}...")
    result = subprocess.run(cmd, check=False)
    # Per-file errors are routine for this archive: a few unreadable
    # directories (exit 23) and DOS-era filenames whose raw cp437 bytes
    # APFS rejects as non-UTF-8 (exit 1 under Apple's openrsync, which has
    # no --iconv).  Losing a handful of files is immaterial to a
    # statistical corpus — only a transfer that produced nothing is fatal.
    if result.returncode:
        transferred = sum(1 for p in dest.rglob("*") if p.is_file())
        if transferred == 0:
            msg = f"rsync {year} failed (exit {result.returncode}), no files"
            raise RuntimeError(msg)
        print(
            f"  rsync {year}: partial transfer "
            f"(exit {result.returncode}, {transferred} files kept)"
        )


def prepare_article(data: bytes) -> str | None:
    """Convert raw art-file bytes to a training article, or None to skip."""
    # DOS convention: 0x1A ends the displayable file; SAUCE metadata and
    # comment blocks follow it.
    eof = data.find(b"\x1a")
    if eof >= 0:
        data = data[:eof]
    data = _ANSI_ESCAPE_RE.sub(b"", data)
    data = data.translate(None, _CONTROL_DELETE)
    if not data:
        return None
    high = len(data) - len(data.translate(None, bytes(range(0x80, 0x100))))
    if high < len(data) * _MIN_HIGH_FRACTION:
        return None
    text = data.decode("cp437")
    if len(text) < _MIN_CHARS:
        return None
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the artpack corpus")
    parser.add_argument("--years", nargs="+", default=list(_DEFAULT_YEARS))
    parser.add_argument("--cache-dir", default="data/")
    parser.add_argument("--max-samples", type=int, default=25000)
    parser.add_argument("--test-data-dir", default="tests/data/")
    parser.add_argument(
        "--skip-rsync",
        action="store_true",
        help="Reprocess already-downloaded raw files without rsyncing",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    raw_dir = cache_dir / "artpacks-raw"
    out_dir = cache_dir / "artpacks" / "zxx"

    exclusions = build_exclusion_set(Path(args.test_data_dir))
    print(f"Exclusion set: {len(exclusions)} fingerprints")

    if not args.skip_rsync:
        for year in args.years:
            rsync_year(year, raw_dir)

    seen: set[str] = set()
    kept = 0
    scanned = 0
    excluded = 0
    # Rebuild the corpus from scratch and scan only the requested years:
    # the raw cache may hold other years from earlier syncs, and leftover
    # articles from a previous invocation must not leak into this one.
    # Build into a temporary sibling first — the existing corpus is only
    # replaced once the rebuild has produced something, so a failed rsync
    # or an over-aggressive filter cannot destroy a good corpus.
    tmp_dir = out_dir.with_name(out_dir.name + ".rebuild")
    if tmp_dir.is_dir():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        path
        for year in args.years
        if (raw_dir / year).is_dir()
        for path in (raw_dir / year).rglob("*")
    )
    for path in candidates:
        if kept >= args.max_samples:
            break
        if not path.is_file():
            continue
        scanned += 1
        text = prepare_article(path.read_bytes())
        if text is None:
            continue
        # Whole-content hash, not the opening one: art files routinely share
        # a group header, and keying dedup on the opening collapsed hundreds
        # of distinct pieces into one.
        fp = content_hash(text)
        if fp in seen:
            continue
        if overlaps_exclusions(text, exclusions):
            excluded += 1
            continue
        seen.add(fp)
        save_article(tmp_dir, kept, text)
        kept += 1

    print(
        f"Scanned {scanned} files: kept {kept} articles, "
        f"{excluded} excluded as test data"
    )
    if kept == 0:
        shutil.rmtree(tmp_dir)
        print("ERROR: no usable art articles produced (existing corpus untouched)")
        sys.exit(1)
    if out_dir.is_dir():
        shutil.rmtree(out_dir)
    tmp_dir.replace(out_dir)


if __name__ == "__main__":
    main()

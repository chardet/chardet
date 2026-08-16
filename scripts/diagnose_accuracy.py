#!/usr/bin/env python3
"""Diagnose encoding detection accuracy failures against the chardet test suite.

This script runs chardet.detect() on every test file and produces a detailed
breakdown of failures grouped by expected encoding, with special attention to
problematic encodings.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import collect_test_files

import chardet
from chardet.enums import EncodingEra
from chardet.evaluation import is_acceptable
from chardet.registry import lookup_encoding

# ---------------------------------------------------------------------------
# Main diagnostic
# ---------------------------------------------------------------------------

# Encodings of special interest
FOCUS_ENCODINGS = {
    "koi8-r",
    "windows-1250",
    "johab",
    "iso-8859-1",
    "windows-1252",
    "iso-8859-15",
    "cp037",
    "cp500",
    "cp437",
    "iso-8859-13",
    "macroman",
    "iso-8859-2",
    "iso-8859-16",
}


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "tests" / "data"
    if not data_dir.is_dir():
        print(f"ERROR: Test data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    test_files = collect_test_files(data_dir)
    print(f"Found {len(test_files)} test files\n")

    # ---- Per-file results ----
    # For each expected encoding (normalized): track correct/total/failures
    enc_total: Counter[str] = Counter()
    enc_correct: Counter[str] = Counter()
    # failures[normalized_expected] -> list of (detected_raw, confidence, size, path)
    failures: dict[str, list[tuple[str | None, float, int, str]]] = defaultdict(list)
    none_results: list[
        tuple[str, str, int, str]
    ] = []  # (expected, language, size, path)

    total = 0
    correct = 0

    for expected_encoding, language, filepath in test_files:
        data = filepath.read_bytes()
        result = chardet.detect(
            data, encoding_era=EncodingEra.ALL, prefer_superset=True
        )
        detected = result["encoding"]
        confidence = result["confidence"]
        size = len(data)
        short_path = f"{filepath.parent.name}/{filepath.name}"

        norm_expected = (
            "None"
            if expected_encoding is None
            else lookup_encoding(expected_encoding) or expected_encoding
        )

        total += 1
        enc_total[norm_expected] += 1

        if is_acceptable(data, expected_encoding, detected):
            correct += 1
            enc_correct[norm_expected] += 1
        else:
            failures[norm_expected].append((detected, confidence, size, short_path))
            if detected is None and expected_encoding is not None:
                none_results.append((expected_encoding, language, size, short_path))

    # ---- Overall summary ----
    accuracy = correct / total if total else 0.0
    print("=" * 80)
    print(f"OVERALL ACCURACY: {correct}/{total} = {accuracy:.1%}")
    print("=" * 80)

    # ---- None results ----
    print(f"\n{'=' * 80}")
    print(f"FILES WHERE detect() RETURNED None: {len(none_results)}")
    print("=" * 80)
    if none_results:
        none_by_enc: dict[str, int] = Counter()
        for exp, _lang, _sz, _path in none_results:
            none_by_enc[exp] += 1
        for enc, count in sorted(none_by_enc.items(), key=lambda x: -x[1]):
            print(f"  {enc}: {count} files returned None")
        print()
        print("  Individual None results:")
        for exp, lang, sz, path in none_results:
            print(f"    expected={exp}, lang={lang}, size={sz:,}B, path={path}")
    else:
        print("  (none)")

    # ---- Per-encoding breakdown (all encodings, sorted by failure count) ----
    print(f"\n{'=' * 80}")
    print("PER-ENCODING ACCURACY (sorted by number of failures)")
    print("=" * 80)

    # Build rows: (failures, normalized_enc, total, correct, accuracy)
    rows = []
    all_encodings = set(enc_total.keys())
    for enc in all_encodings:
        t = enc_total[enc]
        c = enc_correct[enc]
        f = t - c
        acc = c / t if t else 0.0
        rows.append((f, enc, t, c, acc))
    rows.sort(key=lambda r: (-r[0], r[1]))

    for fail_count, enc, t, c, acc in rows:
        marker = (
            " <<<"
            if any((lookup_encoding(fe) or fe) == enc for fe in FOCUS_ENCODINGS)
            else ""
        )
        print(f"\n  {enc}: {c}/{t} correct ({acc:.1%}) — {fail_count} failures{marker}")
        if fail_count == 0:
            continue

        # What do we misdetect as?
        wrong_answers: Counter[str] = Counter()
        sizes = []
        for detected, _conf, sz, _path in failures[enc]:
            label = detected or "<None>"
            wrong_answers[label] += 1
            sizes.append(sz)

        avg_size = sum(sizes) / len(sizes) if sizes else 0
        print(f"    Avg failure file size: {avg_size:,.0f} bytes")
        print("    Most common wrong answers:")
        for answer, cnt in wrong_answers.most_common(10):
            pct = cnt / fail_count * 100
            print(f"      {answer}: {cnt} ({pct:.0f}%)")

    # ---- Deep dive on focus encodings ----
    print(f"\n{'=' * 80}")
    print("DEEP DIVE: FOCUS ENCODINGS (every failure listed)")
    print("=" * 80)

    focus_normalized = set()
    for fe in FOCUS_ENCODINGS:
        focus_normalized.add(lookup_encoding(fe) or fe)

    for enc in sorted(focus_normalized):
        t = enc_total.get(enc, 0)
        c = enc_correct.get(enc, 0)
        if t == 0:
            print(f"\n  {enc}: NO TEST FILES FOUND")
            continue
        f = t - c
        acc = c / t if t else 0.0
        print(f"\n  {enc}: {c}/{t} correct ({acc:.1%})")

        if f == 0:
            print("    All correct!")
            continue

        print(f"    Failures ({f}):")
        for detected, conf, sz, path in failures.get(enc, []):
            det_label = detected or "<None>"
            print(
                f"      expected={enc}, got={det_label} (conf={conf:.2f}), "
                f"size={sz:,}B, path={path}"
            )

    # ---- Quick stats ----
    print(f"\n{'=' * 80}")
    print("SUMMARY STATISTICS")
    print("=" * 80)
    total_failures = total - correct
    print(f"  Total files: {total}")
    print(f"  Correct: {correct}")
    print(f"  Failures: {total_failures}")
    print(f"  None results: {len(none_results)}")
    print(f"  Unique expected encodings: {len(all_encodings)}")
    print("  Encodings with 0% accuracy: ", end="")
    zero_acc = [enc for f, enc, t, c, acc in rows if acc == 0.0 and t > 0]
    print(", ".join(zero_acc) if zero_acc else "(none)")
    print("  Encodings with <50% accuracy: ", end="")
    low_acc = [
        f"{enc} ({acc:.0%})" for f, enc, t, c, acc in rows if 0.0 < acc < 0.5 and t > 0
    ]
    print(", ".join(low_acc) if low_acc else "(none)")


if __name__ == "__main__":
    main()

---
name: update-benchmarks
description: Use when benchmark numbers in docs/performance.rst need refreshing, after performance changes, before releases, or when the user asks to update benchmarks.
---

# Update Benchmarks

Regenerate all benchmark data and update `docs/performance.rst`.

## What Gets Updated

1. **Accuracy & Speed table** (chardet vs chardet 6.0.0 vs charset-normalizer vs cchardet)
2. **Strict (Exact-Match) Scoring table** (lenient vs strict accuracy + concession, per detector)
3. **Speed table** (files/s + mean/median/p90/p95/p99 latency columns)
4. **Latency by Script Family table** (CJK vs non-CJK split, per detector)
5. **Memory table** (chardet vs chardet 6.0.0 vs charset-normalizer vs cchardet)
6. **Memory per Detection table** (per-call peak allocation percentiles)
7. **Language Detection table**
8. **charset-normalizer's Test Set table** (--cn-dataset subset, lenient + strict)
9. **Thread Safety table** (3.13, 3.13t, 3.14, 3.14t, pure + mypyc, 1/2/4/8 threads)
10. **Optional mypyc Compilation table** (pure vs mypyc on current CPython)
11. **Performance Across Python Versions table** (CPython 3.10-3.14 mypyc + pure, PyPy 3.10-3.11 pure)
12. **Historical Performance table** — on a release, append a row for the new version (accuracy, files/s, language); do not re-measure old rows

Also update `docs/index.rst`, `docs/faq.rst`, and `README.md` with derived numbers.

## Step 1: Run Benchmarks

Run these sequentially (not in parallel — concurrent builds cause `/dev/null` permission errors):

```bash
# 1a. Main comparison (accuracy, speed, memory) — chardet + charset-normalizer + cchardet
uv run python scripts/compare_detectors.py --memory --cn --cchardet --mypyc

# 1b. chardet 6.0.0 comparison (accuracy, speed only — memory is very slow for 6.0.0)
uv run python scripts/compare_detectors.py -c 6.0.0 --mypyc

# 1c. charset-normalizer dataset subset
uv run python scripts/compare_detectors.py --cn-dataset --cn --mypyc

# 1d. Cross-version mypyc (CPython only — PyPy can't do mypyc)
uv run python scripts/compare_detectors.py --python 3.10 --python 3.11 --python 3.12 --python 3.13 --python 3.14 --mypyc

# 1e. Cross-version pure (all interpreters)
uv run python scripts/compare_detectors.py --python 3.10 --python 3.11 --python 3.12 --python 3.13 --python 3.14 --python pypy3.10 --python pypy3.11 --pure

# 1f. Thread safety (wall-clock times — use detection: field, not sum of per-file times)
for py in 3.13 3.14 3.13t 3.14t; do
  for build in "--pure" "--mypyc"; do
    for threads in 1 2 4 8; do
      echo "=== $py $build threads=$threads ==="
      uv run python scripts/compare_detectors.py --python "$py" $build --threads "$threads" 2>&1 | grep 'detection:'
    done
  done
done
```

Memory benchmarks are off by default (pass `--memory` to include them). Step 1a includes `--memory` for chardet, charset-normalizer, and cchardet. Step 1b runs chardet 6.0.0 without memory because its memory benchmark is extremely slow. If you need chardet 6.0.0 memory numbers, add `--memory` to step 1b.

## Step 2: Extract Key Numbers

From the main comparisons (1a + 1b), extract:
- **Accuracy (lenient)**: `X/<total> = XX.X%` for each detector
- **Accuracy (strict)**: lenient, strict, and concession columns from the `STRICT vs LENIENT ENCODING ACCURACY` table (lenient credits supersets / byte-order variants / decoded-output equivalence; strict is exact match after alias normalization; concession = files won only under lenient rules)
- **Speed**: total, mean, median, p90, p95, p99, max from the `DETECTION RUNTIME DISTRIBUTION` table
- **Script-family latency**: the CJK and non-CJK rows (files, mean, median, p95, p99, max) from the `LATENCY BY SCRIPT FAMILY` table
- **Files/s**: `<total files> / total_seconds`
- **Memory (process)**: import time, import mem, peak mem, RSS
- **Memory (per detection)**: mean, median, p90, p95, p99 from the `PEAK MEMORY PER DETECTION` table (requires `--memory`; the docs table deliberately omits the max — see the note under "Memory per Detection" in performance.rst)
- **Language**: `X/<total> = XX.X%` for each detector

From the cn-dataset run (1c), also extract the **strict** accuracy for both detectors — the docs discuss how the lenient result reverses under strict scoring on that subset.

The per-encoding concession breakdowns quoted in the docs prose (e.g. "51 ``iso8859-5`` -> ``cp1251``") are **not** printed by compare_detectors.py. Recompute them from the cached per-file results in `.benchmark_results/` (each row has `expected` and `detected`): count `(expected, detected)` pairs where `chardet.evaluation.is_correct()` is true but `is_exact_match()` is false, and report the most common ones.

From thread safety (1f), extract **wall-clock** detection time (the `(detection: X.XXs)` field), NOT the sum-of-per-file-times in the timing distribution.

## Step 3: Update Docs

### docs/performance.rst
Update all tables and derived comparison text:
- Accuracy & Speed tables: numbers from steps 1a + 1b (the Speed table includes p90/p95/p99 columns)
- Strict (Exact-Match) Scoring table: lenient/strict/concession from step 1a + 1b, plus the prose naming the top concession pairs (recomputed per Step 2) and the "+X.Xpp narrows to +X.Xpp" comparison
- Latency by Script Family table: CJK vs non-CJK rows from step 1a; refresh the surrounding prose about which detector wins the CJK tail — this section's claims are sensitive to CJK-path optimizations, so reread the narrative rather than only swapping numbers
- Memory table: numbers from step 1a (skip if unchanged)
- Memory per Detection table: percentiles from step 1a; keep the max excluded from the table, and refresh the "flat vs growing tail" narrative if the shape changed
- Language Detection table: numbers from steps 1a + 1b
- charset-normalizer's Test Set table: numbers from step 1c, including the strict-scoring reversal paragraph
- Thread Safety table: wall-clock times from step 1f
- Optional mypyc Compilation table: use the current default CPython (e.g., 3.14) pure and mypyc numbers from steps 1d/1e. Speedup = mypyc_files_per_sec / pure_files_per_sec
- Performance Across Python Versions table: all numbers from steps 1d/1e
- Historical Performance table: on a release, append the new version's row; leave prior rows alone
- Derived text: "Xx faster than chardet 6.0.0" = chardet_6_mean / chardet_7_mean, "+X.Xpp" accuracy differences, per-percentile speed comparisons ("1.7x at the median, 1.3x at p95, 1.2x at p99") and worst-case comparison, "CPython X.XX + mypyc is the fastest" = highest files/s, PyPy reaches "XX-XX% of mypyc" = pypy_fps / min_mypyc_fps and pypy_fps / max_mypyc_fps

### docs/index.rst
- Accuracy percentage and file count
- Speed comparison multipliers (vs 6.0.0, vs charset-normalizer)

### docs/faq.rst
- charset-normalizer comparison numbers (accuracy incl. strict, per-percentile speed, memory incl. per-detection median/p99, language)
- cchardet comparison numbers
- The CJK-tail comparison (charset-normalizer's p99 vs ours) — like the script-family section, recheck the claim's direction, not just the numbers

### README.md
- "Why chardet 7.0?" section: accuracy, speed multipliers, file count
- Comparison table: accuracy, speed (files/s), language accuracy, peak memory for chardet (mypyc + pure), chardet 6.0.0, charset-normalizer
- Example output dicts (add `mime_type` key if missing)
- "What's New in 7.0" section: speed/accuracy claims

## Step 4: Verify and Commit

```bash
uv run sphinx-build -W docs docs/_build
git add docs/performance.rst docs/index.rst docs/faq.rst README.md
git commit -m "docs: update benchmark numbers for 7.X.0"
git push
```

## Notes

- `compare_detectors.py` caches results in `.benchmark_results/`. Cache keys include the detector version, Python version, build type (pure/mypyc), thread count, and a content hash of the benchmark scripts (`benchmark_time.py`, `benchmark_memory.py`, `utils.py`), equivalence rules (`equivalences.py`), and the test-data submodule commit. Results auto-invalidate when any of these change. The chardet version includes the git commit hash (e.g., `7.2.1.dev25+g3680cc1ad`), so any chardet commit invalidates the local chardet cache, and any test-data change invalidates all caches. The `--cn-dataset` flag doesn't need its own cache key because the benchmark subprocess always runs on all files; the subset filter is applied when aggregating results. Only use `--no-cache` if you need to re-benchmark an unchanged version (e.g., to reduce measurement noise).
- Memory benchmarks are off by default. Pass `--memory` to include them. Only step 1a needs memory.
- PyPy can't use `--mypyc` (mypyc is CPython-only). Always use `--pure` for PyPy.
- `--python` is repeatable: `--python 3.12 --python 3.13` runs both sequentially.
- The test file count (currently 2,517) may change when test-data is updated. The language-detection denominator is smaller (binary/no-language files are excluded) — read both totals from the output rather than assuming them.

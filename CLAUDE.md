# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

0BSD-licensed, ground-up rewrite of chardet (the Python character encoding detector). Drop-in replacement for chardet 6.x — same package name, same public API. Zero runtime dependencies, Python 3.10+, must work on PyPy.

### Versioning

Version is derived from git tags via `hatch-vcs`. The tag is the single source of truth — no hardcoded version strings. Tags do **not** use a `v` prefix: the tag for version 7.3.0 is `7.3.0`, not `v7.3.0`. At tag `7.0.0` the version is `7.0.0`; between tags it's auto-incremented (e.g., `7.0.1.dev3+g...`). The generated `src/chardet/_version.py` is gitignored and should never be committed.

When releasing `X.Y.Z`, also tag the `chardet/test-data` repo with `X.Y.Z` at its current `main` HEAD. The accuracy test suite clones test-data at the matching version tag for release builds, falling back to `main` for dev builds. This ensures `test_accuracy.py` continues to pass for released versions even after test-data is updated.

## Commands

### Development Setup

```bash
uv sync                    # install dependencies
prek install               # set up pre-commit hooks (ruff lint+format, trailing whitespace, etc.)
```

### Testing

```bash
uv run python -m pytest -n auto                      # run all tests (excludes benchmarks)
uv run python -m pytest -n auto tests/test_api.py    # run a specific test file
uv run python -m pytest tests/test_api.py::test_detect_empty  # run a single test
uv run python -m pytest -m benchmark -n auto         # run benchmark tests only
uv run python -m pytest -x -n auto                   # stop on first failure
```

Test data is auto-cloned from `chardet/test-data` GitHub repo on first run (cached in `tests/data/`, gitignored). Accuracy tests are dynamically parametrized from this data via `conftest.py`.

### Linting & Formatting

```bash
uv run ruff check .        # lint
uv run ruff check --fix .  # lint with auto-fix
uv run ruff format .       # format
```

### Training Models

```bash
uv run --group training python scripts/train.py   # retrain bigram models from CulturaX/MADLAD-400/Wikipedia data
uv run python scripts/verify_no_overlap.py  # verify no train/test data overlap
```

Training data is cached in `data/` (gitignored) under `data/culturax/`,
`data/madlad400/`, and `data/wikipedia/` per language. Models are saved to
`src/chardet/models/models.bin`. Test data articles are automatically excluded
from training via content fingerprinting to prevent train/test overlap.

### Benchmarks & Diagnostics

```bash
uv run python scripts/benchmark_time.py     # latency benchmarks
uv run python scripts/benchmark_memory.py   # memory usage benchmarks
uv run python scripts/diagnose_accuracy.py  # detailed accuracy diagnostics
uv run python scripts/compare_detectors.py  # compare against original chardet
```

### Documentation

```bash
uv sync --group docs                          # install Sphinx, Furo, etc.
uv run sphinx-build docs docs/_build          # build HTML docs
uv run sphinx-build -W docs docs/_build       # build with warnings as errors
uv run python scripts/generate_encoding_table.py > docs/supported-encodings.rst  # regenerate encoding table
```

Docs use Sphinx with Furo theme. API reference is auto-generated from source docstrings via autodoc. Published to ReadTheDocs on tag push (`.readthedocs.yaml`). Source files are in `docs/`; `docs/plans/` is excluded from the build.

### Compiled builds (optional)

Two compilers, two hooks. **Enable both** — enabling one alone is not wrong, just unoptimized:

```bash
HATCH_BUILD_HOOK_ENABLE_MYPYC=true HATCH_BUILD_HOOK_ENABLE_CUSTOM=true uv build
```

**mypyc** compiles 13 modules: `models/__init__.py`, `pipeline/structural.py`, `pipeline/validity.py`, `pipeline/statistical.py`, `pipeline/utf1632.py`, `pipeline/utf8.py`, `pipeline/escape.py`, `pipeline/orchestrator.py`, `pipeline/confusion.py`, `pipeline/magic.py`, `pipeline/ascii.py`, `pipeline/language.py`, `pipeline/postprocess.py`. These cannot use `from __future__ import annotations` (FA100 is ignored for them in ruff config).

**Cython** compiles `_kernel.py` alone — the bigram scoring loop, ~36% of compiled runtime — using the build-time-only types in `_kernel.pxd`. Worth about 1.4x. The `.py` is the single implementation and runs interpreted on PyPy and in pure wheels; `models` detects which it has and picks the matching scoring path.

Both hooks are `enable-by-default = false` so their build dependencies stay off pure source installs. Keep the kernel small: an earlier version also held the profile builder and the row-max bound, and moving those out of their mypyc modules made a mypyc-only build **slower than compiling nothing**, because mypyc stopped seeing those loops.

A compiled build leaves nothing behind — the Cython hook's `finalize` deletes every in-tree extension, mypyc's included. That matters: a leftover `.so` shadows the `.py` beside it, is gitignored so `git status` stays clean, and silently makes later edits and "pure" test runs meaningless.

## Architecture

### Detection Pipeline (`src/chardet/pipeline/orchestrator.py`)

All detection flows through `run_pipeline()`, which runs stages in order — each stage either returns a definitive result or passes to the next:

1. **BOM** (`bom.py`) — byte order mark → confidence 1.0
2. **UTF-16/32 patterns** (`utf1632.py`) — null-byte patterns for BOM-less Unicode
3. **Escape sequences** (`escape.py`) — ISO-2022-JP/KR, HZ-GB-2312
4. **Magic numbers** (`magic.py`) — file signature detection (e.g., PDF, images)
5. **Binary detection** (`binary.py`) — null bytes / control chars → encoding=None
6. **Markup charset** (`markup.py`) — `<meta charset>` / `<?xml encoding>` extraction, plus `promote_markup_superset()` which swaps the declared encoding to its Windows superset (Shift_JIS→CP932, EUC-KR→CP949) when structural evidence supports it
7. **ASCII** (`ascii.py`) — pure 7-bit check
8. **UTF-8** (`utf8.py`) — structural multi-byte validation
9. **Byte validity** (`validity.py`) — eliminate encodings that can't decode the data
10. **CJK gating** (in orchestrator) — eliminate CJK candidates lacking multi-byte structure
11. **Structural probing** (`structural.py`) — score multi-byte encoding fit
12. **Statistical scoring** (`statistical.py`) — bigram frequency models for final ranking
13. **Post-processing** (`postprocess.py:postprocess_results()`) — chained rank corrections: confusion-group resolution (delegated to `confusion.py`), niche Latin demotion, KOI8-T promotion
14. **Language detection** (`language.py`) — three-tier fill of the `language` field on every result (single-language map → multi-language bigram → UTF-8 fallback). Runs in `run_pipeline` after the core pipeline.

### Key Types

- **`DetectionResult`** (`pipeline/__init__.py`) — frozen dataclass: `encoding`, `confidence`, `language`, `mime_type`
- **`EncodingInfo`** (`registry.py`) — frozen dataclass: `name`, `aliases`, `era`, `is_multibyte`, `languages`
- **`EncodingEra`** (`enums.py`) — IntFlag for filtering candidates: `MODERN_WEB`, `LEGACY_ISO`, `LEGACY_MAC`, `LEGACY_REGIONAL`, `DOS`, `MAINFRAME`, `ALL`
- **`BigramProfile`** (`models/__init__.py`) — pre-computed weighted bigram frequencies, computed once and reused across all candidate models

### Model Format

Binary file `src/chardet/models/models.bin` — v2 dense zlib-compressed format (magic `CMD2`). Each model is a 65536-byte lookup table indexed by `(b1 << 8) | b2`, stored as a `memoryview` of the decompressed blob. Model keys use `language/encoding` format (e.g., `French/windows-1252`). Loaded lazily on first `detect()` call and cached.

### Public API (`src/chardet/__init__.py`)

- `detect(byte_str, encoding_era, max_bytes, *, prefer_superset, compat_names, include_encodings, exclude_encodings, no_match_encoding, empty_input_encoding)` → `{"encoding": ..., "confidence": ..., "language": ..., "mime_type": ...}`
- `detect_all(byte_str, ignore_threshold, ...)` → list of result dicts
- `UniversalDetector` (`detector.py`) — streaming interface with `feed()`/`close()`/`reset()`

### Accuracy Evaluation (`evaluation.py`)

Tables and predicates for asking "is this detection acceptable, given what was expected?" Defines directional supersets (e.g., utf-8 is acceptable when ascii is expected), bidirectional encoding groups (e.g., ISO-2022-JP variants), and bidirectional language groups (e.g., Slovak/Czech). Used by `tests/test_accuracy.py`, `tests/test_github_issues.py`, and the diagnostic/benchmarking scripts in `scripts/`.

### Public-API Encoding Names (`output_names.py`)

Two output transforms applied to detection results before they cross the public API: `apply_preferred_superset` (for the `prefer_superset=True` option, remaps ISO subsets to Windows supersets) and `apply_compat_names` (for the default `compat_names=True` mode, maps internal codec names to chardet 5.x/6.x display names). Used by `__init__.py` and `detector.py`.

`equivalences.py` is a deprecation shim that re-exports both modules' contents until 8.0.

### Scripts

`scripts/` directory contains training, benchmarking, and diagnostic tools. `scripts/utils.py` provides shared utilities (e.g., `collect_test_files()`) imported by both tests and scripts.

## Workflow Preferences

- **Never use `python -c`**: Always write Python code to a temp file (e.g., `/tmp/script.py`) and run it instead of using inline `python -c "..."`. Inline commands trigger shell safety prompts due to special characters.
- **Never use `cd <dir> && git ...`**: Use `git -C <dir> ...` instead to avoid shell safety prompts about compound `cd` + `git` commands.

## Conventions

- Ruff with `select = ["ALL"]` and targeted ignores — check `pyproject.toml` for the full ignore list
- `from __future__ import annotations` in all source files (except mypyc-compiled modules)
- Frozen dataclasses with `slots=True` for data types
- Era assignments in `registry.py` match chardet 6.0.0
- Training data (CulturaX corpus + HTML) is never the same as evaluation data (chardet test suite)

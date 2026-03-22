# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

0BSD-licensed, ground-up rewrite of chardet (the Python character encoding detector). Drop-in replacement for chardet 6.x — same package name, same public API. Zero runtime dependencies, Python 3.10+, must work on PyPy.

### Versioning

Version is derived from git tags via `hatch-vcs`. The tag is the single source of truth — no hardcoded version strings. At tag `v7.0.0` the version is `7.0.0`; between tags it's auto-incremented (e.g., `7.0.1.dev3+g...`). The generated `src/chardet/_version.py` is gitignored and should never be committed.

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
uv run python scripts/train.py   # retrain bigram models from CulturaX/HTML data
```

Training data is cached in `data/` (gitignored). Models are saved to `src/chardet/models/models.bin`.

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

### Building with mypyc (optional)

```bash
HATCH_BUILD_HOOK_ENABLE_MYPYC=true uv build  # compile hot-path modules
```

Compiled modules: `models/__init__.py`, `pipeline/structural.py`, `pipeline/validity.py`, `pipeline/statistical.py`, `pipeline/utf1632.py`, `pipeline/utf8.py`, `pipeline/escape.py`. These modules cannot use `from __future__ import annotations` (FA100 is ignored for them in ruff config).

## Architecture

### Detection Pipeline (`src/chardet/pipeline/orchestrator.py`)

All detection flows through `run_pipeline()`, which runs stages in order — each stage either returns a definitive result or passes to the next:

1. **BOM** (`bom.py`) — byte order mark → confidence 1.0
2. **UTF-16/32 patterns** (`utf1632.py`) — null-byte patterns for BOM-less Unicode
3. **Escape sequences** (`escape.py`) — ISO-2022-JP/KR, HZ-GB-2312
4. **Binary detection** (`binary.py`) — null bytes / control chars → encoding=None
5. **Markup charset** (`markup.py`) — `<meta charset>` / `<?xml encoding>` extraction
6. **ASCII** (`ascii.py`) — pure 7-bit check
7. **UTF-8** (`utf8.py`) — structural multi-byte validation
8. **Byte validity** (`validity.py`) — eliminate encodings that can't decode the data
9. **CJK gating** (in orchestrator) — eliminate CJK candidates lacking multi-byte structure
10. **Structural probing** (`structural.py`) — score multi-byte encoding fit
11. **Statistical scoring** (`statistical.py`) — bigram frequency models for final ranking
12. **Post-processing** (`_postprocess_results()` in orchestrator) — confusion group resolution (`confusion.py`), niche Latin demotion, KOI8-T promotion

### Key Types

- **`DetectionResult`** (`pipeline/__init__.py`) — frozen dataclass: `encoding`, `confidence`, `language`
- **`EncodingInfo`** (`registry.py`) — frozen dataclass: `name`, `aliases`, `era`, `is_multibyte`, `languages`
- **`EncodingEra`** (`enums.py`) — IntFlag for filtering candidates: `MODERN_WEB`, `LEGACY_ISO`, `LEGACY_MAC`, `LEGACY_REGIONAL`, `DOS`, `MAINFRAME`, `ALL`
- **`BigramProfile`** (`models/__init__.py`) — pre-computed weighted bigram frequencies, computed once and reused across all candidate models

### Model Format

Binary file `src/chardet/models/models.bin` — sparse bigram tables loaded via `struct.unpack`. Each model is a 65536-byte lookup table indexed by `(b1 << 8) | b2`. Model keys use `language/encoding` format (e.g., `French/windows-1252`). Loaded lazily on first `detect()` call and cached.

### Public API (`src/chardet/__init__.py`)

- `detect(data, max_bytes, chunk_size, encoding_era)` → `{"encoding": ..., "confidence": ..., "language": ...}`
- `detect_all(...)` → list of result dicts
- `UniversalDetector` (`detector.py`) — streaming interface with `feed()`/`close()`/`reset()`

### Encoding Equivalences (`equivalences.py`)

Defines acceptable detection mismatches for accuracy testing: directional supersets (e.g., utf-8 is acceptable when ascii is expected) and bidirectional equivalents (UTF-16/32 endian variants). Used by `tests/test_accuracy.py` and diagnostic scripts.

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

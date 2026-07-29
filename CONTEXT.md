# chardet

chardet detects the character encoding of a byte string and the language of its decoded text. Detection is a sequential pipeline: cheap deterministic checks (BOM, magic numbers, escape sequences) run first, followed by byte-validity filtering and finally statistical scoring against pre-trained bigram models. Each stage either commits a result, prunes the candidate set, scores survivors, or refines the final ranking.

## Language

### Result shape

**DetectionResult**:
A frozen dataclass holding `encoding`, `confidence`, `language`, and `mime_type` for one detection candidate.

**Confidence**:
A score in `[0.0, 1.0]` reflecting how the result was determined: 1.0 for BOM, 0.95 for deterministic stages (escape, markup, ASCII, BOM-less UTF-16/32, binary), 0.80–0.99 for UTF-8 scaled by multi-byte ratio, and lower scores for statistical ranking.

**Binary** (the `encoding=None` case):
A detection outcome where data is classified as not-text — null bytes, high control-character ratio, or a recognized binary file signature. Distinct from the **Binary detection stage** that produces it.

### Pipeline architecture

**Pipeline**:
The full sequence of stages in `chardet.pipeline/`, composed by `run_pipeline`. Stateless per-stage; per-call state lives in `PipelineContext`.

**Orchestrator**:
The `run_pipeline` / `_run_pipeline_core` pair in `pipeline/orchestrator.py` that calls each stage in order and threads the `PipelineContext`. A single function, not a dispatcher — see ADR-0001.

**PipelineContext**:
The mutable per-run state object created by `run_pipeline` and threaded through stages. Holds caches (`analysis_cache`, `mb_scores`, `mb_coverage`, `non_ascii_count`) so later stages can reuse work done earlier.

**Stage**:
A function in `chardet.pipeline.<name>` invoked by the **Orchestrator**. Stateless w.r.t. module-level state. Stages come in four kinds:

- **Early-exit stage** — returns a `DetectionResult` to halt the pipeline (BOM, UTF-16/32 patterns, escape, magic, binary, markup, ASCII, UTF-8) or `None` to pass through.
- **Filter stage** — removes candidates from the working set (byte-validity filtering, CJK gating).
- **Scoring stage** — assigns scores to surviving candidates (structural probing, statistical scoring).
- **Refinement stage** — rewrites a result list after scoring (postprocess, language detection).

### Pipeline stages

Listed in execution order. Each stage's name matches its module in `chardet.pipeline/`.

1. **BOM** — byte order mark detection. Confidence 1.0.
2. **UTF-16/32 patterns** — null-byte patterns for BOM-less Unicode.
3. **Escape sequences** — ISO-2022-JP/KR, HZ-GB-2312.
4. **Magic numbers** — 40+ binary file signatures (PNG, PDF, ZIP, etc.) plus ZIP-entry-name disambiguation for OOXML/EPUB.
5. **Binary detection** — null-byte / control-char threshold for unrecognized binary.
6. **Markup charset** — `<meta charset>`, `<?xml encoding>`, PEP 263 coding-declaration extraction. Includes **markup superset promotion**.
7. **ASCII** — pure-7-bit fast path.
8. **UTF-8 validation** — multi-byte structural check.
9. **Byte-validity filtering** — drop candidates whose codec cannot decode the data. An incomplete multi-byte sequence at the very end is tolerated, since the input is usually a prefix of a larger whole.
10. **CJK gating** — drop CJK candidates lacking multi-byte structure (pair ratio, high-byte count, byte coverage, lead-byte diversity).
11. **Structural probing** — score multi-byte encoding fit (`pipeline/structural.py`).
12. **Statistical scoring** — bigram cosine similarity against language-specific **BigramProfile**s.
13. **Post-processing** — chained rank corrections: **confusion-group resolution**, **niche Latin demotion**, **KOI8-T promotion**.
14. **Language detection** — three-tier fill of the `language` field on every result.

### Detection concepts

**Encoding era** (`EncodingEra`):
A bit-flag classification of encodings into `MODERN_WEB`, `LEGACY_ISO`, `LEGACY_MAC`, `LEGACY_REGIONAL`, `DOS`, and `MAINFRAME`. The public-API `encoding_era` parameter narrows the candidate set before detection runs.

**Encoding superset relationship**:
A factual property between two encodings where one decodes a strict superset of the bytes the other decodes (e.g. CP932 ⊃ Shift_JIS, Windows-1252 ⊃ ISO-8859-1, GB18030 ⊃ GB2312). Lossless replacement: any byte sequence valid in the subset is valid in the superset.

**Markup superset promotion**:
Internal pipeline behavior in `pipeline/markup.py`. When the markup-declared encoding is a known subset (Shift_JIS, EUC-KR) and structural evidence supports the superset, the result is swapped to the superset (CP932, CP949). Always-on, part of the Markup charset stage.

**BigramProfile**:
A frozen pre-computed weighted byte-bigram representation for one (language, encoding) pair, loaded once from the **model file** and reused across calls. Used for cosine-similarity scoring in the Statistical stage.

**Confusion group**:
A set of encodings that statistical scoring cannot reliably separate (e.g. ISO-8859-1 / Windows-1252 / ISO-8859-15 on Western text). Resolved by **confusion-group resolution** in `pipeline/confusion.py`.

**Distinguishing byte map**:
A pre-computed mapping of (encoding-pair) → (set of bytes whose Unicode category differs between the two), bundled as the **confusion data file** `confusion.bin`. The data structure that drives confusion-group resolution.

**Category voting**:
The first confusion-resolution mechanism. For each distinguishing byte present in the data, vote for the encoding whose Unicode-category interpretation is more plausible.

**Bigram rescoring**:
The fallback confusion-resolution mechanism when category voting is inconclusive. Rescore the tied candidates against their bigram profiles, restricted to data positions containing distinguishing bytes.

**Niche Latin demotion**:
Postprocess rank correction. When a niche Latin encoding (e.g. ISO-8859-16) outranks a common one but the data contains none of the niche encoding's distinguishing bytes, demote it.

**KOI8-T promotion**:
Postprocess rank correction targeting Tajik Cyrillic, where statistical scoring under-ranks KOI8-T relative to its near-twin KOI8-U.

**Three-tier language detection**:
The language-detection strategy in `pipeline/language.py`: (1) single-language encodings map directly to a language, (2) multi-language encodings pick the best-matching **BigramProfile**, (3) Unicode encodings (UTF-8/16/32) decode-then-score against byte-level bigram profiles.

**CJK gating**:
The filter applied between byte-validity and structural probing that drops CJK candidates lacking genuine multi-byte structure. Prevents false CJK matches on single-byte data.

### Public-API outputs

**Canonical name**:
The internal codec name a stage produces (e.g. `windows-1252`, `cp932`). Lowercase, codec-registry-matched.

**Display name**:
The string returned to library callers after `apply_compat_names` runs (e.g. `Windows-1252`, `CP932`). Driven by `compat_names=True` (the default), which maps internal canonical names to chardet's historical display casing.

**Preferred-superset remapping** (`prefer_superset=True`):
The output transform in `output_names.apply_preferred_superset` that remaps a detected subset codec to its Windows superset before returning. Off by default; opt-in.

### Accuracy evaluation

**Equivalence rule**:
A predicate in `evaluation.py` that decides whether a detected `(encoding, language)` pair is *acceptable* given an expected pair. Distinct from byte-level equality.

**Superset acceptance**:
The directional equivalence rule that counts a superset detection as correct when a subset was expected (utf-8 acceptable for ascii, Windows-1252 for ISO-8859-1, GB18030 for GB2312). Test-suite-only — the production pipeline never sees this.

**Encoding group** / **Language group**:
Bidirectional equivalence sets in `evaluation.py`. Members are interchangeable for accuracy purposes (e.g. the ISO-2022-JP variants, or Slovak/Czech).

### Data

**Model file** (`src/chardet/models/models.bin`):
The v2 dense zlib-compressed binary file holding all **BigramProfile**s, indexed by `language/encoding` keys.

**Confusion data file** (`src/chardet/pipeline/confusion.bin`):
The binary file holding pre-computed **distinguishing byte map**s for all **confusion group** pairs.

**Training data**:
Byte samples from CulturaX, MADLAD-400, and Wikipedia used to fit the bigram profiles. Cached in `data/`, gitignored, never shipped.

**Test data**:
The `chardet/test-data` GitHub repo, cloned to `tests/data/` on first test run, tagged at the matching release version. The accuracy suite parametrizes over its files.

**Content fingerprinting**:
The mechanism in `scripts/verify_no_overlap.py` that excludes any training-data document whose hashed content also appears in the test-data repo. Guarantees no train/test overlap.

## Relationships

- A detection call produces 1+ **DetectionResult**s — one for `detect`, a ranked list for `detect_all`.
- A **DetectionResult** carries exactly one `encoding`, one `language`, one `mime_type`, one `confidence`.
- The **Pipeline** is an ordered composition of **Stage**s, each of one of four kinds.
- A **Stage** reads/writes the per-call **PipelineContext**; no module-level mutable state is shared across calls.
- A **BigramProfile** belongs to exactly one (language, encoding) pair; multiple profiles share an encoding when it serves multiple languages.
- A **Confusion group** is 2+ encodings; **Distinguishing byte maps** are keyed by ordered pairs within the group.
- **Markup superset promotion**, **Preferred-superset remapping**, and **Superset acceptance** all rely on the same **Encoding superset relationship** but apply it at different times — detection / output / evaluation respectively.

## Example dialogue

> **Architecture session:** "I want to factor postprocess into typed dispatch."
> **CONTEXT.md says:** Postprocess is a single **Refinement stage**. Its three operations — **confusion-group resolution**, **niche Latin demotion**, **KOI8-T promotion** — are chained, not pluggable. ADR-0001 also rejects typed-stage dispatch on performance grounds.

> **Architecture session:** "There's `prefer_superset`-style logic in `markup.py`. We should consolidate."
> **CONTEXT.md says:** No — those are two distinct concepts. **Markup superset promotion** is internal pipeline behavior gated on structural evidence; **preferred-superset remapping** is a post-detection output transform driven by a public-API flag. They share the underlying **encoding superset relationship**, but operate at different times.

## Flagged ambiguities

- **"superset"** appears in three independent places: **markup superset promotion** (pipeline), **preferred-superset remapping** (output), **superset acceptance** (evaluation). They share the underlying **encoding superset relationship** but operate at different times on different units. Don't conflate.
- **"binary"** is both an outcome (the `encoding=None` result) and a stage name (`pipeline/binary.py`). Disambiguate by saying "the **Binary detection stage**" vs. "a **binary** result".
- **"model"** is overloaded: the **model file** holds many **BigramProfile**s, but casual prose sometimes uses "the model" for a single profile and sometimes for the whole file. Prefer **BigramProfile** for the unit, **model file** for the artifact.
- **"language"** refers to (1) the field on **DetectionResult**, (2) the **language detection** stage that fills it, and (3) the language part of a **BigramProfile** key. Usually clear from context.

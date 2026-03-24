# Training/Test Data Separation Design

## Problem

The chardet training pipeline downloads CulturaX articles starting from index 0,
and the test data generation script also downloads articles starting from index 0
(first 20 per language). This creates guaranteed overlap: the same text used to
build bigram models is also present in the accuracy test suite.

For most languages this overlap is small (3 test files out of 15,000 training
samples). But for low-resource languages, CulturaX itself is small:

| Language          | Code | CulturaX docs | Overlap severity |
|-------------------|------|---------------|------------------|
| Scottish Gaelic   | gd   | 8,408         | Critical (training exhausts entire corpus) |
| Breton            | br   | 43,765        | High (34% of corpus used for training) |
| Maltese           | mt   | 151,320       | Moderate |
| Malay             | ms   | 238,151       | Moderate |
| Irish             | ga   | 304,251       | Low-moderate |
| Esperanto         | eo   | 460,088       | Low-moderate |
| Croatian          | hr   | 460,690       | Low-moderate |
| Tajik             | tg   | 483,835       | Low-moderate |
| Welsh             | cy   | 549,955       | Low-moderate |

All 29 languages with `culturax_00000.txt`-style test files have confirmed
overlap regardless of corpus size.

## Constraints

- **Test data is fixed.** The `chardet/test-data` repo is not modified. Changing
  it would require rerunning comparison benchmarks.
- **Training target stays at 15,000 samples per language** (configurable via
  `--max-samples`). Supplemental datasets fill gaps left by exclusions.
- **Zero runtime dependencies.** Supplemental datasets are used only at training
  time; the `datasets` library is already a training-only dependency.
- **License compatibility.** All supplemental datasets must be compatible with
  the project's 0BSD license for the trained model output.

## Design

### 1. Test Data Exclusion Mechanism

#### Building the exclusion set

On training startup, scan `tests/data/` (configurable via `--test-data-dir`) to
build a set of content fingerprints:

1. Iterate all directories matching `{encoding}-{language}` in the test data dir.
2. For each file matching `culturax_*`, decode it back to UTF-8 using the
   encoding from the directory name.
3. Compute a SHA-256 fingerprint of the **first 200 characters** of the decoded
   text. The 200-char prefix handles truncation during test file generation
   (test files may be trimmed to target sizes of 500/2000/5000 bytes).
4. Store fingerprints in a `frozenset`.

The fingerprint set is typically small (~1,950 CulturaX test files producing
fewer than 600 unique source articles, since the same article is transcoded to
multiple encodings).

#### Applying exclusions during download

The fingerprint set is checked against **every article from every data source**
(CulturaX, MADLAD-400, Wikipedia). For each downloaded article:

1. Compute the SHA-256 fingerprint of the first 200 characters.
2. If it matches the exclusion set, skip the article and continue streaming.

For CulturaX specifically, an **index-based fast path** also applies: since both
the test data generator and training script stream from index 0, articles at
indices 0-19 are known to overlap and are skipped without content hashing.
Content hashing serves as verification for these and as the primary mechanism for
`culturax_mC4_*` / `culturax_OSCAR-*` named test files where the index mapping
differs.

#### Cache invalidation

The training article cache (`data/culturax/{lang}/`, etc.) stores articles by
sequential index. When the test data exclusion set changes (new test-data version
tag), previously cached articles may include now-excluded content. To handle
this:

- Store the test-data commit hash (or a hash of the exclusion set) in a sentinel
  file (`data/.test_data_hash`).
- On startup, compare the current hash against the sentinel. On mismatch, log a
  warning that the cache may contain excluded articles and recommend
  re-downloading affected languages (or clearing the cache).

### 2. Supplemental Dataset Integration

Three data sources in priority order, each filling toward `--max-samples`:

#### Source 1: CulturaX (primary)

- HF path: `uonlp/CulturaX`, config = language code, split = `"train"`
- License: CC-BY-SA-4.0 (CulturaX itself) / mixed upstream
- Existing behavior, with the exclusion mechanism applied.
- For the 40+ languages with millions of CulturaX articles, this alone fills the
  15,000 target with negligible loss from exclusions.

#### Source 2: MADLAD-400 (first supplement)

- HF path: `allenai/MADLAD-400`, config = language code, split = `"clean"`
- License: CC-BY-4.0 (ODC-BY)
- Different processing pipeline from CulturaX (different LangID, different
  deduplication), so extracted documents differ even where the underlying Common
  Crawl source overlaps.
- Priority language coverage: gd (94K), br (33K), mt (265K), ms (2.3M),
  ga (286K), eo (260K), hr (2.8M), tg (328K), cy (431K).
- Cached in `data/madlad400/{lang}/000000.txt`, etc.
- Content hash exclusion applies.

#### Source 3: Wikipedia (second supplement)

- HF path: `wikimedia/wikipedia`, config = `"20231101.{lang}"`
- License: CC-BY-SA-3.0 / GFDL
- Zero overlap with any web-crawl corpus (editorially created content).
- Text from the `"text"` field (full article content).
- Priority language coverage: gd (~16K), br (~90K), mt (~5K), ms (~370K),
  ga (~63K), eo (~382K), hr (~229K), tg (~100K), cy (~200K).
- Cached in `data/wikipedia/{lang}/000000.txt`, etc.
- Content hash exclusion applies (a Wikipedia article could theoretically appear
  in test data via a web crawl that indexed Wikipedia mirrors).

#### Filling logic

```python
def get_texts(lang, max_samples, cache_dir, exclusions):
    texts = get_culturax_texts(lang, max_samples, cache_dir, exclusions)
    if len(texts) < max_samples:
        texts += get_madlad_texts(lang, max_samples - len(texts), cache_dir, exclusions)
    if len(texts) < max_samples:
        texts += get_wikipedia_texts(lang, max_samples - len(texts), cache_dir, exclusions)
    return texts
```

#### Language code mapping

CulturaX and MADLAD-400 use ISO 639-1 codes directly (matching the registry).
Wikipedia uses `"20231101.{lang}"` format configs. A small mapping dict handles
mismatches:

- Norwegian: `no` in registry → `no` in CulturaX/MADLAD, `20231101.no` in
  Wikipedia (Norwegian Bokmal)
- Other codes are expected to match 1:1; mismatches are logged and the source is
  skipped for that language.

### 3. Training Script Changes

#### New CLI flags

- `--test-data-dir` (default: `tests/data/`) — path to test data directory for
  building the exclusion set.
- `--skip-test-overlap / --no-skip-test-overlap` (default: `--skip-test-overlap`)
  — toggle the exclusion mechanism. Can be disabled for debugging or when test
  data is unavailable.

No new flags for dataset selection. The fallback chain (CulturaX -> MADLAD-400
-> Wikipedia) is always active. If CulturaX fills the target, the others are
never queried.

#### Refactored download functions

The current monolithic `get_texts()` becomes an orchestrator calling
source-specific functions:

- `build_exclusion_set(test_data_dir) -> frozenset[str]` — scans test data,
  returns fingerprint set.
- `get_culturax_texts(lang, needed, cache_dir, exclusions) -> list[str]` —
  existing logic with exclusion checks.
- `get_madlad_texts(lang, needed, cache_dir, exclusions) -> list[str]` — new,
  same caching pattern.
- `get_wikipedia_texts(lang, needed, cache_dir, exclusions) -> list[str]` — new,
  same caching pattern.

Each source-specific function follows the same pattern: check disk cache -> stream
from HF -> fingerprint-check each article -> cache accepted articles.

#### Download phase

The parallel download phase currently spawns threads per language. The
supplemental sources only activate when CulturaX falls short, so most languages
still only touch CulturaX. The download function handles the fallback chain
internally per language — no change to the threading model.

#### Training metadata

The `training_metadata.yaml` output gains a `sources` field per model:

```yaml
French/windows-1252:
  language: fr
  encoding: windows-1252
  samples_used: 15000
  bigram_entries: 4231
  sources:
    culturax: 14997
    madlad400: 3
    wikipedia: 0
  test_articles_excluded: 3
```

### 4. Verification

#### Training-time logging

After building the exclusion set, the training script logs:
- Number of test data fingerprints loaded.
- Per-language: how many articles were skipped from each source due to exclusion.
- Per-language: how many articles came from each source.

#### Dedicated overlap check

A `--verify-no-overlap` flag (or standalone script) that:

1. Loads all cached training articles from `data/culturax/{lang}/`,
   `data/madlad400/{lang}/`, `data/wikipedia/{lang}/`.
2. Loads all test data files, decodes them back to UTF-8.
3. Fingerprints both sets and reports any intersection.
4. Exits non-zero if overlap is found.
5. Can be run in CI or manually after retraining.

#### Accuracy regression

After retraining with cleaned data, run the full accuracy test suite and compare
against the current baseline. Similar results confirm the models were not
overfitting to test data. If accuracy drops for specific languages, that is
evidence of prior overfitting — valuable information that validates this change.

### What does NOT change

- The test data itself (`chardet/test-data` repo).
- Test parametrization, accuracy thresholds, or known-failure lists.
- The model binary format (`models.bin`).
- The detection pipeline or public API.
- The confusion group training (`confusion_training.py`).

# Plan: large-input performance without leaning on max_bytes

## Goal

`detect()` with `max_bytes=len(data)` has fast, bounded cost for any input size
and any encoding, on every build flavor (compiled wheel, pure wheel, source
install, PyPy). `DEFAULT_MAX_BYTES` (200,000) is unchanged, and every call that
uses it must be bit-for-bit unchanged by this work.

Target: about 0.3s on a 272 MiB UTF-8 file with `max_bytes=len(data)`. That is
the scenario behind charset-normalizer's README claim ("Expect 10X faster with
large contents when you uncap Chardet max_bytes default assumption": 0.3s for
them vs 3.4s for chardet 7.5's compiled wheel). Their 0.3s comes from sampling;
ours comes from doing the exhaustive work at C-library speed, which is a
stronger claim (see "Framing" below).

## Where the time goes today

Profiled on the pure build, 32 MiB synthetic inputs, `max_bytes=len(data)`:

| Input     | Time  | Dominant cost                                                        |
| --------- | ----- | -------------------------------------------------------------------- |
| UTF-8     | 0.68s | 97% in `detect_utf8`, a per-byte loop over the whole input            |
| cp1252    | 5.3s  | structural/CJK-gate analyzers 4.5s (full-data loops), validity 1.0s   |
| Shift_JIS | 7.1s  | structural analyzers (johab/sjis/cp932/cp949/gb18030 full-data loops) |
| UTF-8, default cap | 0.005s | (baseline for comparison)                                   |

mypyc shrinks these constants 2-5x but cannot fix the shape: a compiled
per-byte loop runs at roughly 80-150 MB/s while C-library scans (`decode`,
`translate`, `find`) run at 1+ GB/s. The 3.4s headline number *was* our
compiled wheel.

Three other stages scan the full input but are already C-speed and cheap:
ascii (`translate`), binary (`translate`), and escape presence (`in`). The
statistical (16 KiB), language (2 KB), postprocess (16 KiB), utf1632 (4 KiB),
and markup (head) stages already carry internal caps and need no work.

## Framing: exhaustive checks vs evidence caps

The design splits every stage into one of two categories (glossary terms are
in `CONTEXT.md`, decision record in ADR-0006):

- **Exhaustive checks**: exact over every byte of the examination window
  (`max_bytes`). BOM, magic, UTF-8 structural validation, ASCII, binary,
  escape *presence*. These stay exhaustive and get C-library speed where they
  do not have it yet. This is the differentiator vs charset-normalizer: their
  UTF-8 verdict is sampled, ours cannot be wrong about any byte it was given.
- **Evidence caps**: internal, unoverridable convergence bounds on filtering,
  validation, and scoring stages. The new caps are set at 256 KiB, *above*
  `DEFAULT_MAX_BYTES`, which is what makes default calls provably unchanged.
  Caps are documented in `performance.rst`, not hidden.

The word "uncapped" is banned from docs and README prose (see the flagged
ambiguity in `CONTEXT.md`); state the `max_bytes` value used instead.

## Work items

Commit-sized, in order:

### 1. UTF-8 validation: exact decode-based rewrite (`pipeline/utf8.py`)

Replace the hand-rolled per-byte loop with CPython's strict UTF-8 decoder,
which enforces exactly the same rules (overlongs, surrogates, > U+10FFFF):

- Incremental decoder with `final=False`, fed in chunks (around 1 MiB) so a
  272 MiB input never allocates a matching `str`. `final=False` reproduces the
  existing truncated-tail tolerance, the same trick `decodes_without_error`
  uses. Discard decoded output; we only want the verdict.
- Confidence inputs at C speed via `translate` counts: `multibyte_bytes` is
  the count of bytes >= 0x80 (in valid UTF-8 every byte of a multi-byte
  sequence is high), `multibyte_sequences` is the count of lead bytes
  0xC2-0xF4. The confidence formula itself is unchanged.
- The strict decoder fails fast at the first invalid sequence, so non-UTF-8
  inputs stay cheap, same as today.
- `utf8.py` stays on the mypyc module list (harmless, avoids build churn).

Testing: keep the old validator in `tests/` as a differential oracle. Fuzz
random and adversarial buffers (overlongs, surrogates, truncated tails at
every offset, invalid bytes at the very end of large buffers); verdicts *and*
confidences must match exactly.

### 2. Evidence cap: validity + structural + CJK gate

- One shared constant next to `DEFAULT_MAX_BYTES` in `_utils.py` (suggested:
  `EVIDENCE_CAP_BYTES = 256 * 1024`), with a test asserting
  `EVIDENCE_CAP_BYTES >= DEFAULT_MAX_BYTES`. That invariant is the proof that
  default calls are unchanged; if someone ever raises `DEFAULT_MAX_BYTES`
  past the cap, the test fails instead of accuracy silently shifting.
- `filter_by_validity` examines at most the cap. The guarantee becomes "the
  winner decodes everything detection examined", which is already the only
  guarantee default calls have today.
- Structural probing and CJK gating share one sliced view, applied once at
  the analysis-cache level (`ctx.analysis_cache` is shared by both consumers;
  the slice must happen before the cache key, once).

### 3. Escape stage: bound the deep validators

Presence checks (`\x1b`, `~`, `+` and the ISO-2022 designation substrings)
stay exhaustive; they are C-speed `in` scans. The UTF-7 and HZ-GB-2312 deep
validators (`_has_valid_utf7_sequences`, `_has_valid_hz_regions`) walk every
candidate site in per-byte loops, and their pathological case is *rejection*:
a large base64 blob or diff is wall-to-wall `+` runs, none valid. Bound both
validators to the evidence window. Semantics change only for a file whose
first valid UTF-7/HZ sequence sits past 256 KiB, which is essentially a
synthetic case (real UTF-7/HZ shifts in and out constantly).

### 4. Transient-memory bounding (small, optional polish)

- `detect_ascii`: try `data.isascii()` first (no allocation), fall back to
  the `translate` path only when it fails (needed for the null-tolerance
  branch).
- `is_binary` / `detect_ascii` `translate` scans allocate an output copy that
  can approach input size on high-byte data. Chunk them over a `memoryview`
  if the memory benchmark shows a spike worth caring about; skip if not.

### 5. Validation (before/after, not a commit)

- Full test suite plus the existing pruning-contract corpus parity sweep.
- One full accuracy-corpus run before and after, comparing *per-file* results
  (not aggregate accuracy). Zero diffs expected, by construction of the
  cap >= default invariant.

### 6. Benchmarks and docs

- Add large-file benchmarks: 1 MiB / 32 MiB / 272 MiB, utf-8 / cp1252 /
  shift_jis, `max_bytes=len(data)`. (Shipped as a dedicated
  `scripts/benchmark_large_inputs.py` rather than a mode on
  `benchmark_time.py`, whose CLI contract is consumed by
  `compare_detectors.py`.)
- A/B vs charset-normalizer must be interleaved on the same machine (thermal
  drift makes sequential runs lie by ~25%).
- `performance.rst`: new large-input section with the measured numbers and a
  per-stage table of what each stage examines (exhaustive over the window vs
  first N KiB). Published caps, not hidden ones.
- README: a sentence or two stating our own measured numbers. Do not name or
  argue with charset-normalizer; our numbers stand on their own.
- Prose follows the voice profile: no em dashes, US spelling, plain words.

### 7. ADR-0006

`docs/adr/0006-evidence-caps-bound-non-exhaustive-stages.md` (written
alongside this plan).

## Implementation checkpoints

Things to verify while coding, flagged during planning:

- `input_truncated` semantics: it currently means "the caller's data was cut
  by `max_bytes`". Evidence-cap slicing must *not* set it. Check the
  decode-safety flip and anything else in postprocess that consumes it.
- The structural slice and the analysis cache: slice exactly once, before the
  cache is populated, so CJK gating and structural probing can never see
  different windows.
- Rejected on purpose (do not revisit without new data): Cython for these
  modules (compiled loops still lose ~10x to C scans, and pure/PyPy installs
  see no benefit; the 7.6.0 kernel study already priced the mypyc/Cython
  boundary), sampling the exhaustive checks, winner-only full-input
  verification (unbounded demotion cascade, unclear confidence semantics).

## Expected outcomes

- 272 MiB UTF-8, `max_bytes=len(data)`: ~3.4s (compiled) / ~6s (pure) down to
  ~0.3s on every build flavor.
- 32 MiB cp1252 / Shift_JIS: 5-12s down to tens of ms (exhaustive C-speed
  scans) on top of a bounded evidence cost.
- Default calls: bit-for-bit identical results, same ~5ms.

## After release (out of scope here)

- Ask charset-normalizer to re-run their benchmark against the fixed release
  (their table cites chardet 7.5 and will go stale).
- The eventual retirement of `max_bytes` is an 8.0-scale question this work
  enables but does not decide: even at 1+ GB/s the exhaustive checks are
  linear, so the default cap is still constant-time vs linear, and removing
  it changes verdicts for every file over 200 KB (the exhaustive checks would
  suddenly see everything). Accuracy question first, API break second.

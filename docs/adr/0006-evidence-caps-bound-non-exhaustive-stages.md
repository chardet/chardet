# Evidence caps bound non-exhaustive stages

Large inputs with `max_bytes=len(data)` used to cost seconds: `detect_utf8`,
the structural/CJK-gate analyzers, the escape deep validators, and validity
filtering all scanned the full input, and a per-byte loop loses to C-library
scans by roughly 10x even under mypyc (charset-normalizer's "10X faster on
large contents" README claim was measured against our compiled wheel). The
decision is a two-way split. **Exhaustive checks** (BOM, magic, UTF-8
structural validation, ASCII, binary, escape *presence*) stay exact over every
byte of the examination window and run at C-library speed; UTF-8 validation in
particular is decode-based (chunked incremental strict decoder, `final=False`
tail tolerance) rather than a hand-rolled loop, because the strict decoder
enforces the identical rules at ~1 GB/s on every build flavor, pure and PyPy
included. Everything that filters, validates candidates, or scores
(`filter_by_validity`, structural probing, CJK gating, the UTF-7/HZ deep
validators) is bounded by an **evidence cap**: an internal, unoverridable
convergence bound of 256 KiB, deliberately set *above* `DEFAULT_MAX_BYTES` and
pinned there by a test, so every default-capped call is bit-for-bit unchanged.
The split runs along the accept/reject axis, not the stage boundary: a gate
that decides whether an answer is *true* stays exhaustive even inside a
bounded stage. The escape stage's UTF-7 decode gate is the worked example —
its Python-loop sequence validator is capped, but the decode that makes a
`utf-7` verdict correct is not, because a capped decode would hand back
`utf-7` at deterministic confidence for data whose next `decode()` raises.
Bounding costs detections only in the miss direction, and only for evidence
that does not begin within the first 256 KiB. Where a sequence may *begin* and
where it may *end* are separate bounds — the escape validators cap the first at
the evidence window and the second a window later — because a single bound cuts
a sequence straddling the boundary and reads it as malformed, which would lose
the detection for any document whose only escape evidence lands there.
The caps are published in `performance.rst`, not hidden; "uncapped" is banned
from prose because it would now be a lie in one direction and an undersell in
the other (see the flagged ambiguity in `CONTEXT.md`).

Rejected alternatives, for the record. (1) Sampling the exhaustive checks,
charset-normalizer style: discards our one structural differentiator, that
chardet cannot call data UTF-8 that is not valid UTF-8 throughout the window
it examined. (2) Winner-only full-input verification after capped filtering:
keeps the "winner decodes everything" guarantee but needs a failure policy
when the winner breaks at byte 200M, and the demotion cascade is unbounded
with no principled confidence for a candidate the scoring stages never saw.
The guarantee it preserves is one default calls have never had past 200 KB
anyway. (3) Expanding the Cython surface: compiled per-byte loops still lose
~10x to C scans, pure/source/PyPy installs see zero benefit, and the 7.6.0
kernel study already priced the compiler boundary (keep it to `_kernel`).

Consequences: calls with large `max_bytes` are linear only in the exhaustive
checks (~1 GB/s), so `max_bytes` still has a real meaning (constant-time vs
linear, and it bounds what the exhaustive verdicts are about). This work
enables an eventual 8.0-scale retirement of `max_bytes` but deliberately does
not decide it: removing the cap changes verdicts for every file over 200 KB,
which is an accuracy question before it is an API one.

## Amendment, 2026-08-30: the answer decodes the window

Rejected alternative (2) is now adopted in the narrow form its objections
allowed. The cap had turned `max_bytes` into a promise chardet did not keep: a
caller who says "the verdict is about these n bytes" could get back an encoding
that cannot decode them (Windows-1252 for a 300 KB Latin-1 file whose only C1
bytes sit past the cap), while the `detect()` docstring, the FAQ, and the
performance page all still said otherwise. The failure policy is the ranking
itself. After the bounded stages and the rank corrections settle, the winner is
decoded over the whole window with the validity filter's own tolerant decoder;
when it fails, the next entry in the corrected ranking is tried, and every
entry ahead of the first that decodes is dropped, which is what validity would
have done had it read those bytes. The cascade is bounded by the ranking's
length, each step is one C-speed decode that stops at the first bad byte, and
the survivors keep the confidence they earned on the evidence, so no candidate
the scoring stages never saw is invented; when nothing listed decodes, the
no-match fallback answers, exactly as when validity leaves nothing. On the
inputs `tests/test_evidence_cap.py` pins, the outcome is 7.6.0's to the digit.
The cost lands only on windows past the cap, one decode of the window per
candidate tried: on the pure-Python build, 64 MiB of cp1252 goes from 0.06 s to
0.08 s and 64 MiB of Shift_JIS from 0.09 s to 0.19 s. Default calls are
untouched, since the cap sits above the default window.

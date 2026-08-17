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

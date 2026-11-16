Performance
===========

Benchmarked against 3,137 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted. Rows labeled 7.7.1.dev were measured on the
development branch after 7.7.0 (``7.7.1.dev33``), so they describe the
code and models that the next release will ship; `Large Inputs`_ and the
7.7.0 row of `Historical Performance`_ are the 7.7.0 release
measurements.

.. note::

   Every number on this page was measured on an **Apple M4 Max (macOS
   26, 14 cores)**; the current tables use the 3,137-file test suite,
   the historical table the 3,121-file suite of its own session. Absolute timings are **not** comparable
   against numbers published in older versions of these docs: both the
   hardware and the corpus have changed, and the corpus change alone
   moved the pre-7.0 rows by 20--30%. A figure that improved between
   releases may reflect the faster machine, the larger corpus, the
   faster code, or any combination. Comparisons *within* a table are
   valid --- every detector, Python version, and build in a given table
   was measured on the same machine against the same files.  Every
   detector receives the complete file bytes and applies its own
   defaults; chardet examines at most the first 200 KB (``max_bytes``),
   charset-normalizer applies its own chunk sampling.

Detecting a superset of the expected encoding is counted as correct,
since the superset decodes the data without loss (e.g., detecting
Windows-1252 when the expected answer is ISO-8859-1, or GB18030 when
the expected answer is GB2312). Byte-order variants of the same
encoding (e.g., UTF-16-LE vs UTF-16) are also treated as equivalent.
These rules are applied equally to all detectors.

chardet's statistical models are trained on CulturaX, MADLAD-400, and
Wikipedia data. Test files are excluded from training via content
fingerprinting to prevent train/test overlap (verified by
``scripts/verify_no_overlap.py``).

Accuracy
--------

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 15

   * - Detector
     - Correct
     - Accuracy
     - Speed
   * - **chardet 7.7.1.dev (mypyc)**
     - **3128/3137**
     - **99.7%**
     - **4,172 files/s**
   * - chardet 6.0.0
     - 2559/3137
     - 81.6%
     - 10 files/s
   * - charset-normalizer 3.5.2 (mypyc)
     - 2695/3137
     - 85.9%
     - 2,424 files/s
   * - cchardet 3.2.0
     - 1881/3137
     - 60.0%
     - 3,991 files/s

The suite's 8 binary files count as correct for any detector that
declines them (``encoding=None``).  chardet additionally identifies
their format --- every result carries a ``mime_type``, matched against
40+ magic-number signatures --- which no other detector here offers.
That is a capability rather than an accuracy difference, so it appears
nowhere else in these tables; see :doc:`supported-mime-types`.

chardet leads all detectors on accuracy: **+18.1pp** vs chardet 6.0.0,
**+13.8pp** vs charset-normalizer 3.5.2, and **+39.8pp** vs cchardet 3.2.0.
No detector here has higher aggregate throughput. cchardet comes within
5% and has the lowest median, and it detects 39.8pp fewer files
correctly.

One capability difference is big enough to move that headline: 144 of
the 3,137 files (4.6%) are BOM-less utf-7, which charset-normalizer
documents as out of scope for detection (utf-7 sits in its
supported-encodings inventory, but is only identified when a signature
announces it --- the four *signed* utf-7 files in the suite it does
detect).  chardet detects all 144; charset-normalizer detects none of
them.  Scored without those files, charset-normalizer reaches 90.0%
(2695/2993) while chardet stays at 99.7% (2984/2993), so the +13.8pp
lead reads as +9.7pp for anyone who takes BOM-less utf-7 off the
table.

Strict (Exact-Match) Scoring
----------------------------

The numbers above credit supersets, byte-order variants, and
decoded-output equivalence. Other detectors publish accuracy scored on
exact matches only, so those figures are not directly comparable to
ours. Both conventions, on the same files:

.. list-table::
   :header-rows: 1
   :widths: 30 16 16 16

   * - Detector
     - Lenient
     - Strict
     - Concession
   * - **chardet 7.7.1.dev (mypyc)**
     - **99.7%**
     - **88.1%**
     - +11.6pp
   * - charset-normalizer 3.5.2 (mypyc)
     - 85.9%
     - 78.5%
     - +7.4pp
   * - cchardet 3.2.0
     - 60.0%
     - 53.1%
     - +6.8pp

"Concession" is the share of files a detector wins only under lenient
rules. **chardet benefits from lenient scoring more than the others
do** --- 364 files, against charset-normalizer's 231. Our lead survives
the stricter convention but narrows from +13.8pp to +9.6pp.

The largest groups are a subset reported under its Windows code page
(56 ``iso-8859-1`` -> ``windows-1252``, 40 ``iso-8859-9`` ->
``windows-1254``, 37 ``euc-kr`` -> ``cp949``, 31 ``ascii`` ->
``windows-1252``, 24 ``iso-8859-15`` -> ``windows-1252``), followed by
DOS code pages that decode the file to the same text (24 ``cp850`` ->
``cp437``).

This is a deliberate design position, not a scoring convenience: **when
two encodings can both decode the observed bytes, returning the larger
superset is the correct answer.** Detection examines at most the first
200 KB of a file (``max_bytes``). A byte past that window can require
the superset --- a C1 curly quote in what looked like ISO-8859-1, an
extension character in what looked like EUC-KR --- and if it does, the
subset answer garbles or breaks the eventual ``.decode()`` while the
superset reads it correctly: a true superset decodes everything the
subset does, identically. Erring toward the superset is the safer choice
under partial evidence. The web platform reached the same conclusion
for the same reason: the WHATWG/W3C Encoding Standard requires
browsers to decode content labelled ``ascii`` or ``iso-8859-1`` as
``windows-1252``.

Nor does the strict column measure a detection weakness. The gap it
shows is the output convention itself: run with superset remapping
disabled (``prefer_superset=False``), chardet scores **92.2% strict**
(2893/3137) --- ahead of charset-normalizer's 78.5% --- while giving up
12 files of lenient accuracy (3128 of 3137 to 3116). Exact subset
names are available to callers who want them; the tables on this page
use superset output because we consider it the right answer to ship,
and ``prefer_superset=True`` will become the default in chardet 8.0.

The strict column is published for comparability --- other detectors
report exact-match numbers --- and so the convention behind our
headline figure is visible rather than baked in, not because we
consider the two conventions equally good.

Speed
-----

.. list-table::
   :header-rows: 1
   :widths: 26 10 10 10 10 10 10

   * - Detector
     - Files/s
     - Mean
     - Median
     - p90
     - p95
     - p99
   * - **chardet 7.7.1.dev (mypyc)**
     - **4,172**
     - **0.24ms**
     - **0.13ms**
     - **0.47ms**
     - **0.65ms**
     - **1.70ms**
   * - cchardet 3.2.0
     - 3,991
     - 0.25ms
     - 0.04ms
     - 0.72ms
     - 1.07ms
     - 2.15ms
   * - charset-normalizer 3.5.2 (mypyc)
     - 2,424
     - 0.41ms
     - 0.28ms
     - 0.88ms
     - 1.35ms
     - 2.37ms
   * - chardet 6.0.0
     - 10
     - 103.61ms
     - 4.27ms
     - 253.73ms
     - 509.76ms
     - 1631.24ms

With mypyc and the Cython scoring kernel, chardet is **433x faster**
than chardet 6.0.0 at the mean. Unlike the rest of this table, that
ratio is measured with five interleaved rounds timing both detectors
back to back in one session, and 433x is the median of the five: the
per-round ratios spanned 423--442x while absolute timings drifted a few
percent with machine temperature. A ratio derived from this table's
cells instead would inherit that drift on top of the spread, which is
why earlier editions of this page quoted anywhere from 279x to 359x for
earlier code. Treat it as a four-hundred-fold speedup, not as a
three-significant-figure measurement.

Against charset-normalizer 3.5.2, chardet leads at every percentile in
the table: **1.7x on aggregate throughput** (4,172 vs 2,424 files/s),
**2.2x at the median** (0.13ms vs 0.28ms), 1.9x at p90, 2.1x at p95,
and 1.4x at p99 (1.70ms vs 2.37ms), with a worst case 4.6x lower (7.4ms
vs 34.0ms). The one place charset-normalizer still leads is the legacy
CJK tail; see `Latency by Script Family`_.

Against cchardet 3.2.0, aggregate throughput is about level (4,172 vs
3,991 files/s). cchardet has much the lower median (0.04ms vs 0.13ms);
chardet has the better tail from p90 up (p99 1.70ms vs 2.15ms) and a
worst case 3.4x lower (7.4ms vs 25.2ms). cchardet detects 39.8pp fewer
files correctly, and reports no language at all.

Relative orderings can shift with microarchitecture, so the repo carries
a manually-triggered ``benchmark-x86`` workflow that reruns the
chardet/charset-normalizer comparison interleaved on a GitHub x86_64
runner. The first run (Intel Xeon Platinum 8573C, three rounds within
1%) shows the same ordering as this page through p95: chardet at
0.72ms mean, 0.26ms median, and 1.97ms p95 against charset-normalizer's
0.79ms, 0.55ms, and 2.52ms. charset-normalizer's own CI, on its own
corpus, reports the tail percentiles closer than that; corpus
composition moves tails more than instruction sets do.

Latency by Script Family
------------------------

Legacy CJK multi-byte encodings (Big5, GB, EUC, Shift_JIS, ISO-2022,
Johab) need structural probing and statistical scoring across many
candidate models, and that remains chardet's most expensive path ---
though 7.5.0's upper-bound pruning cut that tail roughly in half.
Splitting the same measurements:

.. list-table::
   :header-rows: 1
   :widths: 26 11 8 11 11 11 11

   * - Detector
     - Group
     - Files
     - Median
     - p95
     - p99
     - Max
   * - **chardet 7.7.1.dev**
     - **CJK**
     - 230
     - **0.14ms**
     - 1.11ms
     - 4.17ms
     - 7.37ms
   * - **chardet 7.7.1.dev**
     - **non-CJK**
     - 2,907
     - **0.13ms**
     - **0.62ms**
     - **1.55ms**
     - **6.77ms**
   * - charset-normalizer 3.5.2
     - CJK
     - 230
     - 0.27ms
     - 1.01ms
     - 1.57ms
     - 2.60ms
   * - charset-normalizer 3.5.2
     - non-CJK
     - 2,907
     - 0.28ms
     - 1.39ms
     - 2.39ms
     - 33.98ms

chardet leads on the median in both groups (0.14ms vs 0.27ms on CJK,
0.13ms vs 0.28ms elsewhere) --- escape sequences and clear multi-byte
structure resolve immediately --- and at every percentile outside CJK,
which is 93% of the suite (0.62ms vs 1.39ms at p95, 1.55ms vs 2.39ms
at p99). charset-normalizer owns the CJK tail from p95 up: 1.01ms vs
1.11ms at p95, and 1.57ms against chardet's 4.17ms at p99.

The stakes stay bounded in absolute terms --- chardet's slowest CJK
file completes in under 8ms, and its worst case overall is 4.6x lower
than charset-normalizer's (7.4ms vs 34.0ms).

Percentiles over a mixed corpus are sensitive to how much CJK it
contains: this suite is 7.3% CJK (230/3,137), so a CJK-heavier corpus
shifts chardet's aggregate p95/p99 upward --- by milliseconds, not
orders of magnitude.

``UTF-8``/``UTF-16``/``UTF-32`` count as non-CJK here even when the text
is Chinese, Japanese, or Korean, because they are resolved by BOM or
byte-pattern checks and never reach the disambiguation path.

Large Inputs
------------

Everything above uses the default examination window (``max_bytes``,
200 KB). This section measures the other extreme:
``detect(data, max_bytes=len(data))`` on single-encoding buffers up to
272 MiB, the size charset-normalizer's README uses for its large-content
comparison.

chardet splits its work into two tiers (ADR-0006 in the repo records the
design). **Exhaustive checks** --- BOM, magic numbers, UTF-8 structural
validation, ASCII, binary detection, and escape-sequence presence --- are
exact over every byte of the window, running at C-library scan speed.
**Evidence caps** bound what the remaining stages read: candidate
filtering, structural probing, and rank corrections converge on the
first 256 KiB (262,144 bytes); statistical scoring on the first 16 KiB;
language detection on the first 2 KiB. The caps are convergence bounds,
not correctness bounds --- more bytes were not changing those answers
--- and they sit above the default window, so nothing on the rest of
this page depends on them. One rank correction is switched off rather
than converged: the decode-safety flip, which reasons about the
caller's whole input, stands down when the window exceeds the cap. One
verdict is held exact past the cap regardless: the encoding returned
decodes the whole window. After the bounded stages settle, the winner
is decoded over the window, and when it fails the next candidate that
decodes takes its place, so legacy single-byte and CJK buffers past the
cap pay one C-speed decode of the window on top of the exhaustive
scans. That walk stops at the first candidate that decodes, so a
``detect_all`` ranking past the cap is exact down to its winner and
unverified below it. The one exception is the ``no_match_encoding``
sentinel at confidence 0.10, returned when no candidate survives the
pipeline (and replaced by ``encoding=None`` when the sentinel itself is
excluded by the encoding filters).

The practical consequence: the UTF-8 verdict is *validated*, not
sampled. chardet never reports ``utf-8`` for data that is not valid
UTF-8 through the entire window it was given, which costs one C-speed
decode pass on genuinely large UTF-8 input. charset-normalizer samples
chunks, which is faster on that one column and blind on every other:

.. list-table::
   :header-rows: 1
   :widths: 16 12 24 24

   * - Input
     - Size
     - chardet 7.7.0 (mypyc)
     - charset-normalizer 3.5.2
   * - utf-8
     - 1 MiB
     - 1.2ms
     - **0.6ms**
   * - utf-8
     - 32 MiB
     - 25.8ms
     - **9.1ms**
   * - utf-8
     - 272 MiB
     - 228.1ms
     - **79.2ms**
   * - cp1252
     - 1 MiB
     - **12.2ms**
     - 21.6ms :sup:`*`
   * - cp1252
     - 32 MiB
     - **31.8ms**
     - 695.1ms :sup:`*`
   * - cp1252
     - 272 MiB
     - **205.4ms**
     - 7,610.2ms :sup:`*`
   * - shift_jis
     - 1 MiB
     - 10.5ms
     - 10.6ms
   * - shift_jis
     - 32 MiB
     - **68.5ms**
     - 308.9ms
   * - shift_jis
     - 272 MiB
     - **501.3ms**
     - 2,655.2ms
   * - ascii (base64) :sup:`†`
     - 1 MiB
     - 1.8ms
     - **0.1ms**
   * - ascii (base64) :sup:`†`
     - 32 MiB
     - 21.7ms
     - **1.4ms**
   * - ascii (base64) :sup:`†`
     - 272 MiB
     - 176.1ms
     - **12.0ms**

:sup:`*` misdetected: charset-normalizer returned ``johab`` at 1 and
32 MiB and ``windows-1250`` at 272 MiB for French Windows-1252 text.

:sup:`†` worst case, not a codec: ASCII text in line-wrapped base64, as
in PEM certificates and MIME attachments. Every ``+`` looks like the
start of a UTF-7 sequence, so chardet's escape-sequence check has the
most to reject. Both detectors report ``ascii``.

Median of five interleaved rounds (each round times both detectors back
to back --- thermal drift makes separate blocks incomparable), compiled
wheel, ``charset_normalizer.detect()`` compatibility API. Buffers repeat
a single line or sentence, so this measures the scan machinery, not
model quality.

The columns split by what each detector has to prove. charset-normalizer
wins wherever a cheap structural answer settles the file: about 3x on
large valid UTF-8, and about 15x on base64, where chardet validates ASCII
and scans for escape-shift evidence over the whole window while
charset-normalizer samples chunks. Both are the sampling-versus-exactness
trade, taken knowingly.

Where the answer needs actual statistics --- legacy single-byte and
legacy CJK, the encodings a detector exists for --- chardet is **4.5x to
37x faster** at 32 MiB and above, and charset-normalizer misidentifies
the cp1252 buffers at every size. The asymmetry has one cause: sampling
costs charset-normalizer its short-circuits, so it keeps probing
candidate encodings over chunks spread through a large buffer, while
chardet's non-UTF-8 path drops to bounded evidence as soon as its
C-speed exhaustive scans have ruled out the fast answers.

The pure-Python wheel lands within 10% of the compiled one on these
inputs (0.18s to 0.54s at 272 MiB): past the exhaustive scans and the
winner's decode, what is left is bounded, so compilation moves the
constant inside the window rather than the shape of the curve.

Reproduce with ``python scripts/benchmark_large_inputs.py`` (see its
docstring for the compiled-wheel invocation).

Memory
------

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 15 15

   * - Detector
     - Import Time
     - Import Memory
     - Peak Memory
     - RSS
   * - **chardet 7.7.1.dev**
     - **8.4ms**
     - **1.4 MiB** :sup:`*`
     - **28.6 MiB**
     - **160.8 MiB**
   * - charset-normalizer 3.5.2
     - 5.2ms
     - 2.0 MiB
     - 71.0 MiB
     - 254.8 MiB
   * - cchardet 3.2.0
     - 1.9ms
     - 503 KiB
     - 64.5 MiB
     - 185.8 MiB

:sup:`*` chardet 7.x loads its model tables lazily --- they are not
read until the first ``detect()`` call, so ``import chardet`` costs
about 1 MiB. The full model cost appears in Peak Memory instead.

chardet uses **2.5x less peak memory** than charset-normalizer 3.5.2,
**2.3x less** than cchardet 3.2.0, and has the **lowest RSS of every
detector measured**. Since 7.5.0 decompresses its models incrementally,
its 28.6 MiB peak is the smallest on the table. (cchardet 2.2.1 used to
report a near-zero traced peak because its C allocations were invisible
to ``tracemalloc``; 3.2.0's are visible.)

Read the table knowing the two APIs do different amounts of work:
charset-normalizer's result carries the decoded text (retaining the
``str`` is part of its design), while chardet returns only the
encoding name.  A caller who needs the text pays chardet's numbers
plus one ``bytes.decode`` afterward; charset-normalizer's numbers
include it.

chardet 6.0.0 is omitted from this table: its memory benchmark
instruments every ``detect()`` call with ``tracemalloc``, and at 104ms
per file on the current suite that run does not complete in reasonable
time. Its speed and accuracy appear in `Historical Performance`_.

Memory per Detection
--------------------

The table above measures the whole process. This one measures a single
``detect()`` call: peak CPython allocations during the call, above what
was already resident when it started. It answers a different question ---
not "how much does the library cost to load" but "how much does one more
concurrent detection cost".

.. list-table::
   :header-rows: 1
   :widths: 26 12 12 12 12 12

   * - Detector
     - Mean
     - Median
     - p90
     - p95
     - p99
   * - **chardet 7.7.1.dev**
     - **517 KiB**
     - **545 KiB**
     - **595 KiB**
     - **645 KiB**
     - **917 KiB**
   * - charset-normalizer 3.5.2
     - 132 KiB
     - 58 KiB
     - 187 KiB
     - 276 KiB
     - 784 KiB
   * - cchardet 3.2.0
     - 66 KiB
     - 9 KiB
     - 93 KiB
     - 190 KiB
     - 602 KiB

**charset-normalizer and cchardet allocate less per call than chardet
at typical sizes** --- 58 KiB and 9 KiB at the median against chardet's
545 KiB. chardet's per-call cost is flat instead: it varies by 68% from
median to p99 (545 -> 917 KiB), while charset-normalizer's grows 14x
(58 -> 784 KiB) and cchardet's 68x (9 -> 602 KiB). Neither reaches
chardet's p99, though charset-normalizer comes within 15% of it. So
chardet trades a higher floor for a predictable ceiling, which is the
better shape for sizing a worker pool; the others are the better fit
when most inputs are small and peak footprint per call matters more
than its variance.

One-time lazy initialization is absorbed by a warmup call before the
distribution is measured (a ~23 MiB peak for chardet — the model load
visible in the table above), so every sample here is a steady-state
call.  The maximum is still excluded from the table because it
describes the single largest input file rather than typical calls:
1.5 MiB for chardet, but 63.9 MiB for both charset-normalizer and
cchardet 3.2.0, whose per-call footprints grow with input size.

Reproduce with ``python scripts/compare_detectors.py --memory --cn
--cchardet --mypyc``.

Language Detection
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Detector
     - Correct
     - Accuracy
   * - **chardet 7.7.1.dev**
     - **2907/3129**
     - **92.9%**
   * - charset-normalizer 3.5.2
     - 1714/3129
     - 54.8%
   * - chardet 6.0.0
     - 1211/3129
     - 38.7%
   * - cchardet 3.2.0
     - 0/3129
     - 0.0%

chardet detects language with **92.9% accuracy** --- +38.1pp vs
charset-normalizer 3.5.2 and +54.2pp vs chardet 6.0.0. cchardet 3.2.0 does
not report language. The denominator excludes binary files, which have
no language to detect.

Accuracy on charset-normalizer's Test Set
------------------------------------------

charset-normalizer maintains its own test dataset at
`char-dataset <https://github.com/Ousret/char-dataset>`_. 469 of those
files also exist in the chardet test suite (matched by content hash),
so we can compare both detectors on charset-normalizer's own ground
truth. We filed
`an issue <https://github.com/Ousret/char-dataset/issues/1>`_ about
the 5 files we excluded (4 ambiguous Cyrillic files and 1 corrupted
Vietnamese file) and 2 we relabeled (UTF-8-SIG, not UTF-8).  The
outcome: the corrupted Vietnamese file was fixed upstream, the
ambiguous Cyrillic files stay by design (charset-normalizer scores
itself on whether the label appears anywhere in its candidate list, so
an unverifiable label costs it nothing, but that also makes them
unusable as top-answer ground truth, so we keep them excluded), and
the UTF-8-SIG relabels are a standing convention difference:
charset-normalizer holds that a signature does not make a different
encoding and reports ``utf-8`` plus a BOM property, while we report
the distinct Python codec, because the two decode differently.

.. list-table::
   :header-rows: 1
   :widths: 35 15 15 15

   * - Detector
     - Correct
     - Encoding Accuracy
     - Language Accuracy
   * - **chardet 7.7.1.dev (mypyc)**
     - **469/469**
     - **100.0%**
     - **94.8%**
   * - charset-normalizer 3.5.2 (mypyc)
     - 452/469
     - 96.4%
     - 86.8%

chardet is **+3.6pp more accurate** than charset-normalizer 3.5.2 on
charset-normalizer's own test data --- every file in the subset ---
and **+8.0pp** on language detection.

Under strict scoring the result appears to reverse: on these same
files charset-normalizer scores **89.8%** against chardet's **85.3%**.
This subset is dense in exactly the encodings where we deliberately
emit the Windows superset (33 ``euc-kr`` -> ``cp949``, 8 ``ascii`` ->
``windows-1252``, 6 ``iso-8859-9`` -> ``windows-1254``), so it concedes
14.7pp to leniency against charset-normalizer's 6.6pp. The reversal
measures the output convention, not detection quality: with superset
remapping disabled, chardet scores **94.7% strict on this same
subset** --- ahead of charset-normalizer's 89.8% --- while losing two
files of lenient accuracy. We emit the superset anyway because, as argued under
`Strict (Exact-Match) Scoring`_, it is the correct answer when only a
prefix of the file has been examined. Whichever convention you prefer,
it should be applied to both detectors --- which is the point of
publishing both columns.

For the record, the two corpora are not independent: as of
char-dataset's Vietnamese fix, 463 of its 472 files (98%) are
byte-identical to files in the chardet test suite, and the encoding
labels agree on 437 of them. The disagreements are mostly the same
superset question resolved the other way (17 files we label
``iso8859-8`` and they label ``cp1255``).

You can reproduce these numbers with
``python scripts/compare_detectors.py --cn-dataset --cn --mypyc``.

Thread Safety
-------------

:func:`chardet.detect` and :func:`chardet.detect_all` are fully thread-safe.
Each call carries its own state; what threads share is read-only tables
and caches that are filled idempotently. Thread safety adds no
measurable overhead (< 0.1%).

On free-threaded Python (GIL disabled), detection scales with threads.
Standard GIL Python shows no scaling --- the GIL serializes threads.
Benchmarked with 3,137 files, ``encoding_era=ALL``:

.. list-table::
   :header-rows: 1
   :widths: 14 14 14 14 14

   * - Python
     - 1 thread
     - 2 threads
     - 4 threads
     - 8 threads
   * - 3.13 (pure)
     - 2,420ms
     - 2,410ms
     - 2,410ms
     - 2,410ms
   * - 3.13 (compiled)
     - 690ms
     - 720ms
     - 710ms
     - 720ms
   * - 3.13t (pure)
     - 2,680ms
     - 1,550ms (1.7x)
     - 960ms (2.8x)
     - 1,060ms (2.5x)
   * - 3.14 (pure)
     - 2,330ms
     - 2,310ms
     - 2,320ms
     - 2,310ms
   * - 3.14 (compiled)
     - 760ms
     - 780ms
     - 780ms
     - 790ms
   * - 3.14t (pure)
     - 2,350ms
     - 1,300ms (1.8x)
     - 680ms (3.5x)
     - 430ms (5.5x)
   * - **3.14t (compiled)**
     - 930ms
     - 520ms (1.8x)
     - 320ms (2.9x)
     - 370ms (2.5x)
   * - 3.15 (pure)
     - 2,340ms
     - 2,370ms
     - 2,350ms
     - 2,350ms
   * - 3.15 (compiled)
     - 750ms
     - 760ms
     - 770ms
     - 770ms
   * - 3.15t (pure)
     - 2,720ms
     - 1,470ms (1.9x)
     - 760ms (3.6x)
     - 470ms (5.8x)
   * - **3.15t (compiled)**
     - 900ms
     - 510ms (1.8x)
     - 320ms (2.8x)
     - **300ms (3.0x)**

**3.15t compiled at 8 threads is the fastest configuration measured**
--- 300ms for the whole suite, about 10,000 files/s. Both free-threaded
compiled builds reach 320ms at four threads, and past that the gain is
small or negative; the suite is small enough that scheduling costs
catch up with the remaining parallelism. The pure-Python build keeps
scaling to eight threads, where 3.14t and 3.15t finish the suite in
430--470ms, faster than any single-threaded compiled run.

Scaling here depends on the Cython kernel declaring itself safe without
the GIL. An extension that does not is enough to make CPython re-enable
the GIL for the whole process on import, with a ``RuntimeWarning``, at
which point these rows flatten completely --- 3.14t measured
1.13/1.16/1.17/1.18s before the declaration was added, worse than
shipping no kernel at all. The declaration is accurate rather than a
silencer: the kernel's functions read their arguments, touch no shared
mutable state, and return a value.

The 3.13t compiled row is absent because that build cannot be produced:
the compiled toolchain only supports free-threaded CPython from 3.14t
onward (mypyc's free-threaded runtime calls
``_PyObject_XDecRefDelayed``, which CPython provides from 3.14t, and the
build dependencies' own extensions refuse 3.13t), so compiling for
3.13t fails outright. Prebuilt compiled wheels are published for 3.14t
and 3.15t on Linux and macOS and not for 3.13t, so ``pip install
chardet`` on 3.13t installs the pure-Python wheel.

Individual :class:`~chardet.UniversalDetector` instances are not thread-safe.
Create one instance per thread when using the streaming API.

Optional Compiled Builds
------------------------

Prebuilt compiled wheels are published to PyPI for CPython on Linux,
macOS, and Windows. A regular ``pip install chardet`` will pick them up
automatically --- no extra flags needed.

Two compilers are involved. `mypyc <https://mypyc.readthedocs.io>`_
compiles fifteen modules --- thirteen pipeline stages plus the model
loader and its format reader; the published Windows wheels compile
fourteen and leave the model loader interpreted --- and
`Cython <https://cython.org>`_ compiles one more: ``_kernel.py``,
holding the bigram scoring loop that
is about a third of compiled runtime. Both read the same ``.py``
sources --- ``_kernel.pxd`` supplies C types at build time and ships
nothing --- so PyPy and pure-Python wheels run the same code
interpreted. A few modules check which build they are in and take the
path that suits it: ``models`` selects its scoring path, and the
UTF-16/32 stage counts null bytes with C-level byte searches when
interpreted but keeps its loops when compiled, where mypyc runs them
natively.

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Build
     - Files/s
     - Speedup
   * - Pure Python
     - 1,357
     - baseline
   * - mypyc + Cython kernel
     - 4,172
     - **3.1x**

Both rows are the CPython 3.14 measurements from the cross-version table
below. The ratio is lower than the 4.5x of the previous edition because
the interpreted build got faster, not because the compiled one got
slower. Both builds gained, and the interpreted one gained more (771 to
1,357 files/s, against 3,494 to 4,172): on CPython 3.12 and later its
dot products and pruning bounds now go through ``math.sumprod``, and
the validity and UTF-16/32 stages do less of their work in Python-level
loops.

Pure-Python wheels are always available for PyPy and platforms without
prebuilt binaries, and cost nothing relative to earlier releases: the
compiled kernel is the only consumer of the packed layout it introduces,
so an interpreted install takes the path it always did.

Historical Performance
----------------------

Accuracy and speed of every Python 3-compatible chardet release and its
temporary Python-3-compatible fork `charade <https://pypi.org/project/charade/>`_, measured on
the same 3,121-file test suite with the same equivalence rules. Pure
Python on CPython 3.14 for versions before 7.0; mypyc-compiled for
7.0+, matching what ``pip install chardet`` delivers. Language column
shows "---" for versions that did not support language detection.

Every pre-7.6 row was re-measured in a single session against the
3,121-file suite; the 7.6.0 row is the release-day measurement on the
3,125-file suite of its own session, and the 7.7.0 row is the
release measurement on the 3,138-file suite of its own session. It is
**not** comparable to the same table in earlier editions of these docs:
the suite grew from 2,517 to 3,121 files, and the added files are
harder and larger on average. That alone moved the pre-7.0 rows down by
20--30% and cost chardet 6.0.0 half its throughput, independent of any
code change.

.. list-table::
   :header-rows: 1
   :widths: 22 10 12 10 10 10

   * - Version
     - Date
     - Correct
     - Accuracy
     - Files/s
     - Language
   * - charade 1.0.0
     - 2012-12
     - 905/3121
     - 29.0%
     - 44
     - ---
   * - charade 1.0.1
     - 2012-12
     - 903/3121
     - 28.9%
     - 44
     - ---
   * - charade 1.0.3
     - 2013-01
     - 1279/3121
     - 41.0%
     - 52
     - ---
   * - chardet 2.2.1
     - 2013-12
     - 1280/3121
     - 41.0%
     - 51
     - ---
   * - chardet 2.3.0
     - 2014-10
     - 1433/3121
     - 45.9%
     - 50
     - ---
   * - chardet 3.0.4
     - 2017-06
     - 1577/3121
     - 50.5%
     - 62
     - 14.9%
   * - chardet 4.0.0
     - 2020-12
     - 1577/3121
     - 50.5%
     - 72
     - 15.5%
   * - chardet 5.0.0
     - 2022-06
     - 1950/3121
     - 62.5%
     - 68
     - 15.5%
   * - chardet 5.2.0
     - 2023-08
     - 1980/3121
     - 63.4%
     - 66
     - 15.4%
   * - chardet 6.0.0
     - 2026-02
     - 2638/3121
     - 84.5%
     - 10
     - 38.5%
   * - chardet 7.0.1 (mypyc)
     - 2026-03
     - 2994/3121
     - 95.9%
     - 692
     - 88.8%
   * - chardet 7.2.0 (mypyc)
     - 2026-03
     - 2996/3121
     - 96.0%
     - 676
     - 89.1%
   * - chardet 7.3.0 (mypyc)
     - 2026-03
     - 3009/3121
     - 96.4%
     - 790
     - 89.4%
   * - chardet 7.4.3 (mypyc)
     - 2026-04
     - 3049/3121
     - 97.7%
     - 756
     - 90.4%
   * - chardet 7.5.0 (mypyc)
     - 2026-08
     - 3050/3121
     - 97.7%
     - 2,047
     - 90.4%
   * - chardet 7.5.1 (mypyc)
     - 2026-08
     - 3056/3121
     - 97.9%
     - 2,303
     - 90.4%
   * - chardet 7.6.0 (compiled)
     - 2026-08
     - 3117/3125
     - 99.7%
     - 2,793
     - 91.8%
   * - **chardet 7.7.0 (compiled)**
     - **2026-10**
     - **3130/3138**
     - **99.7%**
     - **3,125**
     - **93.0%**

chardet 3.0.1--3.0.4 had identical accuracy and speed; only 3.0.4 is
shown. chardet 5.1.0--5.2.0 were likewise identical. chardet 7.1.0 and
7.2.0 had identical accuracy; only 7.2.0 is shown. chardet 7.4.0--7.4.2
reached the same 99.3% accuracy as 7.4.3, so only 7.4.3 is shown ---
7.4.0 is no longer installable from PyPI and was re-released as
7.4.0.post2. charade 1.0.2 could not be installed on Python 3.14.
chardet 3.0.0 crashed on Python 3.14 and is omitted.

Performance Across Python Versions
-----------------------------------

Benchmarked chardet 7.7.1.dev across all supported Python versions
(macOS aarch64, 3,137 files, ``encoding_era=ALL``). CPython versions
install compiled wheels automatically; PyPy receives the pure-Python
wheel. Encoding accuracy is identical on every interpreter and both
builds (99.7%), and language accuracy is 92.9% everywhere except PyPy,
where two files of 3,129 land on a different label because the
weighted-cosine ties resolve differently in its floating point; only
speed varies.

.. list-table::
   :header-rows: 1
   :widths: 16 8 10 10 10 10 10 10

   * - Python
     - Wheel
     - Total
     - Files/s
     - Mean
     - Median
     - p90
     - p95
   * - CPython 3.10
     - mypyc
     - 867ms
     - 3,618
     - 0.28ms
     - 0.19ms
     - 0.47ms
     - 0.63ms
   * - CPython 3.10
     - pure
     - 4,475ms
     - 701
     - 1.43ms
     - 0.60ms
     - 3.49ms
     - 5.13ms
   * - CPython 3.11
     - mypyc
     - 881ms
     - 3,561
     - 0.28ms
     - 0.20ms
     - 0.48ms
     - 0.65ms
   * - CPython 3.11
     - pure
     - 3,774ms
     - 831
     - 1.20ms
     - 0.51ms
     - 2.97ms
     - 4.25ms
   * - CPython 3.12
     - mypyc
     - 708ms
     - 4,431
     - 0.23ms
     - 0.13ms
     - 0.42ms
     - 0.60ms
   * - CPython 3.12
     - pure
     - 2,237ms
     - 1,402
     - 0.71ms
     - 0.34ms
     - 1.52ms
     - 2.35ms
   * - **CPython 3.13**
     - **mypyc**
     - **684ms**
     - **4,586**
     - **0.22ms**
     - **0.12ms**
     - **0.42ms**
     - **0.59ms**
   * - CPython 3.13
     - pure
     - 2,403ms
     - 1,305
     - 0.77ms
     - 0.36ms
     - 1.60ms
     - 2.50ms
   * - CPython 3.14
     - mypyc
     - 752ms
     - 4,172
     - 0.24ms
     - 0.13ms
     - 0.47ms
     - 0.65ms
   * - CPython 3.14
     - pure
     - 2,312ms
     - 1,357
     - 0.74ms
     - 0.34ms
     - 1.61ms
     - 2.49ms
   * - CPython 3.15
     - mypyc
     - 734ms
     - 4,274
     - 0.23ms
     - 0.12ms
     - 0.46ms
     - 0.64ms
   * - CPython 3.15
     - pure
     - 2,328ms
     - 1,348
     - 0.74ms
     - 0.36ms
     - 1.61ms
     - 2.45ms
   * - PyPy 3.10
     - pure
     - 2,013ms
     - 1,558
     - 0.64ms
     - 0.19ms
     - 1.23ms
     - 2.08ms
   * - PyPy 3.11
     - pure
     - 1,945ms
     - 1,613
     - 0.62ms
     - 0.18ms
     - 1.22ms
     - 2.00ms

**CPython 3.13 compiled is the fastest combination** at 4,586 files/s,
with 3.12 about 3% behind, 3.15 7% behind, and 3.14 9% behind.
Compilation is worth 3.1--3.5x on CPython 3.12 and later, and 4.3--5.2x
on 3.10 and 3.11. The split is ``math.sumprod``: the interpreted build
scores through it where it exists, which is 3.12 onward, and that alone
puts interpreted 3.12--3.15 at 1,305--1,402 files/s against 701--831 on
the two older versions.

CPython 3.15 (3.15.0rc1) needs no changes: both compilers build against
it and accuracy is identical.

PyPy is the fastest way to run the pure-Python wheel: 1,558--1,613
files/s, ahead of every interpreted CPython, with a median of
0.18--0.19ms that sits beside compiled CPython's 0.12--0.20ms. The JIT
wins on ordinary files and gives some of it back on rare and large
ones, where it never warms up: PyPy's p99 is 7.1--7.4ms against compiled
CPython's 1.5--1.7ms and interpreted CPython 3.12+'s 5.6--5.8ms. The
previous edition measured PyPy at 319--339 files/s with a p99 of
72--77ms, so that tail is about a tenth of what it was.

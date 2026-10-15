Performance
===========

Benchmarked against 3,138 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted, measured on the current development tree
(``7.7.0.dev``) rather than on a tagged release.

.. note::

   Every number on this page was measured on an **Apple M4 Max (macOS
   26, 14 cores)**; the current tables use the 3,138-file test suite,
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
   * - **chardet 7.7.0.dev (mypyc)**
     - **3130/3138**
     - **99.7%**
     - **3,113 files/s**
   * - chardet 6.0.0
     - 2649/3138
     - 84.4%
     - 9 files/s
   * - charset-normalizer 3.5.2 (mypyc)
     - 2718/3138
     - 86.6%
     - 2,473 files/s
   * - cchardet 3.2.0
     - 1886/3138
     - 60.1%
     - 4,054 files/s

The suite's 8 binary files count as correct for any detector that
declines them (``encoding=None``).  chardet additionally identifies
their format --- every result carries a ``mime_type``, matched against
40+ magic-number signatures --- which no other detector here offers.
That is a capability rather than an accuracy difference, so it appears
nowhere else in these tables; see :doc:`supported-mime-types`.

chardet leads all detectors on accuracy: **+15.3pp** vs chardet 6.0.0,
**+13.1pp** vs charset-normalizer 3.5.2, and **+39.6pp** vs cchardet 3.2.0.
Only cchardet is faster, and it detects 39.6pp fewer files correctly.

One capability difference is big enough to move that headline: 145 of
the 3,138 files (4.6%) are BOM-less utf-7, which charset-normalizer
documents as out of scope for detection (utf-7 sits in its
supported-encodings inventory, but is only identified when a signature
announces it --- the four *signed* utf-7 files in the suite it does
detect).  chardet detects all 145; charset-normalizer detects none of
them.  Scored without those files, charset-normalizer reaches 90.8%
(2718/2993) while chardet stays at 99.7% (2985/2993), so the +13.1pp
lead reads as +8.9pp for anyone who takes BOM-less utf-7 off the
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
   * - **chardet 7.7.0.dev (mypyc)**
     - **99.7%**
     - **82.4%**
     - +17.3pp
   * - charset-normalizer 3.5.2 (mypyc)
     - 86.6%
     - 78.2%
     - +8.4pp
   * - cchardet 3.2.0
     - 60.1%
     - 52.5%
     - +7.6pp

"Concession" is the share of files a detector wins only under lenient
rules. **chardet benefits from lenient scoring more than the others
do** --- 544 files, against charset-normalizer's 264. Our lead survives
the stricter convention but narrows from +13.1pp to +4.2pp.

The concessions are overwhelmingly ISO-8859-x to the corresponding
Windows codepage (71 ``iso-8859-2`` -> ``windows-1250``, 62
``iso-8859-1`` -> ``windows-1252``, 51 ``iso-8859-5`` ->
``windows-1251``, 45 ``iso-8859-9`` -> ``windows-1254``, 37 ``euc-kr``
-> ``cp949``).

This is a deliberate design position, not a scoring convenience: **when
two encodings can both decode the observed bytes, returning the larger
superset is the correct answer.** Detection examines at most the first
200 KB of a file (``max_bytes``). A byte past that window can require
the superset --- a C1 curly quote in what looked like ISO-8859-1, an
extension character in what looked like EUC-KR --- and if it does, the
subset answer breaks the eventual ``.decode()`` while the superset
answer never can: the superset decodes everything the subset does,
identically. Erring toward the superset is the only choice that is safe
under partial evidence. The web platform reached the same conclusion
for the same reason: the WHATWG/W3C Encoding Standard requires
browsers to decode content labelled ``ascii`` or ``iso-8859-1`` as
``windows-1252``.

Nor does the strict column measure a detection weakness. The gap it
shows is the output convention itself: run with superset remapping
disabled (``prefer_superset=False``), chardet scores **91.8% strict**
(2882/3138) --- ahead of charset-normalizer's 78.2% --- while giving up
only two files of lenient accuracy (3130 of 3138 to 3128). Exact subset
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
   * - cchardet 3.2.0
     - 4,054
     - 0.25ms
     - 0.04ms
     - 0.71ms
     - 1.06ms
     - 2.09ms
   * - **chardet 7.7.0.dev (mypyc)**
     - **3,113**
     - **0.32ms**
     - **0.15ms**
     - **0.59ms**
     - **0.83ms**
     - **3.50ms**
   * - charset-normalizer 3.5.2 (mypyc)
     - 2,473
     - 0.40ms
     - 0.28ms
     - 0.87ms
     - 1.30ms
     - 2.33ms
   * - chardet 6.0.0
     - 9
     - 107.52ms
     - 4.62ms
     - 262.99ms
     - 530.15ms
     - 1698.25ms

With mypyc and the Cython scoring kernel, chardet is **360x faster**
than chardet 6.0.0 at the mean. Unlike the rest of this table, that
ratio is measured with five interleaved rounds timing both detectors
back to back in one session, and 360x is the median of the five: the
per-round ratios spanned 357--361x while absolute timings drifted a few
percent with machine temperature. A ratio derived from this table's
cells instead would inherit that drift on top of the spread, which is
why earlier editions of this page quoted anywhere from 279x to 331x for
earlier code. Treat it as a three-hundred-fold speedup, not as a
three-significant-figure measurement.

Against charset-normalizer 3.5.2, chardet leads everywhere except the
far tail: **1.3x on aggregate throughput** (3,113 vs 2,473 files/s),
**1.9x at the median** (0.15ms vs 0.28ms), 1.5x at p90 and 1.6x at
p95, with a worst case 3.1x lower (10.4ms vs 32.6ms). charset-normalizer
keeps p99 (2.33ms vs 3.50ms). See `Latency by Script Family`_ --- that
remaining gap is concentrated in legacy CJK.

cchardet 3.2.0 still leads aggregate throughput, at 1.3x chardet (4,054
vs 3,113 files/s), and holds the better p99 (2.09ms vs 3.50ms); chardet's
worst case is 2.5x lower (10.4ms vs 25.7ms). The trade remains accuracy:
cchardet detects 39.6pp fewer files correctly, and reports no language
at all.

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
   * - **chardet 7.7.0.dev**
     - **CJK**
     - 230
     - **0.16ms**
     - 1.53ms
     - 6.79ms
     - 8.22ms
   * - **chardet 7.7.0.dev**
     - **non-CJK**
     - 2,908
     - **0.14ms**
     - **0.80ms**
     - 3.00ms
     - 10.41ms
   * - charset-normalizer 3.5.2
     - CJK
     - 230
     - 0.27ms
     - 1.02ms
     - 1.59ms
     - 2.65ms
   * - charset-normalizer 3.5.2
     - non-CJK
     - 2,908
     - 0.28ms
     - 1.34ms
     - 2.33ms
     - 32.60ms

chardet leads on the median in both groups (0.16ms vs 0.27ms on CJK,
0.14ms vs 0.28ms elsewhere) --- escape sequences and clear multi-byte
structure resolve immediately --- and on p95 outside CJK (0.80ms vs
1.34ms). charset-normalizer owns the CJK tail from p95 up: 1.02ms vs
1.53ms at p95, and 1.59ms against chardet's 6.79ms at p99. That single
group is where the aggregate p99 gap in `Speed`_ comes from; on
non-CJK files, which are 93% of the suite, the gap narrows to 3.00ms
against 2.33ms.

The stakes stay bounded in absolute terms --- chardet's slowest CJK
file completes in under 9ms, and its worst case overall is 3.1x lower
than charset-normalizer's (10.4ms vs 32.6ms).

Percentiles over a mixed corpus are sensitive to how much CJK it
contains: this suite is 7.3% CJK (230/3,138), so a CJK-heavier corpus
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
     - chardet 7.7.0.dev (mypyc)
     - charset-normalizer 3.5.2
   * - utf-8
     - 1 MiB
     - 1.0ms
     - **0.5ms**
   * - utf-8
     - 32 MiB
     - 29.5ms
     - **10.0ms**
   * - utf-8
     - 272 MiB
     - 244.1ms
     - **85.0ms**
   * - cp1252
     - 1 MiB
     - **13.4ms**
     - 23.5ms :sup:`*`
   * - cp1252
     - 32 MiB
     - **35.7ms**
     - 704.9ms :sup:`*`
   * - cp1252
     - 272 MiB
     - **215.0ms**
     - 7,583.1ms :sup:`*`
   * - shift_jis
     - 1 MiB
     - 10.8ms
     - 10.8ms
   * - shift_jis
     - 32 MiB
     - **67.8ms**
     - 315.7ms
   * - shift_jis
     - 272 MiB
     - **505.1ms**
     - 2,704.2ms
   * - base64
     - 1 MiB
     - 1.8ms
     - **0.1ms**
   * - base64
     - 32 MiB
     - 21.7ms
     - **1.5ms**
   * - base64
     - 272 MiB
     - 177.9ms
     - **13.0ms**

:sup:`*` misdetected: charset-normalizer returned ``johab`` at 1 and
32 MiB and ``windows-1250`` at 272 MiB for French Windows-1252 text.

Median of five interleaved rounds (each round times both detectors back
to back --- thermal drift makes separate blocks incomparable), compiled
wheel, ``charset_normalizer.detect()`` compatibility API. Buffers repeat
a single line or sentence, so this measures the scan machinery, not
model quality. The ``base64`` row is line-wrapped certificate data ---
the shape that makes chardet's escape-sequence scan work hardest.

The columns split by what each detector has to prove. charset-normalizer
wins wherever a cheap structural answer settles the file: about 3x on
large valid UTF-8, and 10-15x on base64, where chardet validates ASCII
and scans for escape-shift evidence over the whole window while
charset-normalizer samples chunks. Both are the sampling-versus-exactness
trade, taken knowingly.

Where the answer needs actual statistics --- legacy single-byte and
legacy CJK, the encodings a detector exists for --- chardet is **5x to
35x faster** at 32 MiB and above, and charset-normalizer misidentifies
the cp1252 buffers at every size. The asymmetry has one cause: sampling
costs charset-normalizer its short-circuits, so it keeps probing
candidate encodings over chunks spread through a large buffer, while
chardet's non-UTF-8 path drops to bounded evidence as soon as its
C-speed exhaustive scans have ruled out the fast answers.

The pure-Python wheel lands within 15% of the compiled one on these
inputs (0.19s to 0.63s at 272 MiB): past the exhaustive scans and the
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
   * - **chardet 7.7.0.dev**
     - **6.8ms**
     - **1.1 MiB** :sup:`*`
     - **28.2 MiB**
     - **161.1 MiB**
   * - charset-normalizer 3.5.2
     - 4.8ms
     - 2.0 MiB
     - 71.0 MiB
     - 254.4 MiB
   * - cchardet 3.2.0
     - 1.9ms
     - 503 KiB
     - 64.5 MiB
     - 186.0 MiB

:sup:`*` chardet 7.x loads its model tables lazily --- they are not
read until the first ``detect()`` call, so ``import chardet`` costs
about 1 MiB. The full model cost appears in Peak Memory instead.

chardet uses **2.5x less peak memory** than charset-normalizer 3.5.2,
**2.3x less** than cchardet 3.2.0, and has the **lowest RSS of every
detector measured**. Since 7.5.0 decompresses its models incrementally,
its 28.2 MiB peak is the smallest on the table. (cchardet 2.2.1 used to
report a near-zero traced peak because its C allocations were invisible
to ``tracemalloc``; 3.2.0's are visible.)

Read the table knowing the two APIs do different amounts of work:
charset-normalizer's result carries the decoded text (retaining the
``str`` is part of its design), while chardet returns only the
encoding name.  A caller who needs the text pays chardet's numbers
plus one ``bytes.decode`` afterward; charset-normalizer's numbers
include it.

chardet 6.0.0 is omitted from this table: its memory benchmark
instruments every ``detect()`` call with ``tracemalloc``, and at 103ms
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
   * - **chardet 7.7.0.dev**
     - **515 KiB**
     - **544 KiB**
     - **592 KiB**
     - **636 KiB**
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
544 KiB. chardet's per-call cost is flat instead: it varies by 69% from
median to p99 (544 -> 917 KiB), while charset-normalizer's grows 14x
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
   * - **chardet 7.7.0.dev**
     - **2912/3130**
     - **93.0%**
   * - charset-normalizer 3.5.2
     - 1714/3130
     - 54.8%
   * - chardet 6.0.0
     - 1211/3130
     - 38.7%
   * - cchardet 3.2.0
     - 0/3130
     - 0.0%

chardet detects language with **93.0% accuracy** --- +38.2pp vs
charset-normalizer 3.5.2 and +54.3pp vs chardet 6.0.0. cchardet 3.2.0 does
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
   * - **chardet 7.7.0.dev (mypyc)**
     - **469/469**
     - **100.0%**
     - **94.8%**
   * - charset-normalizer 3.5.2 (mypyc)
     - 457/469
     - 97.4%
     - 86.8%

chardet is **+2.6pp more accurate** than charset-normalizer 3.5.2 on
charset-normalizer's own test data --- every file in the subset ---
and **+8.0pp** on language detection.

Under strict scoring the result appears to reverse: on these same
files charset-normalizer scores **85.7%** against chardet's **68.2%**.
This subset is dense in exactly the encodings where we deliberately
emit the Windows superset (33 ``euc-kr`` -> ``cp949``, 31
``iso-8859-5`` -> ``windows-1251``, 22 ``iso-8859-2`` ->
``windows-1250``), so it concedes 31.8pp to leniency against
charset-normalizer's 11.7pp. The reversal measures the output
convention, not detection quality: with superset remapping disabled,
chardet scores **90.6% strict on this same subset** --- ahead of
charset-normalizer's 85.7% --- while losing two files of lenient
accuracy. We emit the superset anyway because, as argued under
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
Benchmarked with 3,138 files, ``encoding_era=ALL``:

.. list-table::
   :header-rows: 1
   :widths: 14 14 14 14 14

   * - Python
     - 1 thread
     - 2 threads
     - 4 threads
     - 8 threads
   * - 3.13 (pure)
     - 5,110ms
     - 5,080ms
     - 5,060ms
     - 5,010ms
   * - 3.13 (compiled)
     - 840ms
     - 880ms
     - 850ms
     - 860ms
   * - 3.13t (pure)
     - 6,100ms
     - 3,340ms (1.8x)
     - 1,830ms (3.3x)
     - 1,440ms (4.2x)
   * - 3.14 (pure)
     - 4,730ms
     - 4,660ms
     - 4,630ms
     - 4,610ms
   * - 3.14 (compiled)
     - 910ms
     - 910ms
     - 930ms
     - 920ms
   * - 3.14t (pure)
     - 5,120ms
     - 2,660ms (1.9x)
     - 1,400ms (3.7x)
     - 1,090ms (4.7x)
   * - **3.14t (compiled)**
     - 1,010ms
     - 570ms (1.8x)
     - **350ms (2.9x)**
     - 360ms (2.8x)
   * - 3.15 (pure)
     - 4,670ms
     - 4,550ms
     - 4,500ms
     - 4,490ms
   * - 3.15 (compiled)
     - 900ms
     - 910ms
     - 900ms
     - 900ms
   * - 3.15t (pure)
     - 5,190ms
     - 2,700ms (1.9x)
     - 1,420ms (3.7x)
     - 920ms (5.6x)
   * - **3.15t (compiled)**
     - 990ms
     - 560ms (1.8x)
     - **350ms (2.8x)**
     - 360ms (2.8x)

**3.14t and 3.15t compiled at 4 threads are the fastest configurations
measured** --- 350ms for the whole suite, about 9,000 files/s. Eight
threads add nothing over four here; the suite is small enough that
scheduling costs catch up with the remaining parallelism.

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
interpreted, and ``models`` selects the scoring path matching the build
it finds.

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Build
     - Files/s
     - Speedup
   * - Pure Python
     - 667
     - baseline
   * - mypyc + Cython kernel
     - 3,460
     - **5.2x**

Both rows are the CPython 3.14 measurements from the cross-version table
below, so they are directly comparable to each other; the small gap
against the headline table above is run-to-run variance.

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
release measurement on the 3,138-file suite the rest of this page
uses. It is
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
     - **3,113**
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

Benchmarked chardet 7.7.0.dev across all supported Python versions
(macOS aarch64, 3,138 files, ``encoding_era=ALL``). CPython versions
install compiled wheels automatically; PyPy receives the pure-Python
wheel. Encoding accuracy is identical on every interpreter and both
builds (99.7%), and language accuracy is 93.0% everywhere except PyPy,
where two files of 3,130 land on a different label because the
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
     - 1,025ms
     - 3,061
     - 0.33ms
     - 0.20ms
     - 0.53ms
     - 0.72ms
   * - CPython 3.10
     - pure
     - 5,916ms
     - 530
     - 1.89ms
     - 0.85ms
     - 4.47ms
     - 6.51ms
   * - CPython 3.11
     - mypyc
     - 1,020ms
     - 3,076
     - 0.33ms
     - 0.20ms
     - 0.52ms
     - 0.71ms
   * - CPython 3.11
     - pure
     - 4,660ms
     - 673
     - 1.49ms
     - 0.67ms
     - 3.42ms
     - 5.01ms
   * - CPython 3.12
     - mypyc
     - 869ms
     - 3,611
     - 0.28ms
     - 0.13ms
     - 0.47ms
     - 0.68ms
   * - CPython 3.12
     - pure
     - 4,842ms
     - 648
     - 1.54ms
     - 0.66ms
     - 3.63ms
     - 5.31ms
   * - **CPython 3.13**
     - **mypyc**
     - **835ms**
     - **3,758**
     - **0.27ms**
     - **0.13ms**
     - **0.46ms**
     - **0.69ms**
   * - CPython 3.13
     - pure
     - 5,083ms
     - 617
     - 1.62ms
     - 0.70ms
     - 3.72ms
     - 5.55ms
   * - CPython 3.14
     - mypyc
     - 907ms
     - 3,460
     - 0.29ms
     - 0.13ms
     - 0.52ms
     - 0.74ms
   * - CPython 3.14
     - pure
     - 4,705ms
     - 667
     - 1.50ms
     - 0.63ms
     - 3.51ms
     - 5.15ms
   * - CPython 3.15
     - mypyc
     - 884ms
     - 3,550
     - 0.28ms
     - 0.13ms
     - 0.50ms
     - 0.72ms
   * - CPython 3.15
     - pure
     - 4,639ms
     - 676
     - 1.48ms
     - 0.66ms
     - 3.39ms
     - 4.99ms
   * - PyPy 3.10
     - pure
     - 9,816ms
     - 320
     - 3.13ms
     - 0.22ms
     - 3.41ms
     - 8.33ms
   * - PyPy 3.11
     - pure
     - 9,332ms
     - 336
     - 2.97ms
     - 0.22ms
     - 3.29ms
     - 7.98ms

**CPython 3.13 compiled is the fastest combination** at 3,758 files/s,
with 3.12 about 4% behind. Compilation is worth 4.6--6.1x across CPython
versions. 3.14 and 3.15 land 5--8% behind 3.13 compiled;
interpreted, 3.15 is the quickest (676 files/s), with 3.11 and 3.14
close behind --- all six compiled builds measured back-to-back to rule
out drift.

CPython 3.15 (3.15.0rc1) needs no changes: both compilers build against
it, accuracy is identical, and it is marginally the quickest interpreted
build in the table.

PyPy needs reading by percentile rather than by throughput. Its
aggregate (320--336 files/s) is the lowest here, yet its **median is
among the best measured anywhere on this page** --- 0.22ms, close to
compiled CPython's 0.13--0.20ms. The JIT wins decisively on ordinary
files and loses badly on rare and large ones, where it never warms up:
PyPy's p99 is 73--78ms against compiled CPython's 2.7--3.0ms. A single
"PyPy reaches N% of compiled" ratio therefore misdescribes it. For
typical documents PyPy is competitive with the compiled wheel; for a
corpus with a heavy tail it is several times slower overall.

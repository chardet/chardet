Performance
===========

Benchmarked against 3,138 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted, measured on the current development tree
(``7.6.1.dev``) rather than on a tagged release.

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
   * - **chardet 7.6.1.dev (mypyc)**
     - **3130/3138**
     - **99.7%**
     - **2,641 files/s**
   * - chardet 6.0.0
     - 2649/3138
     - 84.4%
     - 9 files/s
   * - charset-normalizer 3.5.1 (mypyc)
     - 2717/3138
     - 86.6%
     - 2,250 files/s
   * - cchardet 3.2.0
     - 1886/3138
     - 60.1%
     - 4,008 files/s

The suite's 8 binary files count as correct for any detector that
declines them (``encoding=None``).  chardet additionally identifies
their format --- every result carries a ``mime_type``, matched against
40+ magic-number signatures --- which no other detector here offers.
That is a capability rather than an accuracy difference, so it appears
nowhere else in these tables; see :doc:`supported-mime-types`.

chardet leads all detectors on accuracy: **+15.3pp** vs chardet 6.0.0,
**+13.1pp** vs charset-normalizer 3.5.1, and **+39.6pp** vs cchardet 3.2.0.
Only cchardet is faster, and it detects 39.6pp fewer files correctly.

One capability difference is big enough to move that headline: 145 of
the 3,138 files (4.6%) are BOM-less utf-7, which charset-normalizer
documents as out of scope for detection (utf-7 sits in its
supported-encodings inventory, but is only identified when a signature
announces it --- the four *signed* utf-7 files in the suite it does
detect).  chardet detects all 145; charset-normalizer detects none of
them.  Scored without those files, charset-normalizer reaches 90.8%
(2717/2993) while chardet stays at 99.7% (2985/2993), so the +13.1pp
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
   * - **chardet 7.6.1.dev (mypyc)**
     - **99.7%**
     - **82.3%**
     - +17.4pp
   * - charset-normalizer 3.5.1 (mypyc)
     - 86.6%
     - 78.2%
     - +8.4pp
   * - cchardet 3.2.0
     - 60.1%
     - 52.5%
     - +7.6pp

"Concession" is the share of files a detector wins only under lenient
rules. **chardet benefits from lenient scoring more than the others
do** --- 546 files, against charset-normalizer's 264. Our lead survives
the stricter convention but narrows from +13.1pp to +4.1pp.

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
     - 4,008
     - 0.25ms
     - 0.04ms
     - 0.72ms
     - 1.06ms
     - 2.11ms
   * - **chardet 7.6.1.dev (mypyc)**
     - **2,641**
     - **0.38ms**
     - **0.15ms**
     - **0.70ms**
     - **1.04ms**
     - **3.86ms**
   * - charset-normalizer 3.5.1 (mypyc)
     - 2,250
     - 0.44ms
     - 0.30ms
     - 0.98ms
     - 1.50ms
     - 2.59ms
   * - chardet 6.0.0
     - 9
     - 105.89ms
     - 4.23ms
     - 259.26ms
     - 518.44ms
     - 1661.43ms

With mypyc and the Cython scoring kernel, chardet is **315x faster**
than chardet 6.0.0 at the mean. Unlike the rest of this table, that
ratio is measured with five interleaved rounds timing both detectors
back to back in one session, and 315x is the median of the five: the
per-round ratios spanned 301--330x while absolute timings drifted a few
percent with machine temperature. A ratio derived from this table's
cells instead would inherit that drift on top of the spread, which is
why earlier editions of this page quoted anywhere from 279x to 331x for
the same code. Treat it as a three-hundred-fold speedup, not as a
three-significant-figure measurement.

Against charset-normalizer 3.5.1, chardet leads everywhere except the
far tail: **1.2x on aggregate throughput** (2,641 vs 2,250 files/s),
**2.0x at the median** (0.15ms vs 0.30ms), 1.4x at both p90 and p95,
with a worst case 2.8x lower (11.9ms vs 33.8ms). charset-normalizer
keeps p99 (2.59ms vs 3.86ms). See `Latency by Script Family`_ --- that
remaining gap is concentrated in legacy CJK.

cchardet 3.2.0 still leads aggregate throughput, at 1.5x chardet (4,008
vs 2,641 files/s), and holds the better p99 (2.11ms vs 3.86ms); chardet's
worst case is 2.1x lower (11.9ms vs 25.3ms). The trade remains accuracy:
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
   * - **chardet 7.6.1.dev**
     - **CJK**
     - 230
     - **0.17ms**
     - 1.82ms
     - 8.19ms
     - 8.68ms
   * - **chardet 7.6.1.dev**
     - **non-CJK**
     - 2,908
     - **0.15ms**
     - **1.01ms**
     - 3.42ms
     - 11.91ms
   * - charset-normalizer 3.5.1
     - CJK
     - 230
     - 0.28ms
     - 1.02ms
     - 1.77ms
     - 2.26ms
   * - charset-normalizer 3.5.1
     - non-CJK
     - 2,908
     - 0.30ms
     - 1.54ms
     - 2.64ms
     - 33.81ms

chardet leads on the median in both groups (0.17ms vs 0.28ms on CJK,
0.15ms vs 0.30ms elsewhere) --- escape sequences and clear multi-byte
structure resolve immediately --- and on p95 outside CJK (1.01ms vs
1.54ms). charset-normalizer owns the CJK tail from p95 up: 1.02ms vs
1.82ms at p95, and 1.77ms against chardet's 8.19ms at p99. That single
group is where the aggregate p99 gap in `Speed`_ comes from; on
non-CJK files, which are 93% of the suite, the gap narrows to 3.42ms
against 2.64ms.

The stakes stay bounded in absolute terms --- chardet's slowest CJK
file completes in under 9ms, and its worst case overall is 2.8x lower
than charset-normalizer's (11.9ms vs 33.8ms).

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
first 256 KB; statistical scoring on the first 16 KB; language detection
on the first 2 KB. The caps are convergence bounds, not correctness
bounds --- more bytes were not changing those answers --- and they sit
above the default window, so nothing on the rest of this page depends
on them. One verdict is held exact past the cap regardless: the
encoding returned decodes the whole window. After the bounded stages
settle, the winner is decoded over the window, and when it fails the
next candidate that decodes takes its place, so legacy single-byte and
CJK buffers past the cap pay one C-speed decode of the window on top
of the exhaustive scans.

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
     - chardet 7.6.1.dev (mypyc)
     - charset-normalizer 3.5.1
   * - utf-8
     - 1 MiB
     - 1.4ms
     - **0.7ms**
   * - utf-8
     - 32 MiB
     - 27.8ms
     - **10.2ms**
   * - utf-8
     - 272 MiB
     - 232.5ms
     - **84.9ms**
   * - cp1252
     - 1 MiB
     - **11.9ms**
     - 33.8ms :sup:`*`
   * - cp1252
     - 32 MiB
     - **27.1ms**
     - 908.9ms :sup:`*`
   * - cp1252
     - 272 MiB
     - **139.8ms**
     - 8,206.7ms :sup:`*`
   * - shift_jis
     - 1 MiB
     - **10.0ms**
     - 10.7ms
   * - shift_jis
     - 32 MiB
     - **24.3ms**
     - 339.3ms
   * - shift_jis
     - 272 MiB
     - **131.3ms**
     - 2,725.2ms
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
     - 175.4ms
     - **12.4ms**

:sup:`*` misdetected: charset-normalizer returned ``windows-1250`` at
every size for French Windows-1252 text.

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
legacy CJK, the encodings a detector exists for --- chardet is **14x to
59x faster** at 32 MiB and above, and charset-normalizer misidentifies
the cp1252 buffers at every size. The asymmetry has one cause: sampling
costs charset-normalizer its short-circuits, so it keeps probing
candidate encodings over chunks spread through a large buffer, while
chardet's non-UTF-8 path drops to bounded evidence as soon as its
C-speed exhaustive scans have ruled out the fast answers.

The pure-Python wheel lands in the same band on these inputs (0.15s to
0.22s at 272 MiB): past the exhaustive scans, what is left is bounded,
so compilation moves the constant inside the window rather than the
shape of the curve.

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
   * - **chardet 7.6.1.dev**
     - **6.8ms**
     - **1,024 KiB** :sup:`*`
     - **27.7 MiB**
     - **160.5 MiB**
   * - charset-normalizer 3.5.1
     - 4.8ms
     - 2.0 MiB
     - 71.0 MiB
     - 255.5 MiB
   * - cchardet 3.2.0
     - 1.8ms
     - 503 KiB
     - 64.5 MiB
     - 186.3 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs about 1 MiB. The full model cost appears in
Peak Memory instead.

chardet uses **2.6x less peak memory** than charset-normalizer 3.5.1,
**2.3x less** than cchardet 3.2.0, and has the **lowest RSS of every
detector measured**. Since 7.5.0 decompresses its models incrementally,
its 27.7 MiB peak is the smallest on the table. (cchardet 2.2.1 used to
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
   * - **chardet 7.6.1.dev**
     - **502 KiB**
     - **537 KiB**
     - **580 KiB**
     - **618 KiB**
     - **740 KiB**
   * - charset-normalizer 3.5.1
     - 133 KiB
     - 58 KiB
     - 189 KiB
     - 282 KiB
     - 785 KiB
   * - cchardet 3.2.0
     - 66 KiB
     - 9 KiB
     - 93 KiB
     - 190 KiB
     - 602 KiB

**charset-normalizer and cchardet allocate less per call than chardet
at typical sizes** --- 58 KiB and 9 KiB at the median against chardet's
537 KiB. chardet's per-call cost is flat instead: it varies by 38% from
median to p99 (537 -> 740 KiB), while charset-normalizer's grows 13x
(58 -> 785 KiB) and cchardet's 67x (9 -> 602 KiB). charset-normalizer
passes chardet by p99; cchardet closes to within 20% of it without
passing. So chardet trades a higher floor for a predictable ceiling,
which is the better shape for sizing a worker pool; the others are the
better fit when most inputs are small and peak footprint per call
matters more than its variance.

One-time lazy initialization is absorbed by a warmup call before the
distribution is measured (a ~23 MiB peak for chardet — the model load
visible in the table above), so every sample here is a steady-state
call.  The maximum is still excluded from the table because it
describes the single largest input file rather than typical calls:
1.3 MiB for chardet, but 63.9 MiB for both charset-normalizer and
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
   * - **chardet 7.6.1.dev**
     - **2873/3130**
     - **91.8%**
   * - charset-normalizer 3.5.1
     - 1714/3130
     - 54.8%
   * - chardet 6.0.0
     - 1211/3130
     - 38.7%
   * - cchardet 3.2.0
     - 0/3130
     - 0.0%

chardet detects language with **91.8% accuracy** --- +37.0pp vs
charset-normalizer 3.5.1 and +53.1pp vs chardet 6.0.0. cchardet 3.2.0 does
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
   * - **chardet 7.6.1.dev (mypyc)**
     - **469/469**
     - **100.0%**
     - **93.5%**
   * - charset-normalizer 3.5.1 (mypyc)
     - 457/469
     - 97.4%
     - 86.8%

chardet is **+2.6pp more accurate** than charset-normalizer 3.5.1 on
charset-normalizer's own test data --- every file in the subset ---
and **+6.7pp** on language detection.

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
Each call carries its own state with no shared mutable data between threads.
Thread safety adds no measurable overhead (< 0.1%).

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
     - 5,520ms
     - 5,460ms
     - 5,440ms
     - 5,410ms
   * - 3.13 (compiled)
     - 950ms
     - 950ms
     - 970ms
     - 960ms
   * - 3.13t (pure)
     - 6,590ms
     - 3,590ms (1.8x)
     - 2,020ms (3.3x)
     - 1,520ms (4.3x)
   * - 3.14 (pure)
     - 4,990ms
     - 5,000ms
     - 4,900ms
     - 4,910ms
   * - 3.14 (compiled)
     - 1,200ms
     - 1,050ms
     - 1,070ms
     - 1,050ms
   * - 3.14t (pure)
     - 5,490ms
     - 2,870ms (1.9x)
     - 1,570ms (3.5x)
     - 1,110ms (4.9x)
   * - **3.14t (compiled)**
     - 1,170ms
     - 640ms (1.8x)
     - 390ms (3.0x)
     - **340ms (3.4x)**
   * - 3.15 (pure)
     - 4,840ms
     - 4,850ms
     - 4,790ms
     - 4,800ms
   * - 3.15 (compiled)
     - 1,060ms
     - 1,080ms
     - 1,070ms
     - 1,060ms
   * - 3.15t (pure)
     - 5,460ms
     - 2,840ms (1.9x)
     - 1,510ms (3.6x)
     - 1,100ms (5.0x)
   * - **3.15t (compiled)**
     - 1,120ms
     - 650ms (1.7x)
     - **380ms (2.9x)**
     - **350ms (3.2x)**

**3.14t compiled at 8 threads is the fastest configuration measured**
--- 340ms for the whole suite, about 9,200 files/s.

Scaling here depends on the Cython kernel declaring itself safe without
the GIL. An extension that does not is enough to make CPython re-enable
the GIL for the whole process on import, with a ``RuntimeWarning``, at
which point these rows flatten completely --- 3.14t measured
1.13/1.16/1.17/1.18s before the declaration was added, worse than
shipping no kernel at all. The declaration is accurate rather than a
silencer: the kernel's functions read their arguments, touch no shared
mutable state, and return a value.

The 3.13t compiled row is absent because that build cannot be produced:
mypy 2.x's free-threaded runtime calls ``_PyObject_XDecRefDelayed``,
which CPython only provides from 3.14t onward, so compiling for 3.13t
fails outright. Prebuilt wheels are published for 3.14t but not 3.13t,
so ``pip install chardet`` on 3.13t installs the pure-Python wheel.

Individual :class:`~chardet.UniversalDetector` instances are not thread-safe.
Create one instance per thread when using the streaming API.

Optional Compiled Builds
------------------------

Prebuilt compiled wheels are published to PyPI for CPython on Linux,
macOS, and Windows. A regular ``pip install chardet`` will pick them up
automatically --- no extra flags needed.

Two compilers are involved. `mypyc <https://mypyc.readthedocs.io>`_
compiles fifteen modules --- thirteen pipeline stages plus the model
loader and its format reader --- and `Cython <https://cython.org>`_
compiles one more: ``_kernel.py``, holding the bigram scoring loop that
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
     - 641
     - baseline
   * - mypyc + Cython kernel
     - 3,053
     - **4.8x**

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
3,125-file suite of its own session, and the rest of this page has since
moved to a 3,138-file suite. It is
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
   * - **chardet 7.6.0 (compiled)**
     - **2026-08**
     - **3117/3125**
     - **99.7%**
     - **2,793**
     - **91.8%**

chardet 3.0.1--3.0.4 had identical accuracy and speed; only 3.0.4 is
shown. chardet 5.1.0--5.2.0 were likewise identical. chardet 7.1.0 and
7.2.0 had identical accuracy; only 7.2.0 is shown. chardet 7.4.0--7.4.2
reached the same 99.3% accuracy as 7.4.3, so only 7.4.3 is shown ---
7.4.0 is no longer installable from PyPI and was re-released as
7.4.0.post2. charade 1.0.2 could not be installed on Python 3.14.
chardet 3.0.0 crashed on Python 3.14 and is omitted.

Performance Across Python Versions
-----------------------------------

Benchmarked chardet 7.6.1.dev across all supported Python versions
(macOS aarch64, 3,138 files, ``encoding_era=ALL``). CPython versions
install compiled wheels automatically; PyPy receives the pure-Python
wheel. Accuracy is identical on every interpreter and both
builds (99.7% encoding, 91.8% language); only speed varies.

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
     - 1,126ms
     - 2,787
     - 0.36ms
     - 0.20ms
     - 0.57ms
     - 0.87ms
   * - CPython 3.10
     - pure
     - 6,331ms
     - 496
     - 2.02ms
     - 0.87ms
     - 4.66ms
     - 6.86ms
   * - CPython 3.11
     - mypyc
     - 1,123ms
     - 2,794
     - 0.36ms
     - 0.20ms
     - 0.57ms
     - 0.86ms
   * - CPython 3.11
     - pure
     - 4,914ms
     - 639
     - 1.57ms
     - 0.68ms
     - 3.56ms
     - 5.23ms
   * - CPython 3.12
     - mypyc
     - 979ms
     - 3,205
     - 0.31ms
     - 0.13ms
     - 0.53ms
     - 0.87ms
   * - CPython 3.12
     - pure
     - 5,138ms
     - 611
     - 1.64ms
     - 0.67ms
     - 3.79ms
     - 5.51ms
   * - **CPython 3.13**
     - **mypyc**
     - **932ms**
     - **3,367**
     - **0.30ms**
     - **0.13ms**
     - **0.51ms**
     - **0.79ms**
   * - CPython 3.13
     - pure
     - 5,434ms
     - 577
     - 1.73ms
     - 0.71ms
     - 3.96ms
     - 5.96ms
   * - CPython 3.14
     - mypyc
     - 1,028ms
     - 3,053
     - 0.33ms
     - 0.13ms
     - 0.59ms
     - 0.89ms
   * - CPython 3.14
     - pure
     - 4,898ms
     - 641
     - 1.56ms
     - 0.64ms
     - 3.64ms
     - 5.21ms
   * - CPython 3.15
     - mypyc
     - 1,023ms
     - 3,067
     - 0.33ms
     - 0.13ms
     - 0.59ms
     - 0.90ms
   * - CPython 3.15
     - pure
     - 4,794ms
     - 655
     - 1.53ms
     - 0.63ms
     - 3.49ms
     - 5.16ms
   * - PyPy 3.10
     - pure
     - 9,554ms
     - 328
     - 3.04ms
     - 0.18ms
     - 3.29ms
     - 8.26ms
   * - PyPy 3.11
     - pure
     - 9,076ms
     - 346
     - 2.89ms
     - 0.18ms
     - 3.22ms
     - 7.93ms

**CPython 3.13 compiled is the fastest combination** at 3,367 files/s,
with 3.12 about 5% behind. Compilation is worth 4.4--5.8x across CPython
versions. 3.14 and 3.15 land about 9% behind 3.13 compiled;
interpreted, 3.15 is the quickest (655 files/s), with 3.14 and 3.11
close behind --- all six compiled builds measured back-to-back to rule
out drift.

CPython 3.15 (3.15.0rc1) needs no changes: both compilers build against
it, accuracy is identical, and it is marginally the quickest interpreted
build in the table.

PyPy needs reading by percentile rather than by throughput. Its
aggregate (328--346 files/s) is the lowest here, yet its **median is
among the best measured anywhere on this page** --- 0.18ms, level with
compiled CPython's 0.13--0.20ms. The JIT wins decisively on ordinary
files and loses badly on rare and large ones, where it never warms up:
PyPy's p99 is 72--77ms against compiled CPython's 3.1--3.4ms. A single
"PyPy reaches N% of compiled" ratio therefore misdescribes it. For
typical documents PyPy is competitive with the compiled wheel; for a
corpus with a heavy tail it is several times slower overall.

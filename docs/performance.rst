Performance
===========

Benchmarked against 2,517 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted.

.. note::

   Timings on this page were re-measured for 7.5.1 on an **Apple M4 Max
   (macOS 26, 14 cores)**. Earlier releases were benchmarked on
   different hardware, so absolute timings are **not** comparable
   against numbers published in older versions of these docs --- a
   number that improved between releases may reflect the faster
   machine, the faster code, or both. Comparisons *within* a table are
   valid: every detector, Python version, and build in a given table
   was measured on the same machine, almost always in the same session
   (the one exception is noted under `Historical Performance`_).

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
   * - **chardet 7.5.1 (mypyc)**
     - **2503/2517**
     - **99.4%**
     - **2,903 files/s**
   * - chardet 6.0.0
     - 2219/2517
     - 88.2%
     - 20 files/s
   * - charset-normalizer 3.4.9 (mypyc)
     - 2150/2517
     - 85.4%
     - 1,054 files/s
   * - cchardet 3.1.0
     - 1411/2517
     - 56.1%
     - 5,277 files/s

chardet leads all detectors on accuracy: **+11.2pp** vs chardet 6.0.0,
**+14.0pp** vs charset-normalizer 3.4.9, and **+43.3pp** vs cchardet 3.1.0.

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
   * - **chardet 7.5.1 (mypyc)**
     - **99.4%**
     - **84.6%**
     - +14.9pp
   * - charset-normalizer 3.4.9 (mypyc)
     - 85.4%
     - 75.9%
     - +9.5pp
   * - cchardet 3.1.0
     - 56.1%
     - 50.1%
     - +6.0pp

"Concession" is the share of files a detector wins only under lenient
rules. **chardet benefits from lenient scoring more than the others
do** --- 374 files, against charset-normalizer's 240. Our lead survives
the stricter convention but narrows from +14.0pp to +8.7pp.

The concessions are overwhelmingly ISO-8859-x to the corresponding
Windows codepage (51 ``iso8859-5`` -> ``cp1251``, 46 ``iso8859-2`` ->
``cp1250``, 33 ``euc_kr`` -> ``cp949``, 33 ``iso8859-1`` ->
``cp1252``).

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
disabled (``prefer_superset=False``), chardet scores **92.0% strict**
(2316/2517) --- ahead of charset-normalizer's 75.9% --- while giving up
only three files of lenient accuracy (99.4% -> 99.3%). Exact subset
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
   * - cchardet 3.1.0
     - 5,277
     - 0.19ms
     - 0.03ms
     - 0.57ms
     - 0.79ms
     - 1.64ms
   * - **chardet 7.5.1 (mypyc)**
     - **2,903**
     - **0.34ms**
     - **0.17ms**
     - **0.85ms**
     - **1.03ms**
     - **1.77ms**
   * - charset-normalizer 3.4.9 (mypyc)
     - 1,054
     - 0.95ms
     - 0.55ms
     - 2.31ms
     - 3.78ms
     - 6.28ms
   * - chardet 6.0.0
     - 20
     - 49.20ms
     - 1.08ms
     - 108.84ms
     - 226.81ms
     - 673.60ms

With mypyc compilation, chardet 7.5.1 is **143x faster** than chardet
6.0.0, and **2.8x faster** than charset-normalizer 3.4.9 (mypyc) at the
mean. The gap holds across the whole distribution: **3.2x at the
median** (0.17ms vs 0.55ms), 3.7x at p95 (1.03ms vs 3.78ms), and 3.5x
at p99 (1.77ms vs 6.28ms), with a worst case 3.2x lower (10ms vs 33ms).
See
`Latency by Script Family`_ for the CJK split, the one subset where
charset-normalizer keeps a (few-millisecond) edge in the tail.

cchardet 3.1.0 leads aggregate throughput at 1.8x chardet (5,277 vs
2,903 files/s) and edges the tail (p99 1.64ms vs chardet's 1.77ms),
but chardet's worst case is 2.2x lower (10ms vs 22ms). The trade
remains accuracy: cchardet detects 43.3pp fewer files correctly.

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
   * - **chardet 7.5.1**
     - **CJK**
     - 183
     - **0.20ms**
     - 1.85ms
     - **4.22ms**
     - 10.31ms
   * - **chardet 7.5.1**
     - **non-CJK**
     - 2,334
     - 0.17ms
     - 1.00ms
     - **1.56ms**
     - 10.09ms
   * - charset-normalizer 3.4.9
     - CJK
     - 183
     - 0.49ms
     - 1.11ms
     - 1.53ms
     - 1.67ms
   * - charset-normalizer 3.4.9
     - non-CJK
     - 2,334
     - 0.56ms
     - 3.99ms
     - 6.42ms
     - 32.59ms

chardet now leads on CJK through the median (0.20ms vs 0.49ms --- escape
sequences and clear multi-byte structure resolve immediately) and even
on the CJK *mean* (0.49ms vs 0.55ms). charset-normalizer keeps the
flatter CJK tail (p99 1.53ms vs chardet's 4.22ms), but the absolute
stakes are small: the gap is a few milliseconds and chardet's slowest
CJK file completes in 10ms. chardet is ahead everywhere else
(p99 1.56ms vs 6.42ms).

Percentiles over a mixed corpus are sensitive to how much CJK it
contains: this suite is 7.2% CJK (183/2,517), so a CJK-heavier corpus
shifts chardet's aggregate p95/p99 upward --- by milliseconds, not
orders of magnitude.

``UTF-8``/``UTF-16``/``UTF-32`` count as non-CJK here even when the text
is Chinese, Japanese, or Korean, because they are resolved by BOM or
byte-pattern checks and never reach the disambiguation path.

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
   * - **chardet 7.5.1**
     - **5.3ms**
     - **995 KiB** :sup:`*`
     - **27.5 MiB**
     - **126.1 MiB**
   * - chardet 6.0.0
     - 17.0ms
     - 12.1 MiB
     - 28.8 MiB
     - 132.3 MiB
   * - charset-normalizer 3.4.9
     - 3.5ms
     - 1.6 MiB
     - 69.9 MiB
     - 216.9 MiB
   * - cchardet 3.1.0
     - 0.7ms
     - 31.8 KiB
     - 64.0 MiB
     - 153.6 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs 995 KiB against chardet 6.0.0's 12.1 MiB. The
full model cost appears in Peak Memory instead.

chardet uses **2.5x less peak memory** than charset-normalizer 3.4.9,
**2.3x less** than cchardet 3.1.0, and has the **lowest RSS of every
detector measured**. Since 7.5.0 decompresses its models incrementally,
its 27.5 MiB peak is the smallest on the table, edging out even chardet
6.0.0's 28.8 MiB --- without the older version's much lower accuracy
and throughput. (cchardet 2.2.1 used to report a near-zero traced peak
because its C allocations were invisible to ``tracemalloc``; 3.1.0's
are visible.)

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
   * - **chardet 7.5.1**
     - **504 KiB**
     - **530 KiB**
     - **564 KiB**
     - **572 KiB**
     - **610 KiB**
   * - charset-normalizer 3.4.9
     - 129 KiB
     - 57 KiB
     - 161 KiB
     - 216 KiB
     - 410 KiB
   * - chardet 6.0.0
     - 108 KiB
     - 69 KiB
     - 182 KiB
     - 301 KiB
     - 876 KiB
   * - cchardet 3.1.0
     - 45 KiB
     - 6 KiB
     - 38 KiB
     - 56 KiB
     - 120 KiB

**charset-normalizer and cchardet allocate less per call than chardet
at typical sizes** --- 57 KiB and 6 KiB at the median against chardet's
530 KiB. chardet's per-call cost is flat instead: it varies by 15% from
median to p99 (530 -> 610 KiB), while charset-normalizer's grows 7x
(57 -> 410 KiB), cchardet's 20x (6 -> 120 KiB), and chardet 6.0.0's 13x
(69 -> 876 KiB). So chardet trades a higher floor for a predictable
ceiling, which is the better shape for sizing a worker pool; the others
are the better fit when most inputs are small and peak footprint per
call matters more than its variance.

One-time lazy initialization is absorbed by a warmup call before the
distribution is measured (a ~23 MiB peak for chardet — the model load
visible in the table above), so every sample here is a steady-state
call.  The maximum is still excluded from the table because it
describes the single largest input file rather than typical calls:
1.3 MiB for chardet, but 63.9 MiB for both charset-normalizer and
cchardet 3.1.0, whose per-call footprints grow with input size.

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
   * - **chardet 7.5.1**
     - **2400/2509**
     - **95.7%**
   * - charset-normalizer 3.4.9
     - 1486/2509
     - 59.2%
   * - chardet 6.0.0
     - 1003/2509
     - 40.0%
   * - cchardet 3.1.0
     - 0/2509
     - 0.0%

chardet detects language with **95.7% accuracy** --- +36.4pp vs
charset-normalizer 3.4.9 and +55.7pp vs chardet 6.0.0. cchardet 3.1.0 does
not report language.

Accuracy on charset-normalizer's Test Set
------------------------------------------

charset-normalizer maintains its own test dataset at
`char-dataset <https://github.com/Ousret/char-dataset>`_. 469 of those
files also exist in the chardet test suite (matched by content hash),
so we can compare both detectors on charset-normalizer's own ground
truth. We filed
`an issue <https://github.com/Ousret/char-dataset/issues/1>`_ about
the 5 files we excluded (4 ambiguous Cyrillic files and 1 corrupted
Vietnamese file) and 2 we relabeled (UTF-8-SIG, not UTF-8).

.. list-table::
   :header-rows: 1
   :widths: 35 15 15 15

   * - Detector
     - Correct
     - Encoding Accuracy
     - Language Accuracy
   * - **chardet 7.5.1 (mypyc)**
     - **467/469**
     - **99.6%**
     - **92.8%**
   * - charset-normalizer 3.4.9 (mypyc)
     - 453/469
     - 96.6%
     - 85.9%

chardet is **+3.0pp more accurate** than charset-normalizer 3.4.9 on
charset-normalizer's own test data, and **+6.9pp** on language
detection.

Under strict scoring the result appears to reverse: on these same
files charset-normalizer scores **84.9%** against chardet's **67.8%**.
This subset is dense in exactly the encodings where we deliberately
emit the Windows superset (33 ``euc_kr`` -> ``cp949``, 31 ``iso8859-5``
-> ``cp1251``, 22 ``iso8859-2`` -> ``cp1250``), so it concedes 31.8pp
to leniency against charset-normalizer's 11.7pp. The reversal measures
the output convention, not detection quality: with superset remapping
disabled, chardet scores **91.3% strict on this same subset** ---
ahead of charset-normalizer's 84.9% --- while losing three files of
lenient accuracy. We emit the superset anyway because, as argued under
`Strict (Exact-Match) Scoring`_, it is the correct answer when only a
prefix of the file has been examined. Whichever convention you prefer,
it should be applied to both detectors --- which is the point of
publishing both columns.

For the record, the two corpora are not independent: 472 of
char-dataset's 477 files (99%) are byte-identical to files in the
chardet test suite, and the encoding labels agree on 442 of them. The
disagreements are mostly the same superset question resolved the other
way (17 files we label ``iso8859-8`` and they label ``cp1255``).

You can reproduce these numbers with
``python scripts/compare_detectors.py --cn-dataset --cn --mypyc``.

Thread Safety
-------------

:func:`chardet.detect` and :func:`chardet.detect_all` are fully thread-safe.
Each call carries its own state with no shared mutable data between threads.
Thread safety adds no measurable overhead (< 0.1%).

On free-threaded Python (GIL disabled), detection scales with threads.
Standard GIL Python shows no scaling --- the GIL serializes threads.
Benchmarked with 2,517 files, ``encoding_era=ALL``:

.. list-table::
   :header-rows: 1
   :widths: 14 14 14 14 14

   * - Python
     - 1 thread
     - 2 threads
     - 4 threads
     - 8 threads
   * - 3.13 (pure)
     - 3,370ms
     - 3,400ms
     - 3,400ms
     - 3,360ms
   * - 3.13t (pure)
     - 4,070ms
     - 2,220ms (1.8x)
     - 1,270ms (3.2x)
     - 1,030ms (4.0x)
   * - 3.13 (mypyc)
     - 790ms
     - 720ms
     - 720ms
     - 740ms
   * - **3.13t (mypyc)** :sup:`*`
     - 810ms
     - 490ms (1.7x)
     - 300ms (2.7x)
     - **270ms (3.0x)**
   * - 3.14 (pure)
     - 3,100ms
     - 3,220ms
     - 3,060ms
     - 3,080ms
   * - 3.14t (pure)
     - 3,380ms
     - 1,760ms (1.9x)
     - 1,100ms (3.1x)
     - 680ms (5.0x)
   * - 3.14 (mypyc)
     - 880ms
     - 850ms
     - 870ms
     - 880ms
   * - **3.14t (mypyc)**
     - 1,230ms
     - 700ms (1.8x)
     - 430ms (2.9x)
     - **380ms (3.2x)**

:sup:`*` The 3.13t mypyc row was compiled locally with mypy 1.19.1. mypy
2.x's free-threaded runtime uses ``_PyObject_XDecRefDelayed``, which CPython
only provides from 3.14t onward, so a 3.13t build fails under mypy 2.x.
Prebuilt mypyc wheels are published for 3.14t but not 3.13t, so
``pip install chardet`` on 3.13t installs the pure-Python wheel.

Individual :class:`~chardet.UniversalDetector` instances are not thread-safe.
Create one instance per thread when using the streaming API.

Optional mypyc Compilation
--------------------------

Prebuilt `mypyc <https://mypyc.readthedocs.io>`_-compiled wheels are
published to PyPI for CPython on Linux, macOS, and Windows. A regular
``pip install chardet`` will pick them up automatically --- no extra flags
needed.

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Build
     - Files/s
     - Speedup
   * - Pure Python
     - 816
     - baseline
   * - mypyc compiled
     - 2,903
     - **3.6x**

Both rows are the CPython 3.14 measurements from the cross-version table
below, so they are directly comparable to each other; the small gap
against the headline table above is run-to-run variance.

Pure-Python wheels are always available for PyPy and platforms without
prebuilt binaries.

Historical Performance
----------------------

Accuracy and speed of every Python 3-compatible chardet release and its
temporary Python-3-compatible fork `charade <https://pypi.org/project/charade/>`_, measured on
the same 2,517-file test suite with the same equivalence rules. Pure
Python on CPython 3.14 for versions before 7.0; mypyc-compiled for
7.0+, matching what ``pip install chardet`` delivers. Language column
shows "---" for versions that did not support language detection.

All rows were measured on the machine noted at the top of this page,
but the 7.5.0 and 7.5.1 rows come from later sessions than the rest
of the table. To bound the session-to-session drift, 7.4.3 was
re-measured back-to-back with 7.5.0 in a single session: the same-session speed
ratio (3.0x) matches the cross-session ratio implied by the table
(3.1x), and the absolute drift was about 10%.

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
     - 716/2517
     - 28.4%
     - 69
     - ---
   * - charade 1.0.1
     - 2012-12
     - 714/2517
     - 28.4%
     - 69
     - ---
   * - charade 1.0.3
     - 2013-01
     - 1018/2517
     - 40.4%
     - 76
     - ---
   * - chardet 2.2.1
     - 2013-12
     - 1019/2517
     - 40.5%
     - 76
     - ---
   * - chardet 2.3.0
     - 2014-10
     - 1165/2517
     - 46.3%
     - 76
     - ---
   * - chardet 3.0.4
     - 2017-06
     - 1253/2517
     - 49.8%
     - 82
     - 16.2%
   * - chardet 4.0.0
     - 2020-12
     - 1253/2517
     - 49.8%
     - 87
     - 16.9%
   * - chardet 5.0.0
     - 2022-06
     - 1618/2517
     - 64.3%
     - 84
     - 16.9%
   * - chardet 5.2.0
     - 2023-08
     - 1645/2517
     - 65.4%
     - 81
     - 16.7%
   * - chardet 6.0.0
     - 2026-02
     - 2219/2517
     - 88.2%
     - 20
     - 40.0%
   * - chardet 7.0.1 (mypyc)
     - 2026-03
     - 2469/2517
     - 98.1%
     - 869
     - 95.2%
   * - chardet 7.2.0 (mypyc)
     - 2026-03
     - 2470/2517
     - 98.1%
     - 865
     - 95.3%
   * - chardet 7.3.0 (mypyc)
     - 2026-03
     - 2470/2517
     - 98.1%
     - 926
     - 95.3%
   * - chardet 7.4.3 (mypyc)
     - 2026-04
     - 2499/2517
     - 99.3%
     - 878
     - 95.7%
   * - chardet 7.5.0 (mypyc)
     - 2026-08
     - 2499/2517
     - 99.3%
     - 2,724
     - 95.7%
   * - **chardet 7.5.1 (mypyc)**
     - **2026-08**
     - **2503/2517**
     - **99.4%**
     - **2,903**
     - **95.7%**

chardet 3.0.1--3.0.4 had identical accuracy and speed; only 3.0.4 is
shown. chardet 5.1.0--5.2.0 were likewise identical. chardet 7.1.0 and
7.2.0 had identical accuracy; only 7.2.0 is shown. chardet 7.4.0--7.4.2
reached the same 99.3% accuracy as 7.4.3, so only 7.4.3 is shown ---
7.4.0 is no longer installable from PyPI and was re-released as
7.4.0.post2. charade 1.0.2 could not be installed on Python 3.14.
chardet 3.0.0 crashed on Python 3.14 and is omitted.

Performance Across Python Versions
-----------------------------------

Benchmarked chardet 7.5.1 across all supported Python versions
(macOS aarch64, 2,517 files, ``encoding_era=ALL``). CPython versions
install mypyc-compiled wheels automatically; PyPy receives the
pure-Python wheel.

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
     - 837ms
     - 3,007
     - 0.33ms
     - 0.21ms
     - 0.68ms
     - 0.82ms
   * - CPython 3.10
     - pure
     - 4,006ms
     - 628
     - 1.59ms
     - 0.85ms
     - 4.08ms
     - 4.98ms
   * - CPython 3.11
     - mypyc
     - 870ms
     - 2,893
     - 0.35ms
     - 0.21ms
     - 0.70ms
     - 0.87ms
   * - CPython 3.11
     - pure
     - 3,089ms
     - 815
     - 1.23ms
     - 0.66ms
     - 3.11ms
     - 3.78ms
   * - CPython 3.12
     - mypyc
     - 784ms
     - 3,210
     - 0.31ms
     - 0.16ms
     - 0.73ms
     - 0.90ms
   * - CPython 3.12
     - pure
     - 3,226ms
     - 780
     - 1.28ms
     - 0.66ms
     - 3.34ms
     - 4.11ms
   * - **CPython 3.13**
     - **mypyc**
     - **776ms**
     - **3,243**
     - **0.31ms**
     - **0.16ms**
     - **0.73ms**
     - **0.91ms**
   * - CPython 3.13
     - pure
     - 3,355ms
     - 750
     - 1.33ms
     - 0.68ms
     - 3.42ms
     - 4.17ms
   * - CPython 3.14
     - mypyc
     - 867ms
     - 2,903
     - 0.34ms
     - 0.17ms
     - 0.85ms
     - 1.03ms
   * - CPython 3.14
     - pure
     - 3,085ms
     - 816
     - 1.23ms
     - 0.62ms
     - 3.19ms
     - 3.93ms
   * - PyPy 3.10
     - pure
     - 3,252ms
     - 774
     - 1.29ms
     - 0.16ms
     - 2.93ms
     - 3.57ms
   * - PyPy 3.11
     - pure
     - 3,102ms
     - 811
     - 1.23ms
     - 0.16ms
     - 2.82ms
     - 3.50ms

**CPython 3.13 + mypyc is the fastest combination** at 3,243 files/s,
with 3.12 within 1% --- the two trade places between sessions. mypyc
provides a 3.5--4.8x speedup across CPython versions; the gap is
smallest on 3.11 and 3.14, and 3.14 remains the fastest pure-Python
CPython. Pure Python on PyPy (774--811 files/s) sits inside the
pure-CPython range (628--816 files/s) and reaches 24--28% of
mypyc-compiled CPython throughput.

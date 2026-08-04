Performance
===========

Benchmarked against 2,517 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted.

.. note::

   Timings on this page were re-measured for 7.4.4 on an **Apple M4 Max
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
   * - **chardet 7.4.4 (mypyc)**
     - **2499/2517**
     - **99.3%**
     - **2,724 files/s**
   * - chardet 6.0.0
     - 2219/2517
     - 88.2%
     - 20 files/s
   * - charset-normalizer 3.4.9 (mypyc)
     - 2150/2517
     - 85.4%
     - 1,051 files/s
   * - cchardet 3.1.0
     - 1411/2517
     - 56.1%
     - 4,652 files/s

chardet leads all detectors on accuracy: **+11.1pp** vs chardet 6.0.0,
**+13.9pp** vs charset-normalizer 3.4.9, and **+43.2pp** vs cchardet 3.1.0.

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
   * - **chardet 7.4.4 (mypyc)**
     - **99.3%**
     - **84.4%**
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
the stricter convention but narrows from +13.9pp to +8.5pp.

The concessions are overwhelmingly ISO-8859-x to the corresponding
Windows codepage (51 ``iso8859-5`` -> ``cp1251``, 46 ``iso8859-2`` ->
``cp1250``, 33 ``iso8859-1`` -> ``cp1252``). Those are safe: the Windows
codepage is a true superset, so it decodes the bytes losslessly and
text passed to ``.decode()`` comes out correct. For content with no C1
bytes the two are genuinely indistinguishable, which is why we score
them as equivalent by default --- but the strict column is published so
the choice is visible rather than baked into a headline number.

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
     - 4,652
     - 0.22ms
     - 0.03ms
     - 0.65ms
     - 0.90ms
     - 1.87ms
   * - **chardet 7.4.4 (mypyc)**
     - **2,724**
     - **0.37ms**
     - **0.16ms**
     - **0.93ms**
     - **1.12ms**
     - **1.85ms**
   * - charset-normalizer 3.4.9 (mypyc)
     - 1,051
     - 0.95ms
     - 0.54ms
     - 2.34ms
     - 3.80ms
     - 6.28ms
   * - chardet 6.0.0
     - 20
     - 49.36ms
     - 1.10ms
     - 109.12ms
     - 228.69ms
     - 671.93ms

With mypyc compilation, chardet 7.4.4 is **134x faster** than chardet
6.0.0, and **2.6x faster** than charset-normalizer 3.4.9 (mypyc) at the
mean. The gap holds across the whole distribution: **3.4x at the
median** (0.16ms vs 0.54ms), at p95 (1.12ms vs 3.80ms), and at p99
(1.85ms vs 6.28ms), with a worst case 2.9x lower (11ms vs 32ms). See
`Latency by Script Family`_ for the CJK split, the one subset where
charset-normalizer keeps a (few-millisecond) edge in the tail.

cchardet 3.1.0 leads aggregate throughput at 1.7x chardet (4,652 vs
2,724 files/s) --- a large improvement over its 2.2.1 release, which
chardet had caught --- but the two meet at the tail (p99 1.87ms vs
chardet's 1.85ms) and chardet's worst case is 2.3x lower (11ms vs
25ms). The trade remains accuracy: cchardet detects 43.2pp fewer
files correctly.

Latency by Script Family
------------------------

Legacy CJK multi-byte encodings (Big5, GB, EUC, Shift_JIS, ISO-2022,
Johab) need structural probing and statistical scoring across many
candidate models, and that remains chardet's most expensive path ---
though 7.4.4's upper-bound pruning cut that tail roughly in half.
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
   * - **chardet 7.4.4**
     - **CJK**
     - 183
     - **0.18ms**
     - 1.86ms
     - **4.72ms**
     - 10.29ms
   * - **chardet 7.4.4**
     - **non-CJK**
     - 2,334
     - 0.16ms
     - 1.10ms
     - **1.71ms**
     - 10.94ms
   * - charset-normalizer 3.4.9
     - CJK
     - 183
     - 0.49ms
     - 1.10ms
     - 1.59ms
     - 1.80ms
   * - charset-normalizer 3.4.9
     - non-CJK
     - 2,334
     - 0.54ms
     - 4.05ms
     - 6.38ms
     - 32.04ms

chardet now leads on CJK through the median (0.18ms vs 0.49ms --- escape
sequences and clear multi-byte structure resolve immediately) and even
on the CJK *mean* (0.51ms vs 0.55ms). charset-normalizer keeps the
flatter CJK tail (p99 1.59ms vs chardet's 4.72ms), but the absolute
stakes are small: the gap is a few milliseconds and chardet's slowest
CJK file completes in 10ms. chardet is ahead everywhere else
(p99 1.71ms vs 6.38ms).

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
   * - **chardet 7.4.4**
     - **5.7ms**
     - **995 KiB** :sup:`*`
     - **27.4 MiB**
     - **125.0 MiB**
   * - chardet 6.0.0
     - 17.0ms
     - 12.1 MiB
     - 28.8 MiB
     - 132.3 MiB
   * - charset-normalizer 3.4.9
     - 3.6ms
     - 1.6 MiB
     - 69.9 MiB
     - 219.8 MiB
   * - cchardet 3.1.0
     - 0.7ms
     - 31.8 KiB
     - 64.0 MiB
     - 153.4 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs 995 KiB against chardet 6.0.0's 12.1 MiB. The
full model cost appears in Peak Memory instead.

chardet uses **2.6x less peak memory** than charset-normalizer 3.4.9,
**2.3x less** than cchardet 3.1.0, and has the **lowest RSS of every
detector measured**. Since 7.4.4 decompresses its models incrementally,
its 27.4 MiB peak is the smallest on the table, edging out even chardet
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
   * - **chardet 7.4.4**
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
   * - **chardet 7.4.4**
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
   * - **chardet 7.4.4 (mypyc)**
     - **463/469**
     - **98.7%**
     - **92.8%**
   * - charset-normalizer 3.4.9 (mypyc)
     - 453/469
     - 96.6%
     - 85.9%

chardet is **+2.1pp more accurate** than charset-normalizer 3.4.9 on
charset-normalizer's own test data, and **+6.9pp** on language
detection.

Under strict scoring the result reverses: on these same files
charset-normalizer scores **84.9%** against chardet's **67.0%**. This
subset is dense in exactly the encodings where we emit the Windows
superset (33 ``euc_kr`` -> ``cp949``, 31 ``iso8859-5`` -> ``cp1251``,
22 ``iso8859-2`` -> ``cp1250``), so it concedes 31.8pp to leniency
against charset-normalizer's 11.7pp. Whichever convention you prefer,
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
     - 3,300ms
     - 3,330ms
     - 3,240ms
     - 3,250ms
   * - 3.13t (pure)
     - 4,000ms
     - 2,200ms (1.8x)
     - 1,230ms (3.3x)
     - 1,020ms (3.9x)
   * - 3.13 (mypyc)
     - 680ms
     - 700ms
     - 690ms
     - 690ms
   * - **3.13t (mypyc)** :sup:`*`
     - 740ms
     - 480ms (1.5x)
     - 290ms (2.6x)
     - **250ms (3.0x)**
   * - 3.14 (pure)
     - 3,020ms
     - 3,010ms
     - 2,960ms
     - 2,980ms
   * - 3.14t (pure)
     - 3,360ms
     - 1,760ms (1.9x)
     - 930ms (3.6x)
     - 710ms (4.7x)
   * - 3.14 (mypyc)
     - 960ms
     - 820ms
     - 820ms
     - 830ms
   * - **3.14t (mypyc)**
     - 1,170ms
     - 680ms (1.7x)
     - 390ms (3.0x)
     - **270ms (4.3x)**

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
     - 839
     - baseline
   * - mypyc compiled
     - 2,724
     - **3.2x**

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
but the 7.4.4 row comes from a later session than the rest of the
table. To bound the session-to-session drift, 7.4.3 was re-measured
back-to-back with 7.4.4 in a single session: the same-session speed
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
   * - **chardet 7.4.4 (mypyc)**
     - **2026-08**
     - **2499/2517**
     - **99.3%**
     - **2,724**
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

Benchmarked chardet 7.4.4 across all supported Python versions
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
     - 800ms
     - 3,146
     - 0.32ms
     - 0.19ms
     - 0.64ms
     - 0.77ms
   * - CPython 3.10
     - pure
     - 3,934ms
     - 640
     - 1.56ms
     - 0.80ms
     - 4.02ms
     - 4.86ms
   * - CPython 3.11
     - mypyc
     - 789ms
     - 3,190
     - 0.31ms
     - 0.19ms
     - 0.63ms
     - 0.76ms
   * - CPython 3.11
     - pure
     - 3,046ms
     - 826
     - 1.21ms
     - 0.63ms
     - 3.08ms
     - 3.73ms
   * - CPython 3.12
     - mypyc
     - 682ms
     - 3,691
     - 0.27ms
     - 0.13ms
     - 0.64ms
     - 0.77ms
   * - CPython 3.12
     - pure
     - 3,188ms
     - 790
     - 1.27ms
     - 0.62ms
     - 3.31ms
     - 4.06ms
   * - **CPython 3.13**
     - **mypyc**
     - **675ms**
     - **3,729**
     - **0.27ms**
     - **0.13ms**
     - **0.64ms**
     - **0.78ms**
   * - CPython 3.13
     - pure
     - 3,290ms
     - 765
     - 1.31ms
     - 0.64ms
     - 3.36ms
     - 4.17ms
   * - CPython 3.14
     - mypyc
     - 924ms
     - 2,724
     - 0.37ms
     - 0.16ms
     - 0.93ms
     - 1.12ms
   * - CPython 3.14
     - pure
     - 2,999ms
     - 839
     - 1.19ms
     - 0.58ms
     - 3.11ms
     - 3.80ms
   * - PyPy 3.10
     - pure
     - 3,202ms
     - 786
     - 1.27ms
     - 0.12ms
     - 2.94ms
     - 3.65ms
   * - PyPy 3.11
     - pure
     - 3,140ms
     - 802
     - 1.25ms
     - 0.12ms
     - 2.86ms
     - 3.65ms

**CPython 3.13 + mypyc is the fastest combination** at 3,729 files/s,
with 3.12 within 1% --- the two trade places between sessions. mypyc
provides a 3.2--4.9x speedup across CPython versions; the gap is
smallest on 3.14, which runs mypyc-compiled code noticeably slower than
3.12/3.13 while running pure Python slightly faster. Pure Python on
PyPy (786--802 files/s) sits inside the pure-CPython range (640--839
files/s) and reaches 21--29% of mypyc-compiled CPython throughput.

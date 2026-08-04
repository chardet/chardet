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
   valid: every detector, Python version, and build in a given table was
   measured on the same machine in the same session.

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
     - **1,067 files/s**
   * - chardet 6.0.0
     - 2219/2517
     - 88.2%
     - 20 files/s
   * - charset-normalizer 3.4.9 (mypyc)
     - 2150/2517
     - 85.4%
     - 1,010 files/s
   * - cchardet 2.2.1
     - 1407/2517
     - 55.9%
     - 2,695 files/s

chardet leads all detectors on accuracy: **+11.1pp** vs chardet 6.0.0,
**+13.9pp** vs charset-normalizer 3.4.9, and **+43.4pp** vs cchardet 2.2.1.

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
   * - cchardet 2.2.1
     - 55.9%
     - 50.5%
     - +5.4pp

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
   * - cchardet 2.2.1
     - 2,695
     - 0.37ms
     - 0.03ms
     - 0.45ms
     - 0.71ms
     - 2.28ms
   * - **chardet 7.4.4 (mypyc)**
     - **1,067**
     - **0.94ms**
     - **0.33ms**
     - **2.55ms**
     - **3.10ms**
     - **5.36ms**
   * - charset-normalizer 3.4.9 (mypyc)
     - 1,010
     - 0.99ms
     - 0.56ms
     - 2.41ms
     - 4.05ms
     - 6.66ms
   * - chardet 6.0.0
     - 20
     - 49.97ms
     - 1.09ms
     - 112.36ms
     - 231.56ms
     - 679.04ms

With mypyc compilation, chardet 7.4.4 is **53x faster** than chardet 6.0.0.
Against charset-normalizer 3.4.9 (mypyc) the two are close on total
throughput (**1.06x**), but chardet is faster across this corpus at
every point of the distribution: **1.7x at the median** (0.33ms vs
0.56ms), **1.3x at p95** (3.10ms vs 4.05ms), and **1.2x at p99** (5.36ms
vs 6.66ms), with a worst case 1.6x lower (20ms vs 32ms). That ordering
is corpus-dependent --- see `Latency by Script Family`_, where
charset-normalizer wins the CJK tail decisively.

cchardet is the fastest in aggregate, but it owns the worst tail of any
detector measured: its slowest single file takes **355ms**, 18x chardet's
worst case, so a latency budget built on its median will be missed badly
on the outliers.

Latency by Script Family
------------------------

Those aggregates hide a real weakness. Legacy CJK multi-byte encodings
(Big5, GB, EUC, Shift_JIS, ISO-2022, Johab) need structural probing and
statistical scoring across many candidate models, and that is by far
chardet's most expensive path. Splitting the same measurements:

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
     - **0.16ms**
     - 5.39ms
     - **10.84ms**
     - 15.04ms
   * - **chardet 7.4.4**
     - **non-CJK**
     - 2,334
     - 0.32ms
     - 2.85ms
     - **4.59ms**
     - 19.74ms
   * - charset-normalizer 3.4.9
     - CJK
     - 183
     - 0.50ms
     - 1.11ms
     - 1.67ms
     - 1.69ms
   * - charset-normalizer 3.4.9
     - non-CJK
     - 2,334
     - 0.56ms
     - 3.99ms
     - 6.51ms
     - 33.06ms

chardet's CJK *median* is its fastest case (0.16ms --- escape sequences
and clear multi-byte structure resolve immediately), but its CJK *tail*
is its worst: **p99 of 10.84ms, 2.4x its own non-CJK p99**, and
**6.5x charset-normalizer's 1.67ms**. charset-normalizer is markedly
flatter on CJK; chardet is ahead on everything else (p99 4.59ms vs
6.51ms).

**On a CJK-heavy workload, charset-normalizer has the better tail
latency and the "faster at every percentile" summary above does not
apply.** Percentiles over a mixed corpus are sensitive to how much CJK
it contains: this suite is 7.2% CJK (183/2,517), so a corpus with a
higher share will shift chardet's aggregate p95/p99 upward. This is the
clearest optimization target in the pipeline --- 7% of files produce
most of the tail.

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
     - **5.1ms**
     - **937 KiB** :sup:`*`
     - **53.8 MiB**
     - **139.1 MiB**
   * - chardet 6.0.0
     - 17.0ms
     - 12.1 MiB
     - 28.8 MiB
     - 132.3 MiB
   * - charset-normalizer 3.4.9
     - 3.7ms
     - 1.6 MiB
     - 69.9 MiB
     - 220.1 MiB
   * - cchardet 2.2.1
     - 0.7ms
     - 29.5 KiB
     - 50.0 KiB
     - 88.5 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs 937 KiB against chardet 6.0.0's 12.1 MiB. The
full model cost appears in Peak Memory instead.

chardet uses **1.3x less peak memory** than charset-normalizer 3.4.9 and
**1.6x less RSS**. chardet 6.0.0 has the smallest footprint of the
Python detectors (28.8 MiB peak) --- the tradeoff for its much lower
accuracy and throughput.

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
     - **518 KiB**
     - **526 KiB**
     - **547 KiB**
     - **554 KiB**
     - **591 KiB**
   * - charset-normalizer 3.4.9
     - 130 KiB
     - 57 KiB
     - 161 KiB
     - 218 KiB
     - 418 KiB
   * - chardet 6.0.0
     - 108 KiB
     - 69 KiB
     - 182 KiB
     - 301 KiB
     - 876 KiB
   * - cchardet 2.2.1
     - 87 B :sup:`†`
     - 92 B :sup:`†`
     - 98 B :sup:`†`
     - 98 B :sup:`†`
     - 106 B :sup:`†`

:sup:`†` cchardet does its work in C, which ``tracemalloc`` cannot see.
Its near-zero figures mean "invisible", not "free".

**charset-normalizer allocates less per call than chardet at typical
sizes** --- 57 KiB at the median against chardet's 526 KiB. chardet's
per-call cost is flat instead: it varies by 12% from median to p99
(526 -> 591 KiB), while charset-normalizer's grows 7x (57 -> 418 KiB) and
chardet 6.0.0's grows 13x (69 -> 876 KiB). So chardet trades a higher
floor for a predictable ceiling, which is the better shape for sizing a
worker pool; charset-normalizer is the better fit when most inputs are
small and peak footprint per call matters more than its variance.

The maximum is excluded from this table because for every Python
detector it is the *first* call, which pays for lazy initialization
(52.9 MiB for chardet, 63.9 MiB for charset-normalizer, 16.5 MiB for
chardet 6.0.0) rather than anything about steady-state detection.

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
   * - cchardet 2.2.1
     - 0/2509
     - 0.0%

chardet detects language with **95.7% accuracy** --- +36.4pp vs
charset-normalizer 3.4.9 and +55.7pp vs chardet 6.0.0. cchardet 2.2.1 does
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
     - 4,040ms
     - 4,040ms
     - 4,050ms
     - 4,060ms
   * - 3.13t (pure)
     - 4,930ms
     - 2,760ms (1.8x)
     - 1,600ms (3.1x)
     - 1,300ms (3.8x)
   * - 3.13 (mypyc)
     - 2,120ms
     - 2,160ms
     - 2,170ms
     - 2,150ms
   * - **3.13t (mypyc)** :sup:`*`
     - 2,240ms
     - 1,310ms (1.7x)
     - 740ms (3.0x)
     - **490ms (4.6x)**
   * - 3.14 (pure)
     - 3,840ms
     - 3,790ms
     - 3,780ms
     - 3,780ms
   * - 3.14t (pure)
     - 4,170ms
     - 2,150ms (1.9x)
     - 1,160ms (3.6x)
     - 980ms (4.3x)
   * - 3.14 (mypyc)
     - 2,360ms
     - 2,230ms
     - 2,220ms
     - 2,230ms
   * - **3.14t (mypyc)**
     - 2,720ms
     - 1,490ms (1.8x)
     - 830ms (3.3x)
     - **560ms (4.9x)**

:sup:`*` The 3.13t mypyc row was compiled locally with mypy 1.x. mypy 2.x's
free-threaded runtime uses ``_PyObject_XDecRefDelayed``, which CPython only
provides from 3.14t onward, so a 3.13t build fails under mypy 2.x. Prebuilt
mypyc wheels are published for 3.14t but not 3.13t, so ``pip install chardet``
on 3.13t installs the pure-Python wheel.

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
     - 658
     - baseline
   * - mypyc compiled
     - 1,064
     - **1.62x**

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
     - **1,059**
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
     - 2,062ms
     - 1,221
     - 0.82ms
     - 0.33ms
     - 2.10ms
     - 2.52ms
   * - CPython 3.10
     - pure
     - 4,765ms
     - 528
     - 1.89ms
     - 0.83ms
     - 4.74ms
     - 5.76ms
   * - **CPython 3.11**
     - **mypyc**
     - **1,968ms**
     - **1,279**
     - **0.78ms**
     - **0.32ms**
     - **1.99ms**
     - **2.42ms**
   * - CPython 3.11
     - pure
     - 3,748ms
     - 672
     - 1.49ms
     - 0.66ms
     - 3.69ms
     - 4.53ms
   * - CPython 3.12
     - mypyc
     - 2,173ms
     - 1,158
     - 0.86ms
     - 0.30ms
     - 2.32ms
     - 2.81ms
   * - CPython 3.12
     - pure
     - 3,940ms
     - 639
     - 1.57ms
     - 0.65ms
     - 4.02ms
     - 4.91ms
   * - CPython 3.13
     - mypyc
     - 2,106ms
     - 1,195
     - 0.84ms
     - 0.29ms
     - 2.26ms
     - 2.73ms
   * - CPython 3.13
     - pure
     - 4,037ms
     - 623
     - 1.60ms
     - 0.67ms
     - 4.04ms
     - 5.01ms
   * - CPython 3.14
     - mypyc
     - 2,366ms
     - 1,064
     - 0.94ms
     - 0.32ms
     - 2.57ms
     - 3.09ms
   * - CPython 3.14
     - pure
     - 3,825ms
     - 658
     - 1.52ms
     - 0.62ms
     - 3.86ms
     - 4.76ms
   * - PyPy 3.10
     - pure
     - 3,226ms
     - 780
     - 1.28ms
     - 0.12ms
     - 2.96ms
     - 3.64ms
   * - PyPy 3.11
     - pure
     - 3,102ms
     - 811
     - 1.23ms
     - 0.12ms
     - 2.87ms
     - 3.55ms

**CPython 3.11 + mypyc is the fastest combination** at 1,279 files/s.
mypyc provides a 1.6--2.3x speedup across CPython versions. PyPy's JIT
is competitive with mypyc: pure Python on PyPy (780--811 files/s) beats every
pure CPython version and reaches 61--76% of mypyc-compiled CPython
throughput.

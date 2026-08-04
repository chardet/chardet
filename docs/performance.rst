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
     - **2,698 files/s**
   * - chardet 6.0.0
     - 2219/2517
     - 88.2%
     - 20 files/s
   * - charset-normalizer 3.4.9 (mypyc)
     - 2150/2517
     - 85.4%
     - 1,024 files/s
   * - cchardet 2.2.1
     - 1407/2517
     - 55.9%
     - 2,706 files/s

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
     - 2,706
     - 0.37ms
     - 0.03ms
     - 0.45ms
     - 0.71ms
     - 2.22ms
   * - **chardet 7.4.4 (mypyc)**
     - **2,698**
     - **0.37ms**
     - **0.16ms**
     - **0.93ms**
     - **1.14ms**
     - **1.92ms**
   * - charset-normalizer 3.4.9 (mypyc)
     - 1,024
     - 0.98ms
     - 0.56ms
     - 2.41ms
     - 3.87ms
     - 6.37ms
   * - chardet 6.0.0
     - 20
     - 50.07ms
     - 1.08ms
     - 111.52ms
     - 230.52ms
     - 685.33ms

With mypyc compilation, chardet 7.4.4 is **135x faster** than chardet
6.0.0, and **2.6x faster** than charset-normalizer 3.4.9 (mypyc) at the
mean. The gap holds across the whole distribution: **3.5x at the
median** (0.16ms vs 0.56ms), **3.4x at p95** (1.14ms vs 3.87ms), and
**3.3x at p99** (1.92ms vs 6.37ms), with a worst case 3.0x lower
(11ms vs 33ms). See `Latency by Script Family`_ for the CJK split, the
one subset where charset-normalizer keeps a (few-millisecond) edge in
the tail.

cchardet and chardet are now tied on aggregate throughput (2,706 vs
2,698 files/s, within run noise), but cchardet owns the worst tail of
any detector measured: its slowest single file takes **354ms**, 32x
chardet's worst case, so a latency budget built on its median will be
missed badly on the outliers.

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
     - **0.19ms**
     - 2.14ms
     - **5.00ms**
     - 10.04ms
   * - **chardet 7.4.4**
     - **non-CJK**
     - 2,334
     - 0.16ms
     - 1.12ms
     - **1.75ms**
     - 10.95ms
   * - charset-normalizer 3.4.9
     - CJK
     - 183
     - 0.52ms
     - 1.16ms
     - 1.58ms
     - 1.63ms
   * - charset-normalizer 3.4.9
     - non-CJK
     - 2,334
     - 0.57ms
     - 4.11ms
     - 6.47ms
     - 32.60ms

chardet now leads on CJK through the median (0.19ms vs 0.52ms --- escape
sequences and clear multi-byte structure resolve immediately) and even
on the CJK *mean* (0.53ms vs 0.58ms). charset-normalizer keeps the
flatter CJK tail (p99 1.58ms vs chardet's 5.00ms), but the absolute
stakes are small: the gap is a few milliseconds and chardet's slowest
CJK file completes in 10ms. chardet is ahead everywhere else
(p99 1.75ms vs 6.47ms).

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
     - **5.1ms**
     - **949 KiB** :sup:`*`
     - **27.4 MiB**
     - **124.2 MiB**
   * - chardet 6.0.0
     - 17.0ms
     - 12.1 MiB
     - 28.8 MiB
     - 132.3 MiB
   * - charset-normalizer 3.4.9
     - 3.8ms
     - 1.6 MiB
     - 69.9 MiB
     - 217.9 MiB
   * - cchardet 2.2.1
     - 0.7ms
     - 29.4 KiB
     - 49.9 KiB
     - 88.2 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs 949 KiB against chardet 6.0.0's 12.1 MiB. The
full model cost appears in Peak Memory instead.

chardet uses **2.6x less peak memory** than charset-normalizer 3.4.9 and
**1.8x less RSS**. Since 7.4.4 decompresses its models incrementally,
chardet also has the smallest peak footprint of the Python detectors
(27.4 MiB, edging out chardet 6.0.0's 28.8 MiB --- without the older
version's much lower accuracy and throughput).

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
     - **514 KiB**
     - **530 KiB**
     - **564 KiB**
     - **572 KiB**
     - **610 KiB**
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
sizes** --- 57 KiB at the median against chardet's 530 KiB. chardet's
per-call cost is flat instead: it varies by 15% from median to p99
(530 -> 610 KiB), while charset-normalizer's grows 7x (57 -> 418 KiB) and
chardet 6.0.0's grows 13x (69 -> 876 KiB). So chardet trades a higher
floor for a predictable ceiling, which is the better shape for sizing a
worker pool; charset-normalizer is the better fit when most inputs are
small and peak footprint per call matters more than its variance.

The maximum is excluded from this table because for every Python
detector it is the *first* call, which pays for lazy initialization
(23.2 MiB for chardet, 63.9 MiB for charset-normalizer, 16.5 MiB for
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
     - 3,330ms
     - 3,280ms
     - 3,320ms
     - 3,310ms
   * - 3.13t (pure)
     - 4,050ms
     - 2,210ms (1.8x)
     - 1,280ms (3.2x)
     - 1,000ms (4.1x)
   * - 3.13 (mypyc)
     - 660ms
     - 660ms
     - 670ms
     - 660ms
   * - **3.13t (mypyc)** :sup:`*`
     - 730ms
     - 440ms (1.7x)
     - 250ms (2.9x)
     - **250ms (2.9x)**
   * - 3.14 (pure)
     - 3,040ms
     - 3,010ms
     - 3,040ms
     - 3,120ms
   * - 3.14t (pure)
     - 3,390ms
     - 1,720ms (2.0x)
     - 970ms (3.5x)
     - 670ms (5.1x)
   * - 3.14 (mypyc)
     - 950ms
     - 840ms
     - 840ms
     - 840ms
   * - **3.14t (mypyc)**
     - 1,150ms
     - 620ms (1.9x)
     - 350ms (3.3x)
     - **220ms (5.2x)**

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
     - 836
     - baseline
   * - mypyc compiled
     - 2,698
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
     - **2,698**
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
     - 767ms
     - 3,282
     - 0.30ms
     - 0.19ms
     - 0.59ms
     - 0.72ms
   * - CPython 3.10
     - pure
     - 3,976ms
     - 633
     - 1.58ms
     - 0.81ms
     - 4.03ms
     - 4.90ms
   * - CPython 3.11
     - mypyc
     - 759ms
     - 3,316
     - 0.30ms
     - 0.18ms
     - 0.59ms
     - 0.72ms
   * - CPython 3.11
     - pure
     - 3,062ms
     - 822
     - 1.22ms
     - 0.64ms
     - 3.01ms
     - 3.75ms
   * - **CPython 3.12**
     - **mypyc**
     - **635ms**
     - **3,964**
     - **0.25ms**
     - **0.12ms**
     - **0.57ms**
     - **0.71ms**
   * - CPython 3.12
     - pure
     - 3,194ms
     - 788
     - 1.27ms
     - 0.62ms
     - 3.29ms
     - 4.09ms
   * - CPython 3.13
     - mypyc
     - 640ms
     - 3,933
     - 0.25ms
     - 0.12ms
     - 0.59ms
     - 0.74ms
   * - CPython 3.13
     - pure
     - 3,304ms
     - 762
     - 1.31ms
     - 0.65ms
     - 3.32ms
     - 4.17ms
   * - CPython 3.14
     - mypyc
     - 933ms
     - 2,698
     - 0.37ms
     - 0.16ms
     - 0.93ms
     - 1.14ms
   * - CPython 3.14
     - pure
     - 3,010ms
     - 836
     - 1.20ms
     - 0.59ms
     - 3.09ms
     - 3.80ms
   * - PyPy 3.10
     - pure
     - 3,267ms
     - 770
     - 1.30ms
     - 0.13ms
     - 3.00ms
     - 3.69ms
   * - PyPy 3.11
     - pure
     - 3,083ms
     - 816
     - 1.22ms
     - 0.12ms
     - 2.83ms
     - 3.47ms

**CPython 3.12 + mypyc is the fastest combination** at 3,964 files/s.
mypyc provides a 3.2--5.2x speedup across CPython versions; the gap is
smallest on 3.14, which runs mypyc-compiled code noticeably slower than
3.12/3.13 while running pure Python slightly faster. Pure Python on
PyPy (770--816 files/s) sits inside the pure-CPython range (633--836
files/s) and reaches 19--30% of mypyc-compiled CPython throughput.

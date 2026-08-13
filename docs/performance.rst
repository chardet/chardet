Performance
===========

Benchmarked against 3,121 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted.

.. note::

   Every number on this page was measured on an **Apple M4 Max (macOS
   26, 14 cores)** against the current 3,121-file test suite, including
   every historical release. Absolute timings are **not** comparable
   against numbers published in older versions of these docs: both the
   hardware and the corpus have changed, and the corpus change alone
   moved the pre-7.0 rows by 20--30%. A figure that improved between
   releases may reflect the faster machine, the larger corpus, the
   faster code, or any combination. Comparisons *within* a table are
   valid --- every detector, Python version, and build in a given table
   was measured on the same machine against the same files.

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
   * - **chardet 7.6.0 (mypyc)**
     - **3113/3121**
     - **99.7%**
     - **1,998 files/s**
   * - chardet 6.0.0
     - 2638/3121
     - 84.5%
     - 10 files/s
   * - charset-normalizer 3.5.0 (mypyc)
     - 2702/3121
     - 86.6%
     - 2,157 files/s
   * - cchardet 3.2.0
     - 1876/3121
     - 60.1%
     - 4,069 files/s

chardet leads all detectors on accuracy: **+15.2pp** vs chardet 6.0.0,
**+13.1pp** vs charset-normalizer 3.5.0, and **+39.6pp** vs cchardet 3.2.0.
It no longer leads on aggregate throughput --- see `Speed`_.

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
   * - **chardet 7.6.0 (mypyc)**
     - **99.7%**
     - **82.4%**
     - +17.4pp
   * - charset-normalizer 3.5.0 (mypyc)
     - 86.6%
     - 78.4%
     - +8.2pp
   * - cchardet 3.2.0
     - 60.1%
     - 52.5%
     - +7.6pp

"Concession" is the share of files a detector wins only under lenient
rules. **chardet benefits from lenient scoring more than the others
do** --- 542 files, against charset-normalizer's 255. Our lead survives
the stricter convention but narrows from +13.1pp to +4.0pp.

The concessions are overwhelmingly ISO-8859-x to the corresponding
Windows codepage (71 ``iso-8859-2`` -> ``windows-1250``, 62
``iso-8859-1`` -> ``windows-1252``, 51 ``iso-8859-5`` ->
``windows-1251``, 45 ``iso-8859-9`` -> ``windows-1254``, 33 ``euc-kr``
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
disabled (``prefer_superset=False``), chardet scores **92.1% strict**
(2873/3121) --- ahead of charset-normalizer's 78.4% --- while giving up
only three files of lenient accuracy (99.7% -> 99.6%). Exact subset
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
     - 4,069
     - 0.25ms
     - 0.04ms
     - 0.71ms
     - 1.01ms
     - 2.10ms
   * - charset-normalizer 3.5.0 (mypyc)
     - 2,157
     - 0.46ms
     - 0.31ms
     - 1.01ms
     - 1.51ms
     - 2.63ms
   * - **chardet 7.6.0 (mypyc)**
     - **1,998**
     - **0.50ms**
     - **0.19ms**
     - **1.04ms**
     - **1.44ms**
     - **5.24ms**
   * - chardet 6.0.0
     - 10
     - 103.27ms
     - 4.05ms
     - 252.64ms
     - 507.98ms
     - 1636.79ms

With mypyc compilation, chardet 7.6.0 is **207x faster** than chardet
6.0.0 at the mean.

Against charset-normalizer 3.5.0 the picture is mixed, and changed with
its 3.5.0 release: **chardet is 1.6x faster at the median** (0.19ms vs
0.31ms) and level through the body of the distribution (p90 1.04ms vs
1.01ms, p95 1.44ms vs 1.51ms), but **charset-normalizer is 2.0x faster
at p99** (2.63ms vs 5.24ms) and slightly ahead on aggregate throughput
(2,157 vs 1,998 files/s). chardet's worst case is 2.4x lower (13.71ms
vs 33.32ms). In short: chardet is quicker on a typical file,
charset-normalizer is steadier on the hard ones, and chardet degrades
less in the extreme. See `Latency by Script Family`_ --- the tail gap
is concentrated in legacy CJK.

cchardet 3.2.0 leads aggregate throughput at 2.0x chardet (4,069 vs
1,998 files/s) and holds the better p99 (2.10ms vs 5.24ms), but
chardet's worst case is 1.8x lower (13.71ms vs 25.22ms). The trade
remains accuracy: cchardet detects 39.6pp fewer files correctly, and
reports no language at all.

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
   * - **chardet 7.6.0**
     - **CJK**
     - 222
     - **0.17ms**
     - 1.99ms
     - 9.00ms
     - 12.25ms
   * - **chardet 7.6.0**
     - **non-CJK**
     - 2,899
     - 0.19ms
     - 1.42ms
     - 5.17ms
     - 13.71ms
   * - charset-normalizer 3.5.0
     - CJK
     - 222
     - 0.32ms
     - 1.02ms
     - 1.48ms
     - 1.93ms
   * - charset-normalizer 3.5.0
     - non-CJK
     - 2,899
     - 0.31ms
     - 1.57ms
     - 2.74ms
     - 33.32ms

chardet leads on the median in both groups (0.17ms vs 0.32ms on CJK,
0.19ms vs 0.31ms elsewhere) --- escape sequences and clear multi-byte
structure resolve immediately. charset-normalizer holds the flatter
tail in both groups, and its CJK advantage is the larger one: p99
1.48ms against chardet's 9.00ms. That is where most of the aggregate
p99 gap in `Speed`_ comes from.

The stakes stay bounded in absolute terms --- chardet's slowest CJK
file completes in 12ms --- but this is a real reversal from 7.5.1,
where chardet held the better non-CJK tail. charset-normalizer 3.5.0
roughly halved its own latency across the board, and its tail is now
flatter than ours everywhere except the extreme, where chardet's worst
case remains 2.4x lower (13.71ms vs 33.32ms).

Percentiles over a mixed corpus are sensitive to how much CJK it
contains: this suite is 7.1% CJK (222/3,121), so a CJK-heavier corpus
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
   * - **chardet 7.6.0**
     - **6.1ms**
     - **1,011 KiB** :sup:`*`
     - **27.6 MiB**
     - **158.5 MiB**
   * - charset-normalizer 3.5.0
     - 4.8ms
     - 1.8 MiB
     - 71.7 MiB
     - 262.1 MiB
   * - cchardet 3.2.0
     - 1.9ms
     - 503 KiB
     - 64.5 MiB
     - 186.1 MiB

:sup:`*` chardet 7.x uses lazy loading --- models and the detection
pipeline are not allocated until the first ``detect()`` call, so
``import chardet`` costs about 1 MiB. The full model cost appears in
Peak Memory instead.

chardet uses **2.6x less peak memory** than charset-normalizer 3.5.0,
**2.3x less** than cchardet 3.2.0, and has the **lowest RSS of every
detector measured**. Since 7.5.0 decompresses its models incrementally,
its 27.6 MiB peak is the smallest on the table. (cchardet 2.2.1 used to
report a near-zero traced peak because its C allocations were invisible
to ``tracemalloc``; 3.2.0's are visible.)

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
   * - **chardet 7.6.0**
     - **494 KiB**
     - **532 KiB**
     - **566 KiB**
     - **583 KiB**
     - **690 KiB**
   * - charset-normalizer 3.5.0
     - 134 KiB
     - 58 KiB
     - 190 KiB
     - 280 KiB
     - 785 KiB
   * - cchardet 3.2.0
     - 67 KiB
     - 9 KiB
     - 92 KiB
     - 189 KiB
     - 602 KiB

**charset-normalizer and cchardet allocate less per call than chardet
at typical sizes** --- 58 KiB and 9 KiB at the median against chardet's
532 KiB. chardet's per-call cost is flat instead: it varies by 30% from
median to p99 (532 -> 690 KiB), while charset-normalizer's grows 14x
(58 -> 785 KiB) and cchardet's 67x (9 -> 602 KiB), overtaking chardet
at p99 in both cases. So chardet trades a higher floor for a
predictable ceiling, which is the better shape for sizing a worker
pool; the others are the better fit when most inputs are small and peak
footprint per call matters more than its variance.

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
   * - **chardet 7.6.0**
     - **2859/3113**
     - **91.8%**
   * - charset-normalizer 3.5.0
     - 1701/3113
     - 54.6%
   * - chardet 6.0.0
     - 1200/3113
     - 38.5%
   * - cchardet 3.2.0
     - 0/3113
     - 0.0%

chardet detects language with **91.8% accuracy** --- +37.2pp vs
charset-normalizer 3.5.0 and +53.3pp vs chardet 6.0.0. cchardet 3.2.0 does
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
Vietnamese file) and 2 we relabeled (UTF-8-SIG, not UTF-8).

.. list-table::
   :header-rows: 1
   :widths: 35 15 15 15

   * - Detector
     - Correct
     - Encoding Accuracy
     - Language Accuracy
   * - **chardet 7.6.0 (mypyc)**
     - **469/469**
     - **100.0%**
     - **93.5%**
   * - charset-normalizer 3.5.0 (mypyc)
     - 457/469
     - 97.4%
     - 86.8%

chardet is **+2.6pp more accurate** than charset-normalizer 3.5.0 on
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
chardet scores **91.3% strict on this same subset** --- ahead of
charset-normalizer's 85.7% --- while losing three files of lenient
accuracy. We emit the superset anyway because, as argued under
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
Benchmarked with 3,121 files, ``encoding_era=ALL``:

.. list-table::
   :header-rows: 1
   :widths: 14 14 14 14 14

   * - Python
     - 1 thread
     - 2 threads
     - 4 threads
     - 8 threads
   * - 3.13 (pure)
     - 5,340ms
     - 5,420ms
     - 5,320ms
     - 5,300ms
   * - 3.13t (pure)
     - 6,440ms
     - 3,490ms (1.8x)
     - 1,950ms (3.3x)
     - 1,490ms (4.3x)
   * - 3.13 (mypyc)
     - 1,210ms
     - 1,200ms
     - 1,210ms
     - 1,210ms
   * - 3.14 (pure)
     - 4,860ms
     - 4,810ms
     - 4,810ms
     - 4,790ms
   * - 3.14t (pure)
     - 5,380ms
     - 2,790ms (1.9x)
     - 1,510ms (3.6x)
     - 1,020ms (5.3x)
   * - 3.14 (mypyc)
     - 1,460ms
     - 1,480ms
     - 1,410ms
     - 1,430ms
   * - **3.14t (mypyc)**
     - 1,990ms
     - 1,140ms (1.7x)
     - 660ms (3.0x)
     - **510ms (3.9x)**

**3.14t with mypyc at 8 threads is the fastest configuration measured**
--- 510ms for the whole suite, about 6,100 files/s.

The 3.13t mypyc row is absent because that build no longer exists:
mypy 2.x's free-threaded runtime calls ``_PyObject_XDecRefDelayed``,
which CPython only provides from 3.14t onward, so compiling for 3.13t
fails outright. Earlier editions of this page carried a 3.13t row built
locally with mypy 1.19.1; it is dropped rather than carried forward,
since it could not be re-measured against the current test suite.
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
     - 643
     - baseline
   * - mypyc compiled
     - 2,220
     - **3.5x**

Both rows are the CPython 3.14 measurements from the cross-version table
below, so they are directly comparable to each other; the small gap
against the headline table above is run-to-run variance.

Pure-Python wheels are always available for PyPy and platforms without
prebuilt binaries.

Historical Performance
----------------------

Accuracy and speed of every Python 3-compatible chardet release and its
temporary Python-3-compatible fork `charade <https://pypi.org/project/charade/>`_, measured on
the same 3,121-file test suite with the same equivalence rules. Pure
Python on CPython 3.14 for versions before 7.0; mypyc-compiled for
7.0+, matching what ``pip install chardet`` delivers. Language column
shows "---" for versions that did not support language detection.

Every row here was re-measured in a single session against the current
test suite, so the table is internally consistent end to end. It is
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
   * - **chardet 7.6.0 (mypyc)**
     - **2026-08**
     - **3113/3121**
     - **99.7%**
     - **1,952**
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

Benchmarked chardet 7.6.0 across all supported Python versions
(macOS aarch64, 3,121 files, ``encoding_era=ALL``). CPython versions
install mypyc-compiled wheels automatically; PyPy receives the
pure-Python wheel. Accuracy is identical on every interpreter and both
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
     - 1,283ms
     - 2,433
     - 0.41ms
     - 0.21ms
     - 0.73ms
     - 1.05ms
   * - CPython 3.10
     - pure
     - 6,232ms
     - 501
     - 2.00ms
     - 0.88ms
     - 4.64ms
     - 6.69ms
   * - CPython 3.11
     - mypyc
     - 1,256ms
     - 2,485
     - 0.40ms
     - 0.21ms
     - 0.71ms
     - 1.03ms
   * - CPython 3.11
     - pure
     - 4,858ms
     - 642
     - 1.56ms
     - 0.68ms
     - 3.52ms
     - 5.12ms
   * - CPython 3.12
     - mypyc
     - 1,217ms
     - 2,565
     - 0.39ms
     - 0.15ms
     - 0.76ms
     - 1.12ms
   * - CPython 3.12
     - pure
     - 5,096ms
     - 612
     - 1.63ms
     - 0.68ms
     - 3.73ms
     - 5.46ms
   * - **CPython 3.13**
     - **mypyc**
     - **1,183ms**
     - **2,638**
     - **0.38ms**
     - **0.15ms**
     - **0.74ms**
     - **1.08ms**
   * - CPython 3.13
     - pure
     - 5,335ms
     - 585
     - 1.71ms
     - 0.70ms
     - 3.90ms
     - 5.93ms
   * - CPython 3.14
     - mypyc
     - 1,406ms
     - 2,220
     - 0.45ms
     - 0.17ms
     - 0.92ms
     - 1.29ms
   * - CPython 3.14
     - pure
     - 4,855ms
     - 643
     - 1.56ms
     - 0.64ms
     - 3.60ms
     - 5.15ms
   * - PyPy 3.10
     - pure
     - 8,951ms
     - 349
     - 2.87ms
     - 0.18ms
     - 3.15ms
     - 7.51ms
   * - PyPy 3.11
     - pure
     - 8,557ms
     - 365
     - 2.74ms
     - 0.17ms
     - 3.03ms
     - 7.20ms

**CPython 3.13 + mypyc is the fastest combination** at 2,638 files/s,
with 3.12 about 3% behind. mypyc provides a 3.5--4.9x speedup across
CPython versions. CPython 3.14 is the outlier: it is the fastest
pure-Python CPython (643 files/s) but the *slowest* compiled one, 16%
behind 3.13 --- measured back-to-back with the other four to rule out
drift.

PyPy needs reading by percentile rather than by throughput. Its
aggregate (349--365 files/s) is the lowest in the table, yet its
**median is the best measured anywhere on this page** --- 0.17ms,
edging out compiled CPython's 0.15--0.21ms. The JIT wins decisively on
ordinary files and loses badly on rare and large ones, where it never
warms up: PyPy's p99 is 62--66ms against compiled CPython's 3.6--4.6ms.
So a single "PyPy reaches N% of mypyc" ratio misdescribes it. For
typical documents PyPy is competitive with the compiled wheel; for a
corpus with a heavy tail it is several times slower overall.

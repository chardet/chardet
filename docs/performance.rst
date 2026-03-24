Performance
===========

Benchmarked against 2,518 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.14 unless noted.

Detecting a superset of the expected encoding is counted as correct,
since the superset decodes the data without loss (e.g., detecting
Windows-1252 when the expected answer is ISO-8859-1, or GB18030 when
the expected answer is GB2312). Byte-order variants of the same
encoding (e.g., UTF-16-LE vs UTF-16) are also treated as equivalent.
These rules are applied equally to all detectors.

Accuracy
--------

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 15

   * - Detector
     - Correct
     - Accuracy
     - Speed
   * - **chardet 7.3.0 (mypyc)**
     - **2483/2518**
     - **98.6%**
     - **512 files/s**
   * - chardet 6.0.0
     - 2220/2518
     - 88.2%
     - 12 files/s
   * - charset-normalizer 3.4.6 (mypyc)
     - 2149/2518
     - 85.3%
     - 363 files/s
   * - cchardet 2.1.19
     - 1407/2518
     - 55.9%
     - 1,926 files/s

chardet leads all detectors on accuracy: **+10.4pp** vs chardet 6.0.0,
**+13.3pp** vs charset-normalizer, and **+42.7pp** vs cchardet.

Speed
-----

.. list-table::
   :header-rows: 1
   :widths: 30 12 12 12 12 12

   * - Detector
     - Files/s
     - Mean
     - Median
     - p90
     - p95
   * - cchardet 2.1.19
     - 1,926
     - 0.52ms
     - 0.05ms
     - 0.66ms
     - 1.07ms
   * - **chardet 7.3.0 (mypyc)**
     - **512**
     - **1.95ms**
     - **0.60ms**
     - **4.94ms**
     - **6.30ms**
   * - charset-normalizer 3.4.6 (mypyc)
     - 363
     - 2.76ms
     - 1.50ms
     - 7.15ms
     - 10.94ms
   * - chardet 6.0.0
     - 12
     - 86.86ms
     - 1.74ms
     - 193.45ms
     - 398.52ms

With mypyc compilation, chardet 7.3.0 is **44x faster** than chardet 6.0.0 and
**1.4x faster** than charset-normalizer 3.4.6 (mypyc). Median time per file is
0.60ms.

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
   * - **chardet 7.3.0**
     - **0.015s**
     - **1.9 MiB**
     - **25.9 MiB**
     - **115.6 MiB**
   * - chardet 6.0.0
     - 0.053s
     - 13.0 MiB
     - 29.5 MiB
     - 122.3 MiB
   * - charset-normalizer
     - 0.010s
     - 1.4 MiB
     - 101.3 MiB
     - 273.3 MiB
   * - cchardet
     - 0.001s
     - 23.2 KiB
     - 26.8 KiB
     - 81.9 MiB

chardet uses **3.9x less peak memory** than charset-normalizer and
**2.4x less RSS**.

Language Detection
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Detector
     - Correct
     - Accuracy
   * - **chardet 7.3.0**
     - **2406/2510**
     - **95.9%**
   * - charset-normalizer 3.4.6
     - 1487/2510
     - 59.2%
   * - chardet 6.0.0
     - 1004/2510
     - 40.0%
   * - cchardet 2.1.19
     - 0/2510
     - 0.0%

chardet detects language with **95.9% accuracy** — +36.7pp vs
charset-normalizer and +55.9pp vs chardet 6.0.0. cchardet does not report
language.

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
   * - **chardet 7.3.0 (mypyc)**
     - **461/469**
     - **98.3%**
     - **92.8%**
   * - charset-normalizer 3.4.6 (mypyc)
     - 453/469
     - 96.6%
     - 85.9%

chardet is **+1.7pp more accurate** than charset-normalizer on
charset-normalizer's own test data, and **+6.9pp** on language
detection.

You can reproduce these numbers with
``python scripts/compare_detectors.py --cn-dataset --cn --mypyc``.

Thread Safety
-------------

:func:`chardet.detect` and :func:`chardet.detect_all` are fully thread-safe.
Each call carries its own state with no shared mutable data between threads.
Thread safety adds no measurable overhead (< 0.1%).

On free-threaded Python (GIL disabled), detection scales with threads.
Standard GIL Python shows no scaling — the GIL serializes threads.
Benchmarked with 2,518 files, ``encoding_era=ALL``:

.. list-table::
   :header-rows: 1
   :widths: 14 14 14 14 14

   * - Python
     - 1 thread
     - 2 threads
     - 4 threads
     - 8 threads
   * - 3.13 (pure)
     - 8,900ms
     - 8,930ms
     - 8,900ms
     - 8,880ms
   * - 3.13t (pure)
     - 10,600ms
     - 8,220ms (1.3x)
     - 5,140ms (2.1x)
     - 4,500ms (2.4x)
   * - 3.13 (mypyc)
     - 4,760ms
     - 4,600ms
     - 4,600ms
     - 4,620ms
   * - **3.13t (mypyc)**
     - 4,780ms
     - 2,400ms (2.0x)
     - 1,270ms (3.8x)
     - **1,030ms (4.6x)**
   * - 3.14 (pure)
     - 6,700ms
     - 6,800ms
     - 6,770ms
     - 6,790ms
   * - 3.14t (pure)
     - 7,460ms
     - 5,640ms (1.3x)
     - 2,480ms (3.0x)
     - 1,840ms (4.1x)
   * - 3.14 (mypyc)
     - 5,110ms
     - 4,660ms
     - 4,690ms
     - 4,670ms
   * - **3.14t (mypyc)**
     - 5,570ms
     - 2,830ms (2.0x)
     - 1,480ms (3.8x)
     - **1,140ms (4.9x)**

Individual :class:`~chardet.UniversalDetector` instances are not thread-safe.
Create one instance per thread when using the streaming API.

Optional mypyc Compilation
--------------------------

Prebuilt `mypyc <https://mypyc.readthedocs.io>`_-compiled wheels are
published to PyPI for CPython on Linux, macOS, and Windows. A regular
``pip install chardet`` will pick them up automatically — no extra flags
needed.

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Build
     - Files/s
     - Speedup
   * - Pure Python
     - 376
     - baseline
   * - mypyc compiled
     - 493
     - **1.31x**

Pure-Python wheels are always available for PyPy and platforms without
prebuilt binaries.

Performance Across Python Versions
-----------------------------------

Benchmarked chardet 7.3.0 across all supported Python versions
(macOS aarch64, 2,518 files, ``encoding_era=ALL``). CPython versions
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
     - 4,440ms
     - 567
     - 1.76ms
     - 0.58ms
     - 4.40ms
     - 5.65ms
   * - CPython 3.10
     - pure
     - 8,480ms
     - 297
     - 3.36ms
     - 1.29ms
     - 7.82ms
     - 9.89ms
   * - **CPython 3.11**
     - **mypyc**
     - **3,880ms**
     - **649**
     - **1.54ms**
     - **0.51ms**
     - **3.79ms**
     - **4.83ms**
   * - CPython 3.11
     - pure
     - 6,590ms
     - 382
     - 2.62ms
     - 1.00ms
     - 6.12ms
     - 7.97ms
   * - CPython 3.12
     - mypyc
     - 4,580ms
     - 550
     - 1.81ms
     - 0.61ms
     - 4.53ms
     - 5.81ms
   * - CPython 3.12
     - pure
     - 6,840ms
     - 368
     - 2.72ms
     - 1.06ms
     - 6.29ms
     - 8.18ms
   * - CPython 3.13
     - mypyc
     - 4,760ms
     - 529
     - 1.89ms
     - 0.63ms
     - 4.74ms
     - 5.86ms
   * - CPython 3.13
     - pure
     - 8,900ms
     - 283
     - 3.53ms
     - 1.38ms
     - 8.09ms
     - 10.65ms
   * - CPython 3.14
     - mypyc
     - 5,110ms
     - 493
     - 2.03ms
     - 0.68ms
     - 5.08ms
     - 6.43ms
   * - CPython 3.14
     - pure
     - 6,700ms
     - 376
     - 2.66ms
     - 1.02ms
     - 6.15ms
     - 8.13ms
   * - PyPy 3.10
     - pure
     - 6,320ms
     - 398
     - 2.50ms
     - 0.27ms
     - 5.21ms
     - 7.48ms
   * - PyPy 3.11
     - pure
     - 6,330ms
     - 398
     - 2.51ms
     - 0.28ms
     - 5.27ms
     - 7.73ms

**CPython 3.11 + mypyc is the fastest combination** at 649 files/s.
mypyc provides a 1.3--1.9x speedup across CPython versions. PyPy's JIT
is competitive with mypyc: pure Python on PyPy (398 files/s) beats every
pure CPython version and reaches 61--81% of mypyc-compiled CPython
throughput.

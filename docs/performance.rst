Performance
===========

Benchmarked against 2,510 test files from the
`chardet test suite <https://github.com/chardet/test-data>`_. All
detectors evaluated with the same equivalence rules. Numbers below are
CPython 3.12 unless noted.

Accuracy
--------

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 15

   * - Detector
     - Correct
     - Accuracy
     - Speed
   * - **chardet 7.0.2 (mypyc)**
     - **2464/2510**
     - **98.2%**
     - **555 files/s**
   * - chardet 7.0.2 (pure)
     - 2464/2510
     - 98.2%
     - 370 files/s
   * - chardet 6.0.0
     - 2213/2510
     - 88.2%
     - 12 files/s
   * - charset-normalizer
     - 2114/2510
     - 84.2%
     - 130 files/s
   * - cchardet
     - 1405/2510
     - 56.0%
     - 1,803 files/s

chardet leads all detectors on accuracy: **+10.0pp** vs chardet 6.0.0,
**+14.0pp** vs charset-normalizer, and **+42.2pp** vs cchardet.

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
   * - cchardet
     - 1,803
     - 0.55ms
     - 0.05ms
     - 0.64ms
     - 1.09ms
   * - **chardet 7.0.2 (mypyc)**
     - **555**
     - **1.80ms**
     - **0.58ms**
     - **4.14ms**
     - **5.49ms**
   * - chardet 7.0.2 (pure)
     - 370
     - 2.70ms
     - 1.02ms
     - 5.85ms
     - 7.70ms
   * - charset-normalizer (mypyc)
     - 130
     - 7.70ms
     - 2.64ms
     - 22.52ms
     - 38.75ms
   * - charset-normalizer (pure)
     - 67
     - 14.87ms
     - 5.06ms
     - 42.83ms
     - 76.24ms
   * - chardet 6.0.0
     - 12
     - 82.29ms
     - 2.29ms
     - 182.19ms
     - 381.65ms

With mypyc compilation, chardet 7.0.2 is **46x faster** than chardet 6.0.0 and
**4.3x faster** than charset-normalizer (mypyc). Even the pure-Python build is
**31x faster** than chardet 6.0.0 and **5.5x faster** than charset-normalizer
(pure). Median time per file is 0.58ms (mypyc) / 1.02ms (pure).

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
   * - **chardet 7.0.2**
     - **0.019s**
     - **2.7 MiB**
     - **26.2 MiB**
     - **115.9 MiB**
   * - chardet 6.0.0
     - 0.036s
     - 13.0 MiB
     - 29.5 MiB
     - 123.3 MiB
   * - charset-normalizer
     - 0.009s
     - 1.3 MiB
     - 101.2 MiB
     - 323.2 MiB
   * - cchardet
     - 0.001s
     - 23.6 KiB
     - 27.2 KiB
     - 81.7 MiB

chardet uses **3.9x less peak memory** than charset-normalizer and
**2.8x less RSS**.

Language Detection
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 20

   * - Detector
     - Correct
     - Accuracy
   * - **chardet 7.0.2**
     - **2380/2502**
     - **95.1%**
   * - charset-normalizer
     - 1476/2502
     - 59.0%
   * - chardet 6.0.0
     - 1002/2502
     - 40.0%
   * - cchardet
     - 0/2502
     - 0.0%

chardet detects language with **95.1% accuracy** — +36.1pp vs
charset-normalizer and +55.1pp vs chardet 6.0.0. cchardet does not report
language.

Thread Safety
-------------

:func:`chardet.detect` and :func:`chardet.detect_all` are fully thread-safe.
Each call carries its own state with no shared mutable data between threads.
Thread safety adds no measurable overhead (< 0.1%).

On free-threaded Python (3.13t+, GIL disabled), detection scales with
threads:

.. list-table::
   :header-rows: 1
   :widths: 20 20 20

   * - Threads
     - Time
     - Speedup
   * - 1
     - 4,361ms
     - baseline
   * - 2
     - 2,337ms
     - 1.9x
   * - 4
     - 1,930ms
     - 2.3x

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
     - 370
     - baseline
   * - mypyc compiled
     - 555
     - **1.50x**

Pure-Python wheels are always available for PyPy and platforms without
prebuilt binaries.

Performance Across Python Versions
-----------------------------------

Benchmarked chardet 7.0.2 across all supported Python versions
(macOS aarch64, 2,510 files, ``encoding_era=ALL``). CPython versions
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
     - 4,475ms
     - 561
     - 1.78ms
     - 0.53ms
     - 3.95ms
     - 5.09ms
   * - CPython 3.10
     - pure
     - 8,796ms
     - 285
     - 3.50ms
     - 1.22ms
     - 7.33ms
     - 9.31ms
   * - **CPython 3.11**
     - **mypyc**
     - **4,079ms**
     - **615**
     - **1.63ms**
     - **0.48ms**
     - **3.54ms**
     - **4.60ms**
   * - CPython 3.11
     - pure
     - 6,797ms
     - 369
     - 2.71ms
     - 0.92ms
     - 5.65ms
     - 7.41ms
   * - CPython 3.12
     - mypyc
     - 4,597ms
     - 546
     - 1.83ms
     - 0.55ms
     - 3.91ms
     - 5.06ms
   * - CPython 3.12
     - pure
     - 6,545ms
     - 383
     - 2.61ms
     - 0.94ms
     - 5.12ms
     - 6.74ms
   * - CPython 3.13
     - mypyc
     - 5,046ms
     - 497
     - 2.01ms
     - 0.58ms
     - 4.32ms
     - 5.65ms
   * - CPython 3.13
     - pure
     - 9,293ms
     - 270
     - 3.70ms
     - 1.30ms
     - 7.41ms
     - 9.66ms
   * - CPython 3.14
     - mypyc
     - 5,064ms
     - 496
     - 2.02ms
     - 0.60ms
     - 4.39ms
     - 5.64ms
   * - CPython 3.14
     - pure
     - 6,977ms
     - 360
     - 2.78ms
     - 0.98ms
     - 5.64ms
     - 7.32ms
   * - PyPy 3.10
     - pure
     - 6,111ms
     - 411
     - 2.43ms
     - 0.24ms
     - 4.99ms
     - 7.43ms
   * - PyPy 3.11
     - pure
     - 6,114ms
     - 410
     - 2.44ms
     - 0.25ms
     - 4.97ms
     - 7.33ms

**CPython 3.11 + mypyc is the fastest combination** at 615 files/s.
mypyc provides a 1.5--2.0x speedup across CPython versions. PyPy's JIT
is competitive with mypyc: pure Python on PyPy (411 files/s) beats every
pure CPython version and reaches 67--100% of mypyc-compiled CPython
throughput.

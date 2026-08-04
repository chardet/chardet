Frequently Asked Questions
==========================

Why does detect() return None for encoding?
--------------------------------------------

chardet returns ``None`` when the data appears to be binary rather than
text. This happens when the data contains null bytes or a high proportion
of control characters that don't match any known text encoding.

.. code-block:: python

   result = chardet.detect(b"\x00\x01\x02\x03")
   # {'encoding': None, 'confidence': 0.95, 'language': None, 'mime_type': 'application/octet-stream'}

How do I increase accuracy?
----------------------------

- **Provide more data.** The default limit of 200,000 bytes is generous
  and most detections converge well within that.  If you are passing very
  short strings (under a few hundred bytes), providing more data may help.
- **Restrict the encoding era.** By default, chardet considers all
  supported encodings. If you know your data only uses modern web
  encodings, pass ``encoding_era=EncodingEra.MODERN_WEB`` to narrow the
  candidate set and reduce false positives.
- **Use detect_all().** If the top result is wrong, the correct encoding
  may be the second candidate. :func:`chardet.detect_all` returns all
  candidates ranked by confidence.
- **Use encoding filters.** If you know exactly which encodings are
  possible, pass ``include_encodings`` to restrict the candidate set.
  Alternatively, use ``exclude_encodings`` to remove known false positives.

How is chardet different from charset-normalizer?
--------------------------------------------------

`charset-normalizer <https://github.com/jawah/charset_normalizer>`_ is
an alternative encoding detector. Key differences:

- **Accuracy:** chardet achieves 99.3% vs charset-normalizer's 85.4% on
  the same test suite.
- **Speed:** 2.6x faster overall with mypyc (2,698 vs 1,024 files/s),
  and faster across the latency distribution on our test suite:
  3.5x at the median (0.16 vs 0.56ms), 3.4x at p95, 3.3x at p99.
  Legacy CJK multi-byte encodings are the one subset where
  charset-normalizer keeps a flatter tail (p99 1.58 vs our 5.00ms) ---
  a difference of a few milliseconds at worst. See :doc:`performance`.
- **Accuracy convention:** our 99.3% credits supersets (Windows-1252 for
  ISO-8859-1); scored on exact matches only it is 84.4% against
  charset-normalizer's 75.9%. Both columns are published.
- **Memory:** chardet uses 2.6x less peak memory (27.4 vs 69.9 MiB) and
  1.8x less RSS. Per ``detect()`` call the ordering reverses ---
  charset-normalizer allocates 57 KiB at the median against chardet's
  530 KiB, but its p99 grows 7x while chardet's stays flat. See
  :doc:`performance` for the full distribution.
- **Language detection:** chardet detects language with 95.7% accuracy vs
  charset-normalizer's 59.2%.

How is chardet different from cchardet?
----------------------------------------

`cchardet <https://github.com/faust-streaming/faust-cchardet>`_ wraps
Mozilla's uchardet C/C++ library. Key differences:

- **Accuracy:** chardet achieves 99.3% vs cchardet's 55.9%.
- **Speed:** tied in aggregate (0.93s for either across 2,517 files),
  though cchardet has the faster median (0.03 vs 0.16ms) and chardet
  the far better worst case (11ms vs 354ms).
- **Encoding breadth:** chardet supports 49 more encodings than cchardet,
  including EBCDIC, Mac, Baltic, and BOM-less UTF-16/32.
- **Dependencies:** chardet is pure Python with zero dependencies.
  cchardet requires a C compiler to build from source.

Is chardet thread-safe?
-------------------------

:func:`chardet.detect` and :func:`chardet.detect_all` are fully
thread-safe and can be called concurrently from any number of threads.

:class:`~chardet.UniversalDetector` instances are **not** thread-safe.
Create one instance per thread when using the streaming API.

``UniversalDetector`` uses the same detection pipeline as ``detect()``
and ``detect_all()``, so results are identical regardless of which API
you use.

Does chardet work on PyPy?
---------------------------

Yes. chardet is pure Python and works on PyPy without modification.
The optional mypyc compilation is CPython-only; PyPy uses the pure-Python
code path automatically.

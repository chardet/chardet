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
- **Pass prefer_superset=True when decoding.** Detection examines at most
  the first 200 KB, and only a superset encoding is guaranteed to decode
  bytes beyond that window; the remap makes the result decode-safe.  The
  default (``False``) skips the renaming and reports the detected
  encoding under its own name --- note it is not a promise of the
  *smallest* matching encoding, since detection may natively choose a
  superset that fits the data better.  ``prefer_superset=True`` will
  become the default in chardet 8.0.

How is chardet different from charset-normalizer?
--------------------------------------------------

`charset-normalizer <https://github.com/jawah/charset_normalizer>`_ is
an alternative encoding detector. Key differences:

- **Accuracy:** chardet achieves 99.3% vs charset-normalizer's 85.4% on
  the same test suite.
- **Speed:** 2.6x faster overall with mypyc (2,724 vs 1,051 files/s),
  and 3.4x faster across the latency distribution on our test suite:
  at the median (0.16 vs 0.54ms), at p95, and at p99.
  Legacy CJK multi-byte encodings are the one subset where
  charset-normalizer keeps a flatter tail (p99 1.59 vs our 4.72ms) ---
  a difference of a few milliseconds at worst. See :doc:`performance`.
- **Accuracy convention:** our 99.3% credits supersets (Windows-1252 for
  ISO-8859-1); scored on exact matches only it is 84.4% against
  charset-normalizer's 75.9%. Both columns are published, but we
  consider the superset the correct answer: detection reads at most the
  first 200 KB, and only the superset is guaranteed to decode the rest
  of the file --- the same reasoning behind the WHATWG/W3C Encoding
  Standard's rule that browsers decode ``ascii`` and ``iso-8859-1``
  content as ``windows-1252``. The strict gap is the convention, not
  the detector: with superset remapping disabled chardet scores 91.9%
  strict, still ahead of charset-normalizer. See :doc:`performance`.
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

- **Accuracy:** chardet achieves 99.3% vs cchardet's 56.1%.
- **Speed:** cchardet 3.1.0 is 1.7x faster in aggregate (0.54s vs
  0.92s across 2,517 files), but the two meet at the tail --- p99
  1.87ms vs our 1.85ms --- and chardet's worst case is lower
  (11ms vs 25ms).
- **Memory:** chardet's peak footprint is 2.3x smaller (27.4 vs
  64.0 MiB traced) with lower RSS (125 vs 153 MiB).
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

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

- **Accuracy:** chardet achieves 99.7% vs charset-normalizer's 86.6% on
  the same test suite.
- **Speed:** mixed, and it changed with charset-normalizer 3.5.0, which
  roughly halved its own latency. chardet is 1.6x faster at the median
  (0.19 vs 0.31ms) and level through the body of the distribution, but
  charset-normalizer is 2.0x faster at p99 (2.63 vs our 5.24ms) and
  slightly ahead in aggregate (2,157 vs 1,998 files/s). chardet's worst
  case is 2.4x lower (13.7 vs 33.3ms). The tail gap is concentrated in
  legacy CJK, where their p99 is 1.48ms against our 9.00ms. See
  :doc:`performance`.
- **Accuracy convention:** our 99.7% credits supersets (Windows-1252 for
  ISO-8859-1); scored on exact matches only it is 82.4% against
  charset-normalizer's 78.4%. Both columns are published, but we
  consider the superset the correct answer: detection reads at most the
  first 200 KB, and only the superset is guaranteed to decode the rest
  of the file --- the same reasoning behind the WHATWG/W3C Encoding
  Standard's rule that browsers decode ``ascii`` and ``iso-8859-1``
  content as ``windows-1252``. The strict gap is the convention, not
  the detector: with superset remapping disabled
  (``prefer_superset=False``) chardet scores 92.1% strict, still ahead
  of charset-normalizer. See :doc:`performance`.
- **Memory:** chardet uses 2.6x less peak memory (27.6 vs 71.7 MiB) and
  1.7x less RSS. Per ``detect()`` call the ordering reverses ---
  charset-normalizer allocates 58 KiB at the median against chardet's
  532 KiB, but its p99 grows 14x to 785 KiB while chardet's stays flat
  at 690 KiB. See :doc:`performance` for the full distribution.
- **Language detection:** chardet detects language with 91.8% accuracy vs
  charset-normalizer's 54.6%.

How is chardet different from cchardet?
----------------------------------------

`cchardet <https://github.com/faust-streaming/faust-cchardet>`_ wraps
Mozilla's uchardet C/C++ library. Key differences:

- **Accuracy:** chardet achieves 99.7% vs cchardet's 60.1%.
- **Speed:** cchardet 3.2.0 is 2.0x faster in aggregate (0.77s vs
  1.56s across 3,121 files) and holds the better tail (p99 2.10ms vs
  our 5.24ms), but chardet's worst case is 1.8x lower (13.7 vs 25.2ms).
- **Memory:** chardet's peak footprint is 2.3x smaller (27.6 vs
  64.5 MiB traced) with lower RSS (159 vs 186 MiB).
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

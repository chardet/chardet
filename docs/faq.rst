Frequently Asked Questions
==========================

Why does detect() return None for encoding?
--------------------------------------------

chardet returns ``None`` when the data appears to be binary rather than
text. This happens when the data contains null bytes or a high proportion
of control characters that don't match any known text encoding.

.. code-block:: python

   result = chardet.detect(b"\x00\x01\x02\x03")
   # {'encoding': None, 'confidence': 0.95, 'language': None}

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

How is chardet different from charset-normalizer?
--------------------------------------------------

`charset-normalizer <https://github.com/jawah/charset_normalizer>`_ is
an alternative encoding detector. Key differences:

- **Accuracy:** chardet achieves 98.2% vs charset-normalizer's 84.2% on
  the same test suite.
- **Speed:** chardet is 4.3x faster with mypyc (555 vs 130 files/s),
  5.5x faster pure Python (370 vs 67 files/s).
- **Memory:** chardet uses 3.9x less peak memory (26.2 vs 101.2 MiB).
- **Language detection:** chardet detects language with 95.1% accuracy vs
  charset-normalizer's 59.0%.

How is chardet different from cchardet?
----------------------------------------

`cchardet <https://github.com/faust-streaming/faust-cchardet>`_ wraps
Mozilla's uchardet C/C++ library. Key differences:

- **Accuracy:** chardet achieves 98.2% vs cchardet's 56.0%.
- **Speed:** cchardet is faster (1.4s vs 4.5s) due to C implementation.
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

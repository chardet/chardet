Usage
=====

Installation
------------

.. code-block:: bash

   pip install chardet

Basic Detection
---------------

Use :func:`chardet.detect` to detect the encoding of a byte string:

.. code-block:: python

   import chardet

   result = chardet.detect(
       "München ist die Hauptstadt Bayerns und eine der"
       " schönsten Städte Deutschlands.".encode("windows-1252")
   )
   print(result)
   # {'encoding': 'Windows-1252', 'confidence': 0.34, 'language': 'de', 'mime_type': 'text/plain'}

The result is a dictionary with four keys:

- ``"encoding"`` — the detected encoding name (e.g., ``"utf-8"``,
  ``"Windows-1252"``), or ``None`` for binary data
- ``"confidence"`` — a float between 0 and 1
- ``"language"`` — the detected language as an ISO 639-1 code (e.g.,
  ``"fr"``), or ``None``
- ``"mime_type"`` — ``"text/plain"`` for text, a format MIME type such
  as ``"image/png"`` for binary files recognized by their magic number
  signature, and ``"application/octet-stream"`` for other binary data.
  Markup gets ``"text/html"``, ``"text/xml"``, or ``"text/x-python"``.

Multiple Candidates
~~~~~~~~~~~~~~~~~~~

Use :func:`chardet.detect_all` to get all candidate encodings ranked by
confidence:

.. code-block:: python

   results = chardet.detect_all(data)
   for r in results:
       print(f"{r['encoding']}: {r['confidence']:.2f}")

By default, results at or below the minimum confidence threshold (0.20)
are filtered out; if no result clears it, the full list is returned so
there is always at least one. Pass ``ignore_threshold=True`` to see all
candidates. With ``prefer_superset=True`` two candidates can map to one
name (ISO-8859-7 and Windows-1253 both become Windows-1253); only the
higher-confidence one is listed.

Streaming Detection
-------------------

For large files or streaming data, use :class:`chardet.UniversalDetector`:

.. code-block:: python

   from chardet import UniversalDetector

   detector = UniversalDetector()
   with open("somefile.txt", "rb") as f:
       for line in f:
           detector.feed(line)
           if detector.done:
               break
   detector.close()
   print(detector.result)

Call :meth:`~chardet.UniversalDetector.reset` to reuse the detector for
another file.

The constructor accepts the same tuning parameters as :func:`~chardet.detect`:

.. code-block:: python

   detector = UniversalDetector(
       encoding_era=EncodingEra.MODERN_WEB,  # restrict candidate encodings
       max_bytes=50_000,                      # stop buffering after 50 KB
   )

Encoding Eras
-------------

By default, chardet considers all supported encodings for maximum
accuracy. Use the ``encoding_era`` parameter to restrict the search to a
specific subset:

.. code-block:: python

   from chardet import detect, EncodingEra

   # Default: all encodings considered
   result = detect(data)

   # Restrict to modern web encodings only
   result = detect(data, encoding_era=EncodingEra.MODERN_WEB)

   # Only legacy ISO encodings
   result = detect(data, encoding_era=EncodingEra.LEGACY_ISO)

Available eras (can be combined with ``|``):

- :attr:`~chardet.EncodingEra.ALL` — All supported encodings (default)
- :attr:`~chardet.EncodingEra.MODERN_WEB` — UTF-8, Windows codepages,
  CJK encodings
- :attr:`~chardet.EncodingEra.LEGACY_ISO` — ISO-8859 family
- :attr:`~chardet.EncodingEra.LEGACY_MAC` — Mac encodings
- :attr:`~chardet.EncodingEra.LEGACY_REGIONAL` — Regional codepages
  (KOI8-T, KZ-1048, etc.) plus UTF-7, HZ-GB-2312, and ISO-2022-KR
- :attr:`~chardet.EncodingEra.DOS` — DOS codepages (CP437, CP850, etc.)
- :attr:`~chardet.EncodingEra.MAINFRAME` — EBCDIC encodings

Encoding Name Options
---------------------

By default, chardet returns encoding names compatible with chardet 5.x/6.x
(e.g., ``"utf-8"``, ``"ascii"``, ``"SHIFT_JIS"``).  Two parameters control
how encoding names are returned:

- ``compat_names`` (default ``True``) — map internal Python codec names to
  chardet 5.x/6.x compatible display names.  Set to ``False`` to get raw
  Python codec names (e.g., ``"shift_jis_2004"`` instead of ``"SHIFT_JIS"``).
- ``prefer_superset`` (default ``False``) — remap legacy ISO/subset encodings
  to their modern Windows/CP superset equivalents (e.g., ASCII →
  Windows-1252, ISO-8859-1 → Windows-1252).  The remap is skipped when
  the superset cannot decode the examined bytes, or when
  ``include_encodings``/``exclude_encodings`` or ``encoding_era`` rule the
  superset out; the detected name is kept in those cases.

.. code-block:: python

   # Default: chardet 5.x compatible names
   chardet.detect(data)
   # {'encoding': 'ascii', ...}

   # Raw Python codec names
   chardet.detect(data, compat_names=False)
   # {'encoding': 'ascii', ...}

   # Superset remapping with compat names
   chardet.detect(data, prefer_superset=True)
   # {'encoding': 'Windows-1252', ...}

   # Superset remapping with raw codec names
   chardet.detect(data, prefer_superset=True, compat_names=False)
   # {'encoding': 'cp1252', ...}

These parameters apply to :func:`~chardet.detect`, :func:`~chardet.detect_all`,
and :class:`~chardet.UniversalDetector`.

The deprecated ``should_rename_legacy=True`` parameter is equivalent to
``prefer_superset=True`` and is still accepted with a deprecation warning.

The following table shows every encoding whose name changes depending on
the ``compat_names`` and ``prefer_superset`` settings.  Encodings not listed
here return the same name in all modes.  The four rows marked with an
asterisk (``Big5``, ``EUC-JP``, ``ISO-2022-JP``, ``SHIFT_JIS``) name a
narrower codec than the internal one; the display name is used only when
that codec decodes the examined data, and the internal name is reported
otherwise.

.. list-table:: Encoding names by parameter combination
   :header-rows: 1
   :widths: 20 20 20 20 20

   * - Internal name
     - ``compat_names=True`` (default)
     - ``compat_names=False``
     - ``prefer_superset=True``
     - ``prefer_superset=True, compat_names=False``
   * - ascii
     - ``ascii``
     - ``ascii``
     - ``Windows-1252``
     - ``cp1252``
   * - big5hkscs
     - ``Big5`` :sup:`*`
     - ``big5hkscs``
     - ``Big5`` :sup:`*`
     - ``big5hkscs``
   * - cp1250
     - ``Windows-1250``
     - ``cp1250``
     - ``Windows-1250``
     - ``cp1250``
   * - cp1251
     - ``Windows-1251``
     - ``cp1251``
     - ``Windows-1251``
     - ``cp1251``
   * - cp1252
     - ``Windows-1252``
     - ``cp1252``
     - ``Windows-1252``
     - ``cp1252``
   * - cp1253
     - ``Windows-1253``
     - ``cp1253``
     - ``Windows-1253``
     - ``cp1253``
   * - cp1254
     - ``Windows-1254``
     - ``cp1254``
     - ``Windows-1254``
     - ``cp1254``
   * - cp1255
     - ``Windows-1255``
     - ``cp1255``
     - ``Windows-1255``
     - ``cp1255``
   * - cp1256
     - ``Windows-1256``
     - ``cp1256``
     - ``Windows-1256``
     - ``cp1256``
   * - cp1257
     - ``Windows-1257``
     - ``cp1257``
     - ``Windows-1257``
     - ``cp1257``
   * - cp855
     - ``IBM855``
     - ``cp855``
     - ``IBM855``
     - ``cp855``
   * - cp866
     - ``IBM866``
     - ``cp866``
     - ``IBM866``
     - ``cp866``
   * - cp874
     - ``CP874``
     - ``cp874``
     - ``CP874``
     - ``cp874``
   * - cp932
     - ``CP932``
     - ``cp932``
     - ``CP932``
     - ``cp932``
   * - cp949
     - ``CP949``
     - ``cp949``
     - ``CP949``
     - ``cp949``
   * - euc_jis_2004
     - ``EUC-JP`` :sup:`*`
     - ``euc_jis_2004``
     - ``EUC-JP`` :sup:`*`
     - ``euc_jis_2004``
   * - euc_kr
     - ``EUC-KR``
     - ``euc_kr``
     - ``CP949``
     - ``cp949``
   * - gb18030
     - ``GB18030``
     - ``gb18030``
     - ``GB18030``
     - ``gb18030``
   * - hz
     - ``HZ-GB-2312``
     - ``hz``
     - ``HZ-GB-2312``
     - ``hz``
   * - iso2022_jp_2
     - ``ISO-2022-JP`` :sup:`*`
     - ``iso2022_jp_2``
     - ``ISO-2022-JP`` :sup:`*`
     - ``iso2022_jp_2``
   * - iso2022_kr
     - ``ISO-2022-KR``
     - ``iso2022_kr``
     - ``ISO-2022-KR``
     - ``iso2022_kr``
   * - iso8859-1
     - ``ISO-8859-1``
     - ``iso8859-1``
     - ``Windows-1252``
     - ``cp1252``
   * - iso8859-13
     - ``ISO-8859-13``
     - ``iso8859-13``
     - ``Windows-1257``
     - ``cp1257``
   * - iso8859-2
     - ``ISO-8859-2``
     - ``iso8859-2``
     - ``Windows-1250``
     - ``cp1250``
   * - iso8859-5
     - ``ISO-8859-5``
     - ``iso8859-5``
     - ``Windows-1251``
     - ``cp1251``
   * - iso8859-6
     - ``ISO-8859-6``
     - ``iso8859-6``
     - ``Windows-1256``
     - ``cp1256``
   * - iso8859-7
     - ``ISO-8859-7``
     - ``iso8859-7``
     - ``Windows-1253``
     - ``cp1253``
   * - iso8859-8
     - ``ISO-8859-8``
     - ``iso8859-8``
     - ``Windows-1255``
     - ``cp1255``
   * - iso8859-9
     - ``ISO-8859-9``
     - ``iso8859-9``
     - ``Windows-1254``
     - ``cp1254``
   * - johab
     - ``Johab``
     - ``johab``
     - ``Johab``
     - ``johab``
   * - koi8-r
     - ``KOI8-R``
     - ``koi8-r``
     - ``KOI8-R``
     - ``koi8-r``
   * - kz1048
     - ``KZ1048``
     - ``kz1048``
     - ``KZ1048``
     - ``kz1048``
   * - mac-cyrillic
     - ``MacCyrillic``
     - ``mac-cyrillic``
     - ``MacCyrillic``
     - ``mac-cyrillic``
   * - mac-greek
     - ``MacGreek``
     - ``mac-greek``
     - ``MacGreek``
     - ``mac-greek``
   * - mac-iceland
     - ``MacIceland``
     - ``mac-iceland``
     - ``MacIceland``
     - ``mac-iceland``
   * - mac-latin2
     - ``MacLatin2``
     - ``mac-latin2``
     - ``MacLatin2``
     - ``mac-latin2``
   * - mac-roman
     - ``MacRoman``
     - ``mac-roman``
     - ``MacRoman``
     - ``mac-roman``
   * - mac-turkish
     - ``MacTurkish``
     - ``mac-turkish``
     - ``MacTurkish``
     - ``mac-turkish``
   * - shift_jis_2004
     - ``SHIFT_JIS`` :sup:`*`
     - ``shift_jis_2004``
     - ``SHIFT_JIS`` :sup:`*`
     - ``shift_jis_2004``
   * - tis-620
     - ``TIS-620``
     - ``tis-620``
     - ``CP874``
     - ``cp874``
   * - utf-16
     - ``UTF-16``
     - ``utf-16``
     - ``UTF-16``
     - ``utf-16``
   * - utf-32
     - ``UTF-32``
     - ``utf-32``
     - ``UTF-32``
     - ``utf-32``
   * - utf-8-sig
     - ``UTF-8-SIG``
     - ``utf-8-sig``
     - ``UTF-8-SIG``
     - ``utf-8-sig``

Encoding Filters
----------------

Use ``include_encodings`` and ``exclude_encodings`` to control exactly which
encodings chardet considers:

.. code-block:: python

   # Only consider UTF-8 and Windows-1252
   result = chardet.detect(data, include_encodings=["utf-8", "windows-1252"])

   # Drop two EBCDIC code pages (for all of them, use
   # encoding_era=EncodingEra.ALL & ~EncodingEra.MAINFRAME)
   result = chardet.detect(data, exclude_encodings=["cp037", "cp500"])

Encoding names are resolved through Python's codec system, so aliases work
(e.g., ``"latin-1"`` for ``"iso8859-1"``).  An empty iterable raises
:class:`ValueError` — pass ``None`` (the default) to disable filtering.

When filtering removes all candidates, chardet returns the
``no_match_encoding`` (default ``"cp1252"``) with confidence 0.10.  That
answer is the caller's sentinel for "nothing fit", so it is the one
result chardet does not check against the data: with
``include_encodings=["utf-8", "windows-1252"]`` and a file that holds
0x81, which neither decodes, the result is still Windows-1252 at 0.10,
and decoding it strictly will raise.  Treat a 0.10 result under a filter
as a miss rather than a detection.  The name is canonicalized and
display-renamed like any other result, so ``no_match_encoding="latin-1"``
reports ``ISO-8859-1``.  If even that encoding is excluded by the
filters, chardet returns ``encoding=None`` with a warning.  Similarly,
``empty_input_encoding``
(default ``"utf-8"``) controls the result for empty input:

.. code-block:: python

   # Custom fallbacks
   result = chardet.detect(
       data,
       include_encodings=["utf-8", "shift_jis"],
       no_match_encoding="utf-8",
       empty_input_encoding="shift_jis",
   )

These parameters apply to :func:`~chardet.detect`,
:func:`~chardet.detect_all`, and :class:`~chardet.UniversalDetector`.

Limiting Bytes
--------------

By default, chardet examines up to 200,000 bytes. Use ``max_bytes`` to
adjust:

.. code-block:: python

   # Examine only the first 10 KB
   result = chardet.detect(data, max_bytes=10_000)

Smaller values are faster but may reduce accuracy for encodings that
require more data to distinguish.

Deprecated Parameters
---------------------

The following parameters are accepted for backward compatibility with
chardet 5.x/6.x but have no effect:

- ``chunk_size`` on :func:`~chardet.detect` and
  :func:`~chardet.detect_all` — previously controlled how data was
  chunked for streaming probers. A deprecation warning is emitted if a
  non-default value is passed.
- ``lang_filter`` on :class:`~chardet.UniversalDetector` — previously
  restricted detection to specific language groups via
  :class:`~chardet.LanguageFilter`. A deprecation warning is emitted if
  set to anything other than :attr:`~chardet.LanguageFilter.ALL`.

Command-Line Tool
-----------------

chardet includes a ``chardetect`` command:

.. code-block:: bash

   # Detect encoding of files
   chardetect somefile.txt anotherfile.csv
   # somefile.txt: utf-8 with confidence 0.99
   # anotherfile.csv: ascii with confidence 1.0

   # Output only the encoding name
   chardetect --minimal somefile.txt
   # utf-8

   # Include detected language
   chardetect -l somefile.txt
   # somefile.txt: utf-8 en (English) with confidence 0.99

   # Minimal output with language
   chardetect --minimal -l somefile.txt
   # utf-8 en

   # Include detected MIME type (similar to file -i)
   chardetect -m somefile.txt somepic.png
   # somefile.txt: utf-8 text/plain with confidence 0.99
   # somepic.png: None image/png with confidence 1.0

   # Minimal output with MIME type
   chardetect --minimal -m somefile.txt
   # utf-8 text/plain

   # Specific encoding era
   chardetect -e dos somefile.txt
   # somefile.txt: cp850 with confidence 0.31

   # Only consider specific encodings
   chardetect -i utf-8,windows-1252 somefile.txt
   # somefile.txt: utf-8 with confidence 0.99

   # Exclude specific encodings
   chardetect -x cp037,cp500 somefile.txt
   # somefile.txt: utf-8 with confidence 0.99

   # Custom fallback when every candidate is ruled out
   chardetect -i utf-8,shift_jis --no-match-encoding utf-8 somefile.txt
   # somefile.txt: utf-8 with confidence 0.10

   # Custom encoding for empty input
   chardetect --empty-input-encoding shift_jis empty.txt
   # empty.txt: SHIFT_JIS with confidence 0.10

   # Report subset encodings under their Windows/CP superset
   chardetect --prefer-superset greek.txt
   # greek.txt: Windows-1253 with confidence 0.3848680620156556

   # Report raw Python codec names
   chardetect --no-compat-names japanese.txt
   # japanese.txt: euc_jis_2004 with confidence 0.770844139781662

   # Read from stdin
   cat somefile.txt | chardetect
   # stdin: utf-8 with confidence 0.99

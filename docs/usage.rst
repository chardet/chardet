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
   # {'encoding': 'windows-1252', 'confidence': 0.34, 'language': 'de'}

The result is a dictionary with three keys:

- ``"encoding"`` — the detected encoding name (e.g., ``"utf-8"``,
  ``"windows-1252"``), or ``None`` if detection failed
- ``"confidence"`` — a float between 0 and 1
- ``"language"`` — the detected language (e.g., ``"French"``), or ``None``

Multiple Candidates
~~~~~~~~~~~~~~~~~~~

Use :func:`chardet.detect_all` to get all candidate encodings ranked by
confidence:

.. code-block:: python

   results = chardet.detect_all(data)
   for r in results:
       print(f"{r['encoding']}: {r['confidence']:.2f}")

By default, results below the minimum confidence threshold (0.20) are
filtered out. Pass ``ignore_threshold=True`` to see all candidates.

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
  (KOI8-T, KZ-1048, etc.)
- :attr:`~chardet.EncodingEra.DOS` — DOS codepages (CP437, CP850, etc.)
- :attr:`~chardet.EncodingEra.MAINFRAME` — EBCDIC encodings

Legacy Renaming
---------------

By default, chardet returns encoding names compatible with chardet 5.x/6.x
(e.g., ``"utf-8"``, ``"ascii"``, ``"SHIFT_JIS"``).  Set
``should_rename_legacy=True`` to get canonical display-cased names and remap
legacy ISO encodings to their modern Windows superset equivalents:

.. code-block:: python

   # Default: chardet 5.x compatible names
   chardet.detect(data)
   # {'encoding': 'ascii', ...}

   # Enable modern naming + superset remapping
   chardet.detect(data, should_rename_legacy=True)
   # {'encoding': 'Windows-1252', ...}

This applies to :func:`~chardet.detect`, :func:`~chardet.detect_all`,
and :class:`~chardet.UniversalDetector`.

The following table shows every encoding whose name changes depending on
the ``should_rename_legacy`` setting.  Encodings not listed here return the
same name in both modes.

.. list-table:: Encoding names by ``should_rename_legacy`` value
   :header-rows: 1
   :widths: 30 30 30

   * - Detected encoding
     - ``False`` (default)
     - ``True``
   * - ASCII
     - ``ascii``
     - ``Windows-1252``
   * - Big5-HKSCS
     - ``Big5``
     - ``Big5-HKSCS``
   * - CP855
     - ``IBM855``
     - ``CP855``
   * - CP866
     - ``IBM866``
     - ``CP866``
   * - EUC-JIS-2004
     - ``EUC-JP``
     - ``EUC-JIS-2004``
   * - EUC-KR
     - ``EUC-KR``
     - ``CP949``
   * - ISO-2022-JP-2
     - ``ISO-2022-JP``
     - ``ISO-2022-JP-2``
   * - ISO-8859-1
     - ``ISO-8859-1``
     - ``Windows-1252``
   * - ISO-8859-2
     - ``ISO-8859-2``
     - ``Windows-1250``
   * - ISO-8859-5
     - ``ISO-8859-5``
     - ``Windows-1251``
   * - ISO-8859-6
     - ``ISO-8859-6``
     - ``Windows-1256``
   * - ISO-8859-7
     - ``ISO-8859-7``
     - ``Windows-1253``
   * - ISO-8859-8
     - ``ISO-8859-8``
     - ``Windows-1255``
   * - ISO-8859-9
     - ``ISO-8859-9``
     - ``Windows-1254``
   * - ISO-8859-11
     - ``ISO-8859-11``
     - ``CP874``
   * - ISO-8859-13
     - ``ISO-8859-13``
     - ``Windows-1257``
   * - KZ-1048
     - ``KZ1048``
     - ``KZ-1048``
   * - Mac-Cyrillic
     - ``MacCyrillic``
     - ``Mac-Cyrillic``
   * - Mac-Greek
     - ``MacGreek``
     - ``Mac-Greek``
   * - Mac-Iceland
     - ``MacIceland``
     - ``Mac-Iceland``
   * - Mac-Latin2
     - ``MacLatin2``
     - ``Mac-Latin2``
   * - Mac-Roman
     - ``MacRoman``
     - ``Mac-Roman``
   * - Mac-Turkish
     - ``MacTurkish``
     - ``Mac-Turkish``
   * - Shift-JIS-2004
     - ``SHIFT_JIS``
     - ``Shift-JIS-2004``
   * - TIS-620
     - ``TIS-620``
     - ``CP874``
   * - UTF-8
     - ``utf-8``
     - ``UTF-8``

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

   # Output only the encoding name
   chardetect --minimal somefile.txt

   # Specific encoding era
   chardetect -e dos somefile.txt

   # Read from stdin
   cat somefile.txt | chardetect

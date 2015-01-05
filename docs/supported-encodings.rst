`Universal Encoding Detector </>`__
===================================

Character encoding auto-detection in Python. As smart as your browser.
Open source.

-  `Download <http://chardet.feedparser.org/download/>`__ ·
-  `Documentation <index.html>`__ ·
-  `FAQ <faq.html>`__

You are here: `Documentation <index.html>`__ → Supported encodings

|[link]| Supported encodings
----------------------------

Universal Encoding Detector currently supports over two dozen character
encodings.

-  ``Big5``, ``GB2312``/``GB18030``, ``EUC-TW``, ``HZ-GB-2312``, and
   ``ISO-2022-CN`` (Traditional and Simplified Chinese)
-  ``EUC-JP``, ``SHIFT_JIS``, and ``ISO-2022-JP`` (Japanese)
-  ``EUC-KR`` and ``ISO-2022-KR`` (Korean)
-  ``KOI8-R``, ``MacCyrillic``, ``IBM855``, ``IBM866``, ``ISO-8859-5``,
   and ``windows-1251`` (Russian)
-  ``ISO-8859-2`` and ``windows-1250`` (Hungarian)
-  ``ISO-8859-5`` and ``windows-1251`` (Bulgarian)
-  ``windows-1252``
-  ``ISO-8859-7`` and ``windows-1253`` (Greek)
-  ``ISO-8859-8`` and ``windows-1255`` (Visual and Logical Hebrew)
-  ``TIS-620`` (Thai)
-  ``UTF-32`` BE, LE, 3412-ordered, or 2143-ordered (with a BOM)
-  ``UTF-16`` BE or LE (with a BOM)
-  ``UTF-8`` (with or without a BOM)
-  ASCII

+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| |Caution|                                                                                                                                                                                                                                                                                                                                                             |
+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Due to inherent similarities between certain encodings, some encodings may be detected incorrectly. In my tests, the most problematic case was Hungarian text encoded as ``ISO-8859-2`` or ``windows-1250`` (encoded as one but reported as the other). Also, Greek text encoded as ``ISO-8859-7`` was often mis-reported as ``ISO-8859-2``. Your mileage may vary.   |
+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

← \ `Frequently asked questions <faq.html>`__

`Usage <usage.html>`__ →

--------------

Copyright © 2006, 2007, 2008 Mark Pilgrim ·
`mark@diveintomark.org <mailto:mark@diveintomark.org>`__ · `Terms of
use <license.html>`__

.. |[link]| image:: images/permalink.gif
   :target: #encodings
.. |Caution| image:: images/caution.png

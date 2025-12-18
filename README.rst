Chardet: The Universal Character Encoding Detector
--------------------------------------------------

.. image:: https://img.shields.io/travis/chardet/chardet/stable.svg
   :alt: Build status
   :target: https://travis-ci.org/chardet/chardet

.. image:: https://img.shields.io/coveralls/chardet/chardet/stable.svg
   :target: https://coveralls.io/r/chardet/chardet

.. image:: https://img.shields.io/pypi/v/chardet.svg
   :target: https://warehouse.python.org/project/chardet/
   :alt: Latest version on PyPI

.. image:: https://img.shields.io/pypi/l/chardet.svg
   :alt: License


Detects

 - ``ASCII``
 - ``Big5`` (Traditional Chinese)
 - ``CP037``
 - ``CP424``
 - ``CP437``
 - ``CP500``
 - ``CP720`` (Arabic)
 - ``CP737`` (Greek)
 - ``CP775`` (Estonian, Latvian, Lithuanian)
 - ``CP850`` (Dutch, English, Finnish, French, German, Italian, Portuguese, Spanish)
 - ``CP852`` (Croatian, Czech, Hungarian, Polish, Romanian, Slovak, Slovene)
 - ``CP855``/``IBM855`` (Bulgarian, Macedonian, Russian, Serbian)
 - ``CP856``/``IBM856`` (Hebrew)
 - ``CP857`` (Turkish)
 - ``CP858`` (Dutch, English, Finnish, French, German, Italian, Portuguese, Spanish)
 - ``CP860`` (Portuguese)
 - ``CP861`` (Icelandic)
 - ``CP862`` (Hebrew)
 - ``CP863`` (French)
 - ``CP864`` (Arabic)
 - ``CP865`` (Nordic)
 - ``CP866``/``IBM866`` (Belarusian, Russian)
 - ``CP874`` (Thai)
 - ``CP875`` (Greek)
 - ``CP932`` (Japanese)
 - ``CP949`` (Korean)
 - ``EUC-JP`` (Japanese)
 - ``EUC-KR`` (Korean)
 - ``GB18030`` (Unified Chinese)
 - ``HZ-GB-2312`` (Simplified Chinese)
 - ``ISO-2022-JP`` (Japanese)
 - ``ISO-2022-KR`` (Korean)
 - ``ISO-8859-1`` (Dutch, English, Finnish, French, German, Italian, Portuguese, Spanish)
 - ``ISO-8859-2`` (Croatian, Czech, Hungarian, Polish, Romanian, Slovak, Slovene)
 - ``ISO-8859-3`` (Esperanto)
 - ``ISO-8859-4`` (Estonian, Latvian, Lithuanian)
 - ``ISO-8859-5`` (Belarusian, Bulgarian, Macedonian, Russian, Serbian)
 - ``ISO-8859-6`` (Arabic)
 - ``ISO-8859-7`` (Greek)
 - ``ISO-8859-8`` (Visual and Logical Hebrew)
 - ``ISO-8859-9`` (Turkish)
 - ``ISO-8859-11`` (Thai)
 - ``ISO-8859-13`` (Estonian, Latvian, Lithuanian)
 - ``ISO-8859-15`` (Danish, Finnish, French, Italian, Portuguese, Spanish)
 - ``Johab`` (Korean)
 - ``KOI8-R`` (Russian)
 - ``KOI8-U`` (Ukrainian)
 - ``KOI8-T`` (Turkish)
 - ``KZ1048`` (Kazakh)
 - ``MacCyrillic`` (Belarusian, Macedonian, Russian, Serbian)
 - ``MacGreek`` (Greek)
 - ``MacIceland`` (Icelandic)
 - ``MacLatin2`` (Croatian, Czech, Hungarian, Polish, Romanian, Slovak, Slovene)
 - ``MacRoman`` (Dutch, English, Finnish, French, German, Italian, Portuguese, Spanish)
 - ``MacTurkish`` (Turkish)
 - ``PTCP154`` (Kazakh)
 - ``SHIFT_JIS`` (Japanese)
 - ``TIS-620`` (Thai)
 - ``UTF-8``
 - ``UTF-16`` (3 variants)
 - ``UTF-32`` (3 variants)
 - ``Windows-1250`` (Croatian, Czech, Hungarian, Polish, Romanian, Slovak, Slovene)
 - ``Windows-1251`` (Belarusian, Bulgarian, Macedonian, Russian, Serbian)
 - ``Windows-1252`` (Dutch, English, Finnish, French, German, Italian, Portuguese, Spanish)
 - ``Windows-1253`` (Greek)
 - ``Windows-1254`` (Turkish)
 - ``Windows-1255`` (Visual and Logical Hebrew)
 - ``Windows-1256`` (Arabic)
 - ``Windows-1257`` (Estonian, Latvian, Lithuanian)
 - ``Windows-1258`` (Vietnamese)


Requires Python 3.10+.

Installation
------------

Install from `PyPI <https://pypi.org/project/chardet/>`_::

    pip install chardet

Documentation
-------------

For users, docs are now available at https://chardet.readthedocs.io/.

Command-line Tool
-----------------

chardet comes with a command-line script which reports on the encodings of one
or more files::

    % chardetect somefile someotherfile
    somefile: windows-1252 with confidence 0.5
    someotherfile: ascii with confidence 1.0

About
-----

This is a continuation of Mark Pilgrim's excellent original chardet port from C, and `Ian Cordasco <https://github.com/sigmavirus24>`_'s
`charade <https://github.com/sigmavirus24/charade>`_ Python 3-compatible fork.

:maintainer: Dan Blanchard

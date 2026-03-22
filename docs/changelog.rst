Changelog
=========

7.3.0
-------------------

- **0BSD license** — the project license has been changed from MIT to
  `0BSD <https://opensource.org/license/0bsd>`_, a maximally permissive
  license with no attribution requirement. All prior 7.x releases are
  should also be considered 0BSD licensed as of this release.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

7.2.0 (2026-03-17)
-------------------

**Features:**

- Added ``include_encodings`` and ``exclude_encodings`` parameters to
  :func:`~chardet.detect`, :func:`~chardet.detect_all`, and
  :class:`~chardet.UniversalDetector` — restrict or exclude specific
  encodings from the candidate set, with corresponding
  ``-i``/``--include-encodings`` and ``-x``/``--exclude-encodings``
  CLI flags
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#343 <https://github.com/chardet/chardet/pull/343>`_)
- Added ``no_match_encoding`` (default ``"cp1252"``) and
  ``empty_input_encoding`` (default ``"utf-8"``) parameters — control
  which encoding is returned when no candidate survives the pipeline or
  the input is empty, with corresponding CLI flags
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#343 <https://github.com/chardet/chardet/pull/343>`_)
- Added ``-l``/``--language`` flag to ``chardetect`` CLI — shows the
  detected language (ISO 639-1 code and English name) alongside the encoding
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#342 <https://github.com/chardet/chardet/pull/342>`_)

7.1.0 (2026-03-11)
-------------------

**Features:**

- Added PEP 263 encoding declaration detection — ``# -*- coding: ... -*-``
  and ``# coding=...`` declarations on lines 1–2 of Python source files are
  now recognized with confidence 0.95
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#249 <https://github.com/chardet/chardet/issues/249>`_)
- Added ``chardet.universaldetector`` backward-compatibility stub so that
  ``from chardet.universaldetector import UniversalDetector`` works with a
  deprecation warning
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#341 <https://github.com/chardet/chardet/issues/341>`_)

**Fixes:**

- Fixed false UTF-7 detection of ASCII text containing ``++`` or ``+word``
  patterns
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#332 <https://github.com/chardet/chardet/issues/332>`_,
  `#335 <https://github.com/chardet/chardet/pull/335>`_)
- Fixed 0.5s startup cost on first ``detect()`` call — model norms are now
  computed during loading instead of lazily iterating 21M entries
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#333 <https://github.com/chardet/chardet/issues/333>`_,
  `#336 <https://github.com/chardet/chardet/pull/336>`_)
- Fixed undocumented encoding name changes between chardet 5.x and 7.0 —
  ``detect()`` now returns chardet 5.x-compatible names by default
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#338 <https://github.com/chardet/chardet/pull/338>`_)
- Improved ISO-2022-JP family detection — recognizes ESC sequences for
  ISO-2022-JP-2004 (JIS X 0213) and ISO-2022-JP-EXT (JIS X 0201 Kana)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed silent truncation of corrupt model data (``iter_unpack`` yielded
  fewer tuples instead of raising)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed incorrect date in LICENSE
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

**Performance:**

- 5.5x faster first-detect time (~0.42s → ~0.075s) by computing model
  norms as a side-product of ``load_models()``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- ~40% faster model parsing via ``struct.iter_unpack`` for bulk entry
  extraction (eliminates ~305K individual ``unpack`` calls)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

**New API parameters:**

- Added ``compat_names`` parameter (default ``True``) to
  :func:`~chardet.detect`, :func:`~chardet.detect_all`, and
  :class:`~chardet.UniversalDetector` — set to ``False`` to get raw Python
  codec names instead of chardet 5.x/6.x compatible display names
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Added ``prefer_superset`` parameter (default ``False``) — remaps legacy
  ISO/subset encodings to their modern Windows/CP superset equivalents
  (e.g., ASCII → Windows-1252, ISO-8859-1 → Windows-1252).
  **This will default to ``True`` in the next major version (8.0).**
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Deprecated ``should_rename_legacy`` in favor of ``prefer_superset`` —
  a deprecation warning is emitted when used
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

**Improvements:**

- Switched internal canonical encoding names to Python codec names
  (e.g., ``"utf-8"`` instead of ``"UTF-8"``), with ``compat_names``
  controlling the public output format.  See :doc:`usage` for the full
  mapping table.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Added ``lookup_encoding()`` to ``registry`` for case-insensitive
  resolution of arbitrary encoding name input to canonical names
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Achieved 100% line coverage across all source modules (+31 tests)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Updated benchmark numbers: 98.2% encoding accuracy, 95.2% language
  accuracy on 2,510 test files
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Pinned test-data cloning to chardet release version tags for
  reproducible builds
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

7.0.1 (2026-03-04)
-------------------

**Fixes:**

- Fixed false UTF-7 detection of SHA-1 git hashes
  (`Alex Rembish <https://github.com/rembish>`_,
  `#324 <https://github.com/chardet/chardet/pull/324>`_)
- Fixed ``_SINGLE_LANG_MAP`` missing aliases for single-language encoding
  lookup (e.g., ``big5`` → ``big5hkscs``)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed PyPy ``TypeError`` in UTF-7 codec handling
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

**Improvements:**

- Retrained bigram models — 24 previously failing test cases now pass
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Updated language equivalences for mutual intelligibility (Slovak/Czech,
  East Slavic + Bulgarian, Malay/Indonesian, Scandinavian languages)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

7.0.0 (2026-03-02)
-------------------

Ground-up, 0BSD-licensed rewrite of chardet
(`Dan Blanchard <https://github.com/dan-blanchard>`_,
`#322 <https://github.com/chardet/chardet/pull/322>`_). Same package name,
same public API — drop-in replacement for chardet 5.x/6.x.

**Highlights:**

- **0BSD license** (previous versions were LGPL)
- **96.8% accuracy** on 2,179 test files (+2.3pp vs chardet 6.0.0,
  +7.7pp vs charset-normalizer)
- **41x faster** than chardet 6.0.0 with mypyc (**28x** pure Python),
  **7.5x faster** than charset-normalizer
- **Language detection** for every result (90.5% accuracy across 49
  languages)
- **99 encodings** across six eras (MODERN_WEB, LEGACY_ISO, LEGACY_MAC,
  LEGACY_REGIONAL, DOS, MAINFRAME)
- **12-stage detection pipeline** — BOM, UTF-16/32 patterns, escape
  sequences, binary detection, markup charset, ASCII, UTF-8 validation,
  byte validity, CJK gating, structural probing, statistical scoring,
  post-processing
- **Bigram frequency models** trained on CulturaX multilingual corpus
  data for all supported language/encoding pairs
- **Optional mypyc compilation** — 1.49x additional speedup on CPython
- **Thread-safe** ``detect()`` and ``detect_all()`` with no measurable
  overhead; scales on free-threaded Python 3.13t+
- **Negligible import memory** (96 B)
- **Zero runtime dependencies**

**Breaking changes vs 6.0.0:**

- ``detect()`` and ``detect_all()`` now default to
  ``encoding_era=EncodingEra.ALL`` (6.0.0 defaulted to ``MODERN_WEB``)
- Internal architecture is completely different (probers replaced by
  pipeline stages). Only the public API is preserved.
- ``LanguageFilter`` is accepted but ignored (deprecation warning
  emitted)
- ``chunk_size`` is accepted but ignored (deprecation warning emitted)

6.0.0.post1 (2026-02-22)
-------------------------

- Fixed ``__version__`` not being set correctly in the package
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

6.0.0 (2026-02-22)
-------------------

**Features:**

- Unified single-byte charset detection with proper language-specific
  bigram models for all single-byte encodings (replaces ``Latin1Prober``
  and ``MacRomanProber`` heuristics)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- 38 new languages: Arabic, Belarusian, Breton, Croatian, Czech, Danish,
  Dutch, English, Esperanto, Estonian, Farsi, Finnish, French, German,
  Icelandic, Indonesian, Irish, Italian, Kazakh, Latvian, Lithuanian,
  Macedonian, Malay, Maltese, Norwegian, Polish, Portuguese, Romanian,
  Scottish Gaelic, Serbian, Slovak, Slovene, Spanish, Swedish, Tajik,
  Ukrainian, Vietnamese, Welsh
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- ``EncodingEra`` filtering via new ``encoding_era`` parameter
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- ``max_bytes`` and ``chunk_size`` parameters for ``detect()``,
  ``detect_all()``, and ``UniversalDetector``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- ``-e``/``--encoding-era`` CLI flag
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- EBCDIC detection (CP037, CP500)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Direct GB18030 support (replaces redundant GB2312 prober)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Binary file detection
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Python 3.12, 3.13, and 3.14 support
  (`Hugo van Kemenade <https://github.com/hugovk>`_,
  `#283 <https://github.com/chardet/chardet/pull/283>`_)
- GitHub Codespaces support
  (`oxygen dioxide <https://github.com/oxygen-dioxide>`_,
  `#312 <https://github.com/chardet/chardet/pull/312>`_)

**Breaking changes:**

- Dropped Python 3.7, 3.8, and 3.9 (requires Python 3.10+)
- Removed ``Latin1Prober`` and ``MacRomanProber``
- Removed EUC-TW support
- Removed ``LanguageFilter.NONE``
- ``detect()`` default changed to ``encoding_era=EncodingEra.MODERN_WEB``

**Fixes:**

- Fixed CP949 state machine
  (`nenw* <https://github.com/HelloWorld017>`_,
  `#268 <https://github.com/chardet/chardet/pull/268>`_)
- Fixed SJIS distribution analysis (second-byte range >= 0x80)
  (`Kadir Can Ozden <https://github.com/bysiber>`_,
  `#315 <https://github.com/chardet/chardet/pull/315>`_)
- Fixed ``max_bytes`` not being passed to ``UniversalDetector``
  (`Kadir Can Ozden <https://github.com/bysiber>`_,
  `#314 <https://github.com/chardet/chardet/pull/314>`_)
- Fixed UTF-16/32 detection for non-ASCII-heavy text
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed GB18030 ``char_len_table``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed UTF-8 state machine
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed ``detect_all()`` returning inactive probers
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed early cutoff bug
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Updated LGPLv2.1 license text for remote-only FSF address
  (`Ben Beasley <https://github.com/musicinmybrain>`_,
  `#307 <https://github.com/chardet/chardet/pull/307>`_)

5.2.0 (2023-08-01)
-------------------

- Added support for running the CLI via ``python -m chardet``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

5.1.0 (2022-12-01)
-------------------

- Added ``should_rename_legacy`` argument to remap legacy encoding names
  to modern equivalents
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#264 <https://github.com/chardet/chardet/pull/264>`_)
- Added MacRoman encoding prober
  (`Elia Robyn Lake <https://github.com/rspeer>`_)
- Added ``--minimal`` flag to ``chardetect`` CLI
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#214 <https://github.com/chardet/chardet/pull/214>`_)
- Added type annotations and mypy CI
  (`Jon Dufresne <https://github.com/jdufresne>`_,
  `#261 <https://github.com/chardet/chardet/pull/261>`_)
- Added support for Python 3.11
  (`Hugo van Kemenade <https://github.com/hugovk>`_,
  `#274 <https://github.com/chardet/chardet/pull/274>`_)
- Added ISO-8859-15 capital letter sharp S handling
  (`Simon Waldherr <https://github.com/SimonWaldherr>`_,
  `#222 <https://github.com/chardet/chardet/pull/222>`_)
- Clarified LGPL version in license trove classifier
  (`Ben Beasley <https://github.com/musicinmybrain>`_,
  `#255 <https://github.com/chardet/chardet/pull/255>`_)
- Removed support for Python 3.6
  (`Jon Dufresne <https://github.com/jdufresne>`_,
  `#260 <https://github.com/chardet/chardet/pull/260>`_)

5.0.0 (2022-06-25)
-------------------

- Added Johab Korean prober
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#207 <https://github.com/chardet/chardet/pull/207>`_)
- Added UTF-16/32 BE/LE probers
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#206 <https://github.com/chardet/chardet/pull/206>`_)
- Added test data for Croatian, Czech, Hungarian, Polish, Slovak,
  Slovene, Greek, Turkish
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Improved XML tag filtering
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#208 <https://github.com/chardet/chardet/pull/208>`_)
- Made ``detect_all`` return child prober confidences
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#210 <https://github.com/chardet/chardet/pull/210>`_)
- Added support for Python 3.10
  (`Hugo van Kemenade <https://github.com/hugovk>`_,
  `#232 <https://github.com/chardet/chardet/pull/232>`_)
- Slight performance increase
  (`deedy5 <https://github.com/deedy5>`_,
  `#252 <https://github.com/chardet/chardet/pull/252>`_)
- Dropped Python 2.7, 3.4, 3.5 (requires Python 3.6+)

4.0.0 (2020-12-10)
-------------------

- Added ``detect_all()`` function returning all candidate encodings
  (`Damien <https://github.com/mdamien>`_,
  `#111 <https://github.com/chardet/chardet/pull/111>`_)
- Converted single-byte charset probers to nested dicts (performance)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#121 <https://github.com/chardet/chardet/pull/121>`_)
- ``CharsetGroupProber`` now short-circuits on definite matches
  (performance)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#203 <https://github.com/chardet/chardet/pull/203>`_)
- Added ``language`` field to ``detect_all`` output
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Switched from Travis to GitHub Actions
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#204 <https://github.com/chardet/chardet/pull/204>`_)
- Dropped Python 2.6, 3.4, 3.5

3.0.4 (2017-06-08)
-------------------

- Fixed packaging issue with ``pytest_runner``
  (`Zac Medico <https://github.com/zmedico>`_,
  `#119 <https://github.com/chardet/chardet/pull/119>`_)
- Included ``test.py`` in source distribution
  (`Zac Medico <https://github.com/zmedico>`_,
  `#118 <https://github.com/chardet/chardet/pull/118>`_)
- Updated old URLs in README and docs
  (`Qi Fan <https://github.com/qfan>`_,
  `#123 <https://github.com/chardet/chardet/pull/123>`_;
  `Jon Dufresne <https://github.com/jdufresne>`_,
  `#129 <https://github.com/chardet/chardet/pull/129>`_)

3.0.3 (2017-05-16)
-------------------

- Fixed crash when debug logging was enabled
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#117 <https://github.com/chardet/chardet/pull/117>`_)

3.0.2 (2017-04-12)
-------------------

- Fixed ``detect`` sometimes returning ``None`` instead of a result dict
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#114 <https://github.com/chardet/chardet/pull/114>`_)

3.0.1 (2017-04-11)
-------------------

- Fixed crash in EUC-TW prober with certain strings
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

3.0.0 (2017-04-11)
-------------------

- Added Turkish ISO-8859-9 detection
  (`queeup <https://github.com/queeup>`_)
- Modernized naming conventions (``typical_positive_ratio`` instead of
  ``mTypicalPositiveRatio``)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#107 <https://github.com/chardet/chardet/pull/107>`_)
- Added ``language`` property to probers and results
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#108 <https://github.com/chardet/chardet/pull/108>`_)
- Switched from Travis to GitHub Actions
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Fixed ``CharsetGroupProber.state`` not being set to ``FOUND_IT``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)
- Added Hypothesis-based fuzz testing
  (`David R. MacIver <https://github.com/DRMacIver>`_,
  `#66 <https://github.com/chardet/chardet/pull/66>`_)
- Don't indicate byte order for UTF-16/32 with given BOM, for
  compatibility with ``decode()``
  (`Sebastian Noack <https://github.com/snoack>`_,
  `#73 <https://github.com/chardet/chardet/pull/73>`_)
- Stop reading file immediately when file type is known
  (`Jason Zavaglia <https://github.com/jpz>`_,
  `#103 <https://github.com/chardet/chardet/pull/103>`_)

chardet 2.3.0 (2014-10-07)
--------------------------

- Added CP932 detection
  (`hashy <https://github.com/hashy>`_)
- Fixed UTF-8 BOM not detected as UTF-8-SIG
  (`atbest <https://github.com/atbest>`_,
  `#32 <https://github.com/chardet/chardet/pull/32>`_)
- Switched ``chardetect`` to use ``argparse``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

chardet 2.2.1 (2013-12-18)
---------------------------

- Fixed missing parenthesis in ``chardetect.py``
  (`Owen <https://github.com/oparrish>`_,
  `#12 <https://github.com/chardet/chardet/pull/12>`_)

chardet 2.2.0 (2013-12-16)
---------------------------

Merged the charade fork back into chardet, unifying Python 2 and Python 3
support under the original package name.

- Added CP949 detection
  (`Kyung-hown Chung <https://github.com/puzzlet>`_)
- Fixed BOM detection
  (`Jean Boussier <https://github.com/byroot>`_)

charade 1.0.3 (2013-01-18)
---------------------------

- Fixed codecs usage for compatibility
  (`Ian Cordasco <https://github.com/sigmavirus24>`_)

charade 1.0.2 (2013-01-18)
---------------------------

- Fixed BOM detection
  (`Jean Boussier <https://github.com/byroot>`_)
- Improved multibyte sequence handling
  (`Kyung-hown Chung <https://github.com/puzzlet>`_)

charade 1.0.1 (2012-12-03)
---------------------------

- Version fix
  (`Ian Cordasco <https://github.com/sigmavirus24>`_)

charade 1.0.0 (2012-12-02)
---------------------------

- Initial release: Python 3 port of chardet, forked as a separate package
  (`Ian Cordasco <https://github.com/sigmavirus24>`_)

chardet 2.1.1 (2012-10-01)
---------------------------

- Bumped version past Mark Pilgrim's last release
- ``chardetect`` can now read from stdin
  (`Erik Rose <https://github.com/erikrose>`_)
- Fixed BOM byte strings for UCS-4-2143 and UCS-4-3412
  (`Toshio Kuratomi <https://github.com/abadger>`_)
- Restored Mark Pilgrim's original docs and COPYING file
  (`Toshio Kuratomi <https://github.com/abadger>`_)

chardet 1.1 (2012-07-27)
-------------------------

- Added ``chardetect`` CLI tool
  (`Erik Rose <https://github.com/erikrose>`_)
- Fixed ``utf8prober`` crash when character is out of range
  (`David Cramer <https://github.com/dcramer>`_)
- Cleaned up detection logic to fail gracefully
  (`David Cramer <https://github.com/dcramer>`_)
- Fixed feed encoding errors
  (`David Cramer <https://github.com/dcramer>`_)

chardet 1.0.1 (2008-04-19)
---------------------------

- Packaging fix, added egg distributions for Python 2.4 and 2.5
  (`Mark Pilgrim <https://github.com/a2mark>`_)

chardet 1.0 (2006-12-23)
-------------------------

- Initial release: Python 2 port of Mozilla's universal charset detector
  (`Mark Pilgrim <https://github.com/a2mark>`_)

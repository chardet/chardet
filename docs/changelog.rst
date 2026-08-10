Changelog
=========

.. note::

   Entries marked "via Claude" were developed with
   `Claude Code <https://claude.ai/code>`_.
   Dan directed the design, reviewed all output, and takes responsibility for
   the result. Unmarked entries by Dan were written without AI assistance.

7.6.0 (unreleased)
-------------------

**Bug Fixes:**

- Fixed space-padded text matching a degenerate Serbian model at up to
  0.93 confidence.  The ``sr/cp1250`` training corpus is Cyrillic, which
  mostly fails to encode into cp1250, so the model learned whitespace
  residue instead of Serbian; ANSI art and column-aligned ``.po`` files
  then matched it on runs of spaces alone.  Statistical scoring now
  skips repeated-whitespace bigrams, mirroring the whitespace collapse
  the training pipeline already applies.  Fixed 21 files in the expanded
  test suite plus a long-standing GB2312 known failure.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed EBCDIC text being invisible to the early pipeline stages.
  EBCDIC uses 0x05 and 0x15 as tab and newline, which the binary stage
  counted as binary indicators, so cp1026 and cp875 pages came back as
  ``encoding=None``.  Charset declarations inside EBCDIC-encoded markup
  (``<meta charset="cp1026">``) were also unreadable to the ASCII
  markup regexes.  The binary stage now treats those controls as
  whitespace when the data is high-byte-dominated, and the markup stage
  scans a cp037 decode of the head for declarations, which works for
  every EBCDIC variant because letters and digits sit at the same code
  points in all of them.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed the last two EBCDIC sibling misdetections from the expanded
  test suite.  A record dump came back as cp273 because three
  backslashes read as Ö under the German page, and a German historic
  file came back as cp500 because the correct sibling sat outside the
  near-tie band that confusion resolution scanned.
  Letter-over-punctuation votes are no longer treated as evidence (a
  backslash between capitals is a plausible path separator, unlike
  box-drawing inside a word), and when no model scores above 0.2 the
  scan now extends down to candidates at half the top confidence,
  requiring the vote and the rescore to agree before overturning the
  ranking.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed a training normalization gap that biased Romanian detection
  toward Windows-1250.  About a third of the Romanian corpus uses
  legacy cedilla forms, which ISO-8859-16 cannot encode, so they were
  silently dropped from its models while cp1250 kept every occurrence
  at the very same byte positions (both pages put the s form at 0xBA
  and the t form at 0xFE).  Cedilla now folds to comma-below when
  training ISO-8859-16, giving both siblings identical weight at the
  shared bytes.  The one test file still disagreeing turned out to be
  mislabeled: its 0x89 bytes sit right after election percentages,
  which is a per-mille sign under cp1250 and an unprintable control
  under ISO-8859-16, so it moved to ``windows-1250-ro``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed the same normalization gap for the euro sign.  Euro-bearing
  text was silently dropped when encoding to the 26 pre-euro
  encodings, leaving their euro-updated siblings (cp1140 over cp500,
  cp858 over cp850, ISO-8859-15 over ISO-8859-1) better fed at exactly
  the byte that should discriminate them.  The euro now folds to the
  generic currency sign wherever it cannot be encoded natively, which
  also fixed an Estonian ISO-8859-13 file whose Baltic near-tie the
  bias had flipped.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Improvements:**

- All bigram models retrained on a refreshed corpus (25,000 CulturaX
  articles per language) with the training pipeline hardened per
  ADR-0004: whitespace collapses after encoding instead of before, a
  retention guard hard-fails any (language, encoding) pair whose corpus
  mostly fails to encode, Serbian gets genuine Latin-script text by
  Gaj transliteration (``sr/cp1250`` went from 119 whitespace-residue
  bigrams to 941 real ones), and CP1006 gains the sixteen Urdu letters
  its substitution table was missing.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- New ANSI-art model.  Prose models carry no signal for box-drawing
  and shading bytes, so artpack files landed on arbitrary winners.
  cp437 detection now includes a bigram profile trained on 16,621
  text-mode art files from the `16colo.rs <https://16colo.rs/>`_
  archive, keyed under the ISO 639 ``zxx`` pseudo-language (no
  linguistic content) and reported with ``language=None``.  The test
  suite's wild artpacks were excluded from training by content
  fingerprint.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Rare-language arbitration: a statistical winner from a language with
  no documented legacy-encoding population (Scottish Gaelic, Welsh,
  Irish, and Breton — ISO-8859-14 was standardized in 1998 but never
  measurably deployed) now yields to a mainstream-language candidate
  scoring within 0.02, when the winner's own confidence is below 0.15.
  Genuine Celtic text is unaffected: it wins by landslides, and eight
  new boundary sentinel files in the test suite guard the gate against
  future drift.  Fixes a Croatian ``.po`` file detected as Scottish
  Gaelic.  Design, evidence, and revision protocol in ADR-0005.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Wiki-markup artifacts are now stripped from training text.  The
  major-language corpora are clean, but low-resource CulturaX slices
  are heavily wiki-derived: the Breton cache alone carried ~3,000
  ``]]``, enough to cross the model weight-preservation threshold and
  plant phantom ``]]`` bigrams on EBCDIC distinguishing bytes, flipping
  cp500/cp1140 resolution on unrelated files.  Doubled link brackets,
  template braces, table pipes, and bold/italic quote runs collapse to
  single characters before bigram counting — markup is not natural
  language in any language.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Confusion-group resolution is now context-aware.  Category voting
  votes per occurrence and demotes letter readings that have no word
  shape (a "letter" quoted between apostrophes, or a lowercase letter
  jammed against a following capital — how EBCDIC record data reads
  under the wrong sibling page).  A vote whose margin comes from such
  demotions overrides the bigram rescore; one won on the naive
  letters-beat-punctuation preference defers to it.  Art-model wins are
  exempt from resolution entirely, since both mechanisms reason about
  prose.  Fixes twelve EBCDIC and Latin files the retrain had left
  hanging on single-byte coin flips.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Statistical dead heats no longer resolve by candidate enumeration
  order.  The English models of cp437, cp850, Windows-1252, and MacRoman
  score identically on ASCII-dominated data, so files with almost no
  high-byte evidence (an ``ioreg`` dump with a single 0xD5 byte, a
  ReadMe with classic-Mac line endings) came back as whichever encoding
  the registry happened to list first.  Three post-processing rules now
  break these ties: prefer the Windows superset (``CP932`` over
  ``SHIFT_JIS``), prefer the more prevalent encoding era when the winner
  has no high-byte evidence at all, and prefer a classic-Mac candidate
  when line endings are bare ``\r``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Confusion resolution now covers cross-family near-ties.  Pair
  generation adds a second tier: encodings that share a registry
  language and at least 45% of their byte table (cp850 and
  Windows-1252 on Spanish, ISO-8859-4 and Windows-1257 on Estonian),
  growing the shipped pair set from 95 to 236.  The language-overlap
  gate keeps cross-script pairs out.  Cross-family pairs demand
  corroboration before acting: the category vote and the bigram
  rescore must agree, and the decisive-vote override stays
  within-family, where sibling models are too similar for the rescore
  to arbitrate on its own.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Training pipeline hardening after a cache-loss post-mortem: worker
  build failures and subset retrains that would drop an existing model
  now abort loudly instead of shipping without it, exclusion-set
  changes filter the article caches in place instead of deleting them
  wholesale, subset retrains preserve metadata provenance for models
  they did not rebuild, and the artpack fetcher builds into a
  temporary directory so a failed sync cannot destroy a good corpus.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

7.5.1 (2026-08-06)
-------------------

**Bug Fixes:**

- Fixed markup-declared encodings being reported under a name that can't
  decode the input.  A page declaring ``Shift_JIS`` but using CP932
  extension characters (like ①) came back as ``SHIFT_JIS``, which fails
  ``.decode()`` on those same bytes.  Superset promotion (``CP932``,
  ``CP949``) now always fires when the reported name can't decode the
  data but the superset can.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed a lying charset declaration beating genuine UTF-8 content.  A
  UTF-8 page declaring ``<meta charset="iso-8859-1">`` came back as
  ISO-8859-1, which decodes to mojibake.  Valid multi-byte UTF-8 now
  wins over a conflicting declaration; pure ASCII and real single-byte
  content still honor it.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed BOM-less UTF-16 byte-order detection for pure-CJK text.  With no
  ASCII in the sample, the only null bytes come from the low byte of
  characters like U+4E00 (一), which sit in the wrong parity position, so
  short Chinese UTF-16 samples came back with reversed endianness at full
  confidence.  Byte order is now chosen by decoding both ways and
  comparing text quality, with the null signal breaking near-ties.  Found
  by scoring chardet against charset-normalizer's char-dataset.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

7.5.0 (2026-08-05)
-------------------

**Bug Fixes:**

- Fixed multi-byte encodings being eliminated when the input ends in an
  incomplete character.  Byte-validity filtering decoded with a one-shot
  strict decode, which cannot tell a truncated tail from corrupt data, so a
  single dangling lead byte dropped every CJK candidate and the result came
  down to input-length parity — a 184-byte GBK sample detected as
  ``GB18030``, the same sample minus one byte as ``Windows-1256``.  This was
  also reachable on complete, well-formed files, because chardet slices its
  own input at ``max_bytes`` and at ``_SCAN_LIMIT`` in
  ``_validate_bytes()``: a valid 14 kB GBK page with an honest
  ``<meta charset="gbk">`` lost its declaration, and with it ``text/html``
  and 0.95 confidence, whenever byte 4096 happened to split a character.
  Validity checks now decode incrementally with ``final=False``, deferring a
  partial trailing character while still rejecting corruption anywhere
  before it.
  (`António Afonso <https://github.com/aadsm>`_ via Claude,
  `#376 <https://github.com/chardet/chardet/pull/376>`_)

- Fixed ``compat_names`` (the default) leaking internal Python codec names
  for seven encodings.  ``detect()`` now returns ``ISO-8859-2``,
  ``ISO-8859-6``, ``ISO-8859-13``, ``Windows-1250``, ``Windows-1256``,
  ``Windows-1257``, and ``CP874`` instead of their lowercase codec
  spellings.  These were absent from ``_COMPAT_NAMES`` after the 7.1.0
  switch to codec-name canonicals, which made default output inconsistent
  with their siblings (e.g. ``cp1250`` vs ``Windows-1251``) and with the
  encoding-name table in :doc:`usage`.
  (`António Afonso <https://github.com/aadsm>`_ via Claude,
  `#374 <https://github.com/chardet/chardet/pull/374>`_)
- Fixed ``compat_names`` (the default) leaking the internal ``cp932`` codec
  name.  ``detect()`` now returns ``CP932`` instead of ``cp932``, matching
  its Japanese siblings (``shift_jis_2004`` → ``SHIFT_JIS``) and the value
  chardet 5.x/6.x returned.
  (`uttam12331 <https://github.com/uttam12331>`_,
  `#375 <https://github.com/chardet/chardet/pull/375>`_)

**Performance:**

- Statistical scoring now skips single-byte models that provably can't
  beat the current runner-up, using per-model row-maximum tables
  (``rowmax.bin``).  Results are bit-identical: multi-byte models are
  always scored in full and ``detect_all()`` bypasses pruning.  Mean
  detection time dropped ~2.9x with mypyc, with the largest gains on
  legacy CJK (p99 from 9.5ms to 3.3ms).
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Model tables are now ``bytes`` (native array indexing under mypyc,
  instead of boxed ``memoryview`` calls), and the model blob is
  decompressed in chunks rather than one shot: peak process memory
  dropped from 53.9 to 27.4 MiB.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Confusion-group resolution and post-processing now use
  ``bytes.translate`` prefilters instead of per-byte Python scans,
  making near-tie resolution cheaper on large inputs.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Improvements:**

- ``prefer_superset=True`` is now documented as the recommended mode and
  **will become the default in chardet 8.0**.  Detection examines at most
  ``max_bytes`` of input, so only the superset encoding is guaranteed to
  decode bytes beyond that window — the same reasoning behind the
  WHATWG/W3C Encoding Standard's rule that browsers decode ``ascii`` and
  ``iso-8859-1`` content as ``windows-1252``.  Callers that depend on
  subset names should start passing ``prefer_superset=False`` explicitly.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``chardet.equivalences`` is now a deprecation shim.  Accuracy-evaluation
  predicates (``is_correct``, ``is_equivalent_detection``, etc.) moved to
  ``chardet.evaluation``; public-API encoding-name remapping
  (``apply_compat_names``, ``apply_preferred_superset``) moved to
  ``chardet.output_names``.  Existing imports keep working with a
  ``DeprecationWarning``.  ``chardet.equivalences`` will be removed in 8.0.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Internal pipeline reorganization: language detection,
  markup-superset promotion, and post-processing rank corrections moved
  out of the orchestrator into ``pipeline/language.py``,
  ``pipeline/markup.py``, and ``pipeline/postprocess.py`` respectively.
  No behavior change.  The two new modules are also added to the mypyc
  compilation list.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

7.4.3 (2026-04-13)
-------------------

**Bug Fixes:**

- Fixed ``ValueError: embedded null character`` crash when input contained
  a ``<meta charset>`` declaration with a null byte in the encoding name
  (e.g. ``b'<meta charset="\x00utf-8">'``). ``codecs.lookup()`` raises
  ``ValueError`` on embedded nulls, and ``lookup_encoding()`` was only
  catching ``LookupError``. Also added defensive ``ValueError`` catches
  in ``_validate_bytes()`` and ``_to_utf8()`` for completeness.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#369 <https://github.com/chardet/chardet/issues/369>`_)

7.4.2 (2026-04-12)
-------------------

**Bug Fixes:**

- Fixed ``RuntimeError: pipeline must always return at least one result``
  on ~2% of all possible two-byte inputs (e.g. ``b"\xf9\x92"``).
  Multi-byte encodings like CP932 and Johab could score above the
  structural confidence threshold on very short inputs, but then
  statistical scoring would return nothing, leaving the pipeline with an
  empty result list instead of falling through to the ``no_match_encoding``
  fallback.
  (`Jason Barnett <https://github.com/jasonwbarnett>`_ via Claude,
  `#367 <https://github.com/chardet/chardet/issues/367>`_,
  `#368 <https://github.com/chardet/chardet/pull/368>`_)

**Improvements:**

- Added ~90 encoding aliases from the WHATWG Encoding Standard and IANA
  Character Sets registry so that ``<meta charset>`` labels like
  ``x-cp1252``, ``x-sjis``, ``dos-874``, ``csUTF8``, and the
  ``cswindows*`` family all resolve correctly through the markup detection
  stage. Every alias was driven by a failing spec-compliance test.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#366 <https://github.com/chardet/chardet/pull/366>`_)
- Added a spec-compliance test suite covering Python decode round-trips
  for all 86 registry encodings, WHATWG web-platform label resolution,
  IANA preferred MIME names, and Unicode/RFC conformance (BOM sniffing,
  UTF-8 boundary cases, UTF-16 surrogate pairs). This is the test suite
  that would have caught the 7.4.1 BOM bug before release.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#366 <https://github.com/chardet/chardet/pull/366>`_)

7.4.1 (2026-04-07)
-------------------

**Bug Fixes:**

- BOM-prefixed UTF-16 and UTF-32 input now reports ``utf-16`` and
  ``utf-32`` instead of the endian-specific variants. Python's
  ``utf-16-le``/``utf-16-be``/``utf-32-le``/``utf-32-be`` codecs keep
  the BOM as a U+FEFF in the decoded string, while ``utf-16``/``utf-32``
  strip it, so callers passing the detection result directly to
  ``.decode()`` were getting a stray BOM at the start of their text.
  BOM-less UTF-16/32 detection (via null-byte patterns) is unchanged
  and still returns the endian-specific name.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#364 <https://github.com/chardet/chardet/issues/364>`_,
  `#365 <https://github.com/chardet/chardet/pull/365>`_)

7.4.0 (2026-03-26)
-------------------

**Performance:**

- Switched to dense zlib-compressed model format (v2): models are now
  stored as contiguous ``memoryview`` slices of a single decompressed
  blob, eliminating per-model ``struct.unpack`` overhead. Cold start
  (import + first detect) dropped from ~75ms to ~13ms with mypyc.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#354 <https://github.com/chardet/chardet/pull/354>`_)

**Accuracy:**

- Accuracy improved from 98.6% to 99.3% (2499/2517 files) through
  a combination of training and scoring improvements:

  - Eliminated train/test data overlap by content-fingerprinting test
    suite articles and excluding them from training data
    (`#351 <https://github.com/chardet/chardet/pull/351>`_)
  - Added MADLAD-400 and Wikipedia as supplemental training sources to
    fill gaps left by exclusion filtering
    (`#351 <https://github.com/chardet/chardet/pull/351>`_)
  - Improved non-ASCII bigram scoring: high-byte bigrams are now
    preserved during training (instead of being crushed by global
    normalization), and weighted by per-bigram IDF so encoding-specific
    byte patterns contribute proportionally to how discriminative they
    are (`#352 <https://github.com/chardet/chardet/pull/352>`_)
  - Added encoding-aware substitution filtering: character substitutions
    during training now only apply for characters the target encoding
    cannot represent
  - Increased training samples from 15K to 25K per language/encoding pair
    (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Bug Fixes:**

- Added dedicated structural analyzers for CP932, CP949, and
  Big5-HKSCS: these superset encodings previously shared their base
  encoding's byte-range analyzer, missing extended ranges unique to each
  superset
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#353 <https://github.com/chardet/chardet/pull/353>`_)

7.3.0 (2026-03-24)
-------------------

**License:**

- **0BSD license** — the project license has been changed from MIT to
  `0BSD <https://opensource.org/license/0bsd>`_, a maximally permissive
  license with no attribution requirement. All prior 7.x releases
  should also be considered 0BSD licensed as of this release.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Features:**

- Added ``mime_type`` field to detection results — identifies file types
  for both binary (via magic number matching) and text content. Returned
  in all ``detect()``, ``detect_all()``, and ``UniversalDetector`` results.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#350 <https://github.com/chardet/chardet/pull/350>`_)
- New ``pipeline/magic.py`` module detects 40+ binary file formats
  including images, audio/video, archives, documents, executables, and
  fonts. ZIP-based formats (XLSX, DOCX, JAR, APK, EPUB, wheel,
  OpenDocument) are distinguished by entry filenames.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#350 <https://github.com/chardet/chardet/pull/350>`_)

**Bug Fixes:**

- Fixed incorrect equivalence between UTF-16-LE and UTF-16-BE in
  accuracy testing — these are distinct encodings with different byte
  order, not interchangeable
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Performance:**

- Added 4 new modules to mypyc compilation (orchestrator, confusion,
  magic, ascii), bringing the total to 11 compiled modules
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Capped statistical scoring at 16 KB — bigram models converge quickly,
  so large files no longer score the full 200 KB. Worst-case detection
  time dropped from 62ms to 26ms with no accuracy loss.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Replaced ``dataclasses.replace()`` with direct ``DetectionResult``
  construction on hot paths, eliminating ~354k function calls per full
  test suite run
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Build:**

- Added riscv64 to the mypyc wheel build matrix — prebuilt wheels are
  now published for RISC-V Linux alongside existing architectures
  (`Bruno Verachten <https://github.com/gounthar>`_,
  `#348 <https://github.com/chardet/chardet/pull/348>`_)

7.2.0 (2026-03-17)
-------------------

**Features:**

- Added ``include_encodings`` and ``exclude_encodings`` parameters to
  :func:`~chardet.detect`, :func:`~chardet.detect_all`, and
  :class:`~chardet.UniversalDetector` — restrict or exclude specific
  encodings from the candidate set, with corresponding
  ``-i``/``--include-encodings`` and ``-x``/``--exclude-encodings``
  CLI flags
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#343 <https://github.com/chardet/chardet/pull/343>`_)
- Added ``no_match_encoding`` (default ``"cp1252"``) and
  ``empty_input_encoding`` (default ``"utf-8"``) parameters — control
  which encoding is returned when no candidate survives the pipeline or
  the input is empty, with corresponding CLI flags
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#343 <https://github.com/chardet/chardet/pull/343>`_)
- Added ``-l``/``--language`` flag to ``chardetect`` CLI — shows the
  detected language (ISO 639-1 code and English name) alongside the encoding
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#342 <https://github.com/chardet/chardet/pull/342>`_)

7.1.0 (2026-03-11)
-------------------

**Features:**

- Added PEP 263 encoding declaration detection — ``# -*- coding: ... -*-``
  and ``# coding=...`` declarations on lines 1–2 of Python source files are
  now recognized with confidence 0.95
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#249 <https://github.com/chardet/chardet/issues/249>`_)
- Added ``chardet.universaldetector`` backward-compatibility stub so that
  ``from chardet.universaldetector import UniversalDetector`` works with a
  deprecation warning
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#341 <https://github.com/chardet/chardet/issues/341>`_)

**Fixes:**

- Fixed false UTF-7 detection of ASCII text containing ``++`` or ``+word``
  patterns
  (`Dan Blanchard <https://github.com/dan-blanchard>`_,
  `#332 <https://github.com/chardet/chardet/issues/332>`_,
  `#335 <https://github.com/chardet/chardet/pull/335>`_)
- Fixed 0.5s startup cost on first ``detect()`` call — model norms are now
  computed during loading instead of lazily iterating 21M entries
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#333 <https://github.com/chardet/chardet/issues/333>`_,
  `#336 <https://github.com/chardet/chardet/pull/336>`_)
- Fixed undocumented encoding name changes between chardet 5.x and 7.0 —
  ``detect()`` now returns chardet 5.x-compatible names by default
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#338 <https://github.com/chardet/chardet/pull/338>`_)
- Improved ISO-2022-JP family detection — recognizes ESC sequences for
  ISO-2022-JP-2004 (JIS X 0213) and ISO-2022-JP-EXT (JIS X 0201 Kana)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed silent truncation of corrupt model data (``iter_unpack`` yielded
  fewer tuples instead of raising)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed incorrect date in LICENSE
  (`Dan Blanchard <https://github.com/dan-blanchard>`_)

**Performance:**

- 5.5x faster first-detect time (~0.42s → ~0.075s) by computing model
  norms as a side-product of ``load_models()``
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ~40% faster model parsing via ``struct.iter_unpack`` for bulk entry
  extraction (eliminates ~305K individual ``unpack`` calls)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**New API parameters:**

- Added ``compat_names`` parameter (default ``True``) to
  :func:`~chardet.detect`, :func:`~chardet.detect_all`, and
  :class:`~chardet.UniversalDetector` — set to ``False`` to get raw Python
  codec names instead of chardet 5.x/6.x compatible display names
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Added ``prefer_superset`` parameter (default ``False``) — remaps legacy
  ISO/subset encodings to their modern Windows/CP superset equivalents
  (e.g., ASCII → Windows-1252, ISO-8859-1 → Windows-1252).
  **This will default to ``True`` in the next major version (8.0).**
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Deprecated ``should_rename_legacy`` in favor of ``prefer_superset`` —
  a deprecation warning is emitted when used
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Improvements:**

- Switched internal canonical encoding names to Python codec names
  (e.g., ``"utf-8"`` instead of ``"UTF-8"``), with ``compat_names``
  controlling the public output format.  See :doc:`usage` for the full
  mapping table.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Added ``lookup_encoding()`` to ``registry`` for case-insensitive
  resolution of arbitrary encoding name input to canonical names
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Achieved 100% line coverage across all source modules (+31 tests)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Updated benchmark numbers: 98.2% encoding accuracy, 95.2% language
  accuracy on 2,510 test files
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Pinned test-data cloning to chardet release version tags for
  reproducible builds
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

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
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Updated language equivalences for mutual intelligibility (Slovak/Czech,
  East Slavic + Bulgarian, Malay/Indonesian, Scandinavian languages)
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

7.0.0 (2026-03-02)
-------------------

Ground-up, 0BSD-licensed rewrite of chardet
(`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
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
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
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
  (`grizlupo <https://github.com/grizlupo>`_,
  `#172 <https://github.com/chardet/chardet/pull/172>`_,
  `#207 <https://github.com/chardet/chardet/pull/207>`_)
- Added UTF-16/32 BE/LE probers
  (`Jason Zavaglia <https://github.com/jpz>`_,
  `#109 <https://github.com/chardet/chardet/pull/109>`_,
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

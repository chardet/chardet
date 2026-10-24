Changelog
=========

.. note::

   Entries marked "via Claude" were developed with
   `Claude Code <https://claude.ai/code>`_.
   Dan directed the design, reviewed all output, and takes responsibility for
   the result. Unmarked entries by Dan were written without AI assistance.

Unreleased
----------

**Features:**

- ``chardetect`` has two new flags.  ``--prefer-superset`` reports a
  detected subset encoding under its Windows code page, like
  ``Windows-1253`` for ISO-8859-7 text, the same as
  ``prefer_superset=True`` in the Python API.  ``--no-compat-names``
  reports the raw Python codec name, like ``euc_jis_2004`` instead of
  ``EUC-JP``.  Output without the flags is unchanged.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#407 <https://github.com/chardet/chardet/pull/407>`_)

**Improvements:**

- Internal cleanup with no change to any result.  ``detect()``,
  ``detect_all()``, ``UniversalDetector``, and ``chardetect`` now share
  one ``DetectionRequest`` that validates the options, runs the
  pipeline, and applies the output names, instead of each spelling that
  out on its own.  ``EncodingInfo`` gained a ``superset`` field, so the
  registry is the one place that says which Windows code page stands in
  for an encoding.  ``UniversalDetector.result`` no longer re-checks the
  buffer on every read.  ADR-0007 has the reasoning.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#407 <https://github.com/chardet/chardet/pull/407>`_)

- The markup stage now owns the whole charset-declaration decision,
  and its parser (``iter_declarations``) can be tested on its own,
  without a window decode in the way.  A declared Shift_JIS or EUC-KR
  page costs one window decode instead of two.  A declaration that fails
  to decode the window is now checked once, however many times the page
  repeats it.  Each check reads the whole window, so 195
  ``<meta charset=euc-kr>`` tags in front of a 16 MiB window ending in a
  bad EUC-KR pair took 14s with ``max_bytes=len(data)``, and now take
  0.2s, about the same as without the tags.  No result changed.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude;
  `Samina <https://github.com/Samin061>`_,
  `#408 <https://github.com/chardet/chardet/pull/408>`_,
  `#411 <https://github.com/chardet/chardet/pull/411>`_)

**Performance:**

- A long base64 run after a ``+`` no longer makes the UTF-7 check
  quadratic.  The decoder never trimmed its bit buffer, so it grew as
  wide as the run and every step copied it again.  A 100,000-character
  run took about a second to check and now takes about 10 ms.
  (`Samina <https://github.com/Samin061>`_,
  `#409 <https://github.com/chardet/chardet/pull/409>`_)

**Bug Fixes:**

- The warning for an excluded ``no_match_encoding`` now points at the
  caller's line when the fallback is reached past the evidence cap.  It
  used to name ``chardet/__init__.py`` on that one path.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#407 <https://github.com/chardet/chardet/pull/407>`_)
- Charset names Python has no codec for no longer pile up in the
  standard library's codec cache.  ``lookup_encoding`` handed every
  unknown name from untrusted markup to ``codecs.lookup``, which keeps
  each miss for the life of the process before Python 3.13.13 and
  3.14.4, so the 1024-entry cap from 7.7.0 did not bound memory.  Names
  the standard library cannot resolve now stop before reaching it.
  (`Samina <https://github.com/Samin061>`_,
  `#410 <https://github.com/chardet/chardet/pull/410>`_)
- BOM-less UTF-16 with emoji or other characters outside the BMP no
  longer comes back byte-swapped, or as binary, when the 4 KB sample or
  the end of a short input cuts a surrogate pair in half.
  (`nk-batman21 <https://github.com/nk-batman21>`_,
  `#412 <https://github.com/chardet/chardet/pull/412>`_)

7.7.0 (2026-10-17)
------------------

**Features:**

- Added a ``-m``/``--mime-type`` flag to the ``chardetect`` CLI, which
  shows the detected MIME type next to the encoding, like ``file -i``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#384 <https://github.com/chardet/chardet/issues/384>`_)

**Accuracy:**

- Visual-order Hebrew is now detected.  The ISO-8859-8 model trains on
  both bidi conventions, so 1990s visual-order pages come back as
  ISO-8859-8 while logical-order text still prefers Windows-1255.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- cp864 Arabic now trains on contextually shaped text in visual order,
  the way real cp864 systems stored it, instead of isolated letter
  forms in logical order.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Performance:**

- Raising ``max_bytes`` on large inputs no longer gets slow.  On the
  compiled build, ``detect(data, max_bytes=len(data))`` on 272 MiB takes
  about 0.23s for cp1252 and 0.56s for Shift_JIS, down from several
  seconds.  UTF-8 validation and a final decode of the winner still read
  the whole window, so the answer still decodes it.  The other stages
  stop at a 256 KB evidence cap, which sits above the default
  ``max_bytes``, so default calls are unchanged, and the default 200 KB
  cap is still the fastest path.  ADR-0006 has the design.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- The UTF-7 ``+`` scan is no longer quadratic on line-wrapped base64
  like PEM certificates, MIME attachments, and JWTs.  128 KiB of it went
  from 5.4 seconds to 1.2 milliseconds.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- A head full of unclosed ``<meta`` or ``<?xml`` tags no longer makes the
  markup scan quadratic, taking it from about 5 ms to about 20 µs.  A
  literal ``<`` inside an attribute value now hides that one tag.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- An EBCDIC ``charset=`` or ``encoding=`` followed by whitespace and no
  value no longer makes the declaration scan backtrack quadratically.
  A crafted 4 KB document used to cost ``detect()`` about 60 ms.
  (`Samina <https://github.com/Samin061>`_,
  `#403 <https://github.com/chardet/chardet/pull/403>`_)
- The pure-Python install on CPython scores bigram models with
  ``operator.itemgetter`` instead of a Python loop, making ``detect()``
  about 1.25x faster and ``detect_all()`` about 1.35x faster across the
  test corpus.  Compiled builds and PyPy keep their existing paths.
  (`Afonso Ribeiro <https://github.com/deadstrobe5>`_)

**Bug Fixes:**

- Language labels on Unicode text no longer tilt toward accent-heavy
  languages, so a French paragraph with a few accents stops coming back
  as Hungarian.  Models and input are now scored in the same
  IDF-weighted space.  Mislabels on the corpus's Unicode files fall from
  140 to 104 of 1587 (French from 20 to 4), and encodings, confidences,
  and MIME types do not move.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Null-separated ASCII records with short fields, like ``find -print0``
  output, no longer come back as UTF-16-LE at 0.95 with Chinese as the
  language.  They get the answer longer records already got: binary, or
  ASCII when the nulls are sparse.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Every answer now decodes the examined window under the name the
  caller receives.  A BOM, a BOM-less UTF-16/32 null pattern, an ISO-2022
  or HZ escape designation, or a ``<meta charset>``/``<?xml encoding>``
  declaration was trusted without decoding the rest of the window, so a
  confident answer could raise further in.  Each now has to decode the
  whole window, and the 5.x/6.x display names ``EUC-JP``, ``SHIFT_JIS``,
  ``Big5``, and ``ISO-2022-JP`` are used only when those narrower codecs
  decode it too.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude;
  `Samina <https://github.com/Samin061>`_,
  `#394 <https://github.com/chardet/chardet/pull/394>`_,
  `#396 <https://github.com/chardet/chardet/pull/396>`_)
- A ``charset=`` inside another attribute, like a refresh URL, no longer
  beats a real ``<meta charset>``, and a declaration naming an unknown
  encoding no longer hides a later one that works.  A repeated attribute
  now keeps its first value, and a ``<meta`` tag that never closes is
  ignored.
  (`Sash <https://github.com/SashaMIT>`_,
  `#389 <https://github.com/chardet/chardet/pull/389>`_)
- The ``charset`` parameter of a ``content`` attribute may now be quoted
  or have spaces around its ``=``.
  (`Huanyi Xie <https://github.com/xiehuanyi>`_,
  `#398 <https://github.com/chardet/chardet/pull/398>`_)
- Markup declarations are read the way the WHATWG prescan reads them.
  Declarations inside ``<!-- -->`` comments are ignored, ``x-user-defined``
  means Windows-1252, and a UTF-16 or UTF-32 label in ASCII markup means
  UTF-8, so an ASCII page declaring ``utf-16le`` no longer comes back as
  UTF-16-LE at 0.95.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- PEP 263 cookies are resolved the way ``tokenize.detect_encoding``
  resolves them, so ``iso-latin-1`` and similar spellings now work,
  ``utf-8-sig`` means UTF-8, and a long first line no longer hides a
  cookie on line 2.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- A PEP 263 cookie on line 2 counts only when line 1 is blank or a
  comment, as in Python, so a ``coding=`` comment after a line of code
  is ignored.
  (`Huanyi Xie <https://github.com/xiehuanyi>`_,
  `#391 <https://github.com/chardet/chardet/pull/391>`_)
- An EBCDIC ``<?xml encoding="...">`` declaration now reports
  ``text/xml`` instead of ``text/html``, which fixes the MIME type for
  ten EBCDIC RSS feeds in the test corpus.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``detect_all(prefer_superset=True)`` no longer lists the same name
  twice.  Greek text came back as ``Windows-1253`` at two confidences;
  each name now appears once, at its higher confidence.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``prefer_superset=True`` no longer swaps in a Windows code page that
  cannot decode the data, like Windows-1252 for ISO-8859-1 text holding
  0x81.  ``apply_preferred_superset`` takes an optional ``data``
  argument for the check.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``prefer_superset=True`` now respects ``include_encodings`` and
  ``exclude_encodings``, keeping the detected name when the filters rule
  out its superset.
  (`00200200 <https://github.com/00200200>`_,
  `#393 <https://github.com/chardet/chardet/pull/393>`_)
- ``chardetect`` now reads one byte past its 200 KB cap, so a multi-byte
  sequence cut at the cap is treated as truncated input instead of the
  end of the file.
  (`00200200 <https://github.com/00200200>`_,
  `#392 <https://github.com/chardet/chardet/pull/392>`_)
- ``lookup_encoding``'s cache is now capped at 1024 entries.  Charset
  names come from untrusted markup, so a stream of distinct spellings
  could grow it without limit.
  (`Samina <https://github.com/Samin061>`_,
  `#390 <https://github.com/chardet/chardet/pull/390>`_)
- ``UniversalDetector`` no longer treats a buffer filled to exactly
  ``max_bytes`` as the whole stream, which could turn a correct
  ``utf-8`` answer into a single-byte codec when a multi-byte sequence
  was cut at the boundary.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- A UTF-32 file with a BOM no longer comes back as UTF-16, or as
  ``utf-32-be`` with the BOM left in, when ``max_bytes`` ends the window
  partway through a code unit.  The default cap is a multiple of four,
  so only custom caps hit this.
  (`Aryan R. Ganjoo <https://github.com/AryanRG>`_,
  `#405 <https://github.com/chardet/chardet/pull/405>`_)
- ``detect_all()`` no longer puts a demoted niche Latin encoding back
  near the top.  The demoted entry now takes the confidence of the
  candidate it sits behind, so the ranking is ordered by confidence as
  documented.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Language detection now honors ``max_bytes`` instead of always reading
  up to 2 KB.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- The deprecated ``chardet.equivalences`` shim is reachable again after a
  bare ``import chardet``, resolves every name the old module had, and
  passes patches through to the module that owns each name, so
  ``mock.patch.object`` on it restores cleanly.  It warns when a name is
  used rather than at import, so importing it no longer fails under
  ``-W error::DeprecationWarning``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- A mostly-ASCII Windows-1252 file with a single ``Ö`` or ``ö`` no
  longer detects as HP-Roman8.  The niche Latin demotion now compares
  the candidate and its replacement on the bytes they read differently,
  so one Welsh ``ŵ`` still keeps ISO-8859-14 and a Kven ``đ`` in Finnish
  still keeps ISO-8859-10.  Some corpus files that came back as
  ISO-8859-1 now come back as Windows-1252, an accepted superset.
  (`António Afonso <https://github.com/aadsm>`_ via Claude,
  `#383 <https://github.com/chardet/chardet/pull/383>`_)
- An English file whose only non-ASCII letter is a capital ``É``,
  ``À``, or ``Ó`` no longer detects as MacRoman, which reads those
  bytes as the ellipsis and curly quotes.  The era-prevalence prior now
  compares the two readings on the bytes they disagree on instead of
  standing down.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude,
  `#383 <https://github.com/chardet/chardet/pull/383>`_)

**Deprecations:**

- ``EncodingInfo.is_multibyte`` is now ``is_multibyte_cjk``, since the
  flag marks CJK byte structure rather than width and is off for UTF-8,
  UTF-16 and UTF-32.  The old attribute still works with a
  ``DeprecationWarning`` and will be removed in 8.0.  ``EncodingInfo``
  is internal and never reaches ``detect()`` callers.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Documentation:**

- The supported encodings table no longer lists UTF-8, UTF-16, UTF-32
  and UTF-7 as single-byte.  The multi-byte column used to copy the
  registry flag that marks CJK byte structure for the structural stage,
  which is off for the Unicode encodings on purpose.  The generator now
  asks each codec whether any character takes more than one byte.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Build:**

- ``pipeline/markup.py`` is now compiled by mypyc (15 modules), so the
  markup superset promotion that moved there no longer runs interpreted
  in compiled wheels.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Test coverage is back to 100%, and CI now enforces it.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- The ``models.bin``, ``rowmax.bin``, ``idf.bin``, and ``langnorm.bin``
  formats now have one owner, ``chardet.models._format``, shared by the
  trainer and the runtime loader.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``scripts/verify_no_overlap.py --require-provenance`` fails unless the
  training metadata records an exclusion set matching the current test
  data.  The shipped models record none until the next full retrain.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

7.6.0 (2026-08-14)
-------------------

**Performance:**

- Compiled wheels now score bigram profiles through a small Cython
  kernel alongside mypyc, and the pair is 4.7x faster than the pure
  wheel on CPython 3.14.  ``_kernel.py`` stays plain Python (PyPy and
  pure wheels run it interpreted, unchanged), ``_kernel.pxd`` adds C
  types at build time and ships nothing, and detection output is
  bit-identical.  The kernel declares itself safe without the GIL, so
  free-threaded CPython scales instead of silently re-enabling the GIL
  on import: 3.14t runs the whole suite in ~340ms across 8 threads,
  the fastest configuration measured.  Compiled builds now need both
  hooks::

      HATCH_BUILD_HOOK_ENABLE_MYPYC=true HATCH_BUILD_HOOK_ENABLE_CUSTOM=true uv build

  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Added support for CPython 3.15, including the free-threaded build.
  No code changes were needed.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Bug Fixes:**

- Fixed delimited ASCII data like ``|NAME,+LAY|`` misdetecting as
  UTF-7, a follow-up to `#371
  <https://github.com/chardet/chardet/issues/371>`_.  Two new checks:
  the whole buffer must actually decode as UTF-7 (``+|`` is an illegal
  shift, so tabular data fails immediately), and a block encoding a
  single code unit must land in a script range where a lone shifted
  character plausibly occurs.  ``+LAY`` decodes to U+2C06, Glagolitic;
  no genuine lone block in the corpus lands anywhere like it, while em
  dashes, ellipses, kanji, and accented letters all pass.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Signed UTF-7 no longer reads as ASCII.  The BOM stage recognizes the
  four UTF-7 signature prefixes (``+/v8-`` and friends) when the rest
  of the buffer decodes as UTF-7 --- the prefix alone is ordinary ASCII
  (a diff of V8 source paths starts with ``+/v8``).  This is a
  deliberate divergence from WHATWG's browser-security exclusion of
  UTF-7: chardet already detects the unsigned form, so refusing only
  the signed one made no sense.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- ``detect()`` no longer returns an encoding that cannot decode the
  input it was given
  (`#380 <https://github.com/chardet/chardet/issues/380>`_).  When the
  whole input has been examined and the winner's only multi-byte
  evidence is an incomplete trailing sequence, the best candidate that
  decodes the input completely wins instead.  Genuinely truncated data
  keeps its answer: CJK cut mid-character, or input sliced at
  ``max_bytes``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Short apostrophe-heavy English is no longer labeled Scottish Gaelic
  or Breton.  A rare-language label on an input under 128 bytes now
  needs a 0.03 lead over the best mainstream language, mirroring the
  encoding-side arbitration in ADR-0005.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Hungarian text no longer loses to a Czech reading: confusion
  rescoring compares tied pairs only under language models both
  encodings have.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Space-padded text no longer matches a degenerate Serbian model at
  high confidence.  Statistical scoring now skips repeated-whitespace
  bigrams, matching the whitespace collapse training already applies.
  Fixed 21 files plus a long-standing GB2312 known failure.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- EBCDIC text is no longer invisible to the early pipeline.  The
  binary stage treats EBCDIC's 0x05/0x15 tab and newline as whitespace
  when the data is high-byte-dominated, and the markup stage reads
  charset declarations through a cp037 decode of the head.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed the last two EBCDIC sibling misdetections: a letter reading
  beating punctuation is no longer evidence by itself, and
  low-confidence near-ties scan deeper but need the category vote and
  the bigram rescore to agree.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Fixed training normalization gaps that starved ISO-8859-16 (legacy
  cedilla forms) and the 26 pre-euro encodings (the euro sign) at
  exactly the bytes that discriminate them from their siblings.
  Cedilla folds to comma-below and the euro to the currency sign
  wherever the target encoding cannot represent them.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)

**Improvements:**

- Retrained every bigram model on a refreshed, deduplicated corpus
  with the ADR-0004 hardening: whitespace collapses after encoding,
  retention guards hard-fail mostly unencodable corpora, Serbian gets
  real Latin-script text, CP1006 gains its sixteen missing Urdu
  letters, and wiki markup is stripped before bigram counting.
  Training provenance is now recorded per model, so test data added
  after a retrain is detectable as such.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- New ANSI-art model.  cp437 detection now includes a profile trained
  on 16,621 text-mode art files from `16colo.rs <https://16colo.rs/>`_,
  keyed under the ``zxx`` pseudo-language and reported with
  ``language=None``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Rare-language arbitration: a low-confidence statistical winner from a
  language with no documented legacy-encoding population (Scottish
  Gaelic, Welsh, Irish, Breton) yields to a near-tied mainstream
  candidate.  Genuine Celtic text wins by landslides and is unaffected;
  eight boundary sentinels in the test suite guard the gate.  Design
  and evidence in ADR-0005.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Confusion-group resolution is context-aware: votes are counted per
  occurrence, letter readings with no word shape are demoted, and
  art-model wins are exempt.  Fixed twelve EBCDIC and Latin files that
  were riding single-byte coin flips.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Statistical dead heats no longer resolve by candidate enumeration
  order.  Three tiebreaks: prefer the Windows superset, prefer the more
  prevalent era when there is no high-byte evidence, and prefer a
  classic-Mac candidate when line endings are bare ``\r``.
  (`Dan Blanchard <https://github.com/dan-blanchard>`_ via Claude)
- Training pipeline hardening after a cache-loss post-mortem: retrains
  that would silently drop a model now abort loudly, caches filter in
  place instead of being deleted wholesale, and the artpack fetcher
  builds into a temporary directory.
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
  post-processing; the markup stage's PEP 263 declaration sniffing was
  requested by `patrikha <https://github.com/patrikha>`_ in
  `#249 <https://github.com/chardet/chardet/issues/249>`_
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
  ``detect_all()``, and ``UniversalDetector``; chunked processing was
  proposed by `deedy5 <https://github.com/deedy5>`_ in
  `#284 <https://github.com/chardet/chardet/issues/284>`_
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

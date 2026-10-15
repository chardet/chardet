How It Works
============

chardet uses a multi-stage detection pipeline. Each stage either returns a
definitive result or passes to the next, progressing from cheap deterministic
checks to more expensive statistical analysis.

Detection Pipeline
------------------

When you call :func:`chardet.detect`, data flows through these stages in
order:

1. **BOM Detection** — Checks for a byte order mark at the start of the
   data. If found, returns ``UTF-8-SIG``, ``UTF-16``, ``UTF-32``, or
   ``utf-7`` with confidence 1.0, but only when the rest of the examined
   window decodes under that encoding; a mark on bytes that do not
   decode is passed over.

2. **UTF-16/32 Patterns** — Detects BOM-less UTF-16 and UTF-32 by
   analyzing null-byte patterns. Interleaved null bytes strongly indicate
   UTF-16; groups of three null bytes indicate UTF-32. ASCII records
   separated by nulls, such as ``find -print0`` output, are not UTF-16:
   when every non-null byte is printable ASCII and fewer than three
   quarters of the code units carry a null, the pattern is rejected.
   The result has to decode the whole window, like every other answer.

3. **Escape Sequences** — Identifies escape-based encodings like
   ISO-2022-JP, ISO-2022-KR, HZ-GB-2312, and UTF-7 by matching their
   characteristic escape byte sequences, then decoding the whole window
   to confirm.

4. **Magic Number Detection** — Identifies binary file types (PNG, JPEG,
   PDF, ZIP, etc.) by their magic number signatures. Returns immediately
   with ``encoding=None`` and a specific ``mime_type`` (e.g.,
   ``"image/png"``). ZIP-based formats like XLSX, DOCX, and EPUB are
   further distinguished by inspecting entry filenames.

5. **Binary Detection** — If more than 1% of the bytes are control
   bytes other than whitespace (nulls included), and the data is neither
   valid UTF-8, nor ASCII with sparse nulls, nor shaped like EBCDIC
   text, it is classified as binary (encoding ``None``).

6. **Markup Charset** — Extracts explicit charset declarations from
   ``<meta charset="...">`` tags and ``http-equiv="Content-Type"``
   content attributes, ``<?xml encoding="..."?>`` processing
   instructions (in EBCDIC as well as ASCII), and PEP 263
   ``# -*- coding: ... -*-`` cookies in the first two lines of Python
   source, where line 2 counts only when line 1 is blank or a comment.
   Markup declarations are read the way the WHATWG prescan reads them:
   comments are skipped, a UTF-16 label found in ASCII bytes is read as
   UTF-8, and ``x-user-defined`` means Windows-1252. A declaration
   counts only if the declared encoding, or its Windows superset for
   Shift_JIS and EUC-KR, decodes the whole examined window, and it does
   not override data that is valid multi-byte UTF-8, which is reported
   as UTF-8 with the markup MIME type.

7. **ASCII Check** — If every byte is printable ASCII, tab, newline, or
   carriage return, returns ``ascii`` at confidence 1.0. Sparse null
   separators, up to 5% of the data, are tolerated at 0.99.

8. **UTF-8 Validation** — Tests whether the data is valid UTF-8 by
   checking multi-byte sequence structure. UTF-8 has very distinctive
   byte patterns that are unlikely to occur in other encodings.

9. **Byte Validity Filtering** — Attempts to decode the data with each
   candidate encoding's Python codec. Any encoding that raises a decode
   error is eliminated. An incomplete multi-byte sequence at the very end
   of the data does not count as an error: detection input is usually a
   prefix of a larger whole, so a partial trailing character means the
   input was cut mid-character rather than that the encoding is wrong.
   This stage and the four after it read at most the first 256 KiB of
   the window, which is above the default ``max_bytes``; past that cap
   the winner is still decoded over the whole window, and a winner that
   fails yields to the next candidate that decodes.

10. **CJK Gating** — Eliminates CJK candidates that lack genuine
    multi-byte structure. Checks pair ratio, high-byte count, byte
    coverage, and lead byte diversity to prevent false CJK matches on
    single-byte data.

11. **Structural Probing** — For multi-byte encodings (CJK), analyzes
    byte sequences to verify they follow the encoding's structural rules
    (lead byte / trail byte patterns, valid ranges).

12. **Statistical Scoring** — Scores remaining candidates using pre-trained
    bigram frequency models. Each model captures the characteristic byte
    pair frequencies of a language written in a specific encoding. The
    candidate with the highest score wins.

13. **Post-processing** — Resolves confusion groups (encodings that are
    statistically hard to distinguish), demotes niche Latin encodings
    when a more common alternative scores similarly, and promotes KOI8-T
    when appropriate.  When statistical scores are effectively tied,
    small priors break the deadlock: a Windows code page wins a dead
    heat with its ISO subset, the more prevalent encoding era wins
    evidence-free dead heats, bare-``\r`` line endings promote
    classic-Mac candidates, and a winner from a language with no
    documented legacy-encoding population (say, Scottish Gaelic in
    ISO-8859-14) yields to a mainstream rival scoring within a hair.
    These priors only ever act inside narrow score bands — a genuine
    file in any supported language wins on its own evidence.  Last, a
    winner whose only multi-byte evidence is a sequence cut off at the
    end of the input yields to the best rival that decodes the complete
    input.

Confidence Scores
-----------------

The confidence score (0.0 to 1.0) reflects how the result was determined:

- **1.0** — BOM detected, pure ASCII, or a recognized binary file
  signature (encoding ``None`` with a specific ``mime_type``)
- **0.99** — ASCII with sparse null separators
- **0.95** — Deterministic match (escape sequences, markup charset,
  BOM-less UTF-16/32, binary detection)
- **0.80–0.99** — UTF-8 detection. Confidence scales with the proportion of
  multi-byte sequences in the data.
- **Usually below 0.95** — Statistical ranking. Higher scores mean the
  data better matches the encoding's expected byte pair frequencies. A
  CJK result whose high bytes almost all form valid multi-byte pairs is
  boosted and can reach 1.0.
- **0.10** — The ``no_match_encoding`` sentinel, returned when no
  candidate survives; if the sentinel itself is ruled out by the
  encoding filters, the result is encoding ``None`` at 0.0.

Internal pipeline stages may temporarily boost confidence above 1.0 for
ranking purposes; ``run_pipeline`` clamps all final results to [0.0, 1.0].

A confidence of ``0.95`` with encoding ``None`` means the data appears to be
binary (not text).

Language Detection
------------------

chardet also returns the detected language alongside the encoding. Language
detection uses three tiers:

1. **Single-language encodings** — Encodings like Big5 (Chinese), EUC-JP
   (Japanese), or ISO-8859-7 (Greek) unambiguously identify the language.

2. **Multi-language encoding models** — For encodings shared across
   languages (e.g., windows-1252 is used for French, German, Spanish,
   etc.), the language is the one whose bigram model won. When the
   encoding was ranked statistically, that is the model the ranking
   chose; when it came from a deterministic stage, such as a declared
   charset, the encoding's language models are scored here.

3. **UTF-8 fallback** — For any result still without a language, such
   as Unicode encodings (UTF-8, UTF-16, UTF-32) or ASCII, the text is
   transcoded to UTF-8 and scored against the UTF-8 bigram models for
   all supported languages.

Tiers 2 and 3 compare bigram profiles by cosine similarity, as the
encoding ranking does, but in a weighted space: the input's bigrams are
weighted by how rare each is across all models (its IDF), and each
language model is normalized under the square root of the same weights.
The encoding ranking weights only the input. That is right for telling
encodings apart, where the rare bigrams are the evidence, but with 49
languages in play it let one high-IDF bigram that two languages share,
such as the UTF-8 pair for ``é``, outweigh every bigram that tells them
apart, and French text came back Hungarian. Charging each model for its
own rare bigrams restores the common bigrams' vote.  On inputs under
128 bytes, a rare-language label (Scottish Gaelic, Welsh, Irish,
Breton) that leads the best mainstream language by less than 0.06 is
reported under the mainstream language instead.

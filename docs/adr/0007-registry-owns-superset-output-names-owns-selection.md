# Registry owns the superset relation, output_names owns the selection

Through 7.7.0 the "Windows superset" relation was written down three times: `output_names.PREFERRED_SUPERSET` (twelve pairs, applied by the `prefer_superset` option), `pipeline/markup.py`'s promotion table (Shift_JIS to CP932, EUC-KR to CP949), and `pipeline/postprocess.py`'s dead-heat table (the same two, plus a `shift_jis` key the pipeline never reports). Nothing kept them in step, and the dead key shows how easily they drift.

The codec fact now lives in one place: `EncodingInfo.superset` in `registry.py`, set for every pair the three tables named. The markup and dead-heat tables are derived from it at import time, filtered to `is_multibyte_cjk`, which reproduces them exactly. `PREFERRED_SUPERSET` stays a literal, because it is not the codec fact. It is the frozen *selection* the `prefer_superset` option applies, and it is this project's documented public surface through `UniversalDetector.LEGACY_MAP`. Tests pin its twelve pairs and check each one against the registry.

Resist "unify the tables" in either direction. Deriving `PREFERRED_SUPERSET` from the registry would add `shift_jis_2004 -> cp932` to it, which changes `prefer_superset=True` output and `LEGACY_MAP`; that is an 8.0 question. Dropping the `is_multibyte_cjk` filter would extend the dead-heat promotion to the ISO/Windows pairs, which is an accuracy change to measure on its own, not a refactor.

## Amendment: six pairs were never supersets

The twelve pairs included six whose Windows code page only resembles the ISO encoding: ISO-8859-2, -5, -6, -7, -8 and -13 against cp1250, cp1251, cp1256, cp1253, cp1255 and cp1257. From 0xA0 up, cp1251 reads 94 bytes differently from ISO-8859-5, cp1256 reads 25 differently from ISO-8859-6 (15 of them letters), cp1250 moves 15 characters, most of them Polish, Czech and Slovak letters, and the other three move a few quotes, currency signs and one Greek letter. `prefer_superset=True` therefore renamed a correct ISO-8859-5 or ISO-8859-6 answer to a name that garbles the text. For Hebrew it erased a signal the detector builds on purpose: ISO-8859-8 is how a visual-order page is told from logical-order Windows-1255.

Both `PREFERRED_SUPERSET` and `EncodingInfo.superset` now hold only true supersets, which are also exactly the labels the WHATWG Encoding Standard merges: ASCII and ISO-8859-1 into windows-1252, ISO-8859-9 into windows-1254, TIS-620 and ISO-8859-11 into windows-874, EUC-KR into its Windows-949 form. Tests pin the table, check each pair byte for byte from 0xA0 up, and check it against the WHATWG list.

This shrinks `LEGACY_MAP` in a 7.x release. That was accepted as a fix: for ISO-8859-2, -5 and -6 text the old output was wrong, and for the rest the new name decodes the examined bytes to the same text as the old one. The rule above still holds for additions: adding a pair, `shift_jis_2004 -> cp932` included, remains an 8.0 question.

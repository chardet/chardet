# Character Encoding Substitutions for Legacy Encodings

## Overview

When generating test files for legacy single-byte character encodings, many modern Unicode characters cannot be represented. This document explains the research findings and substitutions applied by `generate_test_files.py`.

## Research Summary

### 1. Typographic Punctuation

**Problem:** Modern Unicode includes typographic punctuation (en-dash, em-dash, ellipsis, smart quotes) that didn't exist in legacy encodings.

**Solution:** Replace with ASCII equivalents that were historically used:

| Unicode Character   | Code        | Legacy Substitute  | Rationale                                              |
| ------------------- | ----------- | ------------------ | ------------------------------------------------------ |
| – (en-dash)         | U+2013      | `-` (hyphen)       | Historical practice in typewriters and early computers |
| — (em-dash)         | U+2014      | `-` (hyphen)       | Same as en-dash                                        |
| … (ellipsis)        | U+2026      | `...` (three dots) | Standard before Unicode                                |
| ' ' (smart singles) | U+2018/2019 | `'` (apostrophe)   | ASCII fallback                                         |
| " " (smart doubles) | U+201C/201D | `"` (quote mark)   | ASCII fallback                                         |

**References:**

- Windows-1252 character set documentation
- Historical encoding practices for ASCII, ISO-8859-1

### 2. Arabic Punctuation

**Problem:** CP720 and CP864 have very limited Arabic character support. Some Arabic punctuation marks are not available.

**Solution:** Replace with ASCII equivalents:

| Unicode Character    | Code   | Legacy Substitute |
| -------------------- | ------ | ----------------- |
| ، (Arabic comma)     | U+060C | `,` (comma)       |
| ؛ (Arabic semicolon) | U+061B | `;` (semicolon)   |
| ٪ (Arabic percent)   | U+066A | `%` (percent)     |

**Note:** CP720 supports basic Arabic letters, but CP864 has even more limited support. ISO-8859-6 and Windows-1256 have better Arabic coverage.

### 3. Belarusian/Ukrainian Cyrillic 'і'

**Problem:** CP866 (DOS Cyrillic) was designed primarily for Russian and lacks the Belarusian/Ukrainian letter 'і' (U+0456, CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I).

**Why:** The letter 'і' was abolished in Russian orthography in 1918 but remains essential in Belarusian and Ukrainian. CP866 was designed for Russian only.

**Historical workaround:** According to research and DOS-era documentation, users substituted 'і' with Russian 'и' (U+0438, CYRILLIC SMALL LETTER I) when forced to use CP866. This is **linguistically incorrect** as these represent different phonemes, but it was the common practical solution.

**Implementation:** Our `apply_legacy_substitutions()` function implements this historical workaround:

- і (U+0456) → и (U+0438)
- І (U+0406) → И (U+0418)

**Important caveats:**

- This substitution is **semantically wrong** - 'і' and 'и' are different letters with different sounds
- It changes the meaning and spelling of words (e.g., "Білорусь" becomes "Билорусь")
- This was a historical necessity, not a recommended practice
- Modern alternatives (CP855, Windows-1251, ISO-8859-5, KOI8-U) all support 'і' properly

**Alternative encodings that support 'і':**

- CP855: 0x8A (lowercase), 0x8B (uppercase)
- ISO-8859-5: 0xF6 (lowercase), 0xA6 (uppercase)
- Windows-1251: 0xB3 (lowercase), 0xB2 (uppercase)
- KOI8-U: 0xA6 (lowercase), 0xB6 (uppercase)

**References:**

- Code Page 866 Wikipedia article
- GitHub issue #502 on far2l project discussing Ukrainian 'і' in CP866
- Unicode character database for U+0456

### 4. Vietnamese (Windows-1258)

**Problem:** Vietnamese uses three essential diacritics (circumflex â/ê/ô, breve ă, horn ơ/ư) **combined** with tone marks (acute, grave, hook above, tilde, dot below). This creates characters like ấ, ồ, ừ, ẵ.

**Understanding Windows-1258:** Unlike most encodings that use fully precomposed characters, Windows-1258 uses a **two-part system**:

- **Precomposed base letters** with diacritics: â, ê, ô, ă, ơ, ư, đ (7 characters)
- **Combining tone marks** that follow the base: grave (U+0300), acute (U+0301), tilde (U+0303), hook above (U+0309), dot below (U+0323)
- **Example:** The character ế (U+1EBF) is represented as `ê` (U+00EA) + combining acute (U+0301)

**Why this design:** This allows Windows-1258 to represent all Vietnamese letters using only the 7 special base letters plus 5 tone marks, rather than needing 100+ precomposed Unicode characters. It's similar to how Vietnamese was typed on typewriters.

**Solution:** Use a **custom normalization** for Windows-1258 that:

1. Starts with NFC (precomposed) to standardize input
2. Decomposes Vietnamese characters into base+tone form (e.g., ế → ê + acute)
3. Keeps the base letters precomposed (â, ê, ô stay intact, not decomposed to a+circumflex)

**Result:** This approach successfully encodes Vietnamese text in Windows-1258. Example:

- Input: "Tiếng Việt" (NFC, 10 characters)
- Normalized: "Tiếng Việt" (base+combining, 12 characters)
- Encoded: 12 bytes in Windows-1258
- Decodes back and normalizes to original ✓

**References:**

- Windows-1258 Wikipedia article
- Unicode Vietnamese character tables
- Testing with Python's codec library

### 5. Urdu (CP1006)

**Problem:** Python's CP1006 implementation uses **Arabic Presentation Forms** (U+FE70-U+FEFF, U+FB50-U+FDFF) instead of base Arabic letters (U+0600-U+06FF). This means:

- Standard Urdu text with base Arabic letters (ا ب پ ت) cannot be encoded directly
- CP1006 expects pre-shaped visual forms (ﺍ ﺑ ﭖ ﺕ) which require manual shaping
- This is similar to CP864 - it's a visual encoding, not a logical encoding

**Why this design:** CP1006 (like CP864) was designed for systems that couldn't do automatic Arabic shaping. Text had to be manually converted to presentation forms before encoding.

**Historical workarounds:** According to research on Pakistan computing history:

- **Manual shaping**: Text was preprocessed to convert base Arabic letters to their contextual presentation forms (isolated, initial, medial, final)
- **Ad-hoc encodings**: Custom character mappings were used before Unicode
- **Font-based solutions**: Specialized Urdu fonts (Noori Nastaliq, Jameel Noori Nastaliq) that handled shaping
- **Conversion tools**: Utilities to convert between CP1006, InPage format, and eventually Unicode

**Solution:** No practical workaround for automatic test file generation. The issue is that **CP1006 (in both IBM and Unicode Consortium specifications) uses Arabic KAF instead of Urdu KEHEH**, making it less suitable for Urdu text that uses KEHEH.

**Root cause analysis:** CP1006 is documented as an Urdu code page (see [IBM specification](https://public.dhe.ibm.com/software/globalization/gcoc/attachments/CP01006.txt) and [Unicode Consortium mapping](https://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/CP1006.TXT)). Python's implementation correctly matches the Unicode Consortium file. However, the spec itself uses:

- Byte 0xE3-0xE4: Arabic **KAF** (U+FED9, U+FEDB - ك with internal mark)
- Byte 0xE5-0xE6: **GAF** (U+FB92, U+FB94 - گ for "g" sound, Urdu-specific)
- **Missing**: Urdu **KEHEH** (U+FB8E, U+FB90 - ک with diagonal "sar-kesh" stroke)

**Why is this a problem?** In modern Urdu:

- KEHEH (ک) is the standard letter for the /k/ sound
- KAF (ك) is considered archaic or dialectal for Urdu
- These are **visually distinct**: KAF has an internal stroke, KEHEH has a diagonal top-right stroke
- Using KAF instead of KEHEH in Urdu is like using archaic spellings

Additionally, many medial/final presentation forms are missing (REH final, SEEN medial, TEH medial, BEH medial, LAM-ALEF ligature), making connected text difficult to encode.

**Testing results:** The `arabic-reshaper` library correctly converts base Arabic/Urdu letters to presentation forms. However, when tested with common Urdu words using KEHEH, only ~11% encode successfully because:

1. CP1006 spec uses KAF, not KEHEH
2. Many presentation forms are missing

**Historical context:** CP1006 dates from the 1980s and may predate the standardization of KEHEH for Urdu, or it may have been designed for a specific Urdu dialect/usage that preferred KAF. The specification has remained unchanged in Unicode since 1999.

**Not a Python bug:** Python correctly implements the Unicode Consortium specification. The limitation is in the CP1006 standard itself.

**Potential future improvement:** If there were demand for better Urdu support:

1. Could create a modified CP1006 variant that uses KEHEH instead of KAF
2. Add `arabic-reshaper` as an optional dependency
3. Reshape text before encoding
4. Success rate would likely improve significantly

For now, **documents will be skipped** due to the encoding's limitations.

**Note:** Windows-1256 uses base Arabic letters (logical encoding) and has better compatibility with modern Unicode text, though it still lacks some Urdu-specific characters. For proper Urdu support, Unicode is required.

### 6. Hebrew Visual Order (CP424, CP856, CP862)

**Problem:** These DOS-era Hebrew encodings were designed for systems without bidirectional (BiDi) rendering algorithms. Text was stored in "visual order" - the way it appears on screen when rendered left-to-right. Additionally, they only support the 27 basic Hebrew letters, not vowel points (nikud) or other diacritical marks.

**Character Support Limitations:**

- **Supported:** 27 Hebrew letters (U+05D0-U+05EA: א-ת) including final forms
- **Not Supported:** 
  - Vowel points/nikud (U+05B0-U+05C7): kamatz, patach, tzere, segol, etc.
  - Cantillation marks (U+0591-U+05AF)
  - Hebrew punctuation marks like maqaf
  - Other diacritical marks

This is acceptable because modern Hebrew text is typically written without vowel points (except in religious texts, poetry, and children's books).

**Understanding Visual vs. Logical Order:**

- **Logical Order** (Unicode/Modern): Text stored in reading order. Hebrew text stored right-to-left, but the BiDi algorithm handles display. Example: `"Hello שלום world"` stored as-is, BiDi reverses the Hebrew portion for display.

- **Visual Order** (DOS/Legacy): Text stored in display order. Hebrew sequences pre-reversed so simple left-to-right rendering displays correctly. Example: `"Hello םולש world"` (only Hebrew reversed, Latin/numbers unchanged).

**Why Only Hebrew is Reversed:**

DOS systems rendered all text left-to-right without BiDi. To display Hebrew correctly (which reads right-to-left), only the Hebrew character sequences were stored backwards. Latin text, numbers, and punctuation remained in normal left-to-right order since they display correctly that way.

**chardet's Implementation:**

From `chardet/sbcsgroupprober.py`, these encodings are configured with `is_reversed=True`:

```python
SingleByteCharSetProber(CP424_HEBREW_MODEL, is_reversed=True),
SingleByteCharSetProber(CP856_HEBREW_MODEL, is_reversed=True),
SingleByteCharSetProber(CP862_HEBREW_MODEL, is_reversed=True),
```

This tells chardet to perform language model lookups in reverse order, simulating visual Hebrew text.

**Solution:** When generating test files for CP424, CP856, or CP862:
1. Strip Hebrew vowel points and marks (U+0591-U+05CF, excluding letters)
2. Reverse only Hebrew character sequences (U+0590 to U+05FF) while preserving Latin text, numbers, and punctuation in normal order

**References:**

- `chardet/hebrewprober.py` - Detailed explanation of Visual vs Logical Hebrew
- IBM Code Page 424 specification
- DOS Hebrew rendering behavior documentation

### 7. Arabic (CP864)

**Problem:** CP864 is a visual encoding with extensive limitations:

- Only supports some contextual forms (isolated, initial, medial, final)
- Missing most Arabic diacritics (tashkeel) except Shadda
- No support for proper Arabic shaping or bidirectional text
- Lam-Alef and Yeh-Hamza require special handling

**Historical workarounds:** According to IBM documentation and DOS-era sources:

- **Manual shaping**: Text was preprocessed to convert Unicode to "presentation forms" before encoding
- **Bitmap rendering**: Arabic text rendered as images to bypass encoding limitations
- **Character splitting**: Composite characters split into valid CP864 sub-units
- **Bidirectional algorithms**: Manual implementation of RTL text ordering

**Solution:** No practical workaround for our test file generation. CP864 documents will mostly be skipped. Use ISO-8859-6 or Windows-1256 for better Arabic support.

**Note:** CP720, ISO-8859-6, and Windows-1256 all have better Arabic support and work with standard Unicode Arabic text (though still lack full contextual shaping).

## Implementation

### Character Substitutions Applied

The `apply_legacy_substitutions()` function in `generate_test_files.py` performs the following:

1. **Universal substitutions** (all encodings):

   - Typographic dashes → ASCII hyphen
   - Smart quotes → ASCII quotes
   - Ellipsis → Three dots
   - Bullets → Asterisk
   - Zero-width characters → Removed

2. **Arabic-specific substitutions** (CP720, CP864, ISO-8859-6):

   - Arabic punctuation → ASCII equivalents

3. **CP866-specific substitutions** (Belarusian/Ukrainian):

   - 'і' → 'и' (Ukrainian/Belarusian I → Russian I)
   - **Important:** This is linguistically incorrect but was the historical DOS-era workaround

4. **No substitution** for fundamentally incompatible encodings:
   - CP864, CP1006 (Arabic/Urdu) - require manual shaping and have extensive missing characters

### Unicode Normalization

**Most encodings:** Use NFC (precomposed) normalization

- Maximizes compatibility with legacy encoding character sets
- Western European, Cyrillic, Greek, etc. all expect precomposed forms

**Vietnamese (Windows-1258) only:** Use custom partial decomposition via `normalize_vietnamese_for_windows_1258()`

- Decomposes Vietnamese precomposed+tone characters (ế → ê + combining acute)
- This is the ONLY encoding requiring special handling

**Note on other combining characters:**

- Some encodings support combining characters natively (Windows-1255 for Hebrew nikud, TIS-620 for Thai tone marks, Arabic encodings for tashkeel)
- These work fine with standard text - no special handling needed
- Python's codec library handles them correctly

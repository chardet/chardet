# Bug Fixes in Model Training Code

This document summarizes the bugs found and fixed in the character encoding model training code.

## Background

The `create_language_model.py` script is used to train single-byte character set (SBCS) models for chardet. These models are essential for detecting character encodings. When models are trained with bugs, they produce incorrect results that cause detection failures.

## Bugs Fixed

### Bug #1: Missing `alphabet` Parameter in `get_charset_mappings` Call

**Location:** `create_language_model.py`, line 333 (in `generate_sbcs_model` function)

**Description:**
The `get_charset_mappings` function accepts an `alphabet` parameter that specifies which characters are valid letters for a language. This parameter is crucial for correctly categorizing characters during model generation. However, in the `generate_sbcs_model` function, when calling `get_charset_mappings`, the `alphabet` parameter was not being passed even though it was available as a function parameter.

**Impact:**
When `alphabet` is not passed, it defaults to an empty set inside `get_charset_mappings`. This means:
- For languages with `keep_ascii_letters=False`, NO letters would be recognized as valid
- Language-specific characters (e.g., Greek, Cyrillic, Arabic letters) would be categorized as UNDEFINED instead of being assigned their proper frequency ranks
- The resulting models would have no language-specific character information, making detection impossible

**Fix:**
```python
# Before (buggy):
char_to_order, charset_code_points = get_charset_mappings(
    charset_name, char_ranks, keep_ascii_letters
)

# After (fixed):
char_to_order, charset_code_points = get_charset_mappings(
    charset_name, char_ranks, keep_ascii_letters, alphabet
)
```

### Bug #2: Incorrect Bigram Creation When Skipping ASCII Letters

**Location:** `create_language_model.py`, lines 244-254 (in `calc_ngram_freqs` function)

**Description:**
When training models for languages that don't use ASCII letters (e.g., Greek, Cyrillic, Arabic), the code is supposed to skip ASCII letters. However, when an ASCII letter was encountered and skipped, the `prev_char` variable was not reset to `None`. This caused false bigrams to be created.

**Example:**
For the text "αbβ" (where α and β are Greek letters, and 'b' is ASCII to be skipped):
- Process 'α': char_freqs['α']++, prev_char = 'α'
- Skip 'b': continue (prev_char stays 'α') ← BUG!
- Process 'β': Creates bigram 'αβ', even though 'b' is between them

This creates artificial character sequences that don't actually exist in the training data.

**Impact:**
- False bigrams inflated frequency counts for character pairs that aren't actually adjacent
- Language models learned incorrect character transition patterns
- Detection accuracy was reduced because the models didn't reflect true character distributions

**Fix:**
```python
# Before (buggy):
if not keep_ascii_letters and unicode_char in ascii_letters:
    continue
char_freqs[unicode_char] += 1
if prev_char is not None:
    language_model[prev_char][unicode_char] += 1
    num_bigrams += 1
prev_char = unicode_char

# After (fixed):
if not keep_ascii_letters and unicode_char in ascii_letters:
    # Reset prev_char to avoid creating false bigrams
    prev_char = None
    continue
char_freqs[unicode_char] += 1
if prev_char is not None:
    language_model[prev_char][unicode_char] += 1
    num_bigrams += 1
prev_char = unicode_char
```

## Next Steps

After these bugs are fixed, the models need to be retrained using the corrected training code:

1. Run `create_language_model.py` for all affected languages
2. Replace the old model files in the `chardet/` directory
3. Run the test suite to verify improved detection accuracy

## Testing

Comprehensive tests were created to verify both fixes:

1. **Test 1:** Verified that the `alphabet` parameter is correctly passed through to `get_charset_mappings`
2. **Test 2:** Verified that bigrams are not created when ASCII letters are between non-ASCII characters
3. **Test 3:** Verified that `generate_sbcs_model` works correctly with the alphabet parameter

All tests pass with the fixes applied.

## Languages Affected

These bugs primarily affected languages that:
- Use non-ASCII alphabets (Greek, Cyrillic, Arabic, Hebrew, etc.)
- Have `use_ascii=False` in their language metadata

Languages with ASCII-based alphabets (like English, French, German) were less affected since they use `use_ascii=True`.

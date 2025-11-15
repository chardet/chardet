# Language Model Training Notes

## How language models should be built if we keep using "order" as non-encoding mapping (instead of unicode code points):

1. Calculate unicode frequencies of all code points in text files passed in
   for language.
2. Iterate through each code point in unicode frequency dict by descending
   frequency:
   1. If `rank` is less than `SAMPLE_SIZE` (64) and code point is a letter
      1. Add `code_point` to `frequent_non_symbols` set.
3. Initialize `frequenct_non_symbol_bigrams` Counter to cross-product of `frequent_non_symbols`
4. Calculate actual raw frequencies of all `frequent_non_symbol_bigrams`
   bigrams in corpora.
5. Iterate through bigram frequencies in descending order and collapse frequencies into language model...
   1. 512 most frequent sequences = SequenceLikelihood.POSITIVE
   2. 513-1024 most frequent = SequenceLikelihood.LIKELY
   3. frequency <= 3 = SequenceLikelihood.NEGATIVE
   4. Otherwise, SequenceLikelihood.UNLIKELY
6. For each charset:
   1. Build character to order map mapping from code points to charset prober categories or rank orders AND determine what the `SAMPLE_SIZE` most frequent non-symbols are:
      1. Iterate through unicode code points in corpus and their ranks in descending order:
      2. If code point is in encoding/charset...
         1. If code point is a letter...
            1. `char_to_order_map[code_point] = rank`
         2. If the code point is a non-letter, set
            `char_to_order_map[code_point]` to the appropriate
            SingleByteCharsetProber category.
      3. Otherwise, set `char_to_order_map[code_point]` to
         `SingleByteCharsetProber.UDF`.
   2. Calculate typical positive ratio for charset...
      1. (Number of SequenceLikelihood.POSITIVE sequences tokens) /
         (Total number of sequence tokens)
   3. Output `char_to_order_map`, `language_model`, `typical_positive_ratio`,
      `keep_ascii_letters`, `charset_name`, `language` as strings

## How language models should be built if we store info by unicode code points:

TODO: Update this next bit

1. Calculate unicode frequencies of all code points in text files passed in
   for language.
2. For each charset:
   1. Create `BYTES_TO_CODE_POINTS` dict that maps from charset bytes to their
      Unicode code points.
   2. Create `BYTES_TO_CATEGORIES` dict that maps from charset bytes in to
      their SingleByteCharsetProber categories (digit, control, cr/lf, symbol,
      letter).
3. Calculate bigram frequencies of all
4. Initialize `frequenct_non_symbol_bigrams` Counter to cross-product of `frequent_non_symbols`
5. Calculate actual raw frequencies of all `frequent_non_symbol_bigrams`
   bigrams in corpora.
6. Iterate through bigram frequencies in descending order and collapse frequencies into language model...
   1. 512 most frequent sequences = SequenceLikelihood.POSITIVE
   2. 513-1024 most frequent = SequenceLikelihood.LIKELY
   3. frequency <= 3 = SequenceLikelihood.NEGATIVE
   4. Otherwise, SequenceLikelihood.UNLIKELY
7. Calculate typical positive ratio for charset...
   1. (Number of SequenceLikelihood.POSITIVE sequences tokens) / Total number of sequence tokens
8. Output `char_to_order_map`, `language_model`, `typical_positive_ratio`,
   `keep_ascii_letters`, `charset_name`, `language`.

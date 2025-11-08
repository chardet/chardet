#!/usr/bin/env python

######################## BEGIN LICENSE BLOCK ########################
# Contributor(s):
#   10.02.2015 - helour - first attempt
#   08.08.2016 - Dan Blanchard - first usable release
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
#
######################### END LICENSE BLOCK #########################

"""
Create a language model for single byte character encoding detection based on
training data from the CulturaX dataset.
"""

import re
import sys
import unicodedata
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from collections import Counter, defaultdict
from collections.abc import Mapping
from functools import partial
from multiprocessing import Pool
from operator import itemgetter
from string import ascii_letters

try:
    from datasets import load_dataset

    HAVE_DATASETS = True
except Exception:
    HAVE_DATASETS = False
    load_dataset = None  # type: ignore

from chardet import __version__
from chardet.enums import CharacterCategory, SequenceLikelihood
from chardet.metadata.languages import LANGUAGES
from chardet.sbcharsetprober import SingleByteCharSetModel

# Convert ascii_letters into a set to make other ops easier
ascii_letters_set = set(ascii_letters)


POSITIVE_RANK_THRESOLD = 512
LIKELY_RANK_THRESOLD = 1024


def normalize_vietnamese_for_windows_1258(text: str) -> str:
    """Normalize Vietnamese text for Windows-1258 encoding.

    Windows-1258 uses a unique approach:
    - Precomposed base letters with circumflex/breve/horn: â, ê, ô, ă, ơ, ư
    - Combining tone marks: grave, acute, tilde, hook above, dot below

    Example: ế (U+1EBF) → ê (U+00EA) + combining acute (U+0301)

    This function decomposes Vietnamese precomposed+tone characters into
    the form Windows-1258 expects.
    """
    # Start with NFC to get consistent precomposed forms
    nfc = unicodedata.normalize("NFC", text)

    # Map Vietnamese precomposed characters to base+combining tone
    # This is the ONLY way Windows-1258 can represent these characters
    decomposition_map = {
        # Regular vowels + tones
        "à": "a\u0300",
        "á": "a\u0301",
        "ả": "a\u0309",
        "ã": "a\u0303",
        "ạ": "a\u0323",
        "è": "e\u0300",
        "é": "e\u0301",
        "ẻ": "e\u0309",
        "ẽ": "e\u0303",
        "ẹ": "e\u0323",
        "ì": "i\u0300",
        "í": "i\u0301",
        "ỉ": "i\u0309",
        "ĩ": "i\u0303",
        "ị": "i\u0323",
        "ò": "o\u0300",
        "ó": "o\u0301",
        "ỏ": "o\u0309",
        "õ": "o\u0303",
        "ọ": "o\u0323",
        "ù": "u\u0300",
        "ú": "u\u0301",
        "ủ": "u\u0309",
        "ũ": "u\u0303",
        "ụ": "u\u0323",
        "ỳ": "y\u0300",
        "ý": "y\u0301",
        "ỷ": "y\u0309",
        "ỹ": "y\u0303",
        "ỵ": "y\u0323",
        # â (circumflex) + tones
        "ấ": "â\u0301",
        "ầ": "â\u0300",
        "ẩ": "â\u0309",
        "ẫ": "â\u0303",
        "ậ": "â\u0323",
        # ê (circumflex) + tones
        "ế": "ê\u0301",
        "ề": "ê\u0300",
        "ể": "ê\u0309",
        "ễ": "ê\u0303",
        "ệ": "ê\u0323",
        # ô (circumflex) + tones
        "ố": "ô\u0301",
        "ồ": "ô\u0300",
        "ổ": "ô\u0309",
        "ỗ": "ô\u0303",
        "ộ": "ô\u0323",
        # ă (breve) + tones
        "ắ": "ă\u0301",
        "ằ": "ă\u0300",
        "ẳ": "ă\u0309",
        "ẵ": "ă\u0303",
        "ặ": "ă\u0323",
        # ơ (horn) + tones
        "ớ": "ơ\u0301",
        "ờ": "ơ\u0300",
        "ở": "ơ\u0309",
        "ỡ": "ơ\u0303",
        "ợ": "ơ\u0323",
        # ư (horn) + tones
        "ứ": "ư\u0301",
        "ừ": "ư\u0300",
        "ử": "ư\u0309",
        "ữ": "ư\u0303",
        "ự": "ư\u0323",
        # Uppercase variants
        "À": "A\u0300",
        "Á": "A\u0301",
        "Ả": "A\u0309",
        "Ã": "A\u0303",
        "Ạ": "A\u0323",
        "È": "E\u0300",
        "É": "E\u0301",
        "Ẻ": "E\u0309",
        "Ẽ": "E\u0303",
        "Ẹ": "E\u0323",
        "Ì": "I\u0300",
        "Í": "I\u0301",
        "Ỉ": "I\u0309",
        "Ĩ": "I\u0303",
        "Ị": "I\u0323",
        "Ò": "O\u0300",
        "Ó": "O\u0301",
        "Ỏ": "O\u0309",
        "Õ": "O\u0303",
        "Ọ": "O\u0323",
        "Ù": "U\u0300",
        "Ú": "U\u0301",
        "Ủ": "U\u0309",
        "Ũ": "U\u0303",
        "Ụ": "U\u0323",
        "Ỳ": "Y\u0300",
        "Ý": "Y\u0301",
        "Ỷ": "Y\u0309",
        "Ỹ": "Y\u0303",
        "Ỵ": "Y\u0323",
        "Ấ": "Â\u0301",
        "Ầ": "Â\u0300",
        "Ẩ": "Â\u0309",
        "Ẫ": "Â\u0303",
        "Ậ": "Â\u0323",
        "Ế": "Ê\u0301",
        "Ề": "Ê\u0300",
        "Ể": "Ê\u0309",
        "Ễ": "Ê\u0303",
        "Ệ": "Ê\u0323",
        "Ố": "Ô\u0301",
        "Ồ": "Ô\u0300",
        "Ổ": "Ô\u0309",
        "Ỗ": "Ô\u0303",
        "Ộ": "Ô\u0323",
        "Ắ": "Ă\u0301",
        "Ằ": "Ă\u0300",
        "Ẳ": "Ă\u0309",
        "Ẵ": "Ă\u0303",
        "Ặ": "Ă\u0323",
        "Ớ": "Ơ\u0301",
        "Ờ": "Ơ\u0300",
        "Ở": "Ơ\u0309",
        "Ỡ": "Ơ\u0303",
        "Ợ": "Ơ\u0323",
        "Ứ": "Ư\u0301",
        "Ừ": "Ư\u0300",
        "Ử": "Ư\u0309",
        "Ữ": "Ư\u0303",
        "Ự": "Ư\u0323",
    }

    result = []
    for char in nfc:
        result.append(decomposition_map.get(char, char))

    return "".join(result)


def normalize_name(charset_name: str):
    """Convert name to proper Python constant format"""
    # Title case to start
    charset_name = charset_name.upper()
    # Underscores instead of hyphens
    charset_name = charset_name.replace("-", "_")
    return charset_name


def unicode_to_category(
    *,
    unicode_char: str,
    char_ranks: dict[str, int],
    alphabet_set: set[str] | None = None,
) -> int:
    """Convert a Unicode character to categories used by SingleByteCharSetProber

    If alphabet_set is provided, any character in it will be treated as a letter
    regardless of its Unicode category. This is important for languages that use
    combining marks (like Vietnamese) or other non-letter characters as part of
    their alphabet.
    """
    # If this character is in the language's alphabet, treat it as a letter
    if alphabet_set is not None and unicode_char in alphabet_set:
        ret_val = char_ranks.get(unicode_char, 0)
    elif unicode_char in ("\r", "\n"):
        ret_val = CharacterCategory.LINE_BREAK
    else:
        # Fall back to Unicode category-based classification
        unicode_cat = unicodedata.category(unicode_char)
        if unicode_cat.startswith("N"):
            ret_val = CharacterCategory.DIGIT
        # Valid letters have their category set to their order/rank
        elif unicode_cat.startswith("L"):
            ret_val = char_ranks.get(unicode_char, 0)
        # Punctuation, Symbols, and Marks are all symbols as far as we care
        elif unicode_cat.startswith(("P", "S", "M")):
            ret_val = CharacterCategory.SYMBOL
        else:
            ret_val = CharacterCategory.CONTROL
    return ret_val


def get_charset_mappings(
    *,
    charset_name: str,
    char_ranks: dict[str, int],
    alphabet_set: set[str],
    keep_ascii_letters=False,
) -> tuple[dict[int, CharacterCategory], dict[str, bytes]]:
    """Returns `charset_categories` & `charset_code_points` mappings for charset

    `charset_categories` maps from bytes in charset/encoding to categories
    expected by SingleByteCharSetProber except for letters, which have their
    category set to `None`. These will be modified later to map to an "order",
    which is the frequency ranking of each non-symbol character.

    `charset_code_points` maps from unicode code points to charset bytes. This
    is handy for quickly determining what code points are in the encoding.

    It seems like there should be a simpler way to pull these out of the Python
    `encodings` module, but only some encodings have tables in there.
    """
    char_to_order = {}
    charset_code_points = {}
    # 0 - 256 = all possible values for a single byte
    for byte_hex in range(0x0, 0x100):
        # Convert to bytes in Python 2 and 3
        char = bytes((byte_hex,))
        try:
            unicode_char = char.decode(charset_name)
            char_cat = unicode_to_category(
                unicode_char=unicode_char,
                char_ranks=char_ranks,
                alphabet_set=alphabet_set,
            )
            charset_code_points[unicode_char] = char
        except UnicodeDecodeError:
            char_cat = CharacterCategory.UNDEFINED
        char_to_order[byte_hex] = char_cat
    return char_to_order, charset_code_points


def gen_input_lines(input_paths: list[str], input_encoding: str):
    """Yield decoded lines from files in input_paths (for backward compatibility)"""
    for input_path in input_paths:
        with open(input_path, encoding=input_encoding) as input_file:
            yield from input_file


def gen_culturax_lines(
    *,
    language: str,
    num_docs: int | None,
):
    """Generate lines from CulturaX dataset for the given language.

    Args:
        language: ISO language code (e.g., 'en', 'fr', 'de')
        num_docs: Number of documents to process (None means all available)
    """
    if not HAVE_DATASETS:
        raise ValueError(
            "The datasets package is required. Install with: pip install datasets"
        )

    print(f"Loading CulturaX dataset for language: {language}")
    print("(This may take a few moments on first run while downloading/caching)")
    assert load_dataset is not None
    dataset = load_dataset(
        "uonlp/CulturaX",
        language,
        split="train",
        streaming=True,
    )

    char_count = 0
    for doc_count, item in enumerate(dataset):
        text = item.get("text", "")  # type: ignore
        if not text:
            continue

        # Clean up repeated whitespace
        text = re.sub(r"(\s)\1+", r"\1", text)

        for line in text.splitlines(True):
            yield line
            char_count += len(line)

        if num_docs is not None and doc_count >= num_docs:
            print(
                f"\nProcessed {doc_count:,} documents ({char_count:,} characters) from CulturaX"
            )
            return


def calc_ngram_freqs(
    *,
    input_generator,
    alphabet_set: set[str],
    language: str | None = None,
):
    """Create a language model with the likelihoods of all bigrams in input.

    This LM is based on Unicode code point frequencies and not encoded character
    frequencies so that this can be used for all encodings.

    The LM is filtered down to bigrams to those with unigrams that have
    frequencies greater than equal to the lowest seen alphabet character
    frequency.

    For Vietnamese, special normalization is applied to decompose precomposed
    characters with tone marks (e.g., ế → ê + combining acute) to match how
    Windows-1258 encoding actually represents Vietnamese text.
    """
    char_freqs = Counter()
    char_ranks = {}
    language_model = defaultdict(Counter)
    size_in_bytes = 0

    # Calculate unfiltered frequencies
    for line in input_generator:
        prev_char = None
        # Normalize so that combining and non-combining forms are
        # counted as the same, and because this is meant for single-byte
        # encodings, which don't support combining forms
        line = unicodedata.normalize("NFC", line)

        # Vietnamese requires special handling because Windows-1258 uses
        # combining tone marks rather than precomposed characters
        if language == "Vietnamese":
            line = normalize_vietnamese_for_windows_1258(line)

        size_in_bytes += len(line.encode("utf-8"))
        for unicode_char in line:
            # Only consider alphabet characters for this language
            if unicode_char not in alphabet_set:
                prev_char = None
                continue
            char_freqs[unicode_char] += 1
            if prev_char is not None:
                language_model[prev_char][unicode_char] += 1
            prev_char = unicode_char

    num_tokens = sum(char_freqs.values())
    print(
        f"\nUnique letter types in training data: {len(char_freqs):,}\n"
        f"Number of letter tokens in training data: {num_tokens:,}\n"
        f"Size of training data in bytes: {size_in_bytes:,}"
    )
    missing_letters = alphabet_set - set(char_freqs.keys())
    if missing_letters:
        raise ValueError(
            f"Training data is missing the following letters: "
            f"{', '.join(sorted(missing_letters))}"
        )
    # Filter language model down to only those within sample size
    for rank, (unicode_char, _) in enumerate(
        sorted(list(char_freqs.items()), key=itemgetter(1), reverse=True), 1
    ):
        char_ranks[unicode_char] = rank

    return char_ranks, language_model


def collapse_language_model_freqs(
    *,
    language_model: dict[str, Counter[str]],
    alphabet_set: set[str],
):
    """Collapse bigram frequencies to SequenceLikelihood categories"""
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # Collapse bigram frequencies to SequenceLikelihood categories
    for rank, (_, first_char, second_char) in enumerate(sorted_lm, 1):
        if rank <= POSITIVE_RANK_THRESOLD:
            language_model[first_char][second_char] = SequenceLikelihood.POSITIVE
        elif rank <= LIKELY_RANK_THRESOLD:
            language_model[first_char][second_char] = SequenceLikelihood.LIKELY
        else:
            language_model[first_char][second_char] = SequenceLikelihood.UNLIKELY

    # Make sure all possible bigrams are represented in the model
    for unicode_char1 in alphabet_set:
        for unicode_char2 in alphabet_set:
            if unicode_char2 not in language_model[unicode_char1]:
                language_model[unicode_char1][unicode_char2] = (
                    SequenceLikelihood.NEGATIVE
                )


def flatten_language_model(language_model):
    """Yield items from model as (count, first_char, second_char) tuples"""
    for first_char, sub_dict in language_model.items():
        for second_char, count in sub_dict.items():
            yield count, first_char, second_char


def generate_sbcs_model(
    *,
    charset_name: str,
    language: str,
    language_model: Mapping[str, Mapping[str, int]],
    char_ranks: dict[str, int],
    keep_ascii_letters: bool,
    alphabet_set: set[str],
):
    """Create a SingleByteCharSetModel object representing the charset."""
    # Setup tables necessary for computing transition frequencies for model
    char_to_order, charset_code_points = get_charset_mappings(
        charset_name=charset_name,
        char_ranks=char_ranks,
        keep_ascii_letters=keep_ascii_letters,
        alphabet_set=alphabet_set,
    )

    # Calculate positive ratio for charset by counting positive likelihood
    # bigrams where both characters are in charset
    # IMPORTANT: We only count bigrams that can be encoded in this charset
    # in both the numerator AND denominator, because at detection time
    # SingleByteCharsetProber.feed() removes characters that can't be encoded.
    pos_count = 0
    likely_count = 0
    charset_bigram_count = 0
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # Count bigrams encodable in this charset and mark top ones as POSITIVE
    for rank, (count, first_char, second_char) in enumerate(sorted_lm, 1):
        # Only consider bigrams where both chars can be encoded in this charset
        if first_char in charset_code_points and second_char in charset_code_points:
            charset_bigram_count += count
            if rank <= POSITIVE_RANK_THRESOLD:
                pos_count += count
            elif rank <= LIKELY_RANK_THRESOLD:
                likely_count += count

    # Ratio is: "Of bigrams this charset can encode, what % are POSITIVE?"
    # Not: "Of all UTF-8 bigrams (including un-encodable), what % are POSITIVE?"
    pos_ratio = (pos_count / charset_bigram_count) if charset_bigram_count else 0

    curr_model = SingleByteCharSetModel(
        charset_name=charset_name,
        language=language,
        char_to_order_map=char_to_order,
        # language_model is filled in later
        language_model=None,  # type: ignore
        typical_positive_ratio=pos_ratio,
        keep_ascii_letters=keep_ascii_letters,
        alphabet="".join(sorted(alphabet_set)),
    )
    return curr_model


def print_char_to_order(var_name, order_map, charset_name, output_file):
    print(f"{var_name} = {{", file=output_file)
    for char, order in sorted(order_map.items()):
        char_bytes = bytes(bytearray((char,)))
        try:
            unicode_char = char_bytes.decode(charset_name)
        except UnicodeError:
            unicode_char = None
        print(
            (
                f"     {char!r}: "
                f"{f'CharacterCategory.{order.name}' if isinstance(order, CharacterCategory) else order}"
                f",  # {unicode_char!r}"
            ),
            file=output_file,
        )
    print("}\n", file=output_file)


def print_language_model(var_name, language_model, output_file, char_ranks):
    print(f"{var_name} = {{", file=output_file)
    for first_char, sub_dict in sorted(language_model.items()):
        # Skip empty sub_dicts
        if not sub_dict:
            continue
        print(
            f"    {char_ranks[first_char]!r}: {{  # {first_char!r}",
            file=output_file,
        )
        for second_char, likelihood in sorted(sub_dict.items()):
            print(
                f"        {char_ranks[second_char]!r}: SequenceLikelihood.{likelihood.name},  # {second_char!r}",
                file=output_file,
            )
        print("    },", file=output_file)
    print("}\n", file=output_file)


def train_model_for_lang(
    language: str,
    *,
    input_encoding: str,
    input_paths: list[str],
):
    """Train a SingleByteCharSetModel for the given language"""
    # Validate language
    language = language.title()
    lang_metadata = LANGUAGES.get(language)
    if not lang_metadata:
        raise ValueError(
            f"Unknown language: {language}. If you are adding a model for a"
            " new language, you must first update metadata/"
            "languages.py"
        )

    print(
        f"\n{language}\n----------------------------------------------------------------\n"
        f"Keep ASCII Letters: {lang_metadata.use_ascii}\n"
        f"Alphabet: {lang_metadata.alphabet}\n"
        f"Data Source: {'Custom files' if input_paths else f'CulturaX ({lang_metadata.num_training_docs:,} docs)' if lang_metadata.num_training_docs else 'CulturaX (all docs)'}"
    )

    # Setup input generator
    if input_paths:
        # Use custom input files if provided
        input_gen = gen_input_lines(input_paths, input_encoding)
        data_size_str = "custom files"
    else:
        # Use CulturaX dataset
        if not HAVE_DATASETS:
            raise ValueError(
                "The datasets package is required. Install with: pip install datasets"
            )
        input_gen = gen_culturax_lines(
            language=lang_metadata.iso_code,
            num_docs=lang_metadata.num_training_docs,
        )
        data_size_str = "CulturaX"

    print(
        f"\nCreating character frequency tables for {language} from {data_size_str} training data"
    )
    sys.stdout.flush()
    alphabet_set = set(lang_metadata.alphabet)
    char_ranks, language_model = calc_ngram_freqs(
        input_generator=input_gen,
        alphabet_set=alphabet_set,
        language=language,
    )

    # Create char-to-order maps (aka char-to-rank dicts)
    charset_models = {}
    for charset_name in lang_metadata.charsets:
        print(f"Creating charset model for {charset_name}")
        sys.stdout.flush()
        charset_models[charset_name] = generate_sbcs_model(
            charset_name=charset_name,
            language=language,
            language_model=language_model,
            char_ranks=char_ranks,
            keep_ascii_letters=lang_metadata.use_ascii,
            alphabet_set=alphabet_set,
        )

    # Collapse language model freqs to SequenceLikelihood values after
    # calculating positive ratio for each charset
    collapse_language_model_freqs(
        language_model=language_model,
        alphabet_set=alphabet_set,
    )

    # Write output files
    print(f"Writing output file for {language}\n\n")
    sys.stdout.flush()
    with open(f"lang{language.lower().replace(' ', '')}model.py", "w") as output_file:
        upper_lang = language.upper().replace(" ", "_")
        # print header to set encoding
        print(
            (
                "from chardet.enums import CharacterCategory, SequenceLikelihood\n"
                "from chardet.sbcharsetprober import SingleByteCharSetModel\n\n"
            ),
            file=output_file,
        )

        lm_name = f"{upper_lang}_LANG_MODEL"
        print_language_model(lm_name, language_model, output_file, char_ranks)

        print(
            "# Character Mapping Table(s):",
            file=output_file,
        )
        for charset_name, sbcs_model in charset_models.items():
            normal_name = normalize_name(charset_name)
            char_to_order_name = f"{normal_name}_{upper_lang}_CHAR_TO_ORDER"
            print_char_to_order(
                char_to_order_name,
                sbcs_model.char_to_order_map,
                charset_name,
                output_file,
            )

            sbcs_model_name = f"{normal_name}_{upper_lang}_MODEL"
            sbcs_model.char_to_order_map.clear()
            sbcs_model_repr = (
                repr(sbcs_model)
                .replace("None", lm_name)
                .replace("{}", char_to_order_name)
                .replace(", ", (",\n" + " " * (len(sbcs_model_name) + 26)))
            )
            print(f"{sbcs_model_name} = {sbcs_model_repr}\n", file=output_file)


def main():
    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "language",
        help="The name of the language the input documents are "
        "in. Also the name of the language the generated "
        "model will detect. If no language is specified, "
        "models for all languages known to chardet will be"
        " trained.",
        nargs="*",
        default=list(sorted(LANGUAGES.keys())),
    )
    parser.add_argument(
        "-e",
        "--input-encoding",
        help="Encoding the input files are in (only used with --input-files).",
        default="UTF-8",
    )
    parser.add_argument(
        "-i",
        "--input-files",
        help="Custom training files to use instead of CulturaX. "
        "If not specified, will use CulturaX dataset.",
        nargs="*",
        dest="input_paths",
    )
    parser.add_argument(
        "-p",
        "--parallel-langs",
        help="Number of language models to train at once.",
        type=int,
        default=8,
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    # Validate requirements
    if not args.input_paths and not HAVE_DATASETS:
        raise ValueError(
            "The datasets package is required to use CulturaX. "
            "Install with: pip install datasets\n"
            "Or provide custom training files with --input-files"
        )

    # Make sure we aren't trying to do anything weird
    if len(args.language) > 1 and args.input_paths:
        raise ValueError(
            "Specifying input paths is not valid when training"
            " models for multiple languages at the same time."
        )

    # Only create multiprocessing pool if doing things in parallel, otherwise
    # it's harder to debug
    if args.parallel_langs > 1 and len(args.language) > 1:
        pool = Pool(args.parallel_langs)
        pool.map_async(
            partial(
                train_model_for_lang,
                input_encoding=args.input_encoding,
                input_paths=args.input_paths,
            ),
            args.language,
        )
        pool.close()
        pool.join()
    else:
        for language in args.language:
            train_model_for_lang(
                language,
                input_encoding=args.input_encoding,
                input_paths=args.input_paths,
            )


if __name__ == "__main__":
    main()

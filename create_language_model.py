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
the given file(s).
"""

import os
import re
import sys
import unicodedata
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from collections import Counter, defaultdict
from functools import partial
from multiprocessing import Pool
from operator import itemgetter
from string import ascii_letters
from typing import Iterable

try:
    from mediawiki import MediaWiki

    HAVE_WIKIPEDIA = True
except Exception:
    HAVE_WIKIPEDIA = False

from chardet import __version__
from chardet.enums import CharacterCategory, SequenceLikelihood
from chardet.metadata.languages import LANGUAGES
from chardet.sbcharsetprober import SingleByteCharSetModel

# Convert ascii_letters into a set to make other ops easier
ascii_letters_set = set(ascii_letters)


def normalize_name(charset_name):
    """Convert name to proper Python constant format"""
    # Title case to start
    charset_name = charset_name.upper()
    # Underscores instead of hyphens
    charset_name = charset_name.replace("-", "_")
    return charset_name


def unicode_to_category(
    *,
    unicode_char: str,
    char_ranks: dict,
    keep_ascii_letters: bool = False,
    alphabet: set[str] | None = None,
) -> CharacterCategory:
    """Convert a Unicode character to categories used by SingleByteCharSetProber"""
    if alphabet is None:
        alphabet = set()
    valid_letters = (alphabet | ascii_letters_set) if keep_ascii_letters else alphabet
    unicode_cat = unicodedata.category(unicode_char)
    if unicode_cat.startswith("N"):
        ret_val = CharacterCategory.DIGIT
    # Valid letters have their category set to their order/rank
    elif unicode_cat.startswith("L"):
        if unicode_char in valid_letters:
            ret_val = char_ranks.get(unicode_char, CharacterCategory.UNDEFINED)
        else:
            ret_val = CharacterCategory.UNDEFINED
    elif unicode_char in ("\r", "\n"):
        ret_val = CharacterCategory.LINE_BREAK
    # Punctuation, Symbols, and Marks are all symbols as far as we care
    elif unicode_cat.startswith(("P", "S", "M")):
        ret_val = CharacterCategory.SYMBOL
    else:
        ret_val = CharacterCategory.CONTROL
    return ret_val


def get_charset_mappings(
    *, charset_name, char_ranks, keep_ascii_letters=False, alphabet=None
):
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
        char = bytes(bytearray((byte_hex,)))
        try:
            unicode_char = char.decode(charset_name)
            char_cat = unicode_to_category(
                unicode_char=unicode_char,
                char_ranks=char_ranks,
                keep_ascii_letters=keep_ascii_letters,
                alphabet=alphabet,
            )
            charset_code_points[unicode_char] = char
        except UnicodeDecodeError:
            char_cat = CharacterCategory.UNDEFINED
        char_to_order[byte_hex] = char_cat
    return char_to_order, charset_code_points


def gen_input_lines(input_paths, input_encoding):
    """Yield decoded lines from files in input_paths"""
    for input_path in input_paths:
        with open(input_path, encoding=input_encoding) as input_file:
            yield from input_file


def gen_wiki_lines(
    *,
    titles: Iterable[str],
    language: str,
    max_depth: int,
    max_pages: int | None = None,
    depth: int = 0,
    visited_pages: set[str] | None = None,
    skipped_pages: set[str] | None = None,
    wikipedia: "MediaWiki | None" = None,  # type: ignore
):
    """Generate lines from Wikipedia articles, starting with titles.

    Will crawl at most `max_depth` deep in the page hierarchy.
    """
    if visited_pages is None:
        visited_pages = set()

    if skipped_pages is None:
        skipped_pages = set()

    if (
        not titles
        or depth > max_depth
        or (max_pages is not None and len(visited_pages) > max_pages)
    ):
        print(
            f"Visited {language} pages: {len(visited_pages)} ({len(skipped_pages)} skipped)"
        )
        return

    # Visit all pages in titles and add their links to next_titles
    next_titles = set()
    for title in titles:
        if title in visited_pages or title in skipped_pages:
            continue
        print(
            f"Visited {language} pages: {len(visited_pages)} ({len(skipped_pages)} skipped)",
            end="\r",
        )
        sys.stdout.flush()
        if max_pages is not None and len(visited_pages) == max_pages:
            break
        try:
            if wikipedia is None:
                raise ValueError("Wikipedia instance is required")
            page = wikipedia.page(title, auto_suggest=False)
            # Remove Wikipedia markup (this is inside of try block because it
            # does an implicit request to Wikipedia to get the content)
            content = re.sub(r"(=+) *([^=]+) *\1", r"\2", page.content)
            # Clean up repeated whitespace, since that could skew model
            content = re.sub(r"(\s)\1+", r"\1", content)
        except Exception:
            if depth > 0:
                skipped_pages.add(title)
                continue
            else:
                print("Failed to visit start page:")
                raise

        visited_pages.add(title)

        yield from content.splitlines(True)

        # Sometimes things go wrong when extracting the links
        try:
            next_titles.update(page.links)
        except Exception:
            continue

    # Recursive generators are fun
    yield from gen_wiki_lines(
        titles=next_titles,
        language=language,
        max_depth=max_depth,
        max_pages=max_pages,
        depth=depth + 1,
        visited_pages=visited_pages,
        skipped_pages=skipped_pages,
        wikipedia=wikipedia,
    )


def calc_ngram_freqs(
    input_generator, alphabet, keep_ascii_letters, save_training_data, training_path
):
    """Create a language model with the likelihoods of all bigrams in input.

    This LM is based on Unicode code point frequencies and not encoded character
    frequencies so that this can be used for all encodings.

    The LM is filtered down to bigrams to those with unigrams that have
    frequencies greater than equal to the lowest seen alphabet character
    frequency.
    """
    char_freqs = Counter()
    char_ranks = {}
    language_model = defaultdict(Counter)
    num_bigrams = 0
    size_in_bytes = 0
    if os.path.exists(training_path):
        print(
            f"\nTraining data file {training_path} already exists. Keeping existing file."
        )
        save_training_data = False
    training_output_file = None
    if save_training_data:
        training_output_file = open(training_path, "w", encoding="utf-8")
    # Calculate unfiltered frequencies
    for line in input_generator:
        prev_char = None
        # Normalize so that combining and non-combining forms are
        # counted as the same, and because this is meant for single-byte
        # encodings, which don't support combining forms
        line = unicodedata.normalize("NFC", line)
        if save_training_data:
            print(line, file=training_output_file)
        size_in_bytes += len(line.encode("utf-8"))
        for unicode_char in line:
            # Skip ASCII letters if we're supposed to
            if not keep_ascii_letters and unicode_char in ascii_letters_set:
                # Reset prev_char to avoid creating false bigrams
                prev_char = None
                continue
            char_freqs[unicode_char] += 1
            if prev_char is not None:
                language_model[prev_char][unicode_char] += 1
                num_bigrams += 1
            prev_char = unicode_char
    if training_output_file is not None:
        training_output_file.close()

    num_tokens = sum(char_freqs.values())
    print(
        f"\nUnique character types in training data: {len(char_freqs):,}\n"
        f"Number of character tokens in training data: {num_tokens:,}\n"
        f"Size of training data in bytes: {size_in_bytes:,}"
    )
    min_alpha_freq = min(
        freq for unicode_char, freq in char_freqs.items() if unicode_char in alphabet
    )

    # Filter language model down to only those within sample size
    for rank, (unicode_char, freq) in enumerate(
        sorted(list(char_freqs.items()), key=itemgetter(1), reverse=True), 1
    ):
        if rank >= CharacterCategory.CONTROL or freq < min_alpha_freq:
            del char_freqs[unicode_char]
            language_model.pop(unicode_char, None)
            for sub_dict in language_model.values():
                sub_dict.pop(unicode_char, None)
        # TODO: Consider changing this next part to only work for letters in
        #       alphabet
        else:
            char_ranks[unicode_char] = rank
            # Set all unseen combos involving this character to NEGATIVE
            # Note: We do this here instead of in SingleByteCharSetProber
            # because this is much faster than doing .get(char, 0) in there.
            for sub_dict in language_model.values():
                if unicode_char not in sub_dict:
                    sub_dict[unicode_char] = SequenceLikelihood.NEGATIVE
    return char_ranks, language_model, num_bigrams


def collapse_language_model_freqs(language_model, sequence_count_threshold):
    """Collapse bigram frequencies to SequenceLikelihood categories"""
    num_unigram_types = len(language_model)
    pos_threshold = min(num_unigram_types * 8, 512)  # Used to be 64 * 8 = 512
    likely_threshold = min(num_unigram_types * 16, 1024)  # Used to be 64 * 16 = 1024

    # # Use fixed thresholds that match the original design
    # pos_threshold = 512  # Top 512 bigrams are "positive"
    # likely_threshold = 1024  # Top 1024 bigrams are "positive" or "likely"

    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # Collapse bigram frequencies to SequenceLikelihood categories
    for rank, (count, first_char, second_char) in enumerate(sorted_lm, 1):
        if rank <= pos_threshold:
            language_model[first_char][second_char] = SequenceLikelihood.POSITIVE
        elif rank <= likely_threshold:
            language_model[first_char][second_char] = SequenceLikelihood.LIKELY
        # Really infrequent bigrams are considered illegal
        elif count <= sequence_count_threshold:
            language_model[first_char][second_char] = SequenceLikelihood.NEGATIVE
        else:
            language_model[first_char][second_char] = SequenceLikelihood.UNLIKELY


def flatten_language_model(language_model):
    """Yield items from model as (count, first_char, second_char) tuples"""
    for first_char, sub_dict in language_model.items():
        for second_char, count in sub_dict.items():
            yield count, first_char, second_char


def generate_sbcs_model(
    *,
    charset_name,
    language,
    language_model,
    num_bigrams,
    char_ranks,
    keep_ascii_letters,
    alphabet,
):
    """Create a SingleByteCharSetModel object representing the charset."""
    # Setup tables necessary for computing transition frequencies for model
    char_to_order, charset_code_points = get_charset_mappings(
        charset_name=charset_name,
        char_ranks=char_ranks,
        keep_ascii_letters=keep_ascii_letters,
        alphabet=alphabet,
    )

    # Calculate positive ratio for charset by counting positive likelihood
    # bigrams where both characters are in charset
    # IMPORTANT: We only count bigrams that can be encoded in this charset
    # in both the numerator AND denominator, because at detection time
    # filter_international_words() removes characters that can't be encoded.
    pos_count = 0
    charset_bigram_count = 0
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)
    pos_threshold = len(sorted_lm) * 8

    # Count bigrams encodable in this charset and mark top ones as POSITIVE
    for rank, (count, first_char, second_char) in enumerate(sorted_lm, 1):
        # Only consider bigrams where both chars can be encoded in this charset
        if first_char in charset_code_points and second_char in charset_code_points:
            charset_bigram_count += count
            if rank <= pos_threshold:
                pos_count += count

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
        alphabet=alphabet,
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
            f"     {char!r}: {order!r},  # {unicode_char!r}",
            file=output_file,
        )
    print("}\n", file=output_file)


def print_language_model(var_name, language_model, output_file, char_ranks):
    print(
        "# 3: Positive\n# 2: Likely\n# 1: Unlikely\n# 0: Negative\n",
        file=output_file,
    )
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
                f"        {char_ranks[second_char]!r}: {likelihood!r},  # {second_char!r}",
                file=output_file,
            )
        print("    },", file=output_file)
    print("}\n", file=output_file)


def train_model_for_lang(
    language,
    depth: int,
    input_encoding=None,
    input_paths=None,
    sequence_count_threshold=None,
    max_pages=None,
    wiki_folder=None,
):
    """Train a SingleByteCharSetModel for the given language and settings"""
    # Validate language
    language = language.title()
    lang_metadata = LANGUAGES.get(language)
    if not lang_metadata:
        raise ValueError(
            f"Unknown language: {language}. If you are adding a model for a"
            " new language, you must first update metadata/"
            "languages.py"
        )

    if wiki_folder and not input_paths:
        wiki_path = os.path.join(wiki_folder, f"wiki_{language}.txt")
        if not os.path.isfile(wiki_path):
            raise ValueError(
                f"Could not find Wikipedia training file for {language} at {wiki_path}"
            )
        input_paths = [wiki_path]

    print(
        f"\n{language}\n----------------------------------------------------------------\n"
        f"Keep ASCII Letters: {lang_metadata.use_ascii}\n"
        f"Alphabet: {lang_metadata.alphabet}\n"
        f"Unlikely Sequence Count Threshold: {sequence_count_threshold}\n"  # spit out together when using multiprocessing  # Do this before other branch to increase chance that this header gets
        + (
            f"Input Encoding: {input_encoding}"
            if input_paths
            else f"Wikipedia Depth: {depth}"
        )
    )

    # See if we're doing file-based or wiki-based training
    if input_paths:
        # Check that files are big enough before doing anything else
        data_size = sum(os.path.getsize(input_path) for input_path in input_paths)
        if data_size < 10000000:
            raise ValueError(
                "Input files must be at least 10MB to train a "
                f"decent model. You only provided {data_size:,} bytes."
            )

        input_gen = gen_input_lines(input_paths, input_encoding)

        data_size_str = f"{data_size:,} bytes of"
    else:
        if not HAVE_WIKIPEDIA:
            raise ValueError(
                "The pymediawiki Python package could not be "
                "imported, so you must either specify input files "
                "to use for training, or install it with pip."
            )
        # At this point we know HAVE_WIKIPEDIA is True, so MediaWiki is available
        assert HAVE_WIKIPEDIA
        wikipedia = MediaWiki(lang=lang_metadata.iso_code)  # type: ignore
        input_gen = gen_wiki_lines(
            titles=lang_metadata.wiki_start_pages,
            language=lang_metadata.iso_code,
            max_depth=depth,
            max_pages=max_pages,
            wikipedia=wikipedia,
        )
        data_size_str = "Wikipedia"

    print(
        f"\nCreating character frequency tables for {language} from {data_size_str} training data"
    )
    sys.stdout.flush()
    char_ranks, language_model, num_bigrams = calc_ngram_freqs(
        input_gen,
        lang_metadata.alphabet,
        lang_metadata.use_ascii,
        not input_paths,
        f"wiki_{language}.txt",
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
            num_bigrams=num_bigrams,
            char_ranks=char_ranks,
            keep_ascii_letters=lang_metadata.use_ascii,
            alphabet=lang_metadata.alphabet,
        )

    # Collapse language model freqs to SequenceLikelihood values after
    # calculating positive ratio for each charset
    collapse_language_model_freqs(language_model, sequence_count_threshold)

    # Write output files
    print(f"Writing output file for {language}\n\n")
    sys.stdout.flush()
    with open(f"lang{language.lower()}model.py", "w") as output_file:
        upper_lang = language.upper()
        # print header to set encoding
        print(
            "from chardet.sbcharsetprober import SingleByteCharSetModel\n\n",
            file=output_file,
        )

        lm_name = f"{upper_lang}_LANG_MODEL"
        print_language_model(lm_name, language_model, output_file, char_ranks)

        print(
            "# 255: Undefined characters that did not exist in training text\n"
            "# 254: Carriage/Return\n"
            "# 253: symbol (punctuation) that does not belong to word\n"
            "# 252: 0 - 9\n"
            "# 251: Control characters\n\n"
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
        "-d",
        "--depth",
        help="Maximum depth to crawl Wikipedia articles for training data.",
        type=int,
        default=2,
    )
    parser.add_argument(
        "-e",
        "--input-encoding",
        help="Encoding the input files are in. Does not need to match CHARSET_NAME.",
        default="UTF-8",
    )
    parser.add_argument(
        "-i",
        "--input-files",
        help="File to use to train language model. If no files "
        "are specified, will crawl Wikipedia for training "
        "data.",
        nargs="*",
        dest="input_paths",
    )
    parser.add_argument(
        "-m",
        "--max-pages",
        help="Maximum number of Wikipedia pages to crawl per language.",
        type=int,
        default=20000,
    )
    parser.add_argument(
        "-p",
        "--parallel-langs",
        help="Number of languages models to train at once.",
        type=int,
        default=8,
    )
    parser.add_argument(
        "-t",
        "--sequence-count-threshold",
        help=(
            "Minimum number of times a particular two-"
            "character sequence must have occurred in the "
            "input files in order to be considered unlikely "
            "(instead of illegal)."
        ),
        type=int,
        default=3,
    )
    parser.add_argument(
        "-w",
        "--wiki-folder",
        help=(
            "Path to folder containing crawled Wikipedia named "
            "'wiki_<language>.txt' files to use for training instead "
            "of crawling Wikipedia. "
            "If this is set, --input-files and --depth are ignored."
        ),
        type=str,
        default="",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    # Make sure we aren't trying to do anything weird
    if len(args.language) > 1:
        if args.input_paths:
            raise ValueError(
                "Specifying input paths is not valid when training"
                " models for multiple languages at the same time. "
                " This only works for Wikipedia training."
            )

    if not HAVE_WIKIPEDIA and not args.input_paths and not args.wiki_folder:
        raise ValueError(
            "The pymediawiki Python package could not be "
            "imported, so you must either specify input files "
            "to use for training, or install it with pip."
        )

    # Only create multiprocessing pool if doing things in parallel, otherwise
    # it's harder to debug
    if args.parallel_langs > 1 and len(args.language) > 1:
        pool = Pool(args.parallel_langs)
        pool.map_async(
            partial(
                train_model_for_lang,
                depth=args.depth,
                input_encoding=args.input_encoding,
                input_paths=args.input_paths,
                sequence_count_threshold=args.sequence_count_threshold,
                max_pages=args.max_pages,
                wiki_folder=args.wiki_folder,
            ),
            args.language,
        )
        pool.close()
        pool.join()
    else:
        for language in args.language:
            train_model_for_lang(
                language,
                depth=args.depth,
                input_encoding=args.input_encoding,
                input_paths=args.input_paths,
                sequence_count_threshold=args.sequence_count_threshold,
                max_pages=args.max_pages,
                wiki_folder=args.wiki_folder,
            )


if __name__ == "__main__":
    main()

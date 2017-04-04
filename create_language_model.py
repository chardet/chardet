#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from __future__ import absolute_import, print_function

import os
import re
import sys
import unicodedata
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import Counter, defaultdict
from functools import partial
from io import open
from multiprocessing import Pool
from operator import itemgetter
from string import ascii_letters

try:
    from mediawiki import MediaWiki
    HAVE_WIKIPEDIA = True
except:
    HAVE_WIKIPEDIA = False

from chardet import __version__
from chardet.compat import iteritems
from chardet.metadata.languages import LANGUAGES
from chardet.enums import CharacterCategory, SequenceLikelihood
from chardet.sbcharsetprober import SingleByteCharSetModel


# Turn ascii_letters into a set to make other ops easier
ascii_letters = set(ascii_letters)


def normalize_name(charset_name):
    """Convert name to proper Python constant format"""
    # Title case to start
    charset_name = charset_name.upper()
    # Underscores instead of hyphens
    charset_name = charset_name.replace('-', '_')
    return charset_name

def unicode_to_category(unicode_char, char_ranks, keep_ascii_letters=False,
                        alphabet=None):
    """Convert a Unicode character to categories used by SingleByteCharSetProber
    """
    if alphabet is None:
        alphabet = set()
    valid_letters = (alphabet | ascii_letters) if keep_ascii_letters else alphabet
    unicode_cat = unicodedata.category(unicode_char)
    if unicode_cat.startswith('N'):
        ret_val = CharacterCategory.DIGIT
    # Valid letters have their category set to their order/rank
    elif unicode_cat.startswith('L'):
        if unicode_char in valid_letters:
            ret_val = char_ranks.get(unicode_char, CharacterCategory.UNDEFINED)
        else:
            ret_val = CharacterCategory.UNDEFINED
    elif unicode_char in ('\r', '\n'):
        ret_val = CharacterCategory.LINE_BREAK
    # Punctuation, Symbols, and Marks are all symbols as far as we care
    elif unicode_cat.startswith(('P', 'S', 'M')):
        ret_val = CharacterCategory.SYMBOL
    else:
        ret_val = CharacterCategory.CONTROL
    return ret_val


def get_charset_mappings(charset_name, char_ranks, keep_ascii_letters=False,
                         alphabet=None):
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
            char_cat = unicode_to_category(unicode_char,
                                           char_ranks,
                                           keep_ascii_letters=keep_ascii_letters,
                                           alphabet=alphabet)
            charset_code_points[unicode_char] = char
        except UnicodeDecodeError:
            char_cat = CharacterCategory.UNDEFINED
        char_to_order[byte_hex] = char_cat
    return char_to_order, charset_code_points


def gen_input_lines(input_paths, input_encoding):
    """Yield decoded lines from files in input_paths"""
    for input_path in input_paths:
        with open(input_path, 'r', encoding=input_encoding) as input_file:
            for line in input_file:
                yield line


def gen_wiki_lines(titles, language, max_depth, max_pages=None, depth=0,
                   visited_pages=None, skipped_pages=None, wikipedia=None):
    """Generate lines from Wikipedia articles, starting with titles.

    Will crawl at most `max_depth` deep in the page hierarchy.
    """
    if visited_pages is None:
        visited_pages = set()

    if skipped_pages is None:
        skipped_pages = set()

    if not titles or depth > max_depth or len(visited_pages) > max_pages:
        print('Visited {} pages: {} ({} skipped)'.format(language,
                                                         len(visited_pages),
                                                         len(skipped_pages)))
        return

    # Visit all pages in titles and add their links to next_titles
    next_titles = set()
    for title in titles:
        if title in visited_pages or title in skipped_pages:
            continue
        print('Visited {} pages: {} ({} skipped)'.format(language,
                                                         len(visited_pages),
                                                         len(skipped_pages)),
              end='\r')
        sys.stdout.flush()
        if len(visited_pages) == max_pages:
            break
        try:
            page = wikipedia.page(title, auto_suggest=False)
            # Remove Wikipedia markup (this is inside of try block because it
            # an implicit request to Wikipedia to get the content does)
            content = re.sub(r'(=+) *([^=]+) *\1', r'\2', page.content)
            # Clean up repeated whitespace, since that could skew model
            content = re.sub(r'(\s)\1+', '\1', content)
        except:
            if depth > 0:
                skipped_pages.add(title)
                continue
            else:
                print('Failed to visit start page:')
                raise

        visited_pages.add(title)

        for line in content.splitlines(True):
            yield line

        # Sometimes things go wrong when extracting the links
        try:
            next_titles.update(page.links)
        except:
            continue

    # Recursive generators are fun
    for line in gen_wiki_lines(next_titles, language, max_depth,
                               depth=depth + 1,
                               visited_pages=visited_pages,
                               skipped_pages=skipped_pages,
                               max_pages=max_pages,
                               wikipedia=wikipedia):
        yield line


def calc_ngram_freqs(input_generator, alphabet, keep_ascii_letters):
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
    # Calculate unfiltered frequencies
    for line in input_generator:
        prev_char = None
        # Normalize so that combining and non-combining forms are
        # counted as the same, and because this is meant for single-byte
        # encodings, which don't support combining forms
        line = unicodedata.normalize('NFC', line)
        for unicode_char in line:
            # Skip ASCII letters if we're supposed to
            if not keep_ascii_letters and unicode_char in ascii_letters:
                continue
            char_freqs[unicode_char] += 1
            if prev_char is not None:
                language_model[prev_char][unicode_char] += 1
                num_bigrams += 1
            prev_char = unicode_char

    print('\nUnique character types in training data: {}'.format(len(char_freqs)))
    print('Number of character tokens in training data: {}'
          .format(sum(char_freqs.values())))

    min_alpha_freq = min(freq for unicode_char, freq in char_freqs.items()
                         if unicode_char in alphabet)

    # Filter language model down to only those within sample size
    for rank, (unicode_char, freq) in enumerate(sorted(list(char_freqs.items()),
                                                       key=itemgetter(1),
                                                       reverse=True),
                                                1):
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
    pos_threshold = num_unigram_types * 8  # Used to be 64 * 8 = 512
    likely_threshold = num_unigram_types * 16  # Used to be 64 * 16 = 1024
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # TODO: Re-evaluate these numbers because positive happens really often now
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
    for first_char, sub_dict in iteritems(language_model):
        for second_char, count in iteritems(sub_dict):
            yield count, first_char, second_char


def generate_sbcs_model(charset_name, language, language_model, num_bigrams,
                        char_ranks, keep_ascii_letters, alphabet):
    """Create a SingleByteCharSetModel object representing the charset."""
    # Setup tables necessary for computing transition frequencies for model
    char_to_order, charset_code_points = get_charset_mappings(charset_name,
                                                              char_ranks,
                                                              keep_ascii_letters)

    # Calculate positive ratio for charset by counting positive likelihood
    # bigrams where both characters are in charset
    pos_count = 0
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # Collapse bigram frequencies to SequenceLikelihood categories
    for rank, (count, first_char, second_char) in enumerate(sorted_lm, 1):
        if rank <= 512 and (first_char in charset_code_points and
                            second_char in charset_code_points):
            pos_count += count
    pos_ratio = (pos_count / num_bigrams) if num_bigrams else 0

    curr_model = SingleByteCharSetModel(charset_name=charset_name,
                                        language=language,
                                        char_to_order_map=char_to_order,
                                        # language_model is filled in later
                                        language_model=None,
                                        typical_positive_ratio=pos_ratio,
                                        keep_ascii_letters=keep_ascii_letters,
                                        alphabet=alphabet)
    return curr_model


def print_char_to_order(var_name, order_map, charset_name, output_file):
    print('{} = {{'.format(var_name), file=output_file)
    for char, order in sorted(iteritems(order_map)):
        char_bytes = bytes(bytearray((char,)))
        try:
            unicode_char = char_bytes.decode(charset_name)
        except UnicodeError:
            unicode_char = None
        print('     {!r}: {!r},  # {!r}'.format(char, order, unicode_char),
              file=output_file)
    print('}\n', file=output_file)


def print_language_model(var_name, language_model, output_file, char_ranks):
    print('# 3: Positive\n'
          '# 2: Likely\n'
          '# 1: Unlikely\n'
          '# 0: Negative\n',
          file=output_file)
    print('{} = {{'.format(var_name), file=output_file)
    for first_char, sub_dict in sorted(iteritems(language_model)):
        # Skip empty sub_dicts
        if not sub_dict:
            continue
        print('    {!r}: {{  # {!r}'.format(char_ranks[first_char], first_char),
              file=output_file)
        for second_char, likelihood in sorted(iteritems(sub_dict)):
            print('        {!r}: {!r},  # {!r}'.format(char_ranks[second_char],
                                                       likelihood,
                                                       second_char),
                  file=output_file)
        print('    },', file=output_file)
    print('}\n', file=output_file)


def train_model_for_lang(language, depth=None, input_encoding=None,
                         input_paths=None, sequence_count_threshold=None,
                         max_pages=None):
    """Train a SingleByteCharSetModel for the given language and settings"""
    # Validate language
    language = language.title()
    lang_metadata = LANGUAGES.get(language)
    if not lang_metadata:
        raise ValueError('Unknown language: {}. If you are adding a model for a'
                         ' new language, you must first update metadata/'
                         'languages.py'.format(language))

    print('\n{}\n----------------------------------------------------------------'
          .format(language))
    print('Keep ASCII Letters: {}'.format(lang_metadata.use_ascii))
    print('Alphabet: {}'.format(lang_metadata.alphabet))
    print('Unlikely Sequence Count Threshold: {}'.format(sequence_count_threshold))
    # Do this before other branch to increase chance that this header gets spit
    # out together when using multiprocessing
    if input_paths:
        print('Input Encoding: {}'.format(input_encoding))
    else:
        print('Wikipedia Depth: {}'.format(depth))

    # See if we're doing file-based or wiki-based training
    if input_paths:
        # Check that files are big enough before doing anything else
        data_size = sum(os.path.getsize(input_path)
                        for input_path in input_paths)
        if data_size < 10000000:
            raise ValueError('Input files must be at least 10MB to train a '
                             'decent model. You only provided {} bytes.'
                             .format(data_size))

        input_gen = gen_input_lines(input_paths, input_encoding)

        data_size_str = '{} bytes of'.format(data_size)
    else:
        if not HAVE_WIKIPEDIA:
            raise ValueError('The wikipedia Python package could not be '
                             'imported, so you must either specify input files '
                             'to use for training, or install it with pip.')
        wikipedia = MediaWiki(lang=lang_metadata.iso_code)
        input_gen = gen_wiki_lines(lang_metadata.wiki_start_pages,
                                   lang_metadata.iso_code, depth,
                                   max_pages=max_pages,
                                   wikipedia=wikipedia)
        data_size_str = 'Wikipedia'

    print('\nCreating character frequency tables for {} from {} training data'
          .format(language, data_size_str))
    sys.stdout.flush()
    char_ranks, language_model, num_bigrams = calc_ngram_freqs(input_gen,
                                                               lang_metadata.alphabet,
                                                               lang_metadata.use_ascii)

    # Create char-to-order maps (aka char-to-rank dicts)
    charset_models = {}
    for charset_name in lang_metadata.charsets:
        print('Creating charset model for {}'.format(charset_name))
        sys.stdout.flush()
        charset_models[charset_name] = generate_sbcs_model(charset_name,
                                                           language,
                                                           language_model,
                                                           num_bigrams,
                                                           char_ranks,
                                                           lang_metadata.use_ascii,
                                                           lang_metadata.alphabet)

    # Collapse language model freqs to SequenceLikelihood values after
    # calculating positive ratio for each charset
    collapse_language_model_freqs(language_model, sequence_count_threshold)

    # Write output files
    print('Writing output file for {}\n\n'.format(language))
    sys.stdout.flush()
    with open('lang{}model.py'.format(language.lower()), 'w') as output_file:
        upper_lang = language.upper()
        # print header to set encoding
        print('#!/usr/bin/env python\n'
              '# -*- coding: utf-8 -*-\n\n'
              'from chardet.sbcharsetprober import SingleByteCharSetModel\n\n',
              file=output_file)

        lm_name = '{}_LANG_MODEL'.format(upper_lang)
        print_language_model(lm_name, language_model, output_file, char_ranks)

        print('# 255: Undefined characters that did not exist in training text\n'
              '# 254: Carriage/Return\n'
              '# 253: symbol (punctuation) that does not belong to word\n'
              '# 252: 0 - 9\n'
              '# 251: Control characters\n\n'
              '# Character Mapping Table(s):',
              file=output_file)
        for charset_name, sbcs_model in iteritems(charset_models):
            normal_name = normalize_name(charset_name)
            char_to_order_name = ('{}_{}_CHAR_TO_ORDER'.format(normal_name,
                                                               upper_lang))
            print_char_to_order(char_to_order_name, sbcs_model.char_to_order_map,
                                charset_name, output_file)

            sbcs_model_name = '{}_{}_MODEL'.format(normal_name, upper_lang)
            sbcs_model.char_to_order_map.clear()
            sbcs_model_repr = (repr(sbcs_model)
                               .replace('None', lm_name)
                               .replace('{}', char_to_order_name)
                               .replace(', ', (',\n' +
                                               ' ' * (len(sbcs_model_name) +
                                                      26))))
            print('{} = {}\n'.format(sbcs_model_name, sbcs_model_repr),
                  file=output_file)


def main():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('language',
                        help='The name of the language the input documents are '
                             'in. Also the name of the language the generated '
                             'model will detect. If no language is specified, '
                             'models for all languages known to chardet will be'
                             ' trained.',
                        nargs='*')
    parser.add_argument('-d', '--depth',
                        help='Maximum depth to crawl Wikipedia articles for '
                             'training data.',
                        type=int, default=2)
    parser.add_argument('-e', '--input_encoding',
                        help='Encoding the input files are in. Does not need to'
                             ' match CHARSET_NAME.',
                        default='UTF-8')
    parser.add_argument('-i', '--input_files',
                        help='File to use to train language model. If no files '
                             'are specified, will crawl Wikipedia for training '
                             'data.',
                        nargs='*',
                        dest='input_paths')
    parser.add_argument('-m', '--max_pages',
                        help='Maximum number of Wikipedia pages to crawl per '
                             'language.',
                        type=int, default=20000)
    parser.add_argument('-p', '--parallel_langs',
                        help='Number of languages models to train at once.',
                        type=int, default=8)
    parser.add_argument('-t', '--sequence_count_threshold',
                        help='Minimum number of times a particular two-'
                             'character sequence must have occurred in the '
                             'input files in order to be considered unlikely '
                             '(instead of illegal).',
                        type=int, default=3)
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args()

    if not args.language:
        args.language = list(sorted(LANGUAGES.keys()))

    # Make sure we aren't trying to do anything weird
    if len(args.language) > 1:
        if args.input_paths:
            raise ValueError('Specifying input paths is not valid when training'
                             ' models for multiple languages at the same time. '
                             ' This only works for Wikipedia training.')

    # Only create multiprocessing pool if doing things in parallel, otherwise
    # it's harder to debug
    if args.parallel_langs > 1 and len(args.language) > 1:
        pool = Pool(args.parallel_langs)
        pool.map_async(partial(train_model_for_lang,
                               depth=args.depth,
                               input_encoding=args.input_encoding,
                               input_paths=args.input_paths,
                               sequence_count_threshold=args.sequence_count_threshold,
                               max_pages=args.max_pages),
                       args.language)
        pool.close()
        pool.join()
    else:
        for language in args.language:
            train_model_for_lang(language,
                                 depth=args.depth,
                                 input_encoding=args.input_encoding,
                                 input_paths=args.input_paths,
                                 sequence_count_threshold=args.sequence_count_threshold,
                                 max_pages=args.max_pages)


if __name__ == '__main__':
    main()

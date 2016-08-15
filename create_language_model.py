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
Input text will be filtered. Only chars from the given charset will be
processed.
If you want to create good language model you need at least 10MB file.
For example the Mozilla Russian language model was created from 20MB file.
Please don't use XML or HTML files, because they contains too many English
terms,
also please remove all english paragraphs such as infolines from the project
Gutenberg.

Usage: python CreateLanguageModel.py input_file_in_utf_8 charset_name keep_ascii_letters

- input_file_in_utf_8 is any raw text file in UTF-8!
proper file name is 'czech.raw', 'slovak.txt', 'slovene.txt', ...

- charset_name is name of the charset for which you want to create language model
e.g. ISO-8859-2, windows-1250, IBM866, ... Please look at 'CharsetsTabs.txt' file.

- keep_ascii_letters is flag which controls the using of the english alphabet
"""
from __future__ import absolute_import, print_function

import os
import sys
import unicodedata
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import Counter, defaultdict
from io import open, StringIO
from operator import itemgetter
from string import ascii_letters

from chardet import __version__
from chardet.compat import iteritems
from chardet.enums import CharacterCategory, SequenceLikelihood
from chardet.sbcharsetprober import SingleByteCharSetModel


def normalize_name(charset_name):
    """Convert name to proper Python constant format"""
    # Title case to start
    charset_name = charset_name.upper()
    # Underscores instead of hyphens
    charset_name = charset_name.replace('-', '_')
    return charset_name


def unicode_to_category(unicode_char, char_ranks, keep_ascii_letters=False):
    """Convert a Unicode character to categories used by SingleByteCharSetProber
    """
    unicode_cat = unicodedata.category(unicode_char)
    if unicode_cat.startswith('N'):
        ret_val = CharacterCategory.DIGIT
    elif unicode_cat.startswith('L'):
        if not keep_ascii_letters and unicode_char in ascii_letters:
            ret_val = CharacterCategory.CONTROL
        else:
            ret_val = char_ranks.get(unicode_char, CharacterCategory.UNDEFINED)
    elif unicode_char in ('\r', '\n'):
        ret_val = CharacterCategory.LINE_BREAK
    # Punctuation, Symbols, and Marks are all symbols as far as we care
    elif unicode_cat.startswith(('P', 'S', 'M')):
        ret_val = CharacterCategory.SYMBOL
    else:
        ret_val = CharacterCategory.CONTROL
    return ret_val


def get_charset_mappings(charset_name, char_ranks, keep_ascii_letters=False):
    """Returns `charset_categories` & `charset_code_points` mappings for charset

    `charset_categories` maps from bytes in charset/encoding to categories
    expected by SingleByteCharSetProber except for letters, which have their
    category set to `ALPHA`. These will be modified later to map to an "order",
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
                                           keep_ascii_letters=keep_ascii_letters)
            charset_code_points[unicode_char] = char
        except UnicodeDecodeError:
            char_cat = CharacterCategory.UNDEFINED
        char_to_order[char] = char_cat
    return char_to_order, charset_code_points


def calc_ngram_freqs(input_paths, input_encoding, sample_size,
                     sequence_count_threshold, keep_ascii_letters):
    """Create a language model with the likelihoods of all bigrams in input.

    This LM is based on Unicode code point frequencies and not encoded character
    frequencies so that this can be used for all encodings.

    The LM is filtered down to bigrams for the `sample_size` most frequent
    unigrams.
    """
    char_freqs = Counter()
    char_ranks = {}
    language_model = defaultdict(Counter)
    num_bigrams = 0
    # Calculate unfiltered frequencies
    for input_path in input_paths:
        prev_char = None
        with open(input_path, 'r', encoding=input_encoding) as input_file:
            for line in input_file:
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

    print('Unique character types in training data: {}'.format(len(char_freqs)))

    # Filter language model down to only those within sample size
    for rank, (unicode_char, _) in enumerate(sorted(list(char_freqs.items()),
                                                    key=itemgetter(1),
                                                    reverse=True),
                                             1):
        char_ranks[unicode_char] = rank
        if rank > sample_size:
            del char_freqs[unicode_char]
            language_model.pop(unicode_char, None)
            for sub_dict in language_model.values():
                sub_dict.pop(unicode_char, None)
        else:
            # Set all unseen combos involving this character to NEGATIVE
            # Note: We do this here instead of in SingleByteCharSetProber
            # because this is much faster than switching .get(char, 0) in there.
            for sub_dict in language_model.values():
                if unicode_char not in sub_dict:
                    sub_dict[unicode_char] = 0
    return char_ranks, language_model, num_bigrams


def collapse_language_model_freqs(language_model, sequence_count_threshold):
    """Collapse bigram frequencies to SequenceLikelihood categories"""
    sorted_lm = sorted(flatten_language_model(language_model), reverse=True)

    # Collapse bigram frequencies to SequenceLikelihood categories
    for rank, (count, first_char, second_char) in enumerate(sorted_lm, 1):
        if rank <= 512:
            language_model[first_char][second_char] = SequenceLikelihood.POSITIVE
        elif rank <= 1024:
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


def generate_sbcs_model(charset_name, language, sample_size, language_model,
                        num_bigrams, char_ranks, keep_ascii_letters):
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
    pos_ratio = pos_count / num_bigrams

    curr_model = SingleByteCharSetModel(charset_name=charset_name,
                                        language=language,
                                        char_to_order_map=char_to_order,
                                        # language_model is filled in later
                                        language_model=None,
                                        typical_positive_ratio=pos_ratio,
                                        keep_ascii_letters=keep_ascii_letters,
                                        sample_size=sample_size)
    return curr_model


def print_dict_literal(var_name, to_print, output_file):
    print('{} = {{'.format(var_name), file=output_file)
    for key, val in sorted(iteritems(to_print)):
        print('     {!r}: {!r}'.format(key, val), file=output_file)
    print('}\n', file=output_file)


def print_language_model(var_name, language_model, output_file, char_ranks):
    print('# 3: Positive\n'
          '# 2: Likely\n'
          '# 1: Unlikely\n'
          '# 0: 0 - 9\n',
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


def main():
    parser = ArgumentParser(description='Creates a language model for single '
                                        'byte character encoding detection '
                                        'based on the given file(s).',
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('language',
                        help='The name of the language the input documents are '
                             'in. Also the name of the language the generated '
                             'model will detect.')
    parser.add_argument('-c', '--charset_name',
                        help='Name of encoding language model can be used for.',
                        nargs='+')
    parser.add_argument('-i', '--input_file',
                        help='File to use to train language model.',
                        nargs='+',
                        dest='input_paths')
    parser.add_argument('-a', '--keep_ascii_letters',
                        help='By default all ASCII/English letters are filtered'
                             ' out of the documents (and any docs processed by '
                             'the trained model. Use this flag to retain them.',
                        action='store_true')
    parser.add_argument('-e', '--input_encoding',
                        help='Encoding the input files are in. Does not need to'
                             ' match CHARSET_NAME.',
                        default='UTF-8')
    parser.add_argument('-s', '--sample_size',
                        help='The number of most frequent non-symbol characters'
                             ' to calculate precedence/transition/bigram matrix'
                             ' for.',
                        type=int, default=64)
    parser.add_argument('-t', '--sequence_count_threshold',
                        help='Minimum number of times a particular two-'
                             'character sequence must have occurred in the '
                             'input files in order to be considered unlikely '
                             '(instead of illegal).',
                        type=int, default=3)
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args()

    # Check that files are big enough before doing anything else
    data_size = sum(os.path.getsize(input_path) for input_path in args.input_paths)
    if data_size < 10000000:
        raise ValueError('Input files must be at least 10MB to train a decent '
                         'model. You only provided {} bytes.'.format(data_size))

    print('Input Encoding: {}'.format(args.input_encoding))
    print('Keep ASCII Letters: {}'.format(args.keep_ascii_letters))
    print('Sample Size: {}'.format(args.sample_size))
    print('Unlikely Sequence Count Threshold: {}'.format(args.sequence_count_threshold))

    print('\nCreating character frequency tables for {} from {} bytes of '
          'training data'.format(args.language, data_size))
    sys.stdout.flush()
    char_ranks, language_model, num_bigrams = calc_ngram_freqs(args.input_paths,
                                                               args.input_encoding,
                                                               args.sample_size,
                                                               args.sequence_count_threshold,
                                                               args.keep_ascii_letters)

    # Create char-to-order maps (aka char-to-rank dicts)
    charset_models = {}
    for charset_name in args.charset_name:
        print('Creating charset model for {}'.format(charset_name))
        sys.stdout.flush()
        charset_models[charset_name] = generate_sbcs_model(charset_name,
                                                           args.language,
                                                           args.sample_size,
                                                           language_model,
                                                           num_bigrams,
                                                           char_ranks,
                                                           args.keep_ascii_letters)

    # Collapse language model freqs to SequenceLikelihood values after
    # calculating positive ratio for each charset
    collapse_language_model_freqs(language_model, args.sequence_count_threshold)

    # Write output files
    print('Writing output file for {}'.format(args.language))
    sys.stdout.flush()
    with open('lang{}model.py'.format(args.language.lower()), 'w') as output_file:
        upper_lang = args.language.upper()
        # print header to set encoding
        print('#!/usr/bin/env python\n'
              '# -*- coding: utf-8 -*-\n',
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
            print_dict_literal(char_to_order_name, sbcs_model.char_to_order_map,
                               output_file)

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


if __name__ == '__main__':
    main()

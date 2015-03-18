######################## BEGIN LICENSE BLOCK ########################
# Contributor(s):
#   10.02.2015 - helour - first release
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
 Input text will be filtered. Only chars from the given charset will be processed
 If you want to create good language model you need at least 10MB file.
 For example the mozilla russian language model was created from 20MB file.
 Please don't use XML or HTML file, it contains too many english words,
 also please remove all english paragraphs such as infolines from the project Gutenberg

 Usage: python CreateLanguageModel.py input_file_in_utf_8 charset_name keep_english_letters

 - input_file_in_utf_8 is any raw text file in UTF-8!
   proper file name is 'czech.raw', 'slovak.txt', 'slovene.txt', ...

 - charset_name is name of the charset for which you want to create language model
   e.g. ISO-8859-2, windows-1250, IBM866, ... Please look at 'CharsetsTabs.txt' file.

 - keep_english_letters is flag which controls the using of the english alphabet
"""

import os, sys, codecs, operator
from collections import OrderedDict

NULL = -1

ALPHA  = 0
DIGIT  = 252
SYMBOL = 253
CRLF   = 254
CTRL   = 255

SAMPLE_SIZE = 64
POSITIVE_SEQUENCE = 3
NEGATIVE_SEQUENCE = 0
MOZILLA_MAGIC_NUMBER = 3 # Higher value creates more negative sequences (it removes "noise" characters)

english_letters = [
  'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
  'a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']

def first_letter_to_uppercase(string):
    return string[0].upper() + string[1:]

def normalize_charset_name(string):
    return first_letter_to_uppercase(string).replace('-', '_');

try:
    file_name = sys.argv[1]
    charset_name = sys.argv[2]
    keep_english_letters = sys.argv[3]
except:
    print("Usage: %s input_file_in_utf_8 charset_name keep_english_letters" % sys.argv[0])
    sys.exit(1)

keep_english_letters = True if keep_english_letters.lower() in ['1', 'true', 'yes', 'y'] else False

try: # Python 3.x doesn't have iteritems
    iteritems = dict.iteritems
except AttributeError:
    iteritems = dict.items

# ***************************************************** CREATING CHARSMAP TABLE FOR GIVEN CHARSET ***************************************************** #
charsmap_table = OrderedDict([])
counter = NULL
xx_counter = 0
with codecs.open('CharsetsTabs.txt', 'r', encoding='utf-8') as f: # File 'CharsetsTabs.txt' must be included with this script!
    for line in f:                          # It contains tables of common character sets like the Latin-2, Windows-1250, ...)
        if charset_name.lower() in line.lower():
            chars = []
            counter = 0
            continue
        if counter > 16:
            break
        if counter != NULL:
            counter += 1
        if counter > 1:
            chars = line.split()[1:]
            for char in chars:
                if char == 'XX':
                    charsmap_table['XX' + str(xx_counter)] = CTRL # The 'XX' in the charset table indicates a nonexisting character
                    xx_counter += 1
                elif char == 'lf':
                    charsmap_table['\r'] = CRLF
                elif char == 'cr':
                    charsmap_table['\n'] = CRLF
                elif char == 'sp':
                    charsmap_table[' '] = SYMBOL
                elif len(char) == 1:
                    if char.isdigit():
                        charsmap_table[char] = DIGIT
                    elif char.isalpha():
                        if not keep_english_letters and char in english_letters:
                            charsmap_table[char] = CTRL
                        else:
                            charsmap_table[char] = ALPHA
                    else:
                        charsmap_table[char] = SYMBOL
                else:
                    charsmap_table[char] = CTRL

if counter == NULL:
    print("Wrong/unknown charset name! Please check the 'CharsetsTabs.txt' file.")
    sys.exit(1)

# *************************************************************** CHARS FREQUENCY TABLE *************************************************************** #
letters_table = []
for char in charsmap_table:
    if charsmap_table[char] == ALPHA:
        letters_table.append(char)

chars_frequency_table = OrderedDict([])
for char in charsmap_table:
    chars_frequency_table[char] = 0

lang_name = os.path.splitext(os.path.basename(file_name))[0]
print("Creating chars frequency table for %s language" % lang_name)
with codecs.open(file_name, 'r', encoding='utf-8') as f:
    for line in f:
        for char in line:
            if char in chars_frequency_table:
                chars_frequency_table[char] += 1

counter = 0
frequent_letters_table = []

for char, chars_count in sorted(iteritems(chars_frequency_table), key=operator.itemgetter(1), reverse=True):
    if char in letters_table:
        counter += 1
        charsmap_table[char] = counter
        if counter <= SAMPLE_SIZE:
            frequent_letters_table.append(char)

# ****************************************************************** CHARMAP OUTPUT ******************************************************************* #
with open('lang' + lang_name + 'model.py', 'w') as f:
    f.write('%s_%s_char_to_order_map = (\n' % (normalize_charset_name(charset_name), first_letter_to_uppercase(lang_name)))
    f.write('  #0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F\n  ')
    counter = 1
    for item in charsmap_table:
        f.write('%3d,' % charsmap_table[item])
        if counter % 16 == 0:
            f.write('  # %2X\n  ' % int(counter-16))
        counter += 1
    f.write(')\n\n')

# *************************************************************** BIGRAM FREQUENCY TABLE ************************************************************** #
twochars_sequences_frequency_table = OrderedDict([])
for char1 in frequent_letters_table:
    for char2 in frequent_letters_table:
        twochars_sequences_frequency_table[char1+char2] = 0

print("Creating bigrams frequency table for %s language" % lang_name)
num_chars = 0
num_frequent_chars = 0
num_sequences = 0
with codecs.open(file_name, 'r', encoding='utf-8') as f:
    for line in f:
        last_char = ''
        for char in line:
            if char in letters_table:
                num_chars += 1
            if char in frequent_letters_table:
                num_frequent_chars += 1
            sequence = last_char + char
            if sequence in twochars_sequences_frequency_table:
                num_sequences += 1
                twochars_sequences_frequency_table[sequence] += 1
            last_char = char

counter = 0
for sequence, sequences_count in sorted(iteritems(twochars_sequences_frequency_table), key=operator.itemgetter(1), reverse=True):
    counter += 1
    if counter <= 512:
        twochars_sequences_frequency_table[sequence] = POSITIVE_SEQUENCE
    elif counter <= 1024:
        twochars_sequences_frequency_table[sequence] = 2
    elif sequences_count <= MOZILLA_MAGIC_NUMBER:
        twochars_sequences_frequency_table[sequence] = NEGATIVE_SEQUENCE
    else:
        twochars_sequences_frequency_table[sequence] = 1

# ******************************************************** CALCULATING TYPICAL POSITIVE RATIO ********************************************************* #
print("Calulating typical positive ratio")
num_positive_sequences = 0
num_negative_sequences = 0
with codecs.open(file_name, 'r', encoding='utf-8') as f:
    for line in f:
        last_char = ''
        for char in line:
            sequence = last_char + char
            if sequence in twochars_sequences_frequency_table:
                if twochars_sequences_frequency_table[sequence] == POSITIVE_SEQUENCE:
                    num_positive_sequences += 1
                if twochars_sequences_frequency_table[sequence] == NEGATIVE_SEQUENCE:
                    num_negative_sequences += 1
            last_char = char

#typical_positive_ratio = float(num_sequences - num_negative_sequences) / num_sequences * num_frequent_chars / num_chars
typical_positive_ratio = float(num_positive_sequences) / num_sequences * num_frequent_chars / num_chars

# *************************************************************** LANGUAGE MODEL OUTPUT *************************************************************** #
print("Writing language model")
with open('lang' + lang_name + 'model.py', 'a') as f:
    f.write('%s_LangModel = (\n  ' % first_letter_to_uppercase(lang_name))
    counter = 1
    for val in twochars_sequences_frequency_table.values():
        f.write(str(val) + ',')
        if counter % 32 == 0:
            f.write('\n  ')
        counter += 1
    f.write(')\n\n')

    f.write('%s_%s_Model = {\n' % (normalize_charset_name(charset_name), first_letter_to_uppercase(lang_name)))
    f.write("  'char_to_order_map': %s_%s_char_to_order_map,\n" % (normalize_charset_name(charset_name), first_letter_to_uppercase(lang_name)))
    f.write("  'precedence_matrix': %s_LangModel,\n" % first_letter_to_uppercase(lang_name))
    f.write("  'typical_positive_ratio': %0.4f,\n" % typical_positive_ratio)
    f.write("  'keep_english_letter': %s,\n" % str(keep_english_letters))
    f.write("  'charset_name': \"%s\",\n" % charset_name)
    f.write("  'language': \"%s\"\n" % first_letter_to_uppercase(lang_name))
    f.write('  }\n\n')

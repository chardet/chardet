######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Universal charset detector code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 2001
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Mark Pilgrim - port to Python
#   Shy Shalom - original C code
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
######################### END LICENSE BLOCK #########################

import re
from io import BytesIO

from . import constants


class CharSetProber(object):

    def __init__(self):
        self._mState = None

    def reset(self):
        self._mState = constants.eDetecting

    def get_charset_name(self):
        return None

    def feed(self, buf):
        pass

    def get_state(self):
        return self._mState

    def get_confidence(self):
        return 0.0

    @staticmethod
    def filter_high_bit_only(buf):
        buf = re.sub(b'([\x00-\x7F])+', b' ', buf)
        return buf

    @staticmethod
    def filter_international_words(buf):
        """
        We define three types of bytes:
        alphabet: english alphabets [a-zA-Z]
        international: international characters [\x80-\xFF]
        marker: everything else [^a-zA-Z\x80-\xFF]

        The input buffer can be thought to contain a series of words delimited
        by markers. This function works to filter all words that contain at
        least one international character. All contiguous sequences of markers
        are replaced by a single space ascii character.

        This filter applies to all scripts which do not use English characters.
        """
        filtered = BytesIO()

        # This regex expression filters out only words that have at-least one
        # international character. The word may include one marker character at
        # the end.
        words = re.findall(
            b'[a-zA-Z]*[\x80-\xFF]+[a-zA-Z]*[^a-zA-Z\x80-\xFF]?', buf)

        for word in words:
            filtered.write(word[:-1])

            # If the last character in the word is a marker, replace it with a
            # space as markers shouldn't affect our analysis (they are used
            # similarly across all languages and may thus have similar
            # frequencies).
            last_char = word[-1:]
            last_char = last_char if (last_char.isalpha() or
                                      last_char >= b'\x80') else b' '
            filtered.write(last_char)

        return filtered.getvalue()

    @staticmethod
    def filter_with_english_letters(buf):
        """
        We define three types of bytes:
        alphabet: english alphabets [a-zA-Z]
        international: international characters [\x80-\xFF]
        marker: everything else [^a-zA-Z\x80-\xFF]

        The input buffer can be thought to contain a series of words delimited
        by markers. This function works to filter all words that contain at
        least one international character. All contiguous sequences of markers
        are replaced by a single space ascii character.

        This filter applies to all scripts which contain both English
        characters and extended ASCII characters.
        """
        filtered = BytesIO()
        in_tag = False
        prev = 0

        for curr in range(len(buf)):
            buf_char = buf[curr:curr + 1]
            # Check if we're coming out of or entering an HTML tag
            if buf_char == b'>':
                in_tag = False
            elif buf_char == b'<':
                in_tag = True

            # If current character is not extended-ASCII and not alphabetic...
            if buf_char < b'\x80' and not buf_char.isalpha():
                # ...and we're not in a tag
                if curr > prev and not in_tag:
                    # Keep everything after last non-extended-ASCII,
                    # non-alphabetic character
                    filtered.write(buf[prev:curr])
                    # Output a space to delimit stretch we kept
                    filtered.write(b' ')
                prev = curr + 1

        # If we're not in a tag...
        if not in_tag:
            # Keep everything after last non-extended-ASCII, non-alphabetic
            # character
            filtered.write(buf[prev:])

        return filtered.getvalue()

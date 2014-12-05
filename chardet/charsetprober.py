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

from . import constants
import re


class CharSetProber:
    def __init__(self):
        pass

    def reset(self):
        self._mState = constants.eDetecting

    def get_charset_name(self):
        return None

    def feed(self, aBuf):
        pass

    def get_state(self):
        return self._mState

    def get_confidence(self):
        return 0.0

    def filter_high_bit_only(self, aBuf):
        aBuf = re.sub(b'([\x00-\x7F])+', b' ', aBuf)
        return aBuf

    def filter_without_english_letters(self, aBuf):
        """
            returns a byte string by saving only bytes that are inclusively
            between a high ascii byte (> 127) and a low ascii byte that is not
            an english alphabet.
        """
        newStr = b""
        prev = 0
        curr = 0
        meetMSB = False

        ord_a = ord('a')
        ord_z = ord('z')
        ord_A = ord('A')
        ord_Z = ord('Z')

        for curr in range(0, len(aBuf)):
            ord_curr = ord(aBuf[curr])
            if ord_curr & 0x80:
                meetMSB = True
            elif not (ord_A < ord_curr < ord_Z or
                      ord_a < ord_curr < ord_z):
                if meetMSB and curr > prev:
                    while prev < curr:
                        newStr += aBuf[prev]
                        prev += 1
                    prev += 1
                    newStr += b' '
                    meetMSB = False
                else:
                    prev = curr + 1
        if meetMSB and curr > prev:
            while prev < curr:
                newStr += aBuf[prev]
                prev += 1

        return newStr

    def filter_with_english_letters(self, aBuf):
        # TODO
        return aBuf

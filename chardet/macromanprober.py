
######################## BEGIN LICENSE BLOCK ########################
# This code was modified from latin1prober.py by Rob Speer <rob@lumino.so>.
# The Original Code is Mozilla Universal charset detector code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 2001
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Rob Speer - adapt to MacRoman encoding
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

from charsetprober import CharSetProber
import constants
import operator

FREQ_CAT_NUM = 4

UDF = 0 # undefined
OTH = 1 # other
ASC = 2 # ascii capital letter
ASS = 3 # ascii small letter
ACV = 4 # accent capital vowel
ACO = 5 # accent capital other
ASV = 6 # accent small vowel
ASO = 7 # accent small other
ODD = 8 # character that is unlikely to appear
CLASS_NUM = 9 # total classes

# The change from Latin1 is that we explicitly look for extended characters
# that are infrequently-occurring symbols, and consider them to always be
# improbable. This should let MacRoman get out of the way of more likely
# encodings in most situations.

MacRoman_CharToClass = ( \
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 00 - 07
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 08 - 0F
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 10 - 17
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 18 - 1F
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 20 - 27
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 28 - 2F
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 30 - 37
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # 38 - 3F
  OTH, ASC, ASC, ASC, ASC, ASC, ASC, ASC,   # 40 - 47
  ASC, ASC, ASC, ASC, ASC, ASC, ASC, ASC,   # 48 - 4F
  ASC, ASC, ASC, ASC, ASC, ASC, ASC, ASC,   # 50 - 57
  ASC, ASC, ASC, OTH, OTH, OTH, OTH, OTH,   # 58 - 5F
  OTH, ASS, ASS, ASS, ASS, ASS, ASS, ASS,   # 60 - 67
  ASS, ASS, ASS, ASS, ASS, ASS, ASS, ASS,   # 68 - 6F
  ASS, ASS, ASS, ASS, ASS, ASS, ASS, ASS,   # 70 - 77
  ASS, ASS, ASS, OTH, OTH, OTH, OTH, OTH,   # 78 - 7F
  ACV, ACV, ACO, ACV, ACO, ACV, ACV, ASV,   # 80 - 87
  ASV, ASV, ASV, ASV, ASV, ASO, ASV, ASV,   # 88 - 8F
  ASV, ASV, ASV, ASV, ASV, ASV, ASO, ASV,   # 90 - 97
  ASV, ASV, ASV, ASV, ASV, ASV, ASV, ASV,   # 98 - 9F
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, ASO,   # A0 - A7
  OTH, OTH, ODD, ODD, OTH, OTH, ACV, ACV,   # A8 - AF
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, OTH,   # B0 - B7
  OTH, OTH, OTH, OTH, OTH, OTH, ASV, ASV,   # B8 - BF
  OTH, OTH, ODD, OTH, ODD, OTH, OTH, OTH,   # C0 - C7
  OTH, OTH, OTH, ACV, ACV, ACV, ACV, ASV,   # C8 - CF
  OTH, OTH, OTH, OTH, OTH, OTH, OTH, ODD,   # D0 - D7
  ASV, ACV, ODD, OTH, OTH, OTH, OTH, OTH,   # D8 - DF
  OTH, OTH, OTH, OTH, OTH, ACV, ACV, ACV,   # E0 - E7
  ACV, ACV, ACV, ACV, ACV, ACV, ACV, ACV,   # E8 - EF
  ODD, ACV, ACV, ACV, ACV, ASV, ODD, ODD,   # F0 - F7
  ODD, ODD, ODD, ODD, ODD, ODD, ODD, ODD,   # F8 - FF
)

# 0 : illegal
# 1 : very unlikely
# 2 : normal
# 3 : very likely
MacRomanClassModel = ( \
# UDF OTH ASC ASS ACV ACO ASV ASO ODD
   0,  0,  0,  0,  0,  0,  0,  0,  0,  # UDF
   0,  3,  3,  3,  3,  3,  3,  3,  1,  # OTH
   0,  3,  3,  3,  3,  3,  3,  3,  1,  # ASC
   0,  3,  3,  3,  1,  1,  3,  3,  1,  # ASS
   0,  3,  3,  3,  1,  2,  1,  2,  1,  # ACV
   0,  3,  3,  3,  3,  3,  3,  3,  1,  # ACO
   0,  3,  1,  3,  1,  1,  1,  3,  1,  # ASV
   0,  3,  1,  3,  1,  1,  3,  3,  1,  # ASO
   0,  1,  1,  1,  1,  1,  1,  1,  1,  # ODD
)

class MacRomanProber(CharSetProber):
    def __init__(self):
        CharSetProber.__init__(self)
        self.reset()

    def reset(self):
        self._mLastCharClass = OTH
        self._mFreqCounter = [0] * FREQ_CAT_NUM

        # express the prior that MacRoman is a somewhat rare encoding;
        # this can be done by starting out in a slightly improbable state
        # that must be overcome
        self._mFreqCounter[2] = 10

        CharSetProber.reset(self)

    def get_charset_name(self):
        return "macroman"

    def feed(self, aBuf):
        aBuf = self.filter_with_english_letters(aBuf)
        for c in aBuf:
            try:
                charClass = MacRoman_CharToClass[ord(c)]
            except IndexError:
                return constants.eError
            freq = MacRomanClassModel[(self._mLastCharClass * CLASS_NUM) + charClass]
            if freq == 0:
                self._mState = constants.eNotMe
                break
            self._mFreqCounter[freq] += 1
            self._mLastCharClass = charClass

        return self.get_state()

    def get_confidence(self):
        if self.get_state() == constants.eNotMe:
            return 0.01

        total = float(reduce(operator.add, self._mFreqCounter))
        if total < 0.01:
            confidence = 0.0
        else:
            confidence = (self._mFreqCounter[3] / total) - (self._mFreqCounter[1] * 20.0 / total)
        if confidence < 0.0:
            confidence = 0.0

        return confidence

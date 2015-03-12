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
#   helour - new model for Dutch, English, Finnish, French, Italy,
#            Portuguese and Spanish
#            German language has own model because of wrong correlation
#            with Portuguese and some others languages
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

from .charsetprober import CharSetProber
from .compat import wrap_ord
from .enums import ProbingState

NUMBER_OF_SEQ_CAT = 4
POSITIVE_CAT = 3
LIKELY_CAT   = 2
UNLIKELY_CAT = 1
NEGATIVE_CAT = 0

ASV = 0  # ascii small vowel
SVA = 1  # small vowel accent
SVO = 2  # small vowel other
ASC = 3  # ascii small consonant
SCO = 4  # small consonant other
ACV = 5  # ascii capital vowel
CVA = 6  # capital vowel accent
CVO = 7  # capital vowel other
ACC = 8  # ascii capital consonant
CCO = 9  # capital consonant other
CLASS_NUM = CCO + 1

CTR = 251 # control char
DIG = 252 # digit
SYM = 253 # symbol
CRF = 254 # CR/LF
UDF = 255 # undefined char

Latin1_CharToClass = (
  #0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F
  CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CRF,CTR,CTR,CRF,CTR,CTR,  #  0
  CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,CTR,  # 10
  SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,  # 20
  DIG,DIG,DIG,DIG,DIG,DIG,DIG,DIG,DIG,DIG,SYM,SYM,SYM,SYM,SYM,SYM,  # 30
  SYM,ACV,ACC,ACC,ACC,ACV,ACC,ACC,ACC,ACV,ACC,ACC,ACC,ACC,ACC,ACV,  # 40
  ACC,ACC,ACC,ACC,ACC,ACV,ACC,ACC,ACC,ACV,ACC,SYM,SYM,SYM,SYM,SYM,  # 50
  SYM,ASV,ASC,ASC,ASC,ASV,ASC,ASC,ASC,ASV,ASC,ASC,ASC,ASC,ASC,ASV,  # 60
  ASC,ASC,ASC,ASC,ASC,ASV,ASC,ASC,ASC,ASV,ASC,SYM,SYM,SYM,SYM,CTR,  # 70
  SYM,UDF,SYM,SCO,SYM,SYM,SYM,SYM,SYM,SYM,CCO,SYM,CVO,UDF,CCO,UDF,  # 80
  UDF,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SCO,SYM,SVO,UDF,SCO,CVO,  # 90
  SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,  # A0
  SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,SYM,  # B0
  CVA,CVA,CVA,CVA,CVO,CVO,CVO,CCO,CVA,CVA,CVA,CVO,CVA,CVA,CVA,CVO,  # C0
  CCO,CCO,CVA,CVA,CVA,CVA,CVO,SYM,CVO,CVA,CVA,CVA,CVO,CVA,CCO,SCO,  # D0
  SVA,SVA,SVA,SVA,SVO,SVO,SVO,SCO,SVA,SVA,SVA,SVO,SVA,SVA,SVA,SVO,  # E0
  SCO,SCO,SVA,SVA,SVA,SVA,SVO,SYM,SVO,SVA,SVA,SVA,SVO,SVA,SCO,SVO,  # F0
)

# 0 : illegal
# 1 : very unlikely
# 2 : normal
# 3 : very likely
Latin1_ClassModel = (
  #ASV SVA SVO ASC SCO ACV CVA CVO ACC CCO
    3,  3,  2,  3,  3,  1,  0,  0,  1,  0,  # ASV
    3,  1,  0,  3,  1,  0,  0,  0,  0,  0,  # SVA
    2,  1,  3,  3,  0,  0,  0,  0,  0,  0,  # SVO
    3,  3,  3,  3,  2,  0,  0,  0,  1,  0,  # ASC
    3,  2,  0,  0,  0,  0,  0,  0,  0,  0,  # SCO
    2,  1,  1,  3,  1,  1,  1,  1,  2,  1,  # ACV
    1,  0,  0,  1,  0,  1,  0,  0,  1,  0,  # CVA
    1,  0,  1,  1,  0,  1,  0,  1,  1,  0,  # CVO
    3,  2,  1,  3,  0,  2,  1,  1,  1,  1,  # ACC
    1,  1,  0,  0,  0,  1,  1,  0,  0,  0,  # CCO
)

class Latin1Prober(CharSetProber):
    def __init__(self):
        super(Latin1Prober, self).__init__()
        self._last_char_class = None
        self._seq_counters = None
        self._total_seqs = None
        self.reset()

    def reset(self):
        self._last_char_class = CTR # or SYM
        self._seq_counters = [0] * NUMBER_OF_SEQ_CAT
        self._total_seqs = 0
        CharSetProber.reset(self)

    @property
    def charset_name(self):
        return "ISO-8859-1"

    @property
    def language(self):
        return "Latin1"

    def feed(self, byte_str):
        byte_str = self.filter_with_english_letters(byte_str)
        for c in byte_str:
            char_class = Latin1_CharToClass[wrap_ord(c)]
            if char_class == UDF:
                self._state = ProbingState.not_me
                break
            if self._last_char_class < CLASS_NUM and char_class < CLASS_NUM:
                self._total_seqs += 1
                freq = Latin1_ClassModel[(self._last_char_class * CLASS_NUM) + char_class]
                self._seq_counters[freq] += 1
            self._last_char_class = char_class

        return self.state

    def get_confidence(self):
        if self.state == ProbingState.not_me:
            return 0.01

        if self._total_seqs < 5:
            confidence = 0.0
        else:
            confidence = (self._seq_counters[POSITIVE_CAT] + 0.25 * self._seq_counters[LIKELY_CAT] -
                          self._seq_counters[UNLIKELY_CAT] - self._seq_counters[NEGATIVE_CAT]) / self._total_seqs
        # lower the confidence of latin1 so that other more accurate detector can take priority.
        confidence = confidence * 0.805
        return confidence

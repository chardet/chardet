######################## BEGIN LICENSE BLOCK ########################
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 1998
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Jason Zavaglia
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
from chardet.enums import ProbingState
from .charsetprober import CharSetProber


# This class simply looks for occurrences of zero bytes, and infers
# whether the file is UTF16 or UTF32 (low-endian or big-endian)
# For instance, files looking like ( \0 \0 \0 [nonzero] )+
# appear to be UTF32LE.  Files looking like ( \0 [notzero] )+ appear
# may be guessed to be UTF16LE.

class UTF1632Prober(CharSetProber):

    # how many logical characters to scan before feeling confident in our prediction
    MIN_CHARS_FOR_DETECTION = 20
    # a fixed constant ratio of expected zeros or non-zeros in modulo-position.
    EXPECTED_RATIO = 0.94

    def __init__(self):
        super(UTF1632Prober, self).__init__()
        self.position = 0
        self.zeros_at_mod = [0] * 4
        self.nonzeros_at_mod = [0] * 4
        self._state = ProbingState.DETECTING
        self.reset()

    def reset(self):
        super(UTF1632Prober, self).reset()
        self.position = 0
        self.zeros_at_mod = [0] * 4
        self.nonzeros_at_mod = [0] * 4
        self._state = ProbingState.DETECTING

    @property
    def charset_name(self):
        if self.is_likely_utf32be():
            return "utf-32be"
        if self.is_likely_utf32le():
            return "utf-32le"
        if self.is_likely_utf16be():
            return "utf-16be"
        if self.is_likely_utf16le():
            return "utf-16le"
        # default to something valid
        return "utf-16"

    @property
    def language(self):
        return ""

    def approx_32bit_chars(self):
        return max(1.0, self.position / 4.0)

    def approx_16bit_chars(self):
        return max(1.0, self.position / 2.0)

    def is_likely_utf32be(self):
        approx_chars = self.approx_32bit_chars()
        return approx_chars >= self.MIN_CHARS_FOR_DETECTION and (
            self.zeros_at_mod[0] / approx_chars > self.EXPECTED_RATIO and
            self.zeros_at_mod[1] / approx_chars > self.EXPECTED_RATIO and
            self.zeros_at_mod[2] / approx_chars > self.EXPECTED_RATIO and
            self.nonzeros_at_mod[3] / approx_chars > self.EXPECTED_RATIO)

    def is_likely_utf32le(self):
        approx_chars = self.approx_32bit_chars()
        return approx_chars >= self.MIN_CHARS_FOR_DETECTION and (
            self.nonzeros_at_mod[0] / approx_chars > self.EXPECTED_RATIO and
            self.zeros_at_mod[1] / approx_chars > self.EXPECTED_RATIO and
            self.zeros_at_mod[2] / approx_chars > self.EXPECTED_RATIO and
            self.zeros_at_mod[3] / approx_chars > self.EXPECTED_RATIO)

    def is_likely_utf16be(self):
        approx_chars = self.approx_16bit_chars()
        return approx_chars >= self.MIN_CHARS_FOR_DETECTION and (
            (self.nonzeros_at_mod[1] + self.nonzeros_at_mod[3]) / approx_chars > self.EXPECTED_RATIO and
            (self.zeros_at_mod[0] + self.zeros_at_mod[2]) / approx_chars > self.EXPECTED_RATIO)

    def is_likely_utf16le(self):
        approx_chars = self.approx_16bit_chars()
        return approx_chars >= self.MIN_CHARS_FOR_DETECTION and (
            (self.nonzeros_at_mod[0] + self.nonzeros_at_mod[2]) / approx_chars > self.EXPECTED_RATIO and
            (self.zeros_at_mod[1] + self.zeros_at_mod[3]) / approx_chars > self.EXPECTED_RATIO)

    def feed(self, byte_str):
        for c in byte_str:
            if c == 0:
                self.zeros_at_mod[self.position % 4] += 1
            else:
                self.nonzeros_at_mod[self.position % 4] += 1
            self.position += 1
        return self.state()

    def state(self):
        if self._state in [ProbingState.NOT_ME, ProbingState.FOUND_IT]:
            # terminal, decided states
            return self._state
        elif self.get_confidence() > 0.95:
            self._state = ProbingState.FOUND_IT
        elif self.position > 4 * 1024:
            # if we get to 4kb into the file, and we can't conclude it's UTF,
            # let's give up
            self._state = ProbingState.NOT_ME
        return self._state

    def get_confidence(self):
        confidence = 0.99

        if self.is_likely_utf16le() or self.is_likely_utf16be() or self.is_likely_utf32le() or self.is_likely_utf32be():
            return confidence
        else:
            return 0.01

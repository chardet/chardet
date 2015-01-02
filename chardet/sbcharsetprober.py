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

from .charsetprober import CharSetProber
from .compat import wrap_ord
from .enums import ProbingState


class SingleByteCharSetProber(CharSetProber):
    SAMPLE_SIZE = 64
    SB_ENOUGH_REL_THRESHOLD = 1024
    POSITIVE_SHORTCUT_THRESHOLD = 0.95
    NEGATIVE_SHORTCUT_THRESHOLD = 0.05
    SYMBOL_CAT_ORDER = 250
    NUMBER_OF_SEQ_CAT = 4
    POSITIVE_CAT = NUMBER_OF_SEQ_CAT - 1

    def __init__(self, model, reversed=False, nameProber=None):
        super(SingleByteCharSetProber, self).__init__()
        self._Model = model
        # TRUE if we need to reverse every pair in the model lookup
        self._Reversed = reversed
        # Optional auxiliary prober for name decision
        self._NameProber = nameProber
        self.reset()

    def reset(self):
        super(SingleByteCharSetProber, self).reset()
        # char order of last character
        self._LastOrder = 255
        self._SeqCounters = [0] * self.NUMBER_OF_SEQ_CAT
        self._TotalSeqs = 0
        self._TotalChar = 0
        # characters that fall in our sampling range
        self._FreqChar = 0

    def get_charset_name(self):
        if self._NameProber:
            return self._NameProber.get_charset_name()
        else:
            return self._Model['charsetName']

    def feed(self, aBuf):
        if not self._Model['keepEnglishLetter']:
            aBuf = self.filter_international_words(aBuf)
        aLen = len(aBuf)
        if not aLen:
            return self.get_state()
        for c in aBuf:
            order = self._Model['charToOrderMap'][wrap_ord(c)]
            if order < self.SYMBOL_CAT_ORDER:
                self._TotalChar += 1
            if order < self.SAMPLE_SIZE:
                self._FreqChar += 1
                if self._LastOrder < self.SAMPLE_SIZE:
                    self._TotalSeqs += 1
                    if not self._Reversed:
                        i = (self._LastOrder * self.SAMPLE_SIZE) + order
                        model = self._Model['precedenceMatrix'][i]
                    else:  # reverse the order of the letters in the lookup
                        i = (order * self.SAMPLE_SIZE) + self._LastOrder
                        model = self._Model['precedenceMatrix'][i]
                    self._SeqCounters[model] += 1
            self._LastOrder = order

        if self.get_state() == ProbingState.detecting:
            if self._TotalSeqs > self.SB_ENOUGH_REL_THRESHOLD:
                cf = self.get_confidence()
                if cf > self.POSITIVE_SHORTCUT_THRESHOLD:
                    self.logger.debug('%s confidence = %s, we have a winner',
                                      self._Model['charsetName'], cf)
                    self._State = ProbingState.found_it
                elif cf < self.NEGATIVE_SHORTCUT_THRESHOLD:
                    self.logger.debug('%s confidence = %s, below negative '
                                      'shortcut threshhold %s',
                                      self._Model['charsetName'], cf,
                                      self.NEGATIVE_SHORTCUT_THRESHOLD)
                    self._State = ProbingState.not_me

        return self.get_state()

    def get_confidence(self):
        r = 0.01
        if self._TotalSeqs > 0:
            r = ((1.0 * self._SeqCounters[self.POSITIVE_CAT]) / self._TotalSeqs
                 / self._Model['mTypicalPositiveRatio'])
            r = r * self._FreqChar / self._TotalChar
            if r >= 1.0:
                r = 0.99
        return r

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
#   Proofpoint, Inc.
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
from .enums import ProbingState, SMState


class MultiByteCharSetProber(CharSetProber):
    """
    MultiByteCharSetProber
    """

    def __init__(self, language_filter=None):
        super(MultiByteCharSetProber, self).__init__(language_filter=language_filter)
        self._DistributionAnalyzer = None
        self._CodingSM = None
        self._LastChar = [0, 0]

    def reset(self):
        super(MultiByteCharSetProber, self).reset()
        if self._CodingSM:
            self._CodingSM.reset()
        if self._DistributionAnalyzer:
            self._DistributionAnalyzer.reset()
        self._LastChar = [0, 0]

    def get_charset_name(self):
        pass

    def feed(self, aBuf):
        aLen = len(aBuf)
        for i in range(0, aLen):
            codingState = self._CodingSM.next_state(aBuf[i])
            if codingState == SMState.error:
                self.logger.debug('%s prober hit error at byte %s',
                                  self.get_charset_name(), i)
                self._State = ProbingState.not_me
                break
            elif codingState == SMState.its_me:
                self._State = ProbingState.found_it
                break
            elif codingState == SMState.start:
                charLen = self._CodingSM.get_current_charlen()
                if i == 0:
                    self._LastChar[1] = aBuf[0]
                    self._DistributionAnalyzer.feed(self._LastChar, charLen)
                else:
                    self._DistributionAnalyzer.feed(aBuf[i - 1:i + 1],
                                                     charLen)

        self._LastChar[0] = aBuf[aLen - 1]

        if self.get_state() == ProbingState.detecting:
            if (self._DistributionAnalyzer.got_enough_data() and
                    (self.get_confidence() > self.SHORTCUT_THRESHOLD)):
                self._State = ProbingState.found_it

        return self.get_state()

    def get_confidence(self):
        return self._DistributionAnalyzer.get_confidence()

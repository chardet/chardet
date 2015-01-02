######################## BEGIN LICENSE BLOCK ########################
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 1998
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Mark Pilgrim - port to Python
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

from .enums import ProbingState, SMState
from .mbcharsetprober import MultiByteCharSetProber
from .codingstatemachine import CodingStateMachine
from .chardistribution import EUCJPDistributionAnalysis
from .jpcntx import EUCJPContextAnalysis
from .mbcssm import EUCJPSMModel


class EUCJPProber(MultiByteCharSetProber):
    def __init__(self):
        super(EUCJPProber, self).__init__()
        self._CodingSM = CodingStateMachine(EUCJPSMModel)
        self._DistributionAnalyzer = EUCJPDistributionAnalysis()
        self._ContextAnalyzer = EUCJPContextAnalysis()
        self.reset()

    def reset(self):
        super(EUCJPProber, self).reset()
        self._ContextAnalyzer.reset()

    def get_charset_name(self):
        return "EUC-JP"

    def feed(self, aBuf):
        aLen = len(aBuf)
        for i in range(0, aLen):
            # PY3K: aBuf is a byte array, so aBuf[i] is an int, not a byte
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
                    self._ContextAnalyzer.feed(self._LastChar, charLen)
                    self._DistributionAnalyzer.feed(self._LastChar, charLen)
                else:
                    self._ContextAnalyzer.feed(aBuf[i - 1:i + 1], charLen)
                    self._DistributionAnalyzer.feed(aBuf[i - 1:i + 1],
                                                     charLen)

        self._LastChar[0] = aBuf[aLen - 1]

        if self.get_state() == ProbingState.detecting:
            if (self._ContextAnalyzer.got_enough_data() and
               (self.get_confidence() > self.SHORTCUT_THRESHOLD)):
                self._State = ProbingState.found_it

        return self.get_state()

    def get_confidence(self):
        contxtCf = self._ContextAnalyzer.get_confidence()
        distribCf = self._DistributionAnalyzer.get_confidence()
        return max(contxtCf, distribCf)

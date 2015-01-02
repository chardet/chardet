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

from .charsetprober import CharSetProber
from .codingstatemachine import CodingStateMachine
from .compat import wrap_ord
from .enums import LanguageFilter, ProbingState, SMState
from .escsm import (HZSMModel, ISO2022CNSMModel, ISO2022JPSMModel,
                    ISO2022KRSMModel)


class EscCharSetProber(CharSetProber):
    """
    This CharSetProber uses a "code scheme" approach for detecting encodings,
    whereby easily recognizable escape or shift sequences are relied on to
    identify these encodings.
    """

    def __init__(self, language_filter=None):
        super(EscCharSetProber, self).__init__(language_filter=language_filter)
        self._CodingSM = []
        if self._language_filter & LanguageFilter.chinese_simplified:
            self._CodingSM.append(CodingStateMachine(HZSMModel))
            self._CodingSM.append(CodingStateMachine(ISO2022CNSMModel))
        if self._language_filter & LanguageFilter.japanese:
            self._CodingSM.append(CodingStateMachine(ISO2022JPSMModel))
        if self._language_filter & LanguageFilter.korean:
            self._CodingSM.append(CodingStateMachine(ISO2022KRSMModel))
        self._ActiveSM = None
        self._DetectedCharset = None
        self._State = None
        self.reset()

    def reset(self):
        super(EscCharSetProber, self).reset()
        for codingSM in self._CodingSM:
            if not codingSM:
                continue
            codingSM.active = True
            codingSM.reset()
        self._ActiveSM = len(self._CodingSM)
        self._DetectedCharset = None

    def get_charset_name(self):
        return self._DetectedCharset

    def get_confidence(self):
        if self._DetectedCharset:
            return 0.99
        else:
            return 0.00

    def feed(self, aBuf):
        for c in aBuf:
            # PY3K: aBuf is a byte array, so c is an int, not a byte
            for codingSM in self._CodingSM:
                if not codingSM:
                    continue
                if not codingSM.active:
                    continue
                codingState = codingSM.next_state(wrap_ord(c))
                if codingState == SMState.error:
                    codingSM.active = False
                    self._ActiveSM -= 1
                    if self._ActiveSM <= 0:
                        self._State = ProbingState.not_me
                        return self.get_state()
                elif codingState == SMState.its_me:
                    self._State = ProbingState.found_it
                    self._DetectedCharset = codingSM.get_coding_state_machine()
                    return self.get_state()

        return self.get_state()

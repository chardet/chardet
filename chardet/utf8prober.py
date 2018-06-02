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
from .enums import ProbingState, MachineState
from .codingstatemachine import CodingStateMachine
from .mbcssm import UTF8_SM_MODEL



class UTF8Prober(CharSetProber):
    ONE_CHAR_PROB = 0.5

    def __init__(self):
        super(UTF8Prober, self).__init__()
        self.coding_sm = CodingStateMachine(UTF8_SM_MODEL)
        self._num_mb_chars = None
        self.reset()

    def reset(self):
        super(UTF8Prober, self).reset()
        self.coding_sm.reset()
        self._num_mb_chars = 0

    @property
    def charset_name(self):
        return "utf-8"

    @property
    def language(self):
        return ""

    def feed(self, byte_str):
        for c in byte_str:
            coding_state = self.coding_sm.next_state(c)
            if coding_state == MachineState.ERROR:
                self._state = ProbingState.NOT_ME
                break
            elif coding_state == MachineState.ITS_ME:
                self._state = ProbingState.FOUND_IT
                break
            elif coding_state == MachineState.START:
                if self.coding_sm.get_current_charlen() >= 2:
                    self._num_mb_chars += 1

        if self.state == ProbingState.DETECTING:
            if self.get_confidence() > self.SHORTCUT_THRESHOLD:
                self._state = ProbingState.FOUND_IT

        return self.state

    def get_confidence(self):
        unlike = 0.99
        if self._num_mb_chars == 1:
            # guarantee to be prefered over ISO-8859-1, defaults to 0.731
            unlike *= self.ONE_CHAR_PROB * (1-0.731)/0.99/0.5
            return 1.0 - unlike
        elif self._num_mb_chars < 6:
            unlike *= self.ONE_CHAR_PROB ** self._num_mb_chars
            return 1.0 - unlike
        else:
            return unlike

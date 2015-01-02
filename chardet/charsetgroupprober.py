######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Communicator client code.
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

from .enums import ProbingState
from .charsetprober import CharSetProber


class CharSetGroupProber(CharSetProber):
    def __init__(self, language_filter=None):
        super(CharSetGroupProber, self).__init__(language_filter=language_filter)
        self._ActiveNum = 0
        self._Probers = []
        self._BestGuessProber = None

    def reset(self):
        super(CharSetGroupProber, self).reset()
        self._ActiveNum = 0
        for prober in self._Probers:
            if prober:
                prober.reset()
                prober.active = True
                self._ActiveNum += 1
        self._BestGuessProber = None

    def get_charset_name(self):
        if not self._BestGuessProber:
            self.get_confidence()
            if not self._BestGuessProber:
                return None
        return self._BestGuessProber.get_charset_name()

    def feed(self, aBuf):
        for prober in self._Probers:
            if not prober:
                continue
            if not prober.active:
                continue
            st = prober.feed(aBuf)
            if not st:
                continue
            if st == ProbingState.found_it:
                self._BestGuessProber = prober
                return self.get_state()
            elif st == ProbingState.not_me:
                prober.active = False
                self._ActiveNum -= 1
                if self._ActiveNum <= 0:
                    self._State = ProbingState.not_me
                    return self.get_state()
        return self.get_state()

    def get_confidence(self):
        st = self.get_state()
        if st == ProbingState.found_it:
            return 0.99
        elif st == ProbingState.not_me:
            return 0.01
        bestConf = 0.0
        self._BestGuessProber = None
        for prober in self._Probers:
            if not prober:
                continue
            if not prober.active:
                self.logger.debug(prober.get_charset_name() + ' not active')
                continue
            cf = prober.get_confidence()
            self.logger.debug('%s confidence = %s\n',
                              prober.get_charset_name(), cf)
            if bestConf < cf:
                bestConf = cf
                self._BestGuessProber = prober
        if not self._BestGuessProber:
            return 0.0
        return bestConf

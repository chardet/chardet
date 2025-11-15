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
# License along with this library; if not, see
# <https://www.gnu.org/licenses/>.
######################### END LICENSE BLOCK #########################

from .chardistribution import GB2312DistributionAnalysis
from .codingstatemachine import CodingStateMachine
from .mbcharsetprober import MultiByteCharSetProber
from .mbcssm import GB18030_SM_MODEL


class GB18030Prober(MultiByteCharSetProber):
    def __init__(self) -> None:
        super().__init__()
        self.coding_sm = CodingStateMachine(GB18030_SM_MODEL)
        # GB18030 is a superset of GB2312, so we can reuse GB2312's
        # character distribution analysis for the 2-byte sequences
        self.distribution_analyzer = GB2312DistributionAnalysis()
        self.reset()

    @property
    def charset_name(self) -> str:
        return "GB18030"

    @property
    def language(self) -> str:
        return "Chinese"

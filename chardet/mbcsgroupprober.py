######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Universal charset detector code.
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
#
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2001 Netscape Communications Corporation
# SPDX-FileContributor: Mark Pilgim (port to Python)
# SPDX-FileContributor: Shy Shalom (original C code)
# SPDX-FileContributor: Proofpoint, Inc.
######################### END LICENSE BLOCK #########################

from .big5prober import Big5Prober
from .charsetgroupprober import CharSetGroupProber
from .cp949prober import CP949Prober
from .enums import LanguageFilter
from .eucjpprober import EUCJPProber
from .euckrprober import EUCKRProber
from .euctwprober import EUCTWProber
from .gb2312prober import GB2312Prober
from .johabprober import JOHABProber
from .sjisprober import SJISProber
from .utf8prober import UTF8Prober


class MBCSGroupProber(CharSetGroupProber):
    def __init__(self, lang_filter: LanguageFilter = LanguageFilter.NONE) -> None:
        super().__init__(lang_filter=lang_filter)
        self.probers = [
            UTF8Prober(),
            SJISProber(),
            EUCJPProber(),
            GB2312Prober(),
            EUCKRProber(),
            CP949Prober(),
            Big5Prober(),
            EUCTWProber(),
            JOHABProber(),
        ]
        self.reset()

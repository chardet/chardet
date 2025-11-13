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

from .codingstatemachinedict import CodingStateMachineDict
from .enums import MachineState

# BIG5

# fmt: off
BIG5_CLS = (
    1, 1, 1, 1, 1, 1, 1, 1,  # 00 - 07    #allow 0x00 as legal value
    1, 1, 1, 1, 1, 1, 0, 0,  # 08 - 0f
    1, 1, 1, 1, 1, 1, 1, 1,  # 10 - 17
    1, 1, 1, 0, 1, 1, 1, 1,  # 18 - 1f
    1, 1, 1, 1, 1, 1, 1, 1,  # 20 - 27
    1, 1, 1, 1, 1, 1, 1, 1,  # 28 - 2f
    1, 1, 1, 1, 1, 1, 1, 1,  # 30 - 37
    1, 1, 1, 1, 1, 1, 1, 1,  # 38 - 3f
    2, 2, 2, 2, 2, 2, 2, 2,  # 40 - 47
    2, 2, 2, 2, 2, 2, 2, 2,  # 48 - 4f
    2, 2, 2, 2, 2, 2, 2, 2,  # 50 - 57
    2, 2, 2, 2, 2, 2, 2, 2,  # 58 - 5f
    2, 2, 2, 2, 2, 2, 2, 2,  # 60 - 67
    2, 2, 2, 2, 2, 2, 2, 2,  # 68 - 6f
    2, 2, 2, 2, 2, 2, 2, 2,  # 70 - 77
    2, 2, 2, 2, 2, 2, 2, 1,  # 78 - 7f
    4, 4, 4, 4, 4, 4, 4, 4,  # 80 - 87
    4, 4, 4, 4, 4, 4, 4, 4,  # 88 - 8f
    4, 4, 4, 4, 4, 4, 4, 4,  # 90 - 97
    4, 4, 4, 4, 4, 4, 4, 4,  # 98 - 9f
    4, 3, 3, 3, 3, 3, 3, 3,  # a0 - a7
    3, 3, 3, 3, 3, 3, 3, 3,  # a8 - af
    3, 3, 3, 3, 3, 3, 3, 3,  # b0 - b7
    3, 3, 3, 3, 3, 3, 3, 3,  # b8 - bf
    3, 3, 3, 3, 3, 3, 3, 3,  # c0 - c7
    3, 3, 3, 3, 3, 3, 3, 3,  # c8 - cf
    3, 3, 3, 3, 3, 3, 3, 3,  # d0 - d7
    3, 3, 3, 3, 3, 3, 3, 3,  # d8 - df
    3, 3, 3, 3, 3, 3, 3, 3,  # e0 - e7
    3, 3, 3, 3, 3, 3, 3, 3,  # e8 - ef
    3, 3, 3, 3, 3, 3, 3, 3,  # f0 - f7
    3, 3, 3, 3, 3, 3, 3, 0  # f8 - ff
)

BIG5_ST = (
    MachineState.ERROR,MachineState.START,MachineState.START,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,#00-07
    MachineState.ERROR,MachineState.ERROR,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ERROR,#08-0f
    MachineState.ERROR,MachineState.START,MachineState.START,MachineState.START,MachineState.START,MachineState.START,MachineState.START,MachineState.START#10-17
)
# fmt: on

BIG5_CHAR_LEN_TABLE = (0, 1, 1, 2, 0)

BIG5_SM_MODEL: CodingStateMachineDict = {
    "class_table": BIG5_CLS,
    "class_factor": 5,
    "state_table": BIG5_ST,
    "char_len_table": BIG5_CHAR_LEN_TABLE,
    "name": "Big5",
}

# CP949
# fmt: off

"""
# Classes
0: Unused
1: 00-40, 5B-60, 7B-7F : Ascii
2: C7-FD
3: C9,FE : User-Defined Area
4: 41-52
5: 53-5A, 61-7A
6: 81-A0
7: A1-AC, B0-C5
8: AD-AF
9: C6

# Byte 1
Ascii:   00-7F           : 1 + 4 + 5
State 3: 81-AC, B0-C5    : 6 + 7
State 4: AD-AF           : 8
State 5: C6              : 9
State 6: C7-FE           : 2 (+ 3)


# Byte 2
State 3: 41-5A, 61-7A, 81-FE        : 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9
State 4: 41-5A, 61-7A, 81-A0        : 4 + 5 + 6
State 5: 41-52, A1-FE               : 2 + 3 + 4 + 7 + 8 + 9
State 6: A1-FE                      : 2 + 3 + 7 + 8 + 9
"""

CP949_CLS  = (
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,  # 00 - 0f
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1,  # 10 - 1f
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 20 - 2f
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 30 - 3f
    1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,  # 40 - 4f
    4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 1, 1, 1, 1, 1,  # 50 - 5f
    1, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,  # 60 - 6f
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 1, 1, 1, 1, 1,  # 70 - 7f
    0, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,  # 80 - 8f
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,  # 90 - 9f
    6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8,  # a0 - af
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,  # b0 - bf
    7, 7, 7, 7, 7, 7, 9, 2, 2, 3, 2, 2, 2, 2, 2, 2,  # c0 - cf
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # d0 - df
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # e0 - ef
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 0,  # f0 - ff
)

CP949_ST = (
    #         0                  1                   2                   3                   4                   5                   6                   7                   8                   9
    MachineState.ERROR, MachineState.START, 6,                  MachineState.ERROR, MachineState.START, MachineState.START, 3,                  3,                  4,                  5,                   # START
    MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR,  # ERROR
    MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME, # ITSME
    MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.START, MachineState.START, MachineState.START, MachineState.START, MachineState.START, MachineState.START,  # 3
    MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.START, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR,  # 4
    MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.START, MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.START,  # 5
    MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.START, MachineState.START, MachineState.START,  # 6
)
# fmt: on

CP949_CHAR_LEN_TABLE = (0, 1, 2, 0, 1, 1, 2, 2, 2, 2)

CP949_SM_MODEL: CodingStateMachineDict = {
    "class_table": CP949_CLS,
    "class_factor": 10,
    "state_table": CP949_ST,
    "char_len_table": CP949_CHAR_LEN_TABLE,
    "name": "CP949",
}

# EUC-JP
# fmt: off
EUCJP_CLS = (
    4, 4, 4, 4, 4, 4, 4, 4,  # 00 - 07
    4, 4, 4, 4, 4, 4, 5, 5,  # 08 - 0f
    4, 4, 4, 4, 4, 4, 4, 4,  # 10 - 17
    4, 4, 4, 5, 4, 4, 4, 4,  # 18 - 1f
    4, 4, 4, 4, 4, 4, 4, 4,  # 20 - 27
    4, 4, 4, 4, 4, 4, 4, 4,  # 28 - 2f
    4, 4, 4, 4, 4, 4, 4, 4,  # 30 - 37
    4, 4, 4, 4, 4, 4, 4, 4,  # 38 - 3f
    4, 4, 4, 4, 4, 4, 4, 4,  # 40 - 47
    4, 4, 4, 4, 4, 4, 4, 4,  # 48 - 4f
    4, 4, 4, 4, 4, 4, 4, 4,  # 50 - 57
    4, 4, 4, 4, 4, 4, 4, 4,  # 58 - 5f
    4, 4, 4, 4, 4, 4, 4, 4,  # 60 - 67
    4, 4, 4, 4, 4, 4, 4, 4,  # 68 - 6f
    4, 4, 4, 4, 4, 4, 4, 4,  # 70 - 77
    4, 4, 4, 4, 4, 4, 4, 4,  # 78 - 7f
    5, 5, 5, 5, 5, 5, 5, 5,  # 80 - 87
    5, 5, 5, 5, 5, 5, 1, 3,  # 88 - 8f
    5, 5, 5, 5, 5, 5, 5, 5,  # 90 - 97
    5, 5, 5, 5, 5, 5, 5, 5,  # 98 - 9f
    5, 2, 2, 2, 2, 2, 2, 2,  # a0 - a7
    2, 2, 2, 2, 2, 2, 2, 2,  # a8 - af
    2, 2, 2, 2, 2, 2, 2, 2,  # b0 - b7
    2, 2, 2, 2, 2, 2, 2, 2,  # b8 - bf
    2, 2, 2, 2, 2, 2, 2, 2,  # c0 - c7
    2, 2, 2, 2, 2, 2, 2, 2,  # c8 - cf
    2, 2, 2, 2, 2, 2, 2, 2,  # d0 - d7
    2, 2, 2, 2, 2, 2, 2, 2,  # d8 - df
    0, 0, 0, 0, 0, 0, 0, 0,  # e0 - e7
    0, 0, 0, 0, 0, 0, 0, 0,  # e8 - ef
    0, 0, 0, 0, 0, 0, 0, 0,  # f0 - f7
    0, 0, 0, 0, 0, 0, 0, 5  # f8 - ff
)

EUCJP_ST = (
          3,     4,     3,     5,MachineState.START,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,#00-07
     MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,#08-0f
     MachineState.ITS_ME,MachineState.ITS_ME,MachineState.START,MachineState.ERROR,MachineState.START,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,#10-17
     MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     3,MachineState.ERROR,#18-1f
          3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.START,MachineState.START,MachineState.START#20-27
)
# fmt: on

EUCJP_CHAR_LEN_TABLE = (2, 2, 2, 3, 1, 0)

EUCJP_SM_MODEL: CodingStateMachineDict = {
    "class_table": EUCJP_CLS,
    "class_factor": 6,
    "state_table": EUCJP_ST,
    "char_len_table": EUCJP_CHAR_LEN_TABLE,
    "name": "EUC-JP",
}

# EUC-KR
# fmt: off
EUCKR_CLS  = (
    1, 1, 1, 1, 1, 1, 1, 1,  # 00 - 07
    1, 1, 1, 1, 1, 1, 0, 0,  # 08 - 0f
    1, 1, 1, 1, 1, 1, 1, 1,  # 10 - 17
    1, 1, 1, 0, 1, 1, 1, 1,  # 18 - 1f
    1, 1, 1, 1, 1, 1, 1, 1,  # 20 - 27
    1, 1, 1, 1, 1, 1, 1, 1,  # 28 - 2f
    1, 1, 1, 1, 1, 1, 1, 1,  # 30 - 37
    1, 1, 1, 1, 1, 1, 1, 1,  # 38 - 3f
    1, 1, 1, 1, 1, 1, 1, 1,  # 40 - 47
    1, 1, 1, 1, 1, 1, 1, 1,  # 48 - 4f
    1, 1, 1, 1, 1, 1, 1, 1,  # 50 - 57
    1, 1, 1, 1, 1, 1, 1, 1,  # 58 - 5f
    1, 1, 1, 1, 1, 1, 1, 1,  # 60 - 67
    1, 1, 1, 1, 1, 1, 1, 1,  # 68 - 6f
    1, 1, 1, 1, 1, 1, 1, 1,  # 70 - 77
    1, 1, 1, 1, 1, 1, 1, 1,  # 78 - 7f
    0, 0, 0, 0, 0, 0, 0, 0,  # 80 - 87
    0, 0, 0, 0, 0, 0, 0, 0,  # 88 - 8f
    0, 0, 0, 0, 0, 0, 0, 0,  # 90 - 97
    0, 0, 0, 0, 0, 0, 0, 0,  # 98 - 9f
    0, 2, 2, 2, 2, 2, 2, 2,  # a0 - a7
    2, 2, 2, 2, 2, 3, 3, 3,  # a8 - af
    2, 2, 2, 2, 2, 2, 2, 2,  # b0 - b7
    2, 2, 2, 2, 2, 2, 2, 2,  # b8 - bf
    2, 2, 2, 2, 2, 2, 2, 2,  # c0 - c7
    2, 3, 2, 2, 2, 2, 2, 2,  # c8 - cf
    2, 2, 2, 2, 2, 2, 2, 2,  # d0 - d7
    2, 2, 2, 2, 2, 2, 2, 2,  # d8 - df
    2, 2, 2, 2, 2, 2, 2, 2,  # e0 - e7
    2, 2, 2, 2, 2, 2, 2, 2,  # e8 - ef
    2, 2, 2, 2, 2, 2, 2, 2,  # f0 - f7
    2, 2, 2, 2, 2, 2, 2, 0   # f8 - ff
)

EUCKR_ST = (
    MachineState.ERROR,MachineState.START,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,#00-07
    MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.START #08-0f
)
# fmt: on

EUCKR_CHAR_LEN_TABLE = (0, 1, 2, 0)

EUCKR_SM_MODEL: CodingStateMachineDict = {
    "class_table": EUCKR_CLS,
    "class_factor": 4,
    "state_table": EUCKR_ST,
    "char_len_table": EUCKR_CHAR_LEN_TABLE,
    "name": "EUC-KR",
}

# JOHAB
# fmt: off
JOHAB_CLS = (
    4,4,4,4,4,4,4,4,  # 00 - 07
    4,4,4,4,4,4,0,0,  # 08 - 0f
    4,4,4,4,4,4,4,4,  # 10 - 17
    4,4,4,0,4,4,4,4,  # 18 - 1f
    4,4,4,4,4,4,4,4,  # 20 - 27
    4,4,4,4,4,4,4,4,  # 28 - 2f
    4,3,3,3,3,3,3,3,  # 30 - 37
    3,3,3,3,3,3,3,3,  # 38 - 3f
    3,1,1,1,1,1,1,1,  # 40 - 47
    1,1,1,1,1,1,1,1,  # 48 - 4f
    1,1,1,1,1,1,1,1,  # 50 - 57
    1,1,1,1,1,1,1,1,  # 58 - 5f
    1,1,1,1,1,1,1,1,  # 60 - 67
    1,1,1,1,1,1,1,1,  # 68 - 6f
    1,1,1,1,1,1,1,1,  # 70 - 77
    1,1,1,1,1,1,1,2,  # 78 - 7f
    6,6,6,6,8,8,8,8,  # 80 - 87
    8,8,8,8,8,8,8,8,  # 88 - 8f
    8,7,7,7,7,7,7,7,  # 90 - 97
    7,7,7,7,7,7,7,7,  # 98 - 9f
    7,7,7,7,7,7,7,7,  # a0 - a7
    7,7,7,7,7,7,7,7,  # a8 - af
    7,7,7,7,7,7,7,7,  # b0 - b7
    7,7,7,7,7,7,7,7,  # b8 - bf
    7,7,7,7,7,7,7,7,  # c0 - c7
    7,7,7,7,7,7,7,7,  # c8 - cf
    7,7,7,7,5,5,5,5,  # d0 - d7
    5,9,9,9,9,9,9,5,  # d8 - df
    9,9,9,9,9,9,9,9,  # e0 - e7
    9,9,9,9,9,9,9,9,  # e8 - ef
    9,9,9,9,9,9,9,9,  # f0 - f7
    9,9,5,5,5,5,5,0   # f8 - ff
)

JOHAB_ST = (
# cls = 0                   1                   2                   3                   4                   5                   6                   7                   8                   9
    MachineState.ERROR ,MachineState.START ,MachineState.START ,MachineState.START ,MachineState.START ,MachineState.ERROR ,MachineState.ERROR ,3                  ,3                  ,4                  ,  # MachineState.START
    MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,  # MachineState.ITS_ME
    MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,MachineState.ERROR ,  # MachineState.ERROR
    MachineState.ERROR ,MachineState.START ,MachineState.START ,MachineState.ERROR ,MachineState.ERROR ,MachineState.START ,MachineState.START ,MachineState.START ,MachineState.START ,MachineState.START ,  # 3
    MachineState.ERROR ,MachineState.START ,MachineState.ERROR ,MachineState.START ,MachineState.ERROR ,MachineState.START ,MachineState.ERROR ,MachineState.START ,MachineState.ERROR ,MachineState.START ,  # 4
)
# fmt: on

JOHAB_CHAR_LEN_TABLE = (0, 1, 1, 1, 1, 0, 0, 2, 2, 2)

JOHAB_SM_MODEL: CodingStateMachineDict = {
    "class_table": JOHAB_CLS,
    "class_factor": 10,
    "state_table": JOHAB_ST,
    "char_len_table": JOHAB_CHAR_LEN_TABLE,
    "name": "Johab",
}

# GB2312 - REMOVED
# GB2312 is a subset of GB18030. The GB18030 state machine and prober now
# correctly detect GB2312 content with the same confidence as the old GB2312
# prober (both use GB2312DistributionAnalysis). The LEGACY_MAP renames
# GB2312 → GB18030 for backward compatibility.
# Having both probers was redundant after fixing GB18030's char_len_table.

# GB18030
# GB18030 is a superset of GB2312 and GBK
# It supports:
#   - 1-byte: ASCII (0x00-0x7F)
#   - 2-byte: lead 0x81-0xFE, trail 0x40-0x7E or 0x80-0xFE (GBK/GB2312 compatible)
#   - 4-byte: 0x81-0xFE, 0x30-0x39, 0x81-0xFE, 0x30-0x39 (GB18030 extension)
#
# Byte classes:
#   0: Invalid
#   1: ASCII (0x00-0x7F)
#   2: Digit 0x30-0x39 (can be 2nd or 4th byte in 4-byte sequence)
#   3: Valid 2-byte trail (0x40-0x7E)
#   4: Invalid byte 0x7F
#   5: Valid 2-byte trail and lead for 4-byte (0x80-0xFE)
#   6: Lead byte (0x81-0xFE) - can start 2-byte or 4-byte, or be 3rd byte in 4-byte

# fmt: off
GB18030_CLS = (
    1, 1, 1, 1, 1, 1, 1, 1,  # 00 - 07
    1, 1, 1, 1, 1, 1, 0, 0,  # 08 - 0f
    1, 1, 1, 1, 1, 1, 1, 1,  # 10 - 17
    1, 1, 1, 0, 1, 1, 1, 1,  # 18 - 1f
    1, 1, 1, 1, 1, 1, 1, 1,  # 20 - 27
    1, 1, 1, 1, 1, 1, 1, 1,  # 28 - 2f
    2, 2, 2, 2, 2, 2, 2, 2,  # 30 - 37
    2, 2, 1, 1, 1, 1, 1, 1,  # 38 - 3f
    3, 3, 3, 3, 3, 3, 3, 3,  # 40 - 47
    3, 3, 3, 3, 3, 3, 3, 3,  # 48 - 4f
    3, 3, 3, 3, 3, 3, 3, 3,  # 50 - 57
    3, 3, 3, 3, 3, 3, 3, 3,  # 58 - 5f
    3, 3, 3, 3, 3, 3, 3, 3,  # 60 - 67
    3, 3, 3, 3, 3, 3, 3, 3,  # 68 - 6f
    3, 3, 3, 3, 3, 3, 3, 3,  # 70 - 77
    3, 3, 3, 3, 3, 3, 3, 4,  # 78 - 7f
    5, 6, 6, 6, 6, 6, 6, 6,  # 80 - 87    0x80 can be trail byte (class 5)
    6, 6, 6, 6, 6, 6, 6, 6,  # 88 - 8f
    6, 6, 6, 6, 6, 6, 6, 6,  # 90 - 97
    6, 6, 6, 6, 6, 6, 6, 6,  # 98 - 9f
    6, 6, 6, 6, 6, 6, 6, 6,  # a0 - a7
    6, 6, 6, 6, 6, 6, 6, 6,  # a8 - af
    6, 6, 6, 6, 6, 6, 6, 6,  # b0 - b7
    6, 6, 6, 6, 6, 6, 6, 6,  # b8 - bf
    6, 6, 6, 6, 6, 6, 6, 6,  # c0 - c7
    6, 6, 6, 6, 6, 6, 6, 6,  # c8 - cf
    6, 6, 6, 6, 6, 6, 6, 6,  # d0 - d7
    6, 6, 6, 6, 6, 6, 6, 6,  # d8 - df
    6, 6, 6, 6, 6, 6, 6, 6,  # e0 - e7
    6, 6, 6, 6, 6, 6, 6, 6,  # e8 - ef
    6, 6, 6, 6, 6, 6, 6, 6,  # f0 - f7
    6, 6, 6, 6, 6, 6, 6, 0   # f8 - ff    0xFF is invalid
)

# States:
#   START (0): Initial state
#   ERROR (1): Error state
#   ITS_ME (2): Definitive match
#   FIRST (3): After receiving lead byte (0x81-0xFE)
#   SECOND_4BYTE (4): After digit as 2nd byte in potential 4-byte sequence
#   THIRD_4BYTE (5): After 3rd byte (0x81-0xFE) in 4-byte sequence
GB18030_ST = (
#  cls:    0                     1                   2                   3                   4                  5                 6
    MachineState.ERROR,  MachineState.START, MachineState.START, MachineState.START, MachineState.START,MachineState.ERROR,     3,  # START (0)
    MachineState.ERROR,  MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,  # ERROR (1)
    MachineState.ITS_ME, MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,  # ITS_ME (2)
    MachineState.ERROR,  MachineState.ERROR,          4,MachineState.START, MachineState.ERROR,MachineState.START,MachineState.START,  # FIRST (3): 0x81-0xFE completes 2-byte
    MachineState.ERROR,  MachineState.ERROR, MachineState.ERROR, MachineState.ERROR, MachineState.ERROR,MachineState.ERROR,          5,  # SECOND_4BYTE (4): after 2nd digit
    MachineState.ERROR,  MachineState.ERROR, MachineState.START, MachineState.ERROR, MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,  # THIRD_4BYTE (5): after 3rd byte
)
# fmt: on

# Character length table for distribution analysis
# Class 6 (lead byte) is marked as 2 bytes since that's the most common case
# (2-byte GB2312/GBK sequences). 4-byte sequences will be detected by the state
# machine but won't contribute to character distribution analysis.
GB18030_CHAR_LEN_TABLE = (0, 1, 1, 1, 1, 2, 2)

GB18030_SM_MODEL: CodingStateMachineDict = {
    "class_table": GB18030_CLS,
    "class_factor": 7,
    "state_table": GB18030_ST,
    "char_len_table": GB18030_CHAR_LEN_TABLE,
    "name": "GB18030",
}

# Shift_JIS
# fmt: off
SJIS_CLS = (
    1, 1, 1, 1, 1, 1, 1, 1,  # 00 - 07
    1, 1, 1, 1, 1, 1, 0, 0,  # 08 - 0f
    1, 1, 1, 1, 1, 1, 1, 1,  # 10 - 17
    1, 1, 1, 0, 1, 1, 1, 1,  # 18 - 1f
    1, 1, 1, 1, 1, 1, 1, 1,  # 20 - 27
    1, 1, 1, 1, 1, 1, 1, 1,  # 28 - 2f
    1, 1, 1, 1, 1, 1, 1, 1,  # 30 - 37
    1, 1, 1, 1, 1, 1, 1, 1,  # 38 - 3f
    2, 2, 2, 2, 2, 2, 2, 2,  # 40 - 47
    2, 2, 2, 2, 2, 2, 2, 2,  # 48 - 4f
    2, 2, 2, 2, 2, 2, 2, 2,  # 50 - 57
    2, 2, 2, 2, 2, 2, 2, 2,  # 58 - 5f
    2, 2, 2, 2, 2, 2, 2, 2,  # 60 - 67
    2, 2, 2, 2, 2, 2, 2, 2,  # 68 - 6f
    2, 2, 2, 2, 2, 2, 2, 2,  # 70 - 77
    2, 2, 2, 2, 2, 2, 2, 1,  # 78 - 7f
    3, 3, 3, 3, 3, 2, 2, 3,  # 80 - 87
    3, 3, 3, 3, 3, 3, 3, 3,  # 88 - 8f
    3, 3, 3, 3, 3, 3, 3, 3,  # 90 - 97
    3, 3, 3, 3, 3, 3, 3, 3,  # 98 - 9f
    #0xa0 is illegal in sjis encoding, but some pages does
    #contain such byte. We need to be more error forgiven.
    2, 2, 2, 2, 2, 2, 2, 2,  # a0 - a7
    2, 2, 2, 2, 2, 2, 2, 2,  # a8 - af
    2, 2, 2, 2, 2, 2, 2, 2,  # b0 - b7
    2, 2, 2, 2, 2, 2, 2, 2,  # b8 - bf
    2, 2, 2, 2, 2, 2, 2, 2,  # c0 - c7
    2, 2, 2, 2, 2, 2, 2, 2,  # c8 - cf
    2, 2, 2, 2, 2, 2, 2, 2,  # d0 - d7
    2, 2, 2, 2, 2, 2, 2, 2,  # d8 - df
    3, 3, 3, 3, 3, 3, 3, 3,  # e0 - e7
    3, 3, 3, 3, 3, 4, 4, 4,  # e8 - ef
    3, 3, 3, 3, 3, 3, 3, 3,  # f0 - f7
    3, 3, 3, 3, 3, 0, 0, 0,  # f8 - ff
)

SJIS_ST = (
    MachineState.ERROR,MachineState.START,MachineState.START,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,#00-07
    MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,#08-0f
    MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.START,MachineState.START,MachineState.START #10-17
)
# fmt: on

SJIS_CHAR_LEN_TABLE = (0, 1, 1, 2, 0, 0)

SJIS_SM_MODEL: CodingStateMachineDict = {
    "class_table": SJIS_CLS,
    "class_factor": 6,
    "state_table": SJIS_ST,
    "char_len_table": SJIS_CHAR_LEN_TABLE,
    "name": "Shift_JIS",
}

# UCS2-BE
# fmt: off
UCS2BE_CLS = (
    0, 0, 0, 0, 0, 0, 0, 0,  # 00 - 07
    0, 0, 1, 0, 0, 2, 0, 0,  # 08 - 0f
    0, 0, 0, 0, 0, 0, 0, 0,  # 10 - 17
    0, 0, 0, 3, 0, 0, 0, 0,  # 18 - 1f
    0, 0, 0, 0, 0, 0, 0, 0,  # 20 - 27
    0, 3, 3, 3, 3, 3, 0, 0,  # 28 - 2f
    0, 0, 0, 0, 0, 0, 0, 0,  # 30 - 37
    0, 0, 0, 0, 0, 0, 0, 0,  # 38 - 3f
    0, 0, 0, 0, 0, 0, 0, 0,  # 40 - 47
    0, 0, 0, 0, 0, 0, 0, 0,  # 48 - 4f
    0, 0, 0, 0, 0, 0, 0, 0,  # 50 - 57
    0, 0, 0, 0, 0, 0, 0, 0,  # 58 - 5f
    0, 0, 0, 0, 0, 0, 0, 0,  # 60 - 67
    0, 0, 0, 0, 0, 0, 0, 0,  # 68 - 6f
    0, 0, 0, 0, 0, 0, 0, 0,  # 70 - 77
    0, 0, 0, 0, 0, 0, 0, 0,  # 78 - 7f
    0, 0, 0, 0, 0, 0, 0, 0,  # 80 - 87
    0, 0, 0, 0, 0, 0, 0, 0,  # 88 - 8f
    0, 0, 0, 0, 0, 0, 0, 0,  # 90 - 97
    0, 0, 0, 0, 0, 0, 0, 0,  # 98 - 9f
    0, 0, 0, 0, 0, 0, 0, 0,  # a0 - a7
    0, 0, 0, 0, 0, 0, 0, 0,  # a8 - af
    0, 0, 0, 0, 0, 0, 0, 0,  # b0 - b7
    0, 0, 0, 0, 0, 0, 0, 0,  # b8 - bf
    0, 0, 0, 0, 0, 0, 0, 0,  # c0 - c7
    0, 0, 0, 0, 0, 0, 0, 0,  # c8 - cf
    0, 0, 0, 0, 0, 0, 0, 0,  # d0 - d7
    0, 0, 0, 0, 0, 0, 0, 0,  # d8 - df
    0, 0, 0, 0, 0, 0, 0, 0,  # e0 - e7
    0, 0, 0, 0, 0, 0, 0, 0,  # e8 - ef
    0, 0, 0, 0, 0, 0, 0, 0,  # f0 - f7
    0, 0, 0, 0, 0, 0, 4, 5   # f8 - ff
)

UCS2BE_ST  = (
          5,     7,     7,MachineState.ERROR,     4,     3,MachineState.ERROR,MachineState.ERROR,#00-07
     MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,#08-0f
     MachineState.ITS_ME,MachineState.ITS_ME,     6,     6,     6,     6,MachineState.ERROR,MachineState.ERROR,#10-17
          6,     6,     6,     6,     6,MachineState.ITS_ME,     6,     6,#18-1f
          6,     6,     6,     6,     5,     7,     7,MachineState.ERROR,#20-27
          5,     8,     6,     6,MachineState.ERROR,     6,     6,     6,#28-2f
          6,     6,     6,     6,MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.START #30-37
)
# fmt: on

UCS2BE_CHAR_LEN_TABLE = (2, 2, 2, 0, 2, 2)

UCS2BE_SM_MODEL: CodingStateMachineDict = {
    "class_table": UCS2BE_CLS,
    "class_factor": 6,
    "state_table": UCS2BE_ST,
    "char_len_table": UCS2BE_CHAR_LEN_TABLE,
    "name": "UTF-16BE",
}

# UCS2-LE
# fmt: off
UCS2LE_CLS = (
    0, 0, 0, 0, 0, 0, 0, 0,  # 00 - 07
    0, 0, 1, 0, 0, 2, 0, 0,  # 08 - 0f
    0, 0, 0, 0, 0, 0, 0, 0,  # 10 - 17
    0, 0, 0, 3, 0, 0, 0, 0,  # 18 - 1f
    0, 0, 0, 0, 0, 0, 0, 0,  # 20 - 27
    0, 3, 3, 3, 3, 3, 0, 0,  # 28 - 2f
    0, 0, 0, 0, 0, 0, 0, 0,  # 30 - 37
    0, 0, 0, 0, 0, 0, 0, 0,  # 38 - 3f
    0, 0, 0, 0, 0, 0, 0, 0,  # 40 - 47
    0, 0, 0, 0, 0, 0, 0, 0,  # 48 - 4f
    0, 0, 0, 0, 0, 0, 0, 0,  # 50 - 57
    0, 0, 0, 0, 0, 0, 0, 0,  # 58 - 5f
    0, 0, 0, 0, 0, 0, 0, 0,  # 60 - 67
    0, 0, 0, 0, 0, 0, 0, 0,  # 68 - 6f
    0, 0, 0, 0, 0, 0, 0, 0,  # 70 - 77
    0, 0, 0, 0, 0, 0, 0, 0,  # 78 - 7f
    0, 0, 0, 0, 0, 0, 0, 0,  # 80 - 87
    0, 0, 0, 0, 0, 0, 0, 0,  # 88 - 8f
    0, 0, 0, 0, 0, 0, 0, 0,  # 90 - 97
    0, 0, 0, 0, 0, 0, 0, 0,  # 98 - 9f
    0, 0, 0, 0, 0, 0, 0, 0,  # a0 - a7
    0, 0, 0, 0, 0, 0, 0, 0,  # a8 - af
    0, 0, 0, 0, 0, 0, 0, 0,  # b0 - b7
    0, 0, 0, 0, 0, 0, 0, 0,  # b8 - bf
    0, 0, 0, 0, 0, 0, 0, 0,  # c0 - c7
    0, 0, 0, 0, 0, 0, 0, 0,  # c8 - cf
    0, 0, 0, 0, 0, 0, 0, 0,  # d0 - d7
    0, 0, 0, 0, 0, 0, 0, 0,  # d8 - df
    0, 0, 0, 0, 0, 0, 0, 0,  # e0 - e7
    0, 0, 0, 0, 0, 0, 0, 0,  # e8 - ef
    0, 0, 0, 0, 0, 0, 0, 0,  # f0 - f7
    0, 0, 0, 0, 0, 0, 4, 5   # f8 - ff
)

UCS2LE_ST = (
          6,     6,     7,     6,     4,     3,MachineState.ERROR,MachineState.ERROR,#00-07
     MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,#08-0f
     MachineState.ITS_ME,MachineState.ITS_ME,     5,     5,     5,MachineState.ERROR,MachineState.ITS_ME,MachineState.ERROR,#10-17
          5,     5,     5,MachineState.ERROR,     5,MachineState.ERROR,     6,     6,#18-1f
          7,     6,     8,     8,     5,     5,     5,MachineState.ERROR,#20-27
          5,     5,     5,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     5,     5,#28-2f
          5,     5,     5,MachineState.ERROR,     5,MachineState.ERROR,MachineState.START,MachineState.START #30-37
)
# fmt: on

UCS2LE_CHAR_LEN_TABLE = (2, 2, 2, 2, 2, 2)

UCS2LE_SM_MODEL: CodingStateMachineDict = {
    "class_table": UCS2LE_CLS,
    "class_factor": 6,
    "state_table": UCS2LE_ST,
    "char_len_table": UCS2LE_CHAR_LEN_TABLE,
    "name": "UTF-16LE",
}

# UTF-8
# Adapted from Björn Höhrmann's DFA UTF-8 decoder
# See http://bjoern.hoehrmann.de/utf-8/decoder/dfa/ for details.
# Copyright (c) 2008-2009 Bjoern Hoehrmann <bjoern@hoehrmann.de>
# fmt: off
UTF8_CLS = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 00-0f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 10-1f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 20-2f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 30-3f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 40-4f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 50-5f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 60-6f
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 70-7f
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 80-8f
    9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9,  # 90-9f
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,  # a0-af
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,  # b0-bf
    8, 8, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # c0-cf
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # d0-df
    10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3,  # e0-ef
    11, 6, 6, 6, 5, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,  # f0-ff
)

# Höhrmann's DFA has states 0,12,24,36,48,60,72,84,96 which we map to states 0-8
# State 0=ACCEPT (START), State 1=REJECT (ERROR), States 2-8 are intermediate
UTF8_ST = (
    MachineState.START,MachineState.ERROR,     3,     4,     6,     9,     8,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     5,     7,  # state 0 (START)
    MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,  # state 1 (ERROR)
    MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,MachineState.ITS_ME,  # state 2 (ITS_ME)
    MachineState.ERROR,MachineState.START,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.START,MachineState.ERROR,MachineState.START,MachineState.ERROR,MachineState.ERROR,  # state 3
    MachineState.ERROR,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     3,MachineState.ERROR,     3,MachineState.ERROR,MachineState.ERROR,  # state 4
    MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,  # state 5
    MachineState.ERROR,     3,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     3,MachineState.ERROR,MachineState.ERROR,  # state 6
    MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     4,MachineState.ERROR,     4,MachineState.ERROR,MachineState.ERROR,  # state 7
    MachineState.ERROR,     4,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,     4,MachineState.ERROR,     4,MachineState.ERROR,MachineState.ERROR,  # state 8
    MachineState.ERROR,     4,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,MachineState.ERROR,  # state 9
)
# fmt: on

UTF8_CHAR_LEN_TABLE = (1, 1, 2, 3, 3, 4, 4, 1, 1, 1, 3, 4)

UTF8_SM_MODEL: CodingStateMachineDict = {
    "class_table": UTF8_CLS,
    "class_factor": 12,
    "state_table": UTF8_ST,
    "char_len_table": UTF8_CHAR_LEN_TABLE,
    "name": "UTF-8",
}

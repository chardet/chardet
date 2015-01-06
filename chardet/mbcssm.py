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

from .enums import MachineState

# BIG5

BIG5_CLS = (
    1,1,1,1,1,1,1,1,  # 00 - 07    #allow 0x00 as legal value
    1,1,1,1,1,1,0,0,  # 08 - 0f
    1,1,1,1,1,1,1,1,  # 10 - 17
    1,1,1,0,1,1,1,1,  # 18 - 1f
    1,1,1,1,1,1,1,1,  # 20 - 27
    1,1,1,1,1,1,1,1,  # 28 - 2f
    1,1,1,1,1,1,1,1,  # 30 - 37
    1,1,1,1,1,1,1,1,  # 38 - 3f
    2,2,2,2,2,2,2,2,  # 40 - 47
    2,2,2,2,2,2,2,2,  # 48 - 4f
    2,2,2,2,2,2,2,2,  # 50 - 57
    2,2,2,2,2,2,2,2,  # 58 - 5f
    2,2,2,2,2,2,2,2,  # 60 - 67
    2,2,2,2,2,2,2,2,  # 68 - 6f
    2,2,2,2,2,2,2,2,  # 70 - 77
    2,2,2,2,2,2,2,1,  # 78 - 7f
    4,4,4,4,4,4,4,4,  # 80 - 87
    4,4,4,4,4,4,4,4,  # 88 - 8f
    4,4,4,4,4,4,4,4,  # 90 - 97
    4,4,4,4,4,4,4,4,  # 98 - 9f
    4,3,3,3,3,3,3,3,  # a0 - a7
    3,3,3,3,3,3,3,3,  # a8 - af
    3,3,3,3,3,3,3,3,  # b0 - b7
    3,3,3,3,3,3,3,3,  # b8 - bf
    3,3,3,3,3,3,3,3,  # c0 - c7
    3,3,3,3,3,3,3,3,  # c8 - cf
    3,3,3,3,3,3,3,3,  # d0 - d7
    3,3,3,3,3,3,3,3,  # d8 - df
    3,3,3,3,3,3,3,3,  # e0 - e7
    3,3,3,3,3,3,3,3,  # e8 - ef
    3,3,3,3,3,3,3,3,  # f0 - f7
    3,3,3,3,3,3,3,0  # f8 - ff
)

BIG5_ST = (
    MachineState.error,MachineState.start,MachineState.start,     3,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#00-07
    MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.error,#08-0f
    MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start#10-17
)

BIG5_CHAR_LEN_TABLE = (0, 1, 1, 2, 0)

BIG5_SM_MODEL = {'class_table': BIG5_CLS,
                 'class_factor': 5,
                 'state_table': BIG5_ST,
                 'char_len_table': BIG5_CHAR_LEN_TABLE,
                 'name': 'Big5'}

# CP949

CP949_CLS  = (
    1,1,1,1,1,1,1,1, 1,1,1,1,1,1,0,0,  # 00 - 0f
    1,1,1,1,1,1,1,1, 1,1,1,0,1,1,1,1,  # 10 - 1f
    1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,  # 20 - 2f
    1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,  # 30 - 3f
    1,4,4,4,4,4,4,4, 4,4,4,4,4,4,4,4,  # 40 - 4f
    4,4,5,5,5,5,5,5, 5,5,5,1,1,1,1,1,  # 50 - 5f
    1,5,5,5,5,5,5,5, 5,5,5,5,5,5,5,5,  # 60 - 6f
    5,5,5,5,5,5,5,5, 5,5,5,1,1,1,1,1,  # 70 - 7f
    0,6,6,6,6,6,6,6, 6,6,6,6,6,6,6,6,  # 80 - 8f
    6,6,6,6,6,6,6,6, 6,6,6,6,6,6,6,6,  # 90 - 9f
    6,7,7,7,7,7,7,7, 7,7,7,7,7,8,8,8,  # a0 - af
    7,7,7,7,7,7,7,7, 7,7,7,7,7,7,7,7,  # b0 - bf
    7,7,7,7,7,7,9,2, 2,3,2,2,2,2,2,2,  # c0 - cf
    2,2,2,2,2,2,2,2, 2,2,2,2,2,2,2,2,  # d0 - df
    2,2,2,2,2,2,2,2, 2,2,2,2,2,2,2,2,  # e0 - ef
    2,2,2,2,2,2,2,2, 2,2,2,2,2,2,2,0,  # f0 - ff
)

CP949_ST = (
#cls=    0      1      2      3      4      5      6      7      8      9  # previous state =
    MachineState.error,MachineState.start,     3,MachineState.error,MachineState.start,MachineState.start,     4,     5,MachineState.error,     6, # MachineState.start
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error, # MachineState.error
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me, # MachineState.its_me
    MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.error,MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start, # 3
    MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start, # 4
    MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start, # 5
    MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start, # 6
)

CP949_CHAR_LEN_TABLE = (0, 1, 2, 0, 1, 1, 2, 2, 0, 2)

CP949_SM_MODEL = {'class_table': CP949_CLS,
                  'class_factor': 10,
                  'state_table': CP949_ST,
                  'char_len_table': CP949_CHAR_LEN_TABLE,
                  'name': 'CP949'}

# EUC-JP

EUCJP_CLS = (
    4,4,4,4,4,4,4,4,  # 00 - 07
    4,4,4,4,4,4,5,5,  # 08 - 0f
    4,4,4,4,4,4,4,4,  # 10 - 17
    4,4,4,5,4,4,4,4,  # 18 - 1f
    4,4,4,4,4,4,4,4,  # 20 - 27
    4,4,4,4,4,4,4,4,  # 28 - 2f
    4,4,4,4,4,4,4,4,  # 30 - 37
    4,4,4,4,4,4,4,4,  # 38 - 3f
    4,4,4,4,4,4,4,4,  # 40 - 47
    4,4,4,4,4,4,4,4,  # 48 - 4f
    4,4,4,4,4,4,4,4,  # 50 - 57
    4,4,4,4,4,4,4,4,  # 58 - 5f
    4,4,4,4,4,4,4,4,  # 60 - 67
    4,4,4,4,4,4,4,4,  # 68 - 6f
    4,4,4,4,4,4,4,4,  # 70 - 77
    4,4,4,4,4,4,4,4,  # 78 - 7f
    5,5,5,5,5,5,5,5,  # 80 - 87
    5,5,5,5,5,5,1,3,  # 88 - 8f
    5,5,5,5,5,5,5,5,  # 90 - 97
    5,5,5,5,5,5,5,5,  # 98 - 9f
    5,2,2,2,2,2,2,2,  # a0 - a7
    2,2,2,2,2,2,2,2,  # a8 - af
    2,2,2,2,2,2,2,2,  # b0 - b7
    2,2,2,2,2,2,2,2,  # b8 - bf
    2,2,2,2,2,2,2,2,  # c0 - c7
    2,2,2,2,2,2,2,2,  # c8 - cf
    2,2,2,2,2,2,2,2,  # d0 - d7
    2,2,2,2,2,2,2,2,  # d8 - df
    0,0,0,0,0,0,0,0,  # e0 - e7
    0,0,0,0,0,0,0,0,  # e8 - ef
    0,0,0,0,0,0,0,0,  # f0 - f7
    0,0,0,0,0,0,0,5  # f8 - ff
)

EUCJP_ST = (
          3,     4,     3,     5,MachineState.start,MachineState.error,MachineState.error,MachineState.error,#00-07
     MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#08-0f
     MachineState.its_me,MachineState.its_me,MachineState.start,MachineState.error,MachineState.start,MachineState.error,MachineState.error,MachineState.error,#10-17
     MachineState.error,MachineState.error,MachineState.start,MachineState.error,MachineState.error,MachineState.error,     3,MachineState.error,#18-1f
          3,MachineState.error,MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start#20-27
)

EUCJP_CHAR_LEN_TABLE = (2, 2, 2, 3, 1, 0)

EUCJP_SM_MODEL = {'class_table': EUCJP_CLS,
                  'class_factor': 6,
                  'state_table': EUCJP_ST,
                  'char_len_table': EUCJP_CHAR_LEN_TABLE,
                  'name': 'EUC-JP'}

# EUC-KR

EUCKR_CLS  = (
    1,1,1,1,1,1,1,1,  # 00 - 07
    1,1,1,1,1,1,0,0,  # 08 - 0f
    1,1,1,1,1,1,1,1,  # 10 - 17
    1,1,1,0,1,1,1,1,  # 18 - 1f
    1,1,1,1,1,1,1,1,  # 20 - 27
    1,1,1,1,1,1,1,1,  # 28 - 2f
    1,1,1,1,1,1,1,1,  # 30 - 37
    1,1,1,1,1,1,1,1,  # 38 - 3f
    1,1,1,1,1,1,1,1,  # 40 - 47
    1,1,1,1,1,1,1,1,  # 48 - 4f
    1,1,1,1,1,1,1,1,  # 50 - 57
    1,1,1,1,1,1,1,1,  # 58 - 5f
    1,1,1,1,1,1,1,1,  # 60 - 67
    1,1,1,1,1,1,1,1,  # 68 - 6f
    1,1,1,1,1,1,1,1,  # 70 - 77
    1,1,1,1,1,1,1,1,  # 78 - 7f
    0,0,0,0,0,0,0,0,  # 80 - 87
    0,0,0,0,0,0,0,0,  # 88 - 8f
    0,0,0,0,0,0,0,0,  # 90 - 97
    0,0,0,0,0,0,0,0,  # 98 - 9f
    0,2,2,2,2,2,2,2,  # a0 - a7
    2,2,2,2,2,3,3,3,  # a8 - af
    2,2,2,2,2,2,2,2,  # b0 - b7
    2,2,2,2,2,2,2,2,  # b8 - bf
    2,2,2,2,2,2,2,2,  # c0 - c7
    2,3,2,2,2,2,2,2,  # c8 - cf
    2,2,2,2,2,2,2,2,  # d0 - d7
    2,2,2,2,2,2,2,2,  # d8 - df
    2,2,2,2,2,2,2,2,  # e0 - e7
    2,2,2,2,2,2,2,2,  # e8 - ef
    2,2,2,2,2,2,2,2,  # f0 - f7
    2,2,2,2,2,2,2,0   # f8 - ff
)

EUCKR_ST = (
    MachineState.error,MachineState.start,     3,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#00-07
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.error,MachineState.error,MachineState.start,MachineState.start #08-0f
)

EUCKR_CHAR_LEN_TABLE = (0, 1, 2, 0)

EUCKR_SM_MODEL = {'class_table': EUCKR_CLS,
                'class_factor': 4,
                'state_table': EUCKR_ST,
                'char_len_table': EUCKR_CHAR_LEN_TABLE,
                'name': 'EUC-KR'}

# EUC-TW

EUCTW_CLS = (
    2,2,2,2,2,2,2,2,  # 00 - 07
    2,2,2,2,2,2,0,0,  # 08 - 0f
    2,2,2,2,2,2,2,2,  # 10 - 17
    2,2,2,0,2,2,2,2,  # 18 - 1f
    2,2,2,2,2,2,2,2,  # 20 - 27
    2,2,2,2,2,2,2,2,  # 28 - 2f
    2,2,2,2,2,2,2,2,  # 30 - 37
    2,2,2,2,2,2,2,2,  # 38 - 3f
    2,2,2,2,2,2,2,2,  # 40 - 47
    2,2,2,2,2,2,2,2,  # 48 - 4f
    2,2,2,2,2,2,2,2,  # 50 - 57
    2,2,2,2,2,2,2,2,  # 58 - 5f
    2,2,2,2,2,2,2,2,  # 60 - 67
    2,2,2,2,2,2,2,2,  # 68 - 6f
    2,2,2,2,2,2,2,2,  # 70 - 77
    2,2,2,2,2,2,2,2,  # 78 - 7f
    0,0,0,0,0,0,0,0,  # 80 - 87
    0,0,0,0,0,0,6,0,  # 88 - 8f
    0,0,0,0,0,0,0,0,  # 90 - 97
    0,0,0,0,0,0,0,0,  # 98 - 9f
    0,3,4,4,4,4,4,4,  # a0 - a7
    5,5,1,1,1,1,1,1,  # a8 - af
    1,1,1,1,1,1,1,1,  # b0 - b7
    1,1,1,1,1,1,1,1,  # b8 - bf
    1,1,3,1,3,3,3,3,  # c0 - c7
    3,3,3,3,3,3,3,3,  # c8 - cf
    3,3,3,3,3,3,3,3,  # d0 - d7
    3,3,3,3,3,3,3,3,  # d8 - df
    3,3,3,3,3,3,3,3,  # e0 - e7
    3,3,3,3,3,3,3,3,  # e8 - ef
    3,3,3,3,3,3,3,3,  # f0 - f7
    3,3,3,3,3,3,3,0   # f8 - ff
)

EUCTW_ST = (
    MachineState.error,MachineState.error,MachineState.start,     3,     3,     3,     4,MachineState.error,#00-07
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,#08-0f
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.error,MachineState.start,MachineState.error,#10-17
    MachineState.start,MachineState.start,MachineState.start,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#18-1f
         5,MachineState.error,MachineState.error,MachineState.error,MachineState.start,MachineState.error,MachineState.start,MachineState.start,#20-27
    MachineState.start,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start #28-2f
)

EUCTW_CHAR_LEN_TABLE = (0, 0, 1, 2, 2, 2, 3)

EUCTW_SM_MODEL = {'class_table': EUCTW_CLS,
                'class_factor': 7,
                'state_table': EUCTW_ST,
                'char_len_table': EUCTW_CHAR_LEN_TABLE,
                'name': 'x-euc-tw'}

# GB2312

GB2312_CLS = (
    1,1,1,1,1,1,1,1,  # 00 - 07
    1,1,1,1,1,1,0,0,  # 08 - 0f
    1,1,1,1,1,1,1,1,  # 10 - 17
    1,1,1,0,1,1,1,1,  # 18 - 1f
    1,1,1,1,1,1,1,1,  # 20 - 27
    1,1,1,1,1,1,1,1,  # 28 - 2f
    3,3,3,3,3,3,3,3,  # 30 - 37
    3,3,1,1,1,1,1,1,  # 38 - 3f
    2,2,2,2,2,2,2,2,  # 40 - 47
    2,2,2,2,2,2,2,2,  # 48 - 4f
    2,2,2,2,2,2,2,2,  # 50 - 57
    2,2,2,2,2,2,2,2,  # 58 - 5f
    2,2,2,2,2,2,2,2,  # 60 - 67
    2,2,2,2,2,2,2,2,  # 68 - 6f
    2,2,2,2,2,2,2,2,  # 70 - 77
    2,2,2,2,2,2,2,4,  # 78 - 7f
    5,6,6,6,6,6,6,6,  # 80 - 87
    6,6,6,6,6,6,6,6,  # 88 - 8f
    6,6,6,6,6,6,6,6,  # 90 - 97
    6,6,6,6,6,6,6,6,  # 98 - 9f
    6,6,6,6,6,6,6,6,  # a0 - a7
    6,6,6,6,6,6,6,6,  # a8 - af
    6,6,6,6,6,6,6,6,  # b0 - b7
    6,6,6,6,6,6,6,6,  # b8 - bf
    6,6,6,6,6,6,6,6,  # c0 - c7
    6,6,6,6,6,6,6,6,  # c8 - cf
    6,6,6,6,6,6,6,6,  # d0 - d7
    6,6,6,6,6,6,6,6,  # d8 - df
    6,6,6,6,6,6,6,6,  # e0 - e7
    6,6,6,6,6,6,6,6,  # e8 - ef
    6,6,6,6,6,6,6,6,  # f0 - f7
    6,6,6,6,6,6,6,0   # f8 - ff
)

GB2312_ST = (
    MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,     3,MachineState.error,#00-07
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,#08-0f
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.error,MachineState.error,MachineState.start,#10-17
         4,MachineState.error,MachineState.start,MachineState.start,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#18-1f
    MachineState.error,MachineState.error,     5,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.error,#20-27
    MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.start #28-2f
)

# To be accurate, the length of class 6 can be either 2 or 4.
# But it is not necessary to discriminate between the two since
# it is used for frequency analysis only, and we are validing
# each code range there as well. So it is safe to set it to be
# 2 here.
GB2312_CHAR_LEN_TABLE = (0, 1, 1, 1, 1, 1, 2)

GB2312_SM_MODEL = {'class_table': GB2312_CLS,
                   'class_factor': 7,
                   'state_table': GB2312_ST,
                   'char_len_table': GB2312_CHAR_LEN_TABLE,
                   'name': 'GB2312'}

# Shift_JIS

SJIS_CLS = (
    1,1,1,1,1,1,1,1,  # 00 - 07
    1,1,1,1,1,1,0,0,  # 08 - 0f
    1,1,1,1,1,1,1,1,  # 10 - 17
    1,1,1,0,1,1,1,1,  # 18 - 1f
    1,1,1,1,1,1,1,1,  # 20 - 27
    1,1,1,1,1,1,1,1,  # 28 - 2f
    1,1,1,1,1,1,1,1,  # 30 - 37
    1,1,1,1,1,1,1,1,  # 38 - 3f
    2,2,2,2,2,2,2,2,  # 40 - 47
    2,2,2,2,2,2,2,2,  # 48 - 4f
    2,2,2,2,2,2,2,2,  # 50 - 57
    2,2,2,2,2,2,2,2,  # 58 - 5f
    2,2,2,2,2,2,2,2,  # 60 - 67
    2,2,2,2,2,2,2,2,  # 68 - 6f
    2,2,2,2,2,2,2,2,  # 70 - 77
    2,2,2,2,2,2,2,1,  # 78 - 7f
    3,3,3,3,3,2,2,3,  # 80 - 87
    3,3,3,3,3,3,3,3,  # 88 - 8f
    3,3,3,3,3,3,3,3,  # 90 - 97
    3,3,3,3,3,3,3,3,  # 98 - 9f
    #0xa0 is illegal in sjis encoding, but some pages does
    #contain such byte. We need to be more error forgiven.
    2,2,2,2,2,2,2,2,  # a0 - a7
    2,2,2,2,2,2,2,2,  # a8 - af
    2,2,2,2,2,2,2,2,  # b0 - b7
    2,2,2,2,2,2,2,2,  # b8 - bf
    2,2,2,2,2,2,2,2,  # c0 - c7
    2,2,2,2,2,2,2,2,  # c8 - cf
    2,2,2,2,2,2,2,2,  # d0 - d7
    2,2,2,2,2,2,2,2,  # d8 - df
    3,3,3,3,3,3,3,3,  # e0 - e7
    3,3,3,3,3,4,4,4,  # e8 - ef
    3,3,3,3,3,3,3,3,  # f0 - f7
    3,3,3,3,3,0,0,0)  # f8 - ff


SJIS_ST = (
    MachineState.error,MachineState.start,MachineState.start,     3,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#00-07
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#08-0f
    MachineState.its_me,MachineState.its_me,MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start #10-17
)

SJIS_CHAR_LEN_TABLE = (0, 1, 1, 2, 0, 0)

SJIS_SM_MODEL = {'class_table': SJIS_CLS,
               'class_factor': 6,
               'state_table': SJIS_ST,
               'char_len_table': SJIS_CHAR_LEN_TABLE,
               'name': 'Shift_JIS'}

# UCS2-BE

UCS2BE_CLS = (
    0,0,0,0,0,0,0,0,  # 00 - 07
    0,0,1,0,0,2,0,0,  # 08 - 0f
    0,0,0,0,0,0,0,0,  # 10 - 17
    0,0,0,3,0,0,0,0,  # 18 - 1f
    0,0,0,0,0,0,0,0,  # 20 - 27
    0,3,3,3,3,3,0,0,  # 28 - 2f
    0,0,0,0,0,0,0,0,  # 30 - 37
    0,0,0,0,0,0,0,0,  # 38 - 3f
    0,0,0,0,0,0,0,0,  # 40 - 47
    0,0,0,0,0,0,0,0,  # 48 - 4f
    0,0,0,0,0,0,0,0,  # 50 - 57
    0,0,0,0,0,0,0,0,  # 58 - 5f
    0,0,0,0,0,0,0,0,  # 60 - 67
    0,0,0,0,0,0,0,0,  # 68 - 6f
    0,0,0,0,0,0,0,0,  # 70 - 77
    0,0,0,0,0,0,0,0,  # 78 - 7f
    0,0,0,0,0,0,0,0,  # 80 - 87
    0,0,0,0,0,0,0,0,  # 88 - 8f
    0,0,0,0,0,0,0,0,  # 90 - 97
    0,0,0,0,0,0,0,0,  # 98 - 9f
    0,0,0,0,0,0,0,0,  # a0 - a7
    0,0,0,0,0,0,0,0,  # a8 - af
    0,0,0,0,0,0,0,0,  # b0 - b7
    0,0,0,0,0,0,0,0,  # b8 - bf
    0,0,0,0,0,0,0,0,  # c0 - c7
    0,0,0,0,0,0,0,0,  # c8 - cf
    0,0,0,0,0,0,0,0,  # d0 - d7
    0,0,0,0,0,0,0,0,  # d8 - df
    0,0,0,0,0,0,0,0,  # e0 - e7
    0,0,0,0,0,0,0,0,  # e8 - ef
    0,0,0,0,0,0,0,0,  # f0 - f7
    0,0,0,0,0,0,4,5   # f8 - ff
)

UCS2BE_ST  = (
          5,     7,     7,MachineState.error,     4,     3,MachineState.error,MachineState.error,#00-07
     MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#08-0f
     MachineState.its_me,MachineState.its_me,     6,     6,     6,     6,MachineState.error,MachineState.error,#10-17
          6,     6,     6,     6,     6,MachineState.its_me,     6,     6,#18-1f
          6,     6,     6,     6,     5,     7,     7,MachineState.error,#20-27
          5,     8,     6,     6,MachineState.error,     6,     6,     6,#28-2f
          6,     6,     6,     6,MachineState.error,MachineState.error,MachineState.start,MachineState.start #30-37
)

UCS2BE_CHAR_LEN_TABLE = (2, 2, 2, 0, 2, 2)

UCS2BE_SM_MODEL = {'class_table': UCS2BE_CLS,
                   'class_factor': 6,
                   'state_table': UCS2BE_ST,
                   'char_len_table': UCS2BE_CHAR_LEN_TABLE,
                   'name': 'UTF-16BE'}

# UCS2-LE

UCS2LE_CLS = (
    0,0,0,0,0,0,0,0,  # 00 - 07
    0,0,1,0,0,2,0,0,  # 08 - 0f
    0,0,0,0,0,0,0,0,  # 10 - 17
    0,0,0,3,0,0,0,0,  # 18 - 1f
    0,0,0,0,0,0,0,0,  # 20 - 27
    0,3,3,3,3,3,0,0,  # 28 - 2f
    0,0,0,0,0,0,0,0,  # 30 - 37
    0,0,0,0,0,0,0,0,  # 38 - 3f
    0,0,0,0,0,0,0,0,  # 40 - 47
    0,0,0,0,0,0,0,0,  # 48 - 4f
    0,0,0,0,0,0,0,0,  # 50 - 57
    0,0,0,0,0,0,0,0,  # 58 - 5f
    0,0,0,0,0,0,0,0,  # 60 - 67
    0,0,0,0,0,0,0,0,  # 68 - 6f
    0,0,0,0,0,0,0,0,  # 70 - 77
    0,0,0,0,0,0,0,0,  # 78 - 7f
    0,0,0,0,0,0,0,0,  # 80 - 87
    0,0,0,0,0,0,0,0,  # 88 - 8f
    0,0,0,0,0,0,0,0,  # 90 - 97
    0,0,0,0,0,0,0,0,  # 98 - 9f
    0,0,0,0,0,0,0,0,  # a0 - a7
    0,0,0,0,0,0,0,0,  # a8 - af
    0,0,0,0,0,0,0,0,  # b0 - b7
    0,0,0,0,0,0,0,0,  # b8 - bf
    0,0,0,0,0,0,0,0,  # c0 - c7
    0,0,0,0,0,0,0,0,  # c8 - cf
    0,0,0,0,0,0,0,0,  # d0 - d7
    0,0,0,0,0,0,0,0,  # d8 - df
    0,0,0,0,0,0,0,0,  # e0 - e7
    0,0,0,0,0,0,0,0,  # e8 - ef
    0,0,0,0,0,0,0,0,  # f0 - f7
    0,0,0,0,0,0,4,5   # f8 - ff
)

UCS2LE_ST = (
          6,     6,     7,     6,     4,     3,MachineState.error,MachineState.error,#00-07
     MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#08-0f
     MachineState.its_me,MachineState.its_me,     5,     5,     5,MachineState.error,MachineState.its_me,MachineState.error,#10-17
          5,     5,     5,MachineState.error,     5,MachineState.error,     6,     6,#18-1f
          7,     6,     8,     8,     5,     5,     5,MachineState.error,#20-27
          5,     5,     5,MachineState.error,MachineState.error,MachineState.error,     5,     5,#28-2f
          5,     5,     5,MachineState.error,     5,MachineState.error,MachineState.start,MachineState.start #30-37
)

UCS2LE_CHAR_LEN_TABLE = (2, 2, 2, 2, 2, 2)

UCS2LE_SM_MODEL = {'class_table': UCS2LE_CLS,
                 'class_factor': 6,
                 'state_table': UCS2LE_ST,
                 'char_len_table': UCS2LE_CHAR_LEN_TABLE,
                 'name': 'UTF-16LE'}

# UTF-8

UTF8_CLS = (
    1,1,1,1,1,1,1,1,  # 00 - 07  #allow 0x00 as a legal value
    1,1,1,1,1,1,0,0,  # 08 - 0f
    1,1,1,1,1,1,1,1,  # 10 - 17
    1,1,1,0,1,1,1,1,  # 18 - 1f
    1,1,1,1,1,1,1,1,  # 20 - 27
    1,1,1,1,1,1,1,1,  # 28 - 2f
    1,1,1,1,1,1,1,1,  # 30 - 37
    1,1,1,1,1,1,1,1,  # 38 - 3f
    1,1,1,1,1,1,1,1,  # 40 - 47
    1,1,1,1,1,1,1,1,  # 48 - 4f
    1,1,1,1,1,1,1,1,  # 50 - 57
    1,1,1,1,1,1,1,1,  # 58 - 5f
    1,1,1,1,1,1,1,1,  # 60 - 67
    1,1,1,1,1,1,1,1,  # 68 - 6f
    1,1,1,1,1,1,1,1,  # 70 - 77
    1,1,1,1,1,1,1,1,  # 78 - 7f
    2,2,2,2,3,3,3,3,  # 80 - 87
    4,4,4,4,4,4,4,4,  # 88 - 8f
    4,4,4,4,4,4,4,4,  # 90 - 97
    4,4,4,4,4,4,4,4,  # 98 - 9f
    5,5,5,5,5,5,5,5,  # a0 - a7
    5,5,5,5,5,5,5,5,  # a8 - af
    5,5,5,5,5,5,5,5,  # b0 - b7
    5,5,5,5,5,5,5,5,  # b8 - bf
    0,0,6,6,6,6,6,6,  # c0 - c7
    6,6,6,6,6,6,6,6,  # c8 - cf
    6,6,6,6,6,6,6,6,  # d0 - d7
    6,6,6,6,6,6,6,6,  # d8 - df
    7,8,8,8,8,8,8,8,  # e0 - e7
    8,8,8,8,8,9,8,8,  # e8 - ef
    10,11,11,11,11,11,11,11,  # f0 - f7
    12,13,13,13,14,15,0,0    # f8 - ff
)

UTF8_ST = (
    MachineState.error,MachineState.start,MachineState.error,MachineState.error,MachineState.error,MachineState.error,     12,   10,#00-07
         9,     11,     8,     7,     6,     5,     4,    3,#08-0f
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#10-17
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#18-1f
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#20-27
    MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,MachineState.its_me,#28-2f
    MachineState.error,MachineState.error,     5,     5,     5,     5,MachineState.error,MachineState.error,#30-37
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#38-3f
    MachineState.error,MachineState.error,MachineState.error,     5,     5,     5,MachineState.error,MachineState.error,#40-47
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#48-4f
    MachineState.error,MachineState.error,     7,     7,     7,     7,MachineState.error,MachineState.error,#50-57
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#58-5f
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,     7,     7,MachineState.error,MachineState.error,#60-67
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#68-6f
    MachineState.error,MachineState.error,     9,     9,     9,     9,MachineState.error,MachineState.error,#70-77
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#78-7f
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,     9,MachineState.error,MachineState.error,#80-87
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#88-8f
    MachineState.error,MachineState.error,    12,    12,    12,    12,MachineState.error,MachineState.error,#90-97
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#98-9f
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,    12,MachineState.error,MachineState.error,#a0-a7
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#a8-af
    MachineState.error,MachineState.error,    12,    12,    12,MachineState.error,MachineState.error,MachineState.error,#b0-b7
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,#b8-bf
    MachineState.error,MachineState.error,MachineState.start,MachineState.start,MachineState.start,MachineState.start,MachineState.error,MachineState.error,#c0-c7
    MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error,MachineState.error #c8-cf
)

UTF8_CHAR_LEN_TABLE = (0, 1, 0, 0, 0, 0, 2, 3, 3, 3, 4, 4, 5, 5, 6, 6)

UTF8_SM_MODEL = {'class_table': UTF8_CLS,
                 'class_factor': 16,
                 'state_table': UTF8_ST,
                 'char_len_table': UTF8_CHAR_LEN_TABLE,
                 'name': 'UTF-8'}

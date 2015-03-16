######################## BEGIN LICENSE BLOCK ########################
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


import sys
from .universaldetector import UniversalDetector

def detect(byte_str, txt_cleanup=True):
    PY_VER = 2 if sys.version_info < (3, 0) else 3
    if ((PY_VER == 2 and isinstance(byte_str, unicode)) or
        (PY_VER == 3 and not isinstance(byte_str, bytes))):
        raise ValueError('Expected a bytes object, not a unicode object')
    if PY_VER == 2:
        byte_str = bytearray(byte_str)
    u = UniversalDetector()
    u.feed(byte_str, txt_cleanup)
    u.close()
    return u.result

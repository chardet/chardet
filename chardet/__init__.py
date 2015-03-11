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


from .compat import PY2, PY3
from .universaldetector import UniversalDetector
from .version import __version__, VERSION


def detect(byte_str, txt_cleanup=True):
    if (PY2 and isinstance(byte_str, unicode)) or (PY3 and
                                               not isinstance(byte_str,
                                                              bytes)):
        raise ValueError('Expected a bytes object, not a unicode object')

    u = UniversalDetector()
    u.feed(byte_str, txt_cleanup)
    u.close()
    return u.result

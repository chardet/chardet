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


from .compat import PY2, PY3, bin_type as _bin_type
from .universaldetector import UniversalDetector
from .version import __version__, VERSION


def detect(byte_str):
    if not isinstance(byte_str, _bin_type):
        raise TypeError('Expected object of {0} type, got: {1}'
                        ''.format(_bin_type, type(byte_str)))

    u = UniversalDetector()
    u.feed(byte_str)
    u.close()
    return u.result

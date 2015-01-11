######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Universal charset detector code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 2001
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Mark Pilgrim - port to Python
#   Shy Shalom - original C code
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

from .charsetgroupprober import CharSetGroupProber
from .sbcharsetprober import SingleByteCharSetProber
from .langbulgarianmodel import (ISO_8859_5_BULGARIAN_Model,
                                 WIN1251_BULGARIAN_MODEL)
from .langcyrillicmodel import (WIN1251_CYRILLIC_MODEL, KOI8_CYRILLIC_MODEL,
                                ISO_8859_5_CYRILLIC_MODEL, MAC_CYRILLIC_MODEL,
                                IBM866_MODEL, IBM855_MODEL)
from .langczechmodel import LATIN2_CZECH_MODEL
from .langfinnishmodel import WIN1252_FINNISH_MODEL
from .langfrenchmodel import WIN1252_FRENCH_MODEL
from .langgermanmodel import WIN1252_GERMAN_MODEL
from .langgreekmodel import LATIN7_GREEK_MODEL, WIN1253_GREEK_MODEL
from .langhungarianmodel import LATIN2_HUNGARIAN_MODEL, WIN1250_HUNGARIAN_MODEL
from .langpolishmodel import LATIN2_POLISH_MODEL
from .langspanishmodel import WIN1252_SPANISH_MODEL
from .langswedishmodel import WIN1252_SWEDISH_MODEL
from .langthaimodel import TIS620_THAI_MODEL
from .langhebrewmodel import Win1255HebrewModel
from .hebrewprober import HebrewProber
from .langturkishmodel import LATIN5_TURKISH_MODEL


class SBCSGroupProber(CharSetGroupProber):
    def __init__(self):
        super(SBCSGroupProber, self).__init__()
        self.probers = [
            SingleByteCharSetProber(WIN1251_CYRILLIC_MODEL),
            SingleByteCharSetProber(KOI8_CYRILLIC_MODEL),
            SingleByteCharSetProber(ISO_8859_5_CYRILLIC_MODEL),
            SingleByteCharSetProber(MAC_CYRILLIC_MODEL),
            SingleByteCharSetProber(IBM866_MODEL),
            SingleByteCharSetProber(IBM855_MODEL),
            SingleByteCharSetProber(LATIN7_GREEK_MODEL),
            SingleByteCharSetProber(WIN1253_GREEK_MODEL),
            SingleByteCharSetProber(ISO_8859_5_BULGARIAN_Model),
            SingleByteCharSetProber(WIN1251_BULGARIAN_MODEL),
            SingleByteCharSetProber(TIS620_THAI_MODEL)
        ]
        hebrew_prober = HebrewProber()
        logical_hebrew_prober = SingleByteCharSetProber(Win1255HebrewModel,
                                                        False, hebrew_prober)
        visual_hebrew_prober = SingleByteCharSetProber(Win1255HebrewModel,
                                                       True, hebrew_prober)
        hebrew_prober.set_model_probers(logical_hebrew_prober,
                                        visual_hebrew_prober)
        self.probers.extend([hebrew_prober,
                             logical_hebrew_prober,
                             visual_hebrew_prober,
                             SingleByteCharSetProber(LATIN2_HUNGARIAN_MODEL),
                             SingleByteCharSetProber(WIN1250_HUNGARIAN_MODEL),
                             SingleByteCharSetProber(WIN1252_FRENCH_MODEL),
                             SingleByteCharSetProber(WIN1252_GERMAN_MODEL),
                             SingleByteCharSetProber(WIN1252_SWEDISH_MODEL),
                             SingleByteCharSetProber(LATIN5_TURKISH_MODEL),
                             SingleByteCharSetProber(WIN1252_FINNISH_MODEL),
                             SingleByteCharSetProber(WIN1252_SPANISH_MODEL),
                             SingleByteCharSetProber(LATIN2_CZECH_MODEL),
                             SingleByteCharSetProber(LATIN2_POLISH_MODEL)])
        self.reset()

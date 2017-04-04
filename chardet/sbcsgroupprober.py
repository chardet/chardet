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
from .hebrewprober import HebrewProber
from .langarabicmodel import (
    CP864_ARABIC_MODEL,
    CP720_ARABIC_MODEL,
    ISO_8859_6_ARABIC_MODEL,
    WINDOWS_1256_ARABIC_MODEL,
)
from .langbelarusianmodel import (
    IBM866_BELARUSIAN_MODEL,
    ISO_8859_5_BELARUSIAN_MODEL,
    MACCYRILLIC_BELARUSIAN_MODEL,
    WINDOWS_1251_BELARUSIAN_MODEL,
)
from .langbulgarianmodel import (
    IBM855_BULGARIAN_MODEL,
    ISO_8859_5_BULGARIAN_MODEL,
    WINDOWS_1251_BULGARIAN_MODEL,
)
from .langcroatianmodel import ISO_8859_2_CROATIAN_MODEL, WINDOWS_1250_CROATIAN_MODEL
from .langczechmodel import ISO_8859_2_CZECH_MODEL, WINDOWS_1250_CZECH_MODEL
from .langdanishmodel import (
    ISO_8859_1_DANISH_MODEL,
    ISO_8859_15_DANISH_MODEL,
    WINDOWS_1252_DANISH_MODEL,
)
from .langdutchmodel import ISO_8859_1_DUTCH_MODEL, WINDOWS_1252_DUTCH_MODEL
from .langenglishmodel import ISO_8859_1_ENGLISH_MODEL, WINDOWS_1252_ENGLISH_MODEL
from .langesperantomodel import ISO_8859_3_ESPERANTO_MODEL
from .langestonianmodel import (
    ISO_8859_4_ESTONIAN_MODEL,
    ISO_8859_13_ESTONIAN_MODEL,
    WINDOWS_1257_ESTONIAN_MODEL,
)
from .langfinnishmodel import (
    ISO_8859_1_FINNISH_MODEL,
    ISO_8859_15_FINNISH_MODEL,
    WINDOWS_1252_FINNISH_MODEL,
)
from .langfrenchmodel import (
    ISO_8859_1_FRENCH_MODEL,
    ISO_8859_15_FRENCH_MODEL,
    WINDOWS_1252_FRENCH_MODEL,
)
from .langgermanmodel import ISO_8859_1_GERMAN_MODEL, WINDOWS_1252_GERMAN_MODEL
from .langgreekmodel import ISO_8859_7_GREEK_MODEL, WINDOWS_1253_GREEK_MODEL
from .langhebrewmodel import ISO_8859_8_HEBREW_MODEL, WINDOWS_1255_HEBREW_MODEL
from .langhungarianmodel import ISO_8859_2_HUNGARIAN_MODEL, WINDOWS_1250_HUNGARIAN_MODEL
from .langitalianmodel import (
    ISO_8859_1_ITALIAN_MODEL,
    ISO_8859_15_ITALIAN_MODEL,
    WINDOWS_1252_ITALIAN_MODEL,
)
from .langlatvianmodel import (
    ISO_8859_4_LATVIAN_MODEL,
    ISO_8859_13_LATVIAN_MODEL,
    WINDOWS_1257_LATVIAN_MODEL,
)
from .langlithuanianmodel import (
    ISO_8859_4_LITHUANIAN_MODEL,
    ISO_8859_13_LITHUANIAN_MODEL,
    WINDOWS_1257_LITHUANIAN_MODEL,
)
from .langmacedonianmodel import (
    IBM855_MACEDONIAN_MODEL,
    ISO_8859_5_MACEDONIAN_MODEL,
    MACCYRILLIC_MACEDONIAN_MODEL,
    WINDOWS_1251_MACEDONIAN_MODEL,
)
from .langpolishmodel import ISO_8859_2_POLISH_MODEL, WINDOWS_1250_POLISH_MODEL
from .langportuguesemodel import (
    ISO_8859_1_PORTUGUESE_MODEL,
    ISO_8859_15_PORTUGUESE_MODEL,
    WINDOWS_1252_PORTUGUESE_MODEL,
)
from .langromanianmodel import ISO_8859_2_ROMANIAN_MODEL, WINDOWS_1250_ROMANIAN_MODEL
from .langrussianmodel import (
    IBM855_RUSSIAN_MODEL,
    IBM866_RUSSIAN_MODEL,
    ISO_8859_5_RUSSIAN_MODEL,
    KOI8_R_RUSSIAN_MODEL,
    MACCYRILLIC_RUSSIAN_MODEL,
    WINDOWS_1251_RUSSIAN_MODEL,
)
from .langserbianmodel import (
    IBM855_SERBIAN_MODEL,
    ISO_8859_5_SERBIAN_MODEL,
    MACCYRILLIC_SERBIAN_MODEL,
    WINDOWS_1251_SERBIAN_MODEL,
)
from .langslovakmodel import ISO_8859_2_SLOVAK_MODEL, WINDOWS_1250_SLOVAK_MODEL
from .langslovenemodel import ISO_8859_2_SLOVENE_MODEL, WINDOWS_1250_SLOVENE_MODEL
from .langspanishmodel import (
    ISO_8859_1_SPANISH_MODEL,
    ISO_8859_15_SPANISH_MODEL,
    WINDOWS_1252_SPANISH_MODEL,
)
from .langthaimodel import CP874_THAI_MODEL, ISO_8859_11_THAI_MODEL, TIS_620_THAI_MODEL
from .langturkishmodel import (
    ISO_8859_3_TURKISH_MODEL,
    ISO_8859_9_TURKISH_MODEL,
    WINDOWS_1254_TURKISH_MODEL,
)
from .langvietnamesemodel import WINDOWS_1258_VIETNAMESE_MODEL
from .sbcharsetprober import SingleByteCharSetProber


class SBCSGroupProber(CharSetGroupProber):
    def __init__(self):
        super().__init__()
        hebrew_prober = HebrewProber()
        logical_hebrew_prober = SingleByteCharSetProber(
            WINDOWS_1255_HEBREW_MODEL, False, hebrew_prober
        )
        # TODO: See if using ISO-8859-8 Hebrew model works better here, since
        #       it's actually the visual one
        visual_hebrew_prober = SingleByteCharSetProber(
            WINDOWS_1255_HEBREW_MODEL, True, hebrew_prober
        )
        hebrew_prober.set_model_probers(logical_hebrew_prober, visual_hebrew_prober)
        # TODO: ORDER MATTERS HERE. I changed the order vs what was in master
        #       and several tests failed that did not before. Some thought
        #       should be put into the ordering, and we should consider making
        #       order not matter here, because that is very counter-intuitive.
        self.probers = [
            SingleByteCharSetProber(CP720_ARABIC_MODEL),
            SingleByteCharSetProber(ISO_8859_6_ARABIC_MODEL),
            SingleByteCharSetProber(CP864_ARABIC_MODEL),
            SingleByteCharSetProber(WINDOWS_1256_ARABIC_MODEL),
            SingleByteCharSetProber(IBM866_BELARUSIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_5_BELARUSIAN_MODEL),
            SingleByteCharSetProber(MACCYRILLIC_BELARUSIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1251_BELARUSIAN_MODEL),
            SingleByteCharSetProber(IBM855_BULGARIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_5_BULGARIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1251_BULGARIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_2_CROATIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_CROATIAN_MODEL),
            # SingleByteCharSetProber(ISO_8859_2_CZECH_MODEL),
            # SingleByteCharSetProber(WINDOWS_1250_CZECH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_DANISH_MODEL),
            SingleByteCharSetProber(ISO_8859_15_DANISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_DANISH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_DUTCH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_DUTCH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_ENGLISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_ENGLISH_MODEL),
            SingleByteCharSetProber(ISO_8859_3_ESPERANTO_MODEL),
            SingleByteCharSetProber(ISO_8859_4_ESTONIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_13_ESTONIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1257_ESTONIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_1_FINNISH_MODEL),
            SingleByteCharSetProber(ISO_8859_15_FINNISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_FINNISH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_FRENCH_MODEL),
            SingleByteCharSetProber(ISO_8859_15_FRENCH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_FRENCH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_GERMAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_GERMAN_MODEL),
            SingleByteCharSetProber(ISO_8859_7_GREEK_MODEL),
            SingleByteCharSetProber(WINDOWS_1253_GREEK_MODEL),
            hebrew_prober,
            logical_hebrew_prober,
            visual_hebrew_prober,
            SingleByteCharSetProber(ISO_8859_2_HUNGARIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_HUNGARIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_1_ITALIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_15_ITALIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_ITALIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_4_LATVIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_13_LATVIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1257_LATVIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_4_LITHUANIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_13_LITHUANIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1257_LITHUANIAN_MODEL),
            SingleByteCharSetProber(IBM855_MACEDONIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_5_MACEDONIAN_MODEL),
            SingleByteCharSetProber(MACCYRILLIC_MACEDONIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1251_MACEDONIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_2_POLISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_POLISH_MODEL),
            SingleByteCharSetProber(ISO_8859_1_PORTUGUESE_MODEL),
            SingleByteCharSetProber(ISO_8859_15_PORTUGUESE_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_PORTUGUESE_MODEL),
            SingleByteCharSetProber(ISO_8859_2_ROMANIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_ROMANIAN_MODEL),
            SingleByteCharSetProber(IBM855_RUSSIAN_MODEL),
            SingleByteCharSetProber(IBM866_RUSSIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_5_RUSSIAN_MODEL),
            SingleByteCharSetProber(KOI8_R_RUSSIAN_MODEL),
            SingleByteCharSetProber(MACCYRILLIC_RUSSIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1251_RUSSIAN_MODEL),
            SingleByteCharSetProber(IBM855_SERBIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_5_SERBIAN_MODEL),
            SingleByteCharSetProber(MACCYRILLIC_SERBIAN_MODEL),
            SingleByteCharSetProber(WINDOWS_1251_SERBIAN_MODEL),
            SingleByteCharSetProber(ISO_8859_2_SLOVAK_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_SLOVAK_MODEL),
            SingleByteCharSetProber(ISO_8859_2_SLOVENE_MODEL),
            SingleByteCharSetProber(WINDOWS_1250_SLOVENE_MODEL),
            SingleByteCharSetProber(ISO_8859_1_SPANISH_MODEL),
            SingleByteCharSetProber(ISO_8859_15_SPANISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1252_SPANISH_MODEL),
            SingleByteCharSetProber(CP874_THAI_MODEL),
            SingleByteCharSetProber(ISO_8859_11_THAI_MODEL),
            SingleByteCharSetProber(TIS_620_THAI_MODEL),
            SingleByteCharSetProber(ISO_8859_3_TURKISH_MODEL),
            SingleByteCharSetProber(ISO_8859_9_TURKISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1254_TURKISH_MODEL),
            SingleByteCharSetProber(WINDOWS_1258_VIETNAMESE_MODEL),
        ]
        self.reset()

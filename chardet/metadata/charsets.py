"""
Metadata about charsets used by our model training code and test file
generationcode. Could be used for other things in the future.
"""

from dataclasses import dataclass

from chardet.enums import EncodingEra


@dataclass(frozen=True)
class Charset:
    """Metadata about charsets useful for training models and generating test files."""

    name: str
    is_multi_byte: bool
    encoding_era: EncodingEra


CHARSETS = [
    Charset(name="ASCII", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="Big5", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="CP037", is_multi_byte=False, encoding_era=EncodingEra.MAINFRAME),
    Charset(name="CP424", is_multi_byte=False, encoding_era=EncodingEra.MAINFRAME),
    Charset(name="CP437", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP500", is_multi_byte=False, encoding_era=EncodingEra.MAINFRAME),
    Charset(name="CP720", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="CP737", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP775", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP850", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP852", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP855", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP856", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP857", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP858", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP860", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP861", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP862", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP863", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP864", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP865", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP866", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP869", is_multi_byte=False, encoding_era=EncodingEra.DOS),
    Charset(name="CP874", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="CP875", is_multi_byte=False, encoding_era=EncodingEra.MAINFRAME),
    Charset(name="CP932", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="CP949", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="CP1006", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="CP1026", is_multi_byte=False, encoding_era=EncodingEra.MAINFRAME),
    Charset(name="CP1125", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="EUC-JP", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="EUC-KR", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="GB18030", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="HZ-GB-2312", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(
        name="ISO-2022-JP", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="ISO-2022-KR", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(name="ISO-8859-1", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-2", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-3", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-4", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-5", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-6", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-7", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-8", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-9", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-11", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-13", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="ISO-8859-15", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="Johab", is_multi_byte=True, encoding_era=EncodingEra.LEGACY),
    Charset(name="KOI8-R", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="KOI8-U", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="KOI8-T", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="KZ1048", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacCyrillic", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacGreek", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacIceland", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacLatin2", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacRoman", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="MacTurkish", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="PTCP154", is_multi_byte=False, encoding_era=EncodingEra.LEGACY),
    Charset(name="Shift-JIS", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="TIS-620", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-8", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-16", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-16BE", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-16LE", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-32", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-32BE", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(name="UTF-32LE", is_multi_byte=True, encoding_era=EncodingEra.MODERN_WEB),
    Charset(
        name="Windows-1250", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1251", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1252", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1253", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1254", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1255", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1256", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1257", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
    Charset(
        name="Windows-1258", is_multi_byte=False, encoding_era=EncodingEra.MODERN_WEB
    ),
]

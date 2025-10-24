"""
Metadata about languages used by our model training code for our
SingleByteCharSetProbers.  Could be used for other things in the future.

This code is based on the language metadata from the uchardet project.
"""

from dataclasses import dataclass
from string import ascii_letters

# TODO: Add more languages (like Tajik)


@dataclass(frozen=True)
class Language:
    """Metadata about a language useful for training models

    :ivar name: The human name for the language, in English.
    :type name: str
    :ivar iso_code: 2-letter ISO 639-1 if possible, 3-letter ISO code otherwise,
                    or use another catalog as a last resort.
    :type iso_code: str
    :ivar use_ascii: Whether or not ASCII letters should be included in trained
                     models.
    :type use_ascii: bool
    :ivar charsets: The charsets we want to support and create data for.
    :type charsets: list of str
    :ivar alphabet: The characters in the language's alphabet. If `use_ascii` is
                    `True`, you only need to add those not in the ASCII set.
    :type alphabet: str
    """

    name: str
    iso_code: str
    use_ascii: bool
    charsets: list[str]
    alphabet: str

    def __repr__(self) -> str:
        param_str = ", ".join(
            f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"{self.__class__.__name__}({param_str})"


LANGUAGES = {
    "Arabic": Language(
        name="Arabic",
        iso_code="ar",
        use_ascii=False,
        # We only support encodings that use isolated
        # forms, because the current recommendation is
        # that the rendering system handles presentation
        # forms. This means we purposefully skip CP864.
        # TODO: Figure out if the above comment should be true, since it is not
        charsets=["ISO-8859-6", "WINDOWS-1256", "CP720", "CP864"],
        alphabet="ءآأؤإئابةتثجحخدذرزسشصضطظعغػؼؽؾؿـفقكلمنهوىيًٌٍَُِّ",
    ),
    "Belarusian": Language(
        name="Belarusian",
        iso_code="be",
        use_ascii=False,
        charsets=["ISO-8859-5", "WINDOWS-1251", "CP866", "MacCyrillic", "CP855"],
        alphabet="АБВГДЕЁЖЗІЙКЛМНОПРСТУЎФХЦЧШЫЬЭЮЯабвгдеёжзійклмнопрстуўфхцчшыьэюяʼ",
    ),
    "Bulgarian": Language(
        name="Bulgarian",
        iso_code="bg",
        use_ascii=False,
        charsets=["ISO-8859-5", "WINDOWS-1251", "CP855", "MacCyrillic"],
        alphabet="АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЬЮЯабвгдежзийклмнопрстуфхцчшщъьюя",
    ),
    "Breton": Language(
        name="Breton",
        iso_code="br",
        use_ascii=True,
        charsets=["ISO-8859-14"],
        alphabet="".join(sorted(set(ascii_letters + "ÀÂÈÊÎÔÙÛàâèêîôùû"))),
    ),
    "Welsh": Language(
        name="Welsh",
        iso_code="cy",
        use_ascii=True,
        charsets=["ISO-8859-14"],
        alphabet="".join(
            sorted(
                set(ascii_letters + "ÁÂÄÉÊËÍÎÏÓÔÖÚÛÜÝáâäéêëíîïóôöúûüýÿŴŵŶŷŸẀẁẂẃẄẅỲỳ")
            )
        ),
    ),
    "Czech": Language(
        name="Czech",
        iso_code="cz",
        use_ascii=True,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="".join(sorted(set(ascii_letters + "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"))),
    ),
    "Danish": Language(
        name="Danish",
        iso_code="da",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
            "CP865",
        ],
        alphabet="".join(sorted(set(ascii_letters + "æøåÆØÅ"))),
    ),
    "German": Language(
        name="German",
        iso_code="de",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
        ],
        alphabet="".join(sorted(set(ascii_letters + "äöüßẞÄÖÜ"))),
    ),
    "Greek": Language(
        name="Greek",
        iso_code="el",
        use_ascii=False,
        charsets=["ISO-8859-7", "WINDOWS-1253", "CP737", "CP869", "CP875", "MacGreek"],
        alphabet="αβγδεζηθικλμνξοπρσςτυφχψωάέήίόύώΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΣΤΥΦΧΨΩΆΈΉΊΌΎΏ",
    ),
    "English": Language(
        name="English",
        iso_code="en",
        alphabet=ascii_letters,
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "WINDOWS-1252",
            "MacRoman",
            "ISO-8859-15",
            "CP437",
            "CP850",
            "CP858",
        ],
    ),
    "Esperanto": Language(
        name="Esperanto",
        iso_code="eo",
        # Q, W, X, and Y not used at all
        use_ascii=False,
        charsets=["ISO-8859-3"],
        alphabet="abcĉdefgĝhĥijĵklmnoprsŝtuŭvzABCĈDEFGĜHĤIJĴKLMNOPRSŜTUŬVZ",
    ),
    "Spanish": Language(
        name="Spanish",
        iso_code="es",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
        ],
        alphabet="".join(sorted(set(ascii_letters + "ñáéíóúüÑÁÉÍÓÚÜ"))),
    ),
    "Estonian": Language(
        name="Estonian",
        iso_code="et",
        use_ascii=False,
        charsets=["ISO-8859-4", "ISO-8859-13", "WINDOWS-1257", "CP775"],
        # C, F, Š, Q, W, X, Y, Z, Ž are only for
        # loanwords
        alphabet="ABDEGHIJKLMNOPRSTUVÕÄÖÜabdeghijklmnoprstuvõäöü",
    ),
    "Farsi": Language(
        name="Farsi",
        iso_code="fa",
        use_ascii=False,
        charsets=["WINDOWS-1256", "ISO-8859-6"],
        alphabet="ءآأؤإئابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیًٌٍَُِّ",
    ),
    "Finnish": Language(
        name="Finnish",
        iso_code="fi",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
        ],
        alphabet="".join(sorted(set(ascii_letters + "ÅÄÖŠŽåäöšž"))),
    ),
    "French": Language(
        name="French",
        iso_code="fr",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
            "CP863",
        ],
        alphabet="".join(
            sorted(set(ascii_letters + "àâæçèéêëîïôùûüÿÀÂÆÇÈÉÊËÎÏÔÙÛÜŸŒœ"))
        ),
    ),
    "Irish": Language(
        name="Irish",
        iso_code="ga",
        use_ascii=True,
        charsets=["ISO-8859-14"],
        alphabet="".join(sorted(set(ascii_letters + "ÁÉÍÓÚáéíóú"))),
    ),
    "Scottish Gaelic": Language(
        name="Scottish Gaelic",
        iso_code="gd",
        use_ascii=True,
        charsets=["ISO-8859-14"],
        alphabet="".join(sorted(set(ascii_letters + "ÀÈÌÒÙàèìòù"))),
    ),
    "Hebrew": Language(
        name="Hebrew",
        iso_code="he",
        use_ascii=False,
        charsets=["ISO-8859-8", "WINDOWS-1255", "CP856", "CP862"],
        alphabet="אבגדהוזחטיךכלםמןנסעףפץצקרשתװױײ",
    ),
    "Croatian": Language(
        name="Croatian",
        iso_code="hr",
        # Q, W, X, Y are only used for foreign words.
        use_ascii=False,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="abcčćdđefghijklmnoprsštuvzžABCČĆDĐEFGHIJKLMNOPRSŠTUVZŽ",
    ),
    "Hungarian": Language(
        name="Hungarian",
        iso_code="hu",
        # Q, W, X, Y are only used for foreign words.
        use_ascii=False,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="abcdefghijklmnoprstuvzáéíóöőúüűABCDEFGHIJKLMNOPRSTUVZÁÉÍÓÖŐÚÜŰ",
    ),
    "Icelandic": Language(
        name="Icelandic",
        iso_code="is",
        # Q, W are not used in native Icelandic words
        use_ascii=False,
        charsets=["ISO-8859-1", "ISO-8859-10", "CP861", "MacIceland"],
        alphabet="aábcdðeéfghiíjklmnoóprstuúvxyýþæöAÁBCDÐEÉFGHIÍJKLMNOÓPRSTUÚVXYÝÞÆÖ",
    ),
    "Indonesian": Language(
        name="Indonesian",
        iso_code="id",
        use_ascii=True,
        charsets=["ISO-8859-1", "WINDOWS-1252", "MacRoman"],
        alphabet=ascii_letters,
    ),
    "Italian": Language(
        name="Italian",
        iso_code="it",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
        ],
        alphabet="".join(sorted(set(ascii_letters + "ÀÈÉÌÒÓÙàèéìòóù"))),
    ),
    "Kazakh": Language(
        name="Kazakh",
        iso_code="kk",
        use_ascii=False,
        charsets=["KZ1048", "PTCP154"],
        alphabet="АӘБВГҒДЕЁЖЗИЙКҚЛМНҢОӨПРСТУҰҮФХҺЦЧШЩЪЫІЬЭЮЯаәбвгғдеёжзийкқлмнңоөпрстууұүфхһцчшщъыіьэюя",
    ),
    "Cornish": Language(
        name="Cornish",
        iso_code="kw",
        use_ascii=True,
        charsets=["ISO-8859-14"],
        alphabet="".join(sorted(set(ascii_letters + "ÂÊÎÔÛâêîôûŴŵŶŷ"))),
    ),
    "Lithuanian": Language(
        name="Lithuanian",
        iso_code="lt",
        use_ascii=False,
        charsets=["ISO-8859-13", "WINDOWS-1257", "ISO-8859-4", "CP775"],
        # Q, W, and X not used at all
        alphabet="AĄBCČDEĘĖFGHIĮYJKLMNOPRSŠTUŲŪVZŽaąbcčdeęėfghiįyjklmnoprsštuųūvzž",
    ),
    "Latvian": Language(
        name="Latvian",
        iso_code="lv",
        use_ascii=False,
        charsets=["ISO-8859-13", "WINDOWS-1257", "ISO-8859-4", "CP775"],
        # Q, W, X, Y are only for loanwords
        alphabet="AĀBCČDEĒFGĢHIĪJKĶLĻMNŅOPRSŠTUŪVZŽaābcčdeēfgģhiījkķlļmnņoprsštuūvzž",
    ),
    "Macedonian": Language(
        name="Macedonian",
        iso_code="mk",
        use_ascii=False,
        charsets=["ISO-8859-5", "WINDOWS-1251", "MacCyrillic", "CP855"],
        alphabet="АБВГДЃЕЖЗЅИЈКЛЉМНЊОПРСТЌУФХЦЧЏШабвгдѓежзѕијклљмнњопрстќуфхцчџш",
    ),
    "Maltese": Language(
        name="Maltese",
        iso_code="mt",
        # Y is only used in loanwords
        use_ascii=False,
        charsets=["ISO-8859-3"],
        alphabet="abċdefġghħijklmnopqrstuvwxżzABĊDEFĠGHĦIJKLMNOPQRSTUVWXŻZ",
    ),
    "Malay": Language(
        name="Malay",
        iso_code="ms",
        use_ascii=True,
        charsets=["ISO-8859-1", "WINDOWS-1252", "MacRoman"],
        alphabet=ascii_letters,
    ),
    "Dutch": Language(
        name="Dutch",
        iso_code="nl",
        # àâçèéîïñôùûêŒÀÂÇÈÉÊÎÏÔÑÙÛ are all used for loanwords
        alphabet=ascii_letters,
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "WINDOWS-1252",
            "MacRoman",
            "ISO-8859-15",
            "CP850",
            "CP858",
        ],
    ),
    "Norwegian": Language(
        name="Norwegian",
        iso_code="no",
        # Q, W, X, Z are only used for foreign words
        use_ascii=False,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
            "CP865",
        ],
        alphabet="ABCDEFGHIJKLMNOPRSTUVYÆØÅabcdefghijklmnoprstuvyæøå",
    ),
    "Polish": Language(
        name="Polish",
        iso_code="pl",
        # Q and X are only used for foreign words.
        use_ascii=False,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻaąbcćdeęfghijklłmnńoóprsśtuwyzźż",
    ),
    "Portuguese": Language(
        name="Portuguese",
        iso_code="pt",
        use_ascii=True,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
            "CP860",
        ],
        alphabet="".join(sorted(set(ascii_letters + "ÁÂÃÀÇÉÊÍÓÔÕÚáâãàçéêíóôõú"))),
    ),
    "Romanian": Language(
        name="Romanian",
        iso_code="ro",
        use_ascii=True,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="".join(sorted(set(ascii_letters + "ăâîșțĂÂÎȘȚ"))),
    ),
    "Russian": Language(
        name="Russian",
        iso_code="ru",
        use_ascii=False,
        charsets=[
            "ISO-8859-5",
            "WINDOWS-1251",
            "KOI8-R",
            "MacCyrillic",
            "CP866",
            "CP855",
        ],
        alphabet="абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
    ),
    "Slovak": Language(
        name="Slovak",
        iso_code="sk",
        use_ascii=True,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="".join(
            sorted(set(ascii_letters + "áäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ"))
        ),
    ),
    "Slovene": Language(
        name="Slovene",
        iso_code="sl",
        # Q, W, X, Y are only used for foreign words.
        use_ascii=False,
        charsets=["ISO-8859-2", "WINDOWS-1250", "CP852", "ISO-8859-16", "MacLatin2"],
        alphabet="abcčdefghijklmnoprsštuvzžABCČDEFGHIJKLMNOPRSŠTUVZŽ",
    ),
    # Serbian can be written in both Latin and Cyrillic, but there's no
    # simple way to get the Latin alphabet pages from Wikipedia through
    # the API, so for now we just support Cyrillic.
    "Serbian": Language(
        name="Serbian",
        iso_code="sr",
        use_ascii=False,
        alphabet="АБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШабвгдђежзијклљмнњопрстћуфхцчџш",
        charsets=["ISO-8859-5", "WINDOWS-1251", "MacCyrillic", "CP855"],
    ),
    "Swedish": Language(
        name="Swedish",
        iso_code="sv",
        # Q, W, Z are rare and mainly in loanwords
        use_ascii=False,
        charsets=[
            "ISO-8859-1",
            "ISO-8859-15",
            "WINDOWS-1252",
            "MacRoman",
            "CP850",
            "CP858",
        ],
        alphabet="ABCDEFGHIJKLMNOPRSTUVXYÅÄÖabcdefghijklmnopqrstuvxyzåäö",
    ),
    "Tajik": Language(
        name="Tajik",
        iso_code="tg",
        use_ascii=False,
        charsets=["KOI8-T"],
        alphabet="АБВГҒДЕЁЖЗИӢЙКҚЛМНОПРСТУӮФХҲЧҶШЪЭЮЯабвгғдеёжзиӣйкқлмнопрстуӯфхҳчҷшъэюя",
    ),
    "Thai": Language(
        name="Thai",
        iso_code="th",
        use_ascii=False,
        charsets=["ISO-8859-11", "TIS-620", "CP874"],
        alphabet="กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรฤลฦวศษสหฬอฮฯะัาำิีึืฺุู฿เแโใไๅๆ็่้๊๋์ํ๎๏๐๑๒๓๔๕๖๗๘๙๚๛",
    ),
    "Turkish": Language(
        name="Turkish",
        iso_code="tr",
        # Q, W, and X are not used by Turkish
        use_ascii=False,
        charsets=[
            "ISO-8859-3",
            "ISO-8859-9",
            "WINDOWS-1254",
            "CP857",
            "CP1026",
            "MacTurkish",
        ],
        alphabet="abcçdefgğhıijklmnoöprsştuüvyzâîûABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZÂÎÛ",
    ),
    "Ukrainian": Language(
        name="Ukrainian",
        iso_code="uk",
        use_ascii=False,
        charsets=["ISO-8859-5", "WINDOWS-1251", "KOI8-U", "MacCyrillic", "CP1125"],
        alphabet="АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюяʼ",
    ),
    "Urdu": Language(
        name="Urdu",
        iso_code="ur",
        use_ascii=False,
        charsets=["CP1006"],
        alphabet="ءآأؤإئابةتثجحخدذرزسشصضطظعغػؼؽؾؿـفقكلمنهوىيپچڈڑژکگںھۂۃیے",
    ),
    "Vietnamese": Language(
        name="Vietnamese",
        iso_code="vi",
        use_ascii=False,
        # Windows-1258 is the only common 8-bit
        # Vietnamese encoding supported by Python.
        # From Wikipedia:
        # For systems that lack support for Unicode,
        # dozens of 8-bit Vietnamese code pages are
        # available.[1] The most common are VISCII
        # (TCVN 5712:1993), VPS, and Windows-1258.[3]
        # Where ASCII is required, such as when
        # ensuring readability in plain text e-mail,
        # Vietnamese letters are often encoded
        # according to Vietnamese Quoted-Readable
        # (VIQR) or VSCII Mnemonic (VSCII-MNEM),[4]
        # though usage of either variable-width
        # scheme has declined dramatically following
        # the adoption of Unicode on the World Wide
        # Web.
        charsets=["WINDOWS-1258"],
        alphabet="aăâbcdđeêghiklmnoôơpqrstuưvxyAĂÂBCDĐEÊGHIKLMNOÔƠPQRSTUƯVXY",
    ),
}

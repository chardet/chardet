Supported Encodings
===================

chardet recognises **99 Python text encodings** via
86 detection targets and their aliases, across six
encoding eras.
The default :attr:`~chardet.EncodingEra.ALL` era considers every
encoding below. Pass a narrower era such as
:attr:`~chardet.EncodingEra.MODERN_WEB` to restrict the candidates.
The multi-byte column says whether the codec can spend more than one
byte on a single character.

Modern Web
----------

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - ascii
     - us-ascii
     - No
   * - big5hkscs
     - Big5-HKSCS, Big5HKSCS, big5, big5-tw, csbig5, cp950, cn-big5, x-x-big5, csbig5hkscs
     - Yes
   * - cp1250
     - Windows-1250, cp1250, x-cp1250, cswindows1250
     - No
   * - cp1251
     - Windows-1251, cp1251, x-cp1251, cswindows1251
     - No
   * - cp1252
     - Windows-1252, cp1252, x-cp1252, cswindows1252
     - No
   * - cp1253
     - Windows-1253, cp1253, x-cp1253, cswindows1253
     - No
   * - cp1254
     - Windows-1254, cp1254, x-cp1254, cswindows1254
     - No
   * - cp1255
     - Windows-1255, cp1255, x-cp1255, cswindows1255
     - No
   * - cp1256
     - Windows-1256, cp1256, x-cp1256, cswindows1256
     - No
   * - cp1257
     - Windows-1257, cp1257, x-cp1257, cswindows1257
     - No
   * - cp1258
     - Windows-1258, cp1258, x-cp1258, cswindows1258
     - No
   * - cp874
     - CP874, windows-874, dos-874
     - No
   * - cp932
     - CP932, ms932, mskanji, ms-kanji, cswindows31j, windows-31j
     - Yes
   * - cp949
     - CP949, ms949, uhc, windows-949, csksc56011987, iso-ir-149, ks_c_5601-1987, ks_c_5601-1989, ksc5601, ksc_5601
     - Yes
   * - euc_jis_2004
     - EUC-JIS-2004, euc-jp, eucjp, ujis, u-jis, euc-jisx0213, cseucpkdfmtjapanese, x-euc-jp
     - Yes
   * - euc_kr
     - EUC-KR, euckr, cseuckr
     - Yes
   * - gb18030
     - GB18030, gb-18030, gb2312, gbk, csgb2312, gb_2312, gb_2312-80, x-gbk, csiso58gb231280, iso-ir-58, csgb18030, csgbk, cp936, ms936, windows-936
     - Yes
   * - iso2022_jp_2
     - ISO-2022-JP-2, iso-2022-jp, csiso2022jp, iso2022-jp-1, csiso2022jp2
     - Yes
   * - iso2022_jp_2004
     - ISO-2022-JP-2004, iso2022-jp-3
     - Yes
   * - iso2022_jp_ext
     - ISO-2022-JP-EXT
     - Yes
   * - koi8-r
     - KOI8-R, koi8r, koi, koi8, cskoi8r
     - No
   * - koi8-u
     - KOI8-U, koi8u, koi8-ru, cskoi8u
     - No
   * - shift_jis_2004
     - Shift-JIS-2004, Shift_JIS_2004, shift_jis, sjis, shiftjis, s_jis, shift-jisx0213, x-sjis, csshiftjis, ms_kanji
     - Yes
   * - tis-620
     - TIS-620, tis620, iso-8859-11, iso8859-11, iso885911, cstis620
     - No
   * - utf-16
     - UTF-16, utf16, csutf16
     - Yes
   * - utf-16-be
     - UTF-16-BE, utf-16be, csutf16be
     - Yes
   * - utf-16-le
     - UTF-16-LE, utf-16le, csutf16le
     - Yes
   * - utf-32
     - UTF-32, utf32, csutf32
     - Yes
   * - utf-32-be
     - UTF-32-BE, utf-32be, csutf32be
     - Yes
   * - utf-32-le
     - UTF-32-LE, utf-32le, csutf32le
     - Yes
   * - utf-8
     - utf-8, utf8, csutf8, unicode-1-1-utf-8, unicode11utf8, unicode20utf8, x-unicode20utf8
     - Yes
   * - utf-8-sig
     - UTF-8-SIG, utf-8-bom
     - Yes

Legacy ISO
----------

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - iso8859-1
     - ISO-8859-1, latin-1, latin1, iso8859-1, iso88591
     - No
   * - iso8859-10
     - ISO-8859-10, latin-6, latin6, iso8859-10, iso885910
     - No
   * - iso8859-13
     - ISO-8859-13, latin-7, latin7, iso8859-13, iso885913, csiso885913
     - No
   * - iso8859-14
     - ISO-8859-14, latin-8, latin8, iso8859-14, iso885914, csiso885914, iso-ir-199, iso-celtic, l8
     - No
   * - iso8859-15
     - ISO-8859-15, latin-9, latin9, iso8859-15, iso885915, csisolatin9, csiso885915, l9
     - No
   * - iso8859-16
     - ISO-8859-16, latin-10, latin10, iso8859-16, iso885916, csiso885916, iso-ir-226, l10
     - No
   * - iso8859-2
     - ISO-8859-2, latin-2, latin2, iso8859-2, iso88592
     - No
   * - iso8859-3
     - ISO-8859-3, latin-3, latin3, iso8859-3, iso88593
     - No
   * - iso8859-4
     - ISO-8859-4, latin-4, latin4, iso8859-4, iso88594
     - No
   * - iso8859-5
     - ISO-8859-5, iso8859-5, cyrillic, iso88595
     - No
   * - iso8859-6
     - ISO-8859-6, iso8859-6, arabic, iso88596, iso-8859-6-e, iso-8859-6-i, csiso88596e, csiso88596i
     - No
   * - iso8859-7
     - ISO-8859-7, iso8859-7, greek, iso88597, sun_eu_greek
     - No
   * - iso8859-8
     - ISO-8859-8, iso8859-8, hebrew, iso88598, iso-8859-8-e, iso-8859-8-i, csiso88598e, csiso88598i, visual, logical
     - No
   * - iso8859-9
     - ISO-8859-9, latin-5, latin5, iso8859-9, iso88599
     - No
   * - johab
     - Johab
     - Yes

Legacy Mac
----------

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - mac-cyrillic
     - Mac-Cyrillic, MacCyrillic, maccyrillic, x-mac-cyrillic, x-mac-ukrainian
     - No
   * - mac-greek
     - Mac-Greek, MacGreek, macgreek
     - No
   * - mac-iceland
     - Mac-Iceland, MacIceland, maciceland
     - No
   * - mac-latin2
     - Mac-Latin2, MacLatin2, maclatin2, maccentraleurope
     - No
   * - mac-roman
     - Mac-Roman, MacRoman, macroman, macintosh, csmacintosh, mac, x-mac-roman
     - No
   * - mac-turkish
     - Mac-Turkish, MacTurkish, macturkish
     - No

Legacy Regional
---------------

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - cp1006
     - CP1006
     - No
   * - cp1125
     - CP1125
     - No
   * - cp720
     - CP720
     - No
   * - hp-roman8
     - HP-Roman8, roman8, r8, csHPRoman8
     - No
   * - hz
     - HZ-GB-2312, hz
     - Yes
   * - iso2022_kr
     - ISO-2022-KR, csiso2022kr
     - Yes
   * - koi8-t
     - KOI8-T
     - No
   * - kz1048
     - KZ-1048, kz1048, strk1048-2002, rk1048
     - No
   * - ptcp154
     - PTCP154, pt154, cp154
     - No
   * - utf-7
     - UTF-7, utf7, csutf7
     - Yes

DOS
---

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - cp437
     - CP437
     - No
   * - cp737
     - CP737
     - No
   * - cp775
     - CP775
     - No
   * - cp850
     - CP850
     - No
   * - cp852
     - CP852
     - No
   * - cp855
     - CP855
     - No
   * - cp856
     - CP856
     - No
   * - cp857
     - CP857
     - No
   * - cp858
     - CP858
     - No
   * - cp860
     - CP860
     - No
   * - cp861
     - CP861
     - No
   * - cp862
     - CP862
     - No
   * - cp863
     - CP863
     - No
   * - cp864
     - CP864
     - No
   * - cp865
     - CP865
     - No
   * - cp866
     - CP866
     - No
   * - cp869
     - CP869
     - No

Mainframe (EBCDIC)
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 50 15

   * - Encoding
     - Aliases
     - Multi-byte
   * - cp1026
     - CP1026
     - No
   * - cp1140
     - CP1140, cp037, cp01140, ibm01140, ibm1140, csibm01140
     - No
   * - cp273
     - CP273
     - No
   * - cp424
     - CP424
     - No
   * - cp500
     - CP500
     - No
   * - cp875
     - CP875
     - No

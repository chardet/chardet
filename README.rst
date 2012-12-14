Charade: The Universal character encoding detector
--------------------------------------------------

Detects
 - ASCII, UTF-8, UTF-16 (2 variants), UTF-32 (4 variants)
 - Big5, GB2312, EUC-TW, HZ-GB-2312, ISO-2022-CN (Traditional and Simplified Chinese)
 - EUC-JP, SHIFT_JIS, ISO-2022-JP (Japanese)
 - EUC-KR, ISO-2022-KR (Korean)
 - KOI8-R, MacCyrillic, IBM855, IBM866, ISO-8859-5, windows-1251 (Cyrillic)
 - ISO-8859-2, windows-1250 (Hungarian)
 - ISO-8859-5, windows-1251 (Bulgarian)
 - windows-1252 (English)
 - ISO-8859-7, windows-1253 (Greek)
 - ISO-8859-8, windows-1255 (Visual and Logical Hebrew)
 - TIS-620 (Thai)

Requires Python 2.6 or later

Command-line Tool
-----------------

chardet comes with a command-line script which reports on the encodings of one
or more files::

    % chardetect.py somefile someotherfile
    somefile: windows-1252 with confidence 0.5
    someotherfile: ascii with confidence 1.0

About
-----

This is a port of Mark Pilgrim's excellent chardet. Previous two versions 
needed to be maintained: one that supported python 2.x and one that supported 
python 3.x. With the minor amount of work placed into this port, charade now 
supports both in one codebase.

The base for the work was Mark's last available copy of the chardet source for 
python 3000.

The Reason
~~~~~~~~~~

Does everything have to have a reason? No, but in this case the reason was to 
help out `requests <http://python-requests.org>`_ and anyone else who sorely 
needed this.

What about x, y, or z?
~~~~~~~~~~~~~~~~~~~~~~

If x, y, or z (a colloquialism for other projects that may do the same thing) 
do exist and indeed existed before charade, then I'm disappointed that they 
didn't make themselves better known. It would have saved me quite a few hours.


:maintainer: Ian Cordasco

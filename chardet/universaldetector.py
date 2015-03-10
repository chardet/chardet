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
"""
Module containing the UniversalDetector detector class, which is the primary
class a user of ``chardet`` should use.

:author: Mark Pilgrim (intial port to Python)
:author: Shy Shalom (original C code)
:author: Dan Blanchard (major refactoring for 3.0)
:author: Ian Cordasco
"""


import codecs
import logging
import re

from .enums import InputState, LanguageFilter, ProbingState
from .escprober import EscCharSetProber
from .latin1prober import Latin1Prober
from .mbcsgroupprober import MBCSGroupProber
from .sbcsgroupprober import SBCSGroupProber


class UniversalDetector(object):
    """
    The ``UniversalDetector`` class underlies the ``chardet.detect`` function
    and coordinates all of the different charset probers.

    To get a ``dict`` containing an encoding and its confidence, you can simply
    run:

    .. code::

            u = UniversalDetector()
            u.feed(some_bytes)
            u.close()
            detected = u.result

    """

    MINIMUM_THRESHOLD = 0.20
    HIGH_BYTE_DETECTOR = re.compile(b'[\x80-\xFF]')
    ESC_DETECTOR = re.compile(b'(\033|~{)')

    EXTRA_WINCHARS = re.compile(b'[\x80-\x9F]')
    ISO_WIN_MAP = {'iso-8859-2': 'Windows-1250', 'iso-8859-5':  'Windows-1251', 'iso-8859-1': 'Windows-1252',
                   'iso-8859-7': 'Windows-1253', 'iso-8859-9':  'Windows-1254', 'iso-8859-8': 'Windows-1255',
                   'iso-8859-6': 'Windows-1256', 'iso-8859-13': 'Windows-1257'}

    XML_ESC_MAP = (('&gt;', b'>'), ('&lt;', b'<'), ('&amp;', b'&'), ('&apos;', b"'"), ('&quot;', b'"'), ('&nbsp;', b' '))

    def remove_tags(self, txt):
        for esc, char in  self.XML_ESC_MAP:
            txt = txt.replace(esc, char)

        txt = txt.replace('<![CDATA[', '')
        txt = txt.replace(']]>', '')

        txt = re.sub(br'<!--([^>]*)-->', '', txt, flags=re.DOTALL)
        txt = re.sub(br'<\?*\/*[A-Z]+[^>]*>', '', txt, flags=re.IGNORECASE)
        return txt

    def remove_urls(self, txt):
        txt = re.sub(br'\b(?:(?:https?|ftp|file)://|www\.|ftp\.)'
                         '(?:\([-A-Z0-9+&@#/%=~_|$?!:;,.]*\)|[-A-Z0-9+&@#\/%=~_|$?!:;,.])*'
                         '(?:\([-A-Z0-9+&@#/%=~_|$?!:;,.]*\)|[A-Z0-9+&@#/%=~_|$])',
                     '', txt, flags=re.IGNORECASE)
        return txt

    def remove_html_numbers(self, txt):
        txt = re.sub(br'&#[0-9]{2,};', '', txt)
        txt = re.sub(br'and#[0-9]{2,};', ' ', txt)
        return txt

    def remove_ascii_symbols(self, txt):
        txt = re.sub(br'[-#$%&*()=+:<>/]', ' ', txt)
        return txt

    def remove_digits(self, txt):
        txt = re.sub(br'[0-9]+', '', txt)
        return txt

    def remove_multiple_spaces(self, txt):
        txt = re.sub(br'\s{2,}', ' ', txt)
        return txt

    def remove_empty_lines(self, txt):
        txt = re.sub(br'^(\s|\t)*\n', '', txt, flags=re.MULTILINE)
        return txt

    def __init__(self, lang_filter=LanguageFilter.all):
        self._esc_charset_prober = None
        self._charset_probers = []
        self.result = None
        self.done = None
        self._got_data = None
        self._input_state = None
        self._last_char = None
        self.lang_filter = lang_filter
        self.logger = logging.getLogger(__name__)
        self._txt_buf = None
        self.reset()

    def reset(self):
        """
        Reset the UniversalDetector and all of its probers back to their
        initial states.  This is called by ``__init__``, so you only need to
        call this directly in between analyses of different documents.
        """
        self.result = {'encoding': None, 'confidence': 0.0}
        self.done = False
        self._got_data = False
        self._input_state = InputState.pure_ascii
        self._last_char = b''
        if self._esc_charset_prober:
            self._esc_charset_prober.reset()
        for prober in self._charset_probers:
            prober.reset()

    def feed(self, byte_str, txt_cleanup=True):
        """
        Takes a chunk of a document and feeds it through all of the relevant
        charset probers.

        After calling ``feed``, you can check the value of the ``done``
        attribute to see if you need to continue feeding the
        ``UniversalDetector`` more data, or if it has made a prediction
        (in the ``result`` attribute).

        .. note::
           You should always call ``close`` when you're done feeding in your
           document if ``done`` is not already ``True``.
        """
        if self.done:
            return

        if not len(byte_str):
            return

        self._txt_buf = byte_str
        # First check for known BOMs, since these are guaranteed to be correct
        if not self._got_data:
            # If the data starts with BOM, we know it is UTF
            if byte_str.startswith(codecs.BOM_UTF8):
                # EF BB BF  UTF-8 with BOM
                self.result = {'encoding': "UTF-8-SIG", 'confidence': 1.0}
            elif byte_str.startswith(codecs.BOM_UTF32_LE):
                # FF FE 00 00  UTF-32, little-endian BOM
                self.result = {'encoding': "UTF-32LE", 'confidence': 1.0}
            elif byte_str.startswith(codecs.BOM_UTF32_BE):
                # 00 00 FE FF  UTF-32, big-endian BOM
                self.result = {'encoding': "UTF-32BE", 'confidence': 1.0}
            elif byte_str.startswith(b'\xFE\xFF\x00\x00'):
                # FE FF 00 00  UCS-4, unusual octet order BOM (3412)
                self.result = {'encoding': "X-ISO-10646-UCS-4-3412",
                               'confidence': 1.0}
            elif byte_str.startswith(b'\x00\x00\xFF\xFE'):
                # 00 00 FF FE  UCS-4, unusual octet order BOM (2143)
                self.result = {'encoding': "X-ISO-10646-UCS-4-2143",
                               'confidence': 1.0}
            elif byte_str.startswith(codecs.BOM_LE):
                # FF FE  UTF-16, little endian BOM
                self.result = {'encoding': "UTF-16LE", 'confidence': 1.0}
            elif byte_str.startswith(codecs.BOM_BE):
                # FE FF  UTF-16, big endian BOM
                self.result = {'encoding': "UTF-16BE", 'confidence': 1.0}

            self._got_data = True
            if self.result['encoding'] is not None:
                self.done = True
                return

        # If none of those matched and we've only see ASCII so far, check
        # for high bytes and escape sequences
        if self._input_state == InputState.pure_ascii:
            if self.HIGH_BYTE_DETECTOR.search(byte_str):
                self._input_state = InputState.high_byte
            elif self._input_state == InputState.pure_ascii and \
                    self.ESC_DETECTOR.search(self._last_char + byte_str):
                self._input_state = InputState.esc_ascii

        self._last_char = byte_str[-1:]

        # If we've seen escape sequences, use the EscCharSetProber, which
        # uses a simple state machine to check for known escape sequences in
        # HZ and ISO-2022 encodings, since those are the only encodings that
        # use such sequences.
        if self._input_state == InputState.esc_ascii:
            if not self._esc_charset_prober:
                self._esc_charset_prober = EscCharSetProber(self.lang_filter)
            if self._esc_charset_prober.feed(byte_str) == ProbingState.found_it:
                self.result = {'encoding':
                               self._esc_charset_prober.charset_name,
                               'confidence':
                               self._esc_charset_prober.get_confidence()}
                self.done = True
        # If we've seen high bytes (i.e., those with values greater than 127),
        # we need to do more complicated checks using all our multi-byte and
        # single-byte probers that are left.  The single-byte probers
        # use character bigram distributions to determine the encoding, whereas
        # the multi-byte probers use a combination of character unigram and
        # bigram distributions.
        elif self._input_state == InputState.high_byte:
            if txt_cleanup:
                byte_str = self.remove_tags(byte_str)
                byte_str = self.remove_urls(byte_str)
                byte_str = self.remove_html_numbers(byte_str)
                byte_str = self.remove_ascii_symbols(byte_str)
                byte_str = self.remove_digits(byte_str)
                byte_str = self.remove_multiple_spaces(byte_str)
                byte_str = self.remove_empty_lines(byte_str)
            if not self._charset_probers:
                self._charset_probers = [MBCSGroupProber(self.lang_filter)]
                # If we're checking non-CJK encodings, use single-byte prober
                if self.lang_filter & LanguageFilter.non_cjk:
                    self._charset_probers.append(SBCSGroupProber())
                self._charset_probers.append(Latin1Prober())
            for prober in self._charset_probers:
                if prober.feed(byte_str) == ProbingState.found_it:
                    self.result = {'encoding': prober.charset_name,
                                   'confidence': prober.get_confidence()}
                    self.done = True
                    break

    def close(self):
        """
        Stop analyzing the current document and come up with a final
        prediction.

        :returns:  The ``result`` attribute if a prediction was made, otherwise
                   ``None``.
        """
        if self.done:
            return self.result
        if not self._got_data:
            self.logger.debug('no data received!')
            return
        self.done = True

        if self._input_state == InputState.pure_ascii:
            self.result = {'encoding': 'ascii', 'confidence': 1.0}
            return self.result

        if self._input_state == InputState.high_byte:
            proberConfidence = None
            max_prober_confidence = 0.0
            max_prober = None
            for prober in self._charset_probers:
                if not prober:
                    continue
                proberConfidence = prober.get_confidence()
                if proberConfidence > max_prober_confidence:
                    max_prober_confidence = proberConfidence
                    max_prober = prober
            if max_prober and (max_prober_confidence > self.MINIMUM_THRESHOLD):
                charset_name = max_prober.charset_name
                confidence = max_prober.get_confidence()
                if 'iso-8859' in charset_name.lower():
                    if self.EXTRA_WINCHARS.search(self._txt_buf):
                        charset_name = self.ISO_WIN_MAP.get(charset_name.lower(), charset_name)
                self.result = {'encoding': charset_name, 'confidence': confidence}
                return self.result

        if self.logger.getEffectiveLevel() == logging.DEBUG:
            self.logger.debug('no probers hit minimum threshhold')
            for prober in self._charset_probers[0].mProbers:
                if not prober:
                    continue
                self.logger.debug('%s confidence = %s', prober.charset_name,
                                  prober.get_confidence())

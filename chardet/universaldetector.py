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
# License along with this library; if not, see
# <https://www.gnu.org/licenses/>.
######################### END LICENSE BLOCK #########################
"""
Module containing the UniversalDetector detector class, which is the primary
class a user of ``chardet`` should use.

:author: Mark Pilgrim (initial port to Python)
:author: Shy Shalom (original C code)
:author: Dan Blanchard (major refactoring for 3.0)
:author: Ian Cordasco
"""

import codecs
import logging
import re
from typing import Optional, Union

from .charsetgroupprober import CharSetGroupProber
from .charsetprober import CharSetProber
from .enums import EncodingEra, InputState, LanguageFilter, ProbingState
from .escprober import EscCharSetProber
from .mbcsgroupprober import MBCSGroupProber
from .resultdict import ResultDict
from .sbcsgroupprober import SBCSGroupProber
from .utf1632prober import UTF1632Prober


class UniversalDetector:
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
    HIGH_BYTE_DETECTOR = re.compile(b"[\x80-\xff]")
    ESC_DETECTOR = re.compile(b"(\033|~{)")
    # Bytes in the 0x80-0x9F range are different in Windows vs Mac/ISO encodings:
    # - Windows-125x: Uses for punctuation (smart quotes, dashes, ellipsis, etc.)
    # - Mac encodings: Uses for letters (accented characters)
    # - ISO-8859-x: Mostly undefined control codes
    WIN_BYTE_DETECTOR = re.compile(b"[\x80-\x9f]")
    # Check if Win bytes appear between word characters (suggesting Mac encoding)
    # e.g., "cre\x91rd" (ë in MacRoman) vs " \x91quote\x92 " (smart quotes in Windows)
    MAC_LETTER_IN_WORD_DETECTOR = re.compile(b"[a-zA-Z][\x80-\x9f][a-zA-Z]")
    ISO_WIN_MAP = {
        "iso-8859-1": "Windows-1252",
        "iso-8859-2": "Windows-1250",
        "iso-8859-5": "Windows-1251",
        "iso-8859-6": "Windows-1256",
        "iso-8859-7": "Windows-1253",
        "iso-8859-8": "Windows-1255",
        "iso-8859-9": "Windows-1254",
        "iso-8859-13": "Windows-1257",
    }
    # Based on https://encoding.spec.whatwg.org/#names-and-labels
    # Maps legacy encoding names to their modern/superset equivalents.
    # Uses Python's canonical codec names (case-insensitive).
    LEGACY_MAP = {
        "ascii": "Windows-1252",  # ASCII is subset of Windows-1252
        "iso-8859-1": "Windows-1252",  # Latin-1 extended by Windows-1252
        "iso-8859-2": "Windows-1250",  # Central European
        "iso-8859-5": "Windows-1251",  # Cyrillic
        "iso-8859-6": "Windows-1256",  # Arabic
        "iso-8859-7": "Windows-1253",  # Greek
        "iso-8859-8": "Windows-1255",  # Hebrew
        "iso-8859-9": "Windows-1254",  # Turkish
        "iso-8859-11": "cp874",  # Thai, extended by CP874 (aka Windows-874)
        "iso-8859-13": "Windows-1257",  # Baltic
        "tis-620": "cp874",  # Thai, equivalent to Windows-874
        "gb2312": "GB18030",  # GB2312 < GBK < GB18030 (GB18030 is superset)
        "euc-kr": "CP949",  # EUC-KR extended by CP949 (aka Windows-949)
        "utf-16le": "UTF-16",  # UTF-16LE without BOM -> UTF-16 with BOM handling
    }

    def __init__(
        self,
        lang_filter: LanguageFilter = LanguageFilter.ALL,
        should_rename_legacy: bool = False,
        encoding_era: EncodingEra = EncodingEra.MODERN_WEB,
        max_bytes: int = 200_000,
    ) -> None:
        self._esc_charset_prober: Optional[EscCharSetProber] = None
        self._utf1632_prober: Optional[UTF1632Prober] = None
        self._charset_probers: list[CharSetProber] = []
        self.result: ResultDict = {
            "encoding": None,
            "confidence": 0.0,
            "language": None,
        }
        self.done = False
        self._got_data = False
        self._input_state = InputState.PURE_ASCII
        self._last_char = b""
        self.lang_filter = lang_filter
        self.logger = logging.getLogger(__name__)
        self._has_win_bytes = False
        self._has_mac_letter_pattern = False
        self.should_rename_legacy = should_rename_legacy
        self.encoding_era = encoding_era
        self._total_bytes_fed = 0
        self.max_bytes = max_bytes
        self.reset()

    @property
    def input_state(self) -> int:
        return self._input_state

    @property
    def has_win_bytes(self) -> bool:
        return self._has_win_bytes

    @property
    def charset_probers(self) -> list[CharSetProber]:
        return self._charset_probers

    def _get_utf8_prober(self) -> Optional[CharSetProber]:
        """
        Get the UTF-8 prober from the charset probers.
        Returns None if not found.
        """
        for group_prober in self._charset_probers:
            for prober in getattr(group_prober, "probers", []):
                if prober.charset_name and "utf-8" in prober.charset_name.lower():
                    return prober
        return None

    def reset(self) -> None:
        """
        Reset the UniversalDetector and all of its probers back to their
        initial states.  This is called by ``__init__``, so you only need to
        call this directly in between analyses of different documents.
        """
        self.result = {"encoding": None, "confidence": 0.0, "language": None}
        self.done = False
        self._got_data = False
        self._has_win_bytes = False
        self._has_mac_letter_pattern = False
        self._input_state = InputState.PURE_ASCII
        self._last_char = b""
        self._total_bytes_fed = 0
        if self._esc_charset_prober:
            self._esc_charset_prober.reset()
        if self._utf1632_prober:
            self._utf1632_prober.reset()
        for prober in self._charset_probers:
            prober.reset()

    def feed(self, byte_str: Union[bytes, bytearray]) -> None:
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

        if not byte_str:
            return

        if not isinstance(byte_str, bytearray):
            byte_str = bytearray(byte_str)

        # First check for known BOMs, since these are guaranteed to be correct
        if not self._got_data:
            # If the data starts with BOM, we know it is UTF
            if byte_str.startswith(codecs.BOM_UTF8):
                # EF BB BF  UTF-8 with BOM
                self.result = {
                    "encoding": "UTF-8-SIG",
                    "confidence": 1.0,
                    "language": "",
                }
            elif byte_str.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
                # FF FE 00 00  UTF-32, little-endian BOM
                # 00 00 FE FF  UTF-32, big-endian BOM
                self.result = {"encoding": "UTF-32", "confidence": 1.0, "language": ""}
            elif byte_str.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
                # FF FE  UTF-16, little endian BOM
                # FE FF  UTF-16, big endian BOM
                self.result = {"encoding": "UTF-16", "confidence": 1.0, "language": ""}
            else:
                # Binary file detection - check for excessive null bytes early
                # But UTF-16/32 have null bytes, so check for patterns first

                # Check for no-BOM UTF-16/32 patterns (alternating nulls)
                # UTF-32LE: XX 00 00 00 pattern
                # UTF-32BE: 00 00 00 XX pattern
                # UTF-16LE: XX 00 pattern
                # UTF-16BE: 00 XX pattern
                looks_like_utf16_32 = False
                if len(byte_str) >= 100:
                    sample = byte_str[:100]
                    # Count nulls in even and odd positions
                    even_nulls = sum(1 for i in range(0, 100, 2) if sample[i] == 0)
                    odd_nulls = sum(1 for i in range(1, 100, 2) if sample[i] == 0)
                    # If most even or odd positions are null, likely UTF-16/32
                    if even_nulls > 20 or odd_nulls > 20:
                        looks_like_utf16_32 = True

                if not looks_like_utf16_32:
                    # Sample first 8KB to detect binary files
                    sample_size = min(len(byte_str), 8192)
                    null_count = byte_str[:sample_size].count(0)
                    if null_count > sample_size * 0.1:  # >10% null bytes
                        # Likely a binary file, not text
                        self.result = {
                            "encoding": None,
                            "confidence": 0.0,
                            "language": "",
                        }
                        self.done = True
                        return

            self._got_data = True
            if self.result["encoding"] is not None:
                self.done = True
                return

        # If none of those matched and we've only see ASCII so far, check
        # for high bytes and escape sequences
        if self._input_state == InputState.PURE_ASCII:
            if self.HIGH_BYTE_DETECTOR.search(byte_str):
                self._input_state = InputState.HIGH_BYTE
            elif (
                self._input_state == InputState.PURE_ASCII
                and self.ESC_DETECTOR.search(self._last_char + byte_str)
            ):
                self._input_state = InputState.ESC_ASCII

        self._last_char = byte_str[-1:]

        # Track total bytes processed
        self._total_bytes_fed += len(byte_str)

        # Stop processing after processing enough data
        if self._total_bytes_fed > self.max_bytes:
            self.done = True
            return

        # next we will look to see if it is appears to be either a UTF-16 or
        # UTF-32 encoding
        if not self._utf1632_prober:
            self._utf1632_prober = UTF1632Prober()

        if self._utf1632_prober.state == ProbingState.DETECTING:
            if self._utf1632_prober.feed(byte_str) == ProbingState.FOUND_IT:
                self.result = {
                    "encoding": self._utf1632_prober.charset_name,
                    "confidence": self._utf1632_prober.get_confidence(),
                    "language": "",
                }
                self.done = True
                return

        # If we've seen escape sequences, use the EscCharSetProber, which
        # uses a simple state machine to check for known escape sequences in
        # HZ and ISO-2022 encodings, since those are the only encodings that
        # use such sequences.
        if self._input_state == InputState.ESC_ASCII:
            if not self._esc_charset_prober:
                self._esc_charset_prober = EscCharSetProber(self.lang_filter)
            if self._esc_charset_prober.feed(byte_str) == ProbingState.FOUND_IT:
                self.result = {
                    "encoding": self._esc_charset_prober.charset_name,
                    "confidence": self._esc_charset_prober.get_confidence(),
                    "language": self._esc_charset_prober.language,
                }
                self.done = True
        # If we've seen high bytes (i.e., those with values greater than 127),
        # we need to do more complicated checks using all our multi-byte and
        # single-byte probers that are left.  The single-byte probers
        # use character bigram distributions to determine the encoding, whereas
        # the multi-byte probers use a combination of character unigram and
        # bigram distributions.
        elif self._input_state == InputState.HIGH_BYTE:
            if not self._charset_probers:
                self._charset_probers = [MBCSGroupProber(self.lang_filter)]
                # If we're checking non-CJK encodings, use single-byte prober
                if self.lang_filter & LanguageFilter.NON_CJK:
                    self._charset_probers.append(SBCSGroupProber(self.encoding_era))
            for prober in self._charset_probers:
                if prober.feed(byte_str) == ProbingState.FOUND_IT:
                    charset_name = prober.charset_name
                    # Rename legacy encodings if requested
                    if self.should_rename_legacy:
                        charset_name = self.LEGACY_MAP.get(
                            (charset_name or "").lower(), charset_name
                        )
                    self.result = {
                        "encoding": charset_name,
                        "confidence": prober.get_confidence(),
                        "language": prober.language,
                    }
                    self.done = True
                    break
            if self.WIN_BYTE_DETECTOR.search(byte_str):
                self._has_win_bytes = True
            if self.MAC_LETTER_IN_WORD_DETECTOR.search(byte_str):
                self._has_mac_letter_pattern = True

    def close(self) -> ResultDict:
        """
        Stop analyzing the current document and come up with a final
        prediction.

        :returns:  The ``result`` attribute, a ``dict`` with the keys
                   `encoding`, `confidence`, and `language`.
        """
        # Don't bother with checks if we're already done
        if self.done:
            return self.result
        self.done = True

        if not self._got_data:
            self.logger.debug("no data received!")

        # Default to ASCII if it is all we've seen so far
        elif self._input_state == InputState.PURE_ASCII:
            self.result = {"encoding": "ascii", "confidence": 1.0, "language": ""}

        # Check if escape prober found anything
        elif self._input_state == InputState.ESC_ASCII:
            if self._esc_charset_prober:
                charset_name = self._esc_charset_prober.charset_name
                if charset_name:
                    self.result = {
                        "encoding": charset_name,
                        "confidence": self._esc_charset_prober.get_confidence(),
                        "language": self._esc_charset_prober.language,
                    }
                else:
                    # ESC prober didn't identify a specific encoding
                    # Since input is pure ASCII + ESC, default to UTF-8
                    self.result = {
                        "encoding": "utf-8",
                        "confidence": 1.0,
                        "language": "",
                    }

        # If we have seen non-ASCII, return the best that met MINIMUM_THRESHOLD
        elif self._input_state == InputState.HIGH_BYTE:
            prober_confidence = None
            max_prober_confidence = 0.0
            max_prober = None
            for prober in self._charset_probers:
                if not prober:
                    continue
                prober_confidence = prober.get_confidence()
                if prober_confidence > max_prober_confidence:
                    max_prober_confidence = prober_confidence
                    max_prober = prober
            if max_prober and (max_prober_confidence > self.MINIMUM_THRESHOLD):
                charset_name = max_prober.charset_name
                assert charset_name is not None
                lower_charset_name = charset_name.lower()
                confidence = max_prober.get_confidence()
                # Use Windows encoding name instead of ISO-8859 if we saw any
                # extra Windows-specific bytes
                if lower_charset_name.startswith("iso-8859"):
                    if self._has_win_bytes:
                        charset_name = self.ISO_WIN_MAP.get(
                            lower_charset_name, charset_name
                        )
                # Distinguish between MacRoman and Windows-1252 ONLY
                # These are the only pair where 0x80-0x9F is punctuation (Win) vs letters (Mac)
                # Other Windows/Mac pairs (1250/MacLatin2, 1251/MacCyrillic, etc.) both have letters
                elif (
                    lower_charset_name == "windows-1252"
                    and self._has_mac_letter_pattern
                ):
                    # Check if MacRoman has similar confidence
                    for prober in self._charset_probers:
                        if not prober:
                            continue
                        if isinstance(prober, CharSetGroupProber):
                            for sub_prober in getattr(prober, "probers", []):
                                sub_charset = (sub_prober.charset_name or "").lower()
                                if sub_charset == "macroman":
                                    sub_confidence = sub_prober.get_confidence()
                                    # If MacRoman prober has at least 90% of Windows-1252 confidence,
                                    # and we have letter patterns, prefer MacRoman
                                    if sub_confidence >= confidence * 0.90:
                                        charset_name = sub_prober.charset_name
                                        confidence = sub_confidence
                                        break
                # Rename legacy encodings with superset encodings if asked
                if self.should_rename_legacy:
                    charset_name = self.LEGACY_MAP.get(
                        (charset_name or "").lower(), charset_name
                    )
                self.result = {
                    "encoding": charset_name,
                    "confidence": confidence,
                    "language": max_prober.language,
                }
            else:
                # Default to UTF-8 if no encoding met threshold AND UTF-8 prober
                # hasn't determined this is NOT UTF-8
                # UTF-8 is now the most common encoding on the web and a superset of ASCII
                utf8_prober = self._get_utf8_prober()
                if utf8_prober and utf8_prober.active:
                    # UTF-8 prober didn't rule it out, so default to UTF-8
                    self.result = {
                        "encoding": utf8_prober.charset_name,
                        "confidence": utf8_prober.get_confidence(),
                        "language": utf8_prober.language,
                    }
                else:
                    # UTF-8 was ruled out, return None
                    self.result = {
                        "encoding": None,
                        "confidence": 0.0,
                        "language": None,
                    }

        # Log all prober confidences if none met MINIMUM_THRESHOLD
        if self.logger.getEffectiveLevel() <= logging.DEBUG:
            if self.result["encoding"] is None:
                self.logger.debug("no probers hit minimum threshold")
                for group_prober in self._charset_probers:
                    if not group_prober:
                        continue
                    if isinstance(group_prober, CharSetGroupProber):
                        for prober in group_prober.probers:
                            self.logger.debug(
                                "%s %s confidence = %s",
                                prober.charset_name,
                                prober.language,
                                prober.get_confidence(),
                            )
                    else:
                        self.logger.debug(
                            "%s %s confidence = %s",
                            group_prober.charset_name,
                            group_prober.language,
                            group_prober.get_confidence(),
                        )
        return self.result

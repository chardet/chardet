######################## BEGIN LICENSE BLOCK ########################
#
# Contributor(s):
#   Jason Zavaglia
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
from typing import Union

from .charsetprober import CharSetProber
from .enums import ProbingState


class UTF1632Prober(CharSetProber):
    """
    This class simply looks for occurrences of zero bytes, and infers
    whether the file is UTF16 or UTF32 (low-endian or big-endian)
    For instance, files looking like ( \0 \0 \0 [nonzero] )+
    have a good probability to be UTF32BE.  Files looking like ( \0 [nonzero] )+
    may be guessed to be UTF16BE, and inversely for little-endian varieties.
    """

    # how many logical characters to scan before feeling confident of prediction
    MIN_CHARS_FOR_DETECTION = 20
    # a fixed constant ratio of expected zeros or non-zeros in modulo-position.
    # For ASCII-heavy text in UTF-16/32
    EXPECTED_RATIO = 0.94
    # Minimum ratio for non-ASCII text (e.g., CJK characters in UTF-16)
    # CJK text has fewer null bytes but still shows clear alternating patterns
    # compared to random binary data
    MIN_RATIO = 0.08

    def __init__(self) -> None:
        super().__init__()
        self.position = 0
        self.zeros_at_mod = [0] * 4
        self.nonzeros_at_mod = [0] * 4
        self._state = ProbingState.DETECTING
        self.quad = [0, 0, 0, 0]
        self.invalid_utf16be = False
        self.invalid_utf16le = False
        self.invalid_utf32be = False
        self.invalid_utf32le = False
        self.first_half_surrogate_pair_detected_16be = False
        self.first_half_surrogate_pair_detected_16le = False
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.position = 0
        self.zeros_at_mod = [0] * 4
        self.nonzeros_at_mod = [0] * 4
        self._state = ProbingState.DETECTING
        self.invalid_utf16be = False
        self.invalid_utf16le = False
        self.invalid_utf32be = False
        self.invalid_utf32le = False
        self.first_half_surrogate_pair_detected_16be = False
        self.first_half_surrogate_pair_detected_16le = False
        self.quad = [0, 0, 0, 0]

    @property
    def charset_name(self) -> str:
        if self.is_likely_utf32be():
            return "utf-32be"
        if self.is_likely_utf32le():
            return "utf-32le"
        if self.is_likely_utf16be():
            return "utf-16be"
        if self.is_likely_utf16le():
            return "utf-16le"
        # default to something valid
        return "utf-16"

    @property
    def language(self) -> str:
        return ""

    def approx_32bit_chars(self) -> float:
        return max(1.0, self.position / 4.0)

    def approx_16bit_chars(self) -> float:
        return max(1.0, self.position / 2.0)

    def is_likely_utf32be(self) -> bool:
        approx_chars = self.approx_32bit_chars()
        if approx_chars < self.MIN_CHARS_FOR_DETECTION:
            return False

        # For UTF-32BE: first 3 bytes (0,1,2) often zero, last byte (3) non-zero
        zero_012_ratio = (
            self.zeros_at_mod[0] + self.zeros_at_mod[1] + self.zeros_at_mod[2]
        ) / (approx_chars * 3)
        nonzero_3_ratio = self.nonzeros_at_mod[3] / approx_chars

        return (
            zero_012_ratio > self.MIN_RATIO * 3
            and nonzero_3_ratio > self.EXPECTED_RATIO
            and not self.invalid_utf32be
        )

    def is_likely_utf32le(self) -> bool:
        approx_chars = self.approx_32bit_chars()
        if approx_chars < self.MIN_CHARS_FOR_DETECTION:
            return False

        # For UTF-32LE: first byte (0) non-zero, bytes 1,2,3 often zero
        nonzero_0_ratio = self.nonzeros_at_mod[0] / approx_chars
        zero_123_ratio = (
            self.zeros_at_mod[1] + self.zeros_at_mod[2] + self.zeros_at_mod[3]
        ) / (approx_chars * 3)

        return (
            nonzero_0_ratio > self.EXPECTED_RATIO
            and zero_123_ratio > self.MIN_RATIO * 3
            and not self.invalid_utf32le
        )

    def is_likely_utf16be(self) -> bool:
        approx_chars = self.approx_16bit_chars()
        if approx_chars < self.MIN_CHARS_FOR_DETECTION:
            return False

        nonzero_ratio = (
            self.nonzeros_at_mod[1] + self.nonzeros_at_mod[3]
        ) / approx_chars
        zero_ratio = (self.zeros_at_mod[0] + self.zeros_at_mod[2]) / approx_chars

        # For UTF-16BE, odd positions should be non-zero, even positions should have zeros
        return (
            nonzero_ratio > self.EXPECTED_RATIO
            and zero_ratio > self.MIN_RATIO
            and not self.invalid_utf16be
        )

    def is_likely_utf16le(self) -> bool:
        approx_chars = self.approx_16bit_chars()
        if approx_chars < self.MIN_CHARS_FOR_DETECTION:
            return False

        nonzero_ratio = (
            self.nonzeros_at_mod[0] + self.nonzeros_at_mod[2]
        ) / approx_chars
        zero_ratio = (self.zeros_at_mod[1] + self.zeros_at_mod[3]) / approx_chars

        # For UTF-16LE, even positions should be non-zero, odd positions should have zeros
        # ASCII-heavy: both ratios > 94%
        # CJK-heavy: nonzero_ratio > 94%, zero_ratio might be low but > 20%
        return (
            nonzero_ratio > self.EXPECTED_RATIO
            and zero_ratio > self.MIN_RATIO
            and not self.invalid_utf16le
        )

    def validate_utf32_characters(self, quad: list[int]) -> None:
        """
        Validate if the quad of bytes is valid UTF-32.

        UTF-32 is valid in the range 0x00000000 - 0x0010FFFF
        excluding 0x0000D800 - 0x0000DFFF

        https://en.wikipedia.org/wiki/UTF-32
        """
        if (
            quad[0] != 0
            or quad[1] > 0x10
            or (quad[0] == 0 and quad[1] == 0 and 0xD8 <= quad[2] <= 0xDF)
        ):
            self.invalid_utf32be = True
        if (
            quad[3] != 0
            or quad[2] > 0x10
            or (quad[3] == 0 and quad[2] == 0 and 0xD8 <= quad[1] <= 0xDF)
        ):
            self.invalid_utf32le = True

    def validate_utf16_characters(self, pair: list[int]) -> None:
        """
        Validate if the pair of bytes is  valid UTF-16.

        UTF-16 is valid in the range 0x0000 - 0xFFFF excluding 0xD800 - 0xFFFF
        with an exception for surrogate pairs, which must be in the range
        0xD800-0xDBFF followed by 0xDC00-0xDFFF

        https://en.wikipedia.org/wiki/UTF-16
        """
        if not self.first_half_surrogate_pair_detected_16be:
            if 0xD8 <= pair[0] <= 0xDB:
                self.first_half_surrogate_pair_detected_16be = True
            elif 0xDC <= pair[0] <= 0xDF:
                self.invalid_utf16be = True
        else:
            if 0xDC <= pair[0] <= 0xDF:
                self.first_half_surrogate_pair_detected_16be = False
            else:
                self.invalid_utf16be = True

        if not self.first_half_surrogate_pair_detected_16le:
            if 0xD8 <= pair[1] <= 0xDB:
                self.first_half_surrogate_pair_detected_16le = True
            elif 0xDC <= pair[1] <= 0xDF:
                self.invalid_utf16le = True
        else:
            if 0xDC <= pair[1] <= 0xDF:
                self.first_half_surrogate_pair_detected_16le = False
            else:
                self.invalid_utf16le = True

    def feed(self, byte_str: Union[bytes, bytearray]) -> ProbingState:
        for c in byte_str:
            mod4 = self.position % 4
            self.quad[mod4] = c
            if mod4 == 3:
                self.validate_utf32_characters(self.quad)
                self.validate_utf16_characters(self.quad[0:2])
                self.validate_utf16_characters(self.quad[2:4])
            if c == 0:
                self.zeros_at_mod[mod4] += 1
            else:
                self.nonzeros_at_mod[mod4] += 1
            self.position += 1
        return self.state

    @property
    def state(self) -> ProbingState:
        if self._state in {ProbingState.NOT_ME, ProbingState.FOUND_IT}:
            # terminal, decided states
            return self._state
        if self.get_confidence() > 0.80:
            self._state = ProbingState.FOUND_IT
        elif self.position > 4 * 1024:
            # if we get to 4kb into the file, and we can't conclude it's UTF,
            # let's give up
            self._state = ProbingState.NOT_ME
        return self._state

    def get_confidence(self) -> float:
        return (
            0.85
            if (
                self.is_likely_utf16le()
                or self.is_likely_utf16be()
                or self.is_likely_utf32le()
                or self.is_likely_utf32be()
            )
            else 0.00
        )

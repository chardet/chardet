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
# License along with this library; if not, see
# <https://www.gnu.org/licenses/>.
######################### END LICENSE BLOCK #########################

from typing import Union

from .charsetgroupprober import CharSetGroupProber
from .charsetprober import CharSetProber
from .enums import EncodingEra, InputState
from .resultdict import ResultDict
from .universaldetector import UniversalDetector
from .version import VERSION, __version__

__all__ = ["UniversalDetector", "detect", "detect_all", "__version__", "VERSION"]


def detect(
    byte_str: Union[bytes, bytearray],
    should_rename_legacy: bool | None = None,
    encoding_era: EncodingEra = EncodingEra.MODERN_WEB,
    chunk_size: int = 65_536,
    max_bytes: int = 200_000,
) -> ResultDict:
    """
    Detect the encoding of the given byte string.

    :param byte_str:     The byte sequence to examine.
    :type byte_str:      ``bytes`` or ``bytearray``
    :param should_rename_legacy:  Should we rename legacy encodings
                                  to their more modern equivalents?
                                  If None (default), automatically enabled
                                  when encoding_era is MODERN_WEB.
    :type should_rename_legacy:   ``bool`` or ``None``
    :param encoding_era:  Which era of encodings to consider during detection.
    :type encoding_era:   ``EncodingEra``
    :param chunk_size:    Size of chunks to process at a time
    :type chunk_size:     ``int``
    :param max_bytes:    Maximum number of bytes to examine
    :type chunk_size:     ``int``
    """
    if not isinstance(byte_str, bytearray):
        if not isinstance(byte_str, bytes):
            raise TypeError(
                f"Expected object of type bytes or bytearray, got: {type(byte_str)}"
            )
        byte_str = bytearray(byte_str)

    # Automatically enable legacy remapping for MODERN_WEB era if not explicitly set
    if should_rename_legacy is None:
        should_rename_legacy = encoding_era == EncodingEra.MODERN_WEB

    detector = UniversalDetector(
        should_rename_legacy=should_rename_legacy,
        encoding_era=encoding_era,
        max_bytes=max_bytes,
    )

    # Process in chunks like uchardet does
    for i in range(0, len(byte_str), chunk_size):
        chunk = byte_str[i : i + chunk_size]
        detector.feed(chunk)
        if detector.done:
            break

    return detector.close()


def detect_all(
    byte_str: Union[bytes, bytearray],
    ignore_threshold: bool = False,
    should_rename_legacy: bool | None = None,
    encoding_era: EncodingEra = EncodingEra.MODERN_WEB,
    chunk_size: int = 65_536,
    max_bytes: int = 200_000,
) -> list[ResultDict]:
    """
    Detect all the possible encodings of the given byte string.

    :param byte_str:          The byte sequence to examine.
    :type byte_str:           ``bytes`` or ``bytearray``
    :param ignore_threshold:  Include encodings that are below
                              ``UniversalDetector.MINIMUM_THRESHOLD``
                              in results.
    :type ignore_threshold:   ``bool``
    :param should_rename_legacy:  Should we rename legacy encodings
                                  to their more modern equivalents?
                                  If None (default), automatically enabled
                                  when encoding_era is MODERN_WEB.
    :type should_rename_legacy:   ``bool`` or ``None``
    :param encoding_era:  Which era of encodings to consider during detection.
    :type encoding_era:   ``EncodingEra``
    :param chunk_size:    Size of chunks to process at a time.
    :type chunk_size:     ``int``
    :param max_bytes:    Size of chunks to process at a time.
    :type max_bytes:     ``int``
    """
    if not isinstance(byte_str, bytearray):
        if not isinstance(byte_str, bytes):
            raise TypeError(
                f"Expected object of type bytes or bytearray, got: {type(byte_str)}"
            )
        byte_str = bytearray(byte_str)

    # Automatically enable legacy remapping for MODERN_WEB era if not explicitly set
    if should_rename_legacy is None:
        should_rename_legacy = encoding_era == EncodingEra.MODERN_WEB

    detector = UniversalDetector(
        should_rename_legacy=should_rename_legacy,
        encoding_era=encoding_era,
        max_bytes=max_bytes,
    )

    # Process in chunks like uchardet does
    for i in range(0, len(byte_str), chunk_size):
        chunk = byte_str[i : i + chunk_size]
        detector.feed(chunk)
        if detector.done:
            break

    detector.close()

    if detector.input_state in (InputState.HIGH_BYTE, InputState.ESC_ASCII):
        results: list[ResultDict] = []
        probers: list[CharSetProber] = []
        for prober in detector.charset_probers:
            if isinstance(prober, CharSetGroupProber):
                probers.extend(p for p in prober.probers)
            else:
                probers.append(prober)
        for prober in probers:
            # Skip probers that determined this is NOT their encoding
            if not prober.active:
                continue
            if ignore_threshold or prober.get_confidence() > detector.MINIMUM_THRESHOLD:
                charset_name = prober.charset_name or ""
                lower_charset_name = charset_name.lower()
                # Use Windows encoding name instead of ISO-8859 if we saw any
                # extra Windows-specific bytes
                if lower_charset_name.startswith("iso-8859") and detector.has_win_bytes:
                    charset_name = detector.ISO_WIN_MAP.get(
                        lower_charset_name, charset_name
                    )
                # Rename legacy encodings with superset encodings if asked
                if should_rename_legacy:
                    charset_name = detector.LEGACY_MAP.get(
                        charset_name.lower(), charset_name
                    )
                results.append({
                    "encoding": charset_name,
                    "confidence": prober.get_confidence(),
                    "language": prober.language,
                })
        if len(results) > 0:
            return sorted(results, key=lambda result: -result["confidence"])

    return [detector.result]

"""Stage 0: Binary content detection."""

from __future__ import annotations

from chardet._utils import DEFAULT_MAX_BYTES

# Threshold: if more than this fraction of bytes are binary indicators, it's binary
_BINARY_THRESHOLD = 0.01

# Translation table that maps binary-indicator control bytes (0x00-0x08,
# 0x0E-0x1F — excludes \t \n \v \f \r) to None (deleting them) and keeps
# everything else.  len(data) - len(translated) gives the count in one
# C-level pass.
_BINARY_DELETE = bytes(range(0x09)) + bytes(range(0x0E, 0x20))

# Same table minus the EBCDIC whitespace controls: 0x05 (EBCDIC HT) and
# 0x15 (EBCDIC NL).  EBCDIC text uses these as tab and newline, so they are
# only binary evidence when the rest of the data does not look like EBCDIC.
_BINARY_DELETE_NON_EBCDIC = bytes(b for b in _BINARY_DELETE if b not in (0x05, 0x15))

# Minimum fraction of high bytes (>= 0x80) for data to plausibly be EBCDIC
# text.  EBCDIC encodes all lowercase letters above 0x80, so genuine EBCDIC
# text is dominated by high bytes.
_EBCDIC_MIN_HIGH_FRACTION = 0.25

# High-byte deletion table for the EBCDIC plausibility check.
_HIGH_BYTES_DELETE = bytes(range(0x80, 0x100))


def is_binary(data: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> bool:
    """Return ``True`` if *data* appears to be binary (not text) content.

    :param data: The raw byte data to examine.
    :param max_bytes: Maximum number of bytes to scan.
    :returns: ``True`` if the data is classified as binary.
    """
    data = data[:max_bytes]
    if not data:
        return False

    clean = data.translate(None, _BINARY_DELETE)
    binary_count = len(data) - len(clean)
    if binary_count / len(data) <= _BINARY_THRESHOLD:
        return False

    # Above the threshold — but EBCDIC text uses 0x05 (HT) and 0x15 (NL) as
    # whitespace, which are binary indicators in ASCII-compatible data.  If
    # the excess comes entirely from those two bytes and the data is
    # high-byte-dominated (EBCDIC letters live above 0x80), treat it as text.
    hard_clean = data.translate(None, _BINARY_DELETE_NON_EBCDIC)
    hard_count = len(data) - len(hard_clean)
    if hard_count / len(data) > _BINARY_THRESHOLD:
        return True
    high_count = len(data) - len(data.translate(None, _HIGH_BYTES_DELETE))
    return high_count / len(data) < _EBCDIC_MIN_HIGH_FRACTION

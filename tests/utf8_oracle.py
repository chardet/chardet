# tests/utf8_oracle.py
"""The pre-ADR-0006 hand-rolled UTF-8 validator, kept as a differential oracle.

This is a verbatim copy of ``chardet.pipeline.utf8.detect_utf8`` as it stood
before the decode-based rewrite.  The rewrite claims *exact* equivalence
(verdicts and confidences), and ``test_utf8_equivalence.py`` holds it to that
against this reference.  Do not "fix" or modernize this module; its value is
that it does not change.
"""

from __future__ import annotations

_BASE_CONFIDENCE = 0.80
_MAX_CONFIDENCE = 0.99
_MB_RATIO_SCALE = 6


def oracle_detect_utf8(data: bytes) -> tuple[str, float] | None:
    """Old per-byte validator; returns (encoding, confidence) or None."""
    if not data:
        return None

    i = 0
    length = len(data)
    multibyte_sequences = 0
    multibyte_bytes = 0

    while i < length:
        byte = data[i]

        if byte < 0x80:
            i += 1
            continue

        # Determine expected sequence length from leading byte.
        # 0xC0-0xC1 are overlong 2-byte encodings of ASCII, so we start at 0xC2.
        if 0xC2 <= byte <= 0xDF:
            seq_len = 2
        elif 0xE0 <= byte <= 0xEF:
            seq_len = 3
        elif 0xF0 <= byte <= 0xF4:
            seq_len = 4
        else:
            # Invalid start byte (0x80-0xC1, 0xF5-0xFF)
            return None

        # Truncated final sequence (e.g. from max_bytes slicing) — treat as
        # valid since the bytes seen so far are structurally correct.
        if i + seq_len > length:
            break

        # Validate continuation bytes (must be 0x80-0xBF)
        for j in range(1, seq_len):
            if not (0x80 <= data[i + j] <= 0xBF):
                return None

        # Reject overlong encodings and surrogates
        if seq_len == 3:
            # 0xE0: second byte must be >= 0xA0 (prevents overlong 3-byte)
            if byte == 0xE0 and data[i + 1] < 0xA0:
                return None
            # 0xED: second byte must be <= 0x9F (prevents UTF-16 surrogates)
            if byte == 0xED and data[i + 1] > 0x9F:
                return None
        elif seq_len == 4:
            # 0xF0: second byte must be >= 0x90 (prevents overlong 4-byte)
            if byte == 0xF0 and data[i + 1] < 0x90:
                return None
            # 0xF4: second byte must be <= 0x8F (prevents codepoints above U+10FFFF)
            if byte == 0xF4 and data[i + 1] > 0x8F:
                return None

        multibyte_sequences += 1
        multibyte_bytes += seq_len
        i += seq_len

    # Pure ASCII — let the ASCII detector handle it
    if multibyte_sequences == 0:
        return None

    mb_ratio = multibyte_bytes / length
    confidence_range = _MAX_CONFIDENCE - _BASE_CONFIDENCE
    confidence = min(
        _MAX_CONFIDENCE,
        _BASE_CONFIDENCE + confidence_range * min(mb_ratio * _MB_RATIO_SCALE, 1.0),
    )
    return ("utf-8", confidence)

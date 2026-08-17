"""Stage 1d: UTF-8 structural validation.

Validation is decode-based: CPython's strict UTF-8 decoder enforces exactly
the rules the old hand-rolled loop checked (overlong encodings, surrogates,
codepoints above U+10FFFF) at C speed on every build flavor, where a per-byte
loop runs an order of magnitude slower even compiled.  See ADR-0006.

The input is fed to an incremental decoder in chunks so a large input never
allocates a matching ``str``; decoded output is discarded.  ``final=False``
reproduces the truncated-tail tolerance (an incomplete multi-byte sequence at
the very end is fine, the input is usually a prefix of a larger whole), the
same trick :func:`chardet._utils.decodes_without_error` uses.

Note: ``from __future__ import annotations`` is intentionally omitted because
this module is compiled with mypyc, which does not support PEP 563 string
annotations.
"""

import codecs

from chardet.pipeline import DetectionResult

# Confidence curve parameters for UTF-8 detection.
# Even a small fraction of valid multi-byte sequences is strong evidence.
_BASE_CONFIDENCE = 0.80
_MAX_CONFIDENCE = 0.99
# Scale factor for the multi-byte byte ratio: mb_ratio * 6 saturates the
# confidence ramp at ~17% multi-byte content.
_MB_RATIO_SCALE = 6

# Chunk size for incremental decoding: large enough that per-chunk overhead
# vanishes, small enough that the transient decoded ``str`` stays negligible.
_CHUNK_SIZE = 1 << 20

# Deleting the ASCII range leaves exactly the high bytes, so
# ``len(chunk.translate(None, _ASCII_DELETE))`` counts them at C speed.
_ASCII_DELETE = bytes(range(0x80))

_utf8_decoder = codecs.getincrementaldecoder("utf-8")


def _expected_seq_len(byte: int) -> int:
    """Sequence length a UTF-8 lead byte declares, or 0 for a non-lead.

    0xC0-0xC1 are overlong 2-byte encodings of ASCII, so leads start at 0xC2.
    """
    if 0xC2 <= byte <= 0xDF:
        return 2
    if 0xE0 <= byte <= 0xEF:
        return 3
    if 0xF0 <= byte <= 0xF4:
        return 4
    return 0


def detect_utf8(data: bytes) -> DetectionResult | None:
    """Validate UTF-8 byte structure.

    Returns a result only if multi-byte sequences are found (pure ASCII
    is handled by the ASCII stage).

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` for UTF-8, or ``None``.
    """
    if not data:
        return None
    # Pure ASCII — let the ASCII detector handle it.  ``isascii`` is a single
    # C scan and skips the decode entirely for the common all-ASCII case.
    if data.isascii():
        return None

    length = len(data)
    decoder = _utf8_decoder()
    multibyte_bytes = 0
    pending_len = 0
    pos = 0
    # Start of the incomplete sequence at the very end (== length when the
    # data ends on a sequence boundary).  Bytes from here on are tolerated,
    # not validated, and excluded from the multi-byte counts — matching the
    # old validator, which stopped at a truncated final sequence without
    # examining it.
    tail_start = length
    counted_end = 0
    while pos < length:
        chunk = data[pos : pos + _CHUNK_SIZE]
        chunk_end = pos + len(chunk)
        counted_end = chunk_end
        if pending_len == 0 and chunk.isascii():
            # No pending sequence and no high bytes: trivially valid,
            # nothing to count.
            pos = chunk_end
            continue
        multibyte_bytes += len(chunk.translate(None, _ASCII_DELETE))
        try:
            decoder.decode(chunk, final=False)
        except UnicodeDecodeError as exc:
            # ``exc.object`` is the decoder's pending bytes plus this chunk,
            # and ``exc.start`` sits on the offending sequence's first byte.
            err_start = pos - pending_len + exc.start
            seq_len = _expected_seq_len(data[err_start])
            if seq_len == 0 or err_start + seq_len <= length:
                # Invalid start byte, or a complete-but-invalid sequence.
                return None
            # A truncated final sequence (its declared length overruns the
            # data).  The old validator never examined these bytes, so a
            # garbage continuation inside the overrun is tolerated too.
            tail_start = err_start
            break
        pending_len = len(decoder.getstate()[0])
        pos = chunk_end
    else:
        # Clean finish: the decoder's buffered bytes are the incomplete
        # final sequence, if any.
        tail_start = length - pending_len

    # The counts above include the tolerated tail (and, on the error path,
    # nothing past the erroring chunk — the tolerance condition pins the
    # error to the last 3 bytes, so ``counted_end`` covers the tail).  Trim
    # the tail's contribution: at most 3 bytes.
    if tail_start < counted_end:
        tail = data[tail_start:counted_end]
        multibyte_bytes -= len(tail.translate(None, _ASCII_DELETE))

    # In a validly-decoded prefix every high byte belongs to a complete
    # multi-byte sequence, so "no complete sequences" is exactly "no high
    # bytes outside the tail".  Pure ASCII plus a truncated tail — let the
    # later stages handle it.
    if multibyte_bytes == 0:
        return None

    # Confidence scales with the proportion of multi-byte bytes in the data.
    # Even a small amount of valid multi-byte UTF-8 is strong evidence.
    mb_ratio = multibyte_bytes / length
    confidence_range = _MAX_CONFIDENCE - _BASE_CONFIDENCE
    confidence = min(
        _MAX_CONFIDENCE,
        _BASE_CONFIDENCE + confidence_range * min(mb_ratio * _MB_RATIO_SCALE, 1.0),
    )
    return DetectionResult(encoding="utf-8", confidence=confidence, language=None)

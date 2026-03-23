"""Magic number detection for binary file types."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# (offset, prefix_bytes, mime_type) — longest prefix first within each offset
# to avoid shorter prefixes shadowing longer ones.
_MAGIC_NUMBERS: tuple[tuple[int, bytes, str], ...] = (
    # Images
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"RIFF", ""),  # placeholder — resolved by RIFF sub-check below
    (0, b"MM\x00\x2a", "image/tiff"),
    (0, b"II\x2a\x00", "image/tiff"),
    (0, b"BM", "image/bmp"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x00\x00\x01\x00", "image/x-icon"),
    # Audio/Video
    (0, b"ID3", "audio/mpeg"),
    (0, b"OggS", "audio/ogg"),
    (0, b"fLaC", "audio/flac"),
    (0, b"\x1a\x45\xdf\xa3", "video/webm"),
    # Archives
    (0, b"PK\x03\x04", "application/zip"),
    (0, b"\x1f\x8b", "application/gzip"),
    (0, b"BZh", "application/x-bzip2"),
    (0, b"\xfd7zXZ\x00", "application/x-xz"),
    (0, b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (0, b"Rar!\x1a\x07\x01\x00", "application/vnd.rar"),
    (0, b"Rar!\x1a\x07\x00", "application/vnd.rar"),
    (0, b"\x28\xb5\x2f\xfd", "application/zstd"),
    # Documents
    (0, b"%PDF-", "application/pdf"),
    (0, b"\x00asm", "application/wasm"),
    (0, b"SQLite format 3\x00", "application/x-sqlite3"),
    # Executables
    (0, b"\x7fELF", "application/x-elf"),
    (0, b"\xfe\xed\xfa\xce", "application/x-mach-binary"),
    (0, b"\xfe\xed\xfa\xcf", "application/x-mach-binary"),
    (0, b"\xce\xfa\xed\xfe", "application/x-mach-binary"),
    (0, b"\xcf\xfa\xed\xfe", "application/x-mach-binary"),
    (0, b"MZ", "application/vnd.microsoft.portable-executable"),
    # Fonts
    (0, b"wOFF", "font/woff"),
    (0, b"wOF2", "font/woff2"),
)

# TAR archives have "ustar" at offset 257
_TAR_OFFSET = 257
_TAR_SIGNATURES: tuple[bytes, ...] = (b"ustar\x00", b"ustar ")

# RIFF container subtypes — determined by bytes 8-11
_RIFF_SUBTYPES: dict[bytes, str] = {
    b"WEBP": "image/webp",
    b"WAVE": "audio/wav",
    b"AVI ": "video/x-msvideo",
}

# MP4/MOV ftyp box — "ftyp" at offset 4
_FTYP_MARKER = b"ftyp"
_FTYP_OFFSET = 4
# Major brands that indicate audio rather than video
_AUDIO_FTYP_BRANDS: frozenset[bytes] = frozenset({b"M4A ", b"M4B ", b"F4A "})


def _make_result(mime: str) -> DetectionResult:
    return DetectionResult(encoding=None, confidence=1.0, language=None, mime_type=mime)


def detect_magic(data: bytes) -> DetectionResult | None:
    """Check *data* for known binary file magic numbers.

    :param data: The raw byte data to examine.
    :returns: A :class:`DetectionResult` with ``encoding=None`` and the
        identified MIME type, or ``None`` if no magic number matches.
    """
    if not data:
        return None

    # Check ftyp box (MP4/MOV/M4A/AVIF) — "ftyp" at offset 4
    if len(data) >= 12 and data[_FTYP_OFFSET : _FTYP_OFFSET + 4] == _FTYP_MARKER:
        brand = data[8:12]
        if brand == b"avif":
            return _make_result("image/avif")
        if brand in _AUDIO_FTYP_BRANDS:
            return _make_result("audio/mp4")
        return _make_result("video/mp4")

    # Fixed-offset magic numbers
    for offset, prefix, mime in _MAGIC_NUMBERS:
        end = offset + len(prefix)
        if len(data) >= end and data[offset:end] == prefix:
            # RIFF container — need to check subtype at bytes 8-11
            if prefix == b"RIFF":
                if len(data) >= 12:
                    subtype = _RIFF_SUBTYPES.get(data[8:12])
                    if subtype is not None:
                        return _make_result(subtype)
                continue  # Unknown RIFF subtype — skip
            return _make_result(mime)

    # TAR archive — "ustar" at offset 257
    if len(data) >= _TAR_OFFSET + 6:
        tar_sig = data[_TAR_OFFSET : _TAR_OFFSET + 6]
        if tar_sig in _TAR_SIGNATURES:
            return _make_result("application/x-tar")

    return None

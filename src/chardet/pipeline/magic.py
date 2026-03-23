"""Magic number detection for binary file types."""

from __future__ import annotations

from chardet.pipeline import DetectionResult

# (prefix_bytes, mime_type) — longest prefix first to avoid shorter prefixes
# shadowing longer ones. All entries match at offset 0.
_MAGIC_NUMBERS: tuple[tuple[bytes, str], ...] = (
    # Images
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"MM\x00\x2a", "image/tiff"),
    (b"II\x2a\x00", "image/tiff"),
    (b"BM", "image/bmp"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
    # Audio/Video
    (b"ID3", "audio/mpeg"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"\x1a\x45\xdf\xa3", "video/webm"),
    # Archives
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b", "application/gzip"),
    (b"BZh", "application/x-bzip2"),
    (b"\xfd7zXZ\x00", "application/x-xz"),
    (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (b"Rar!\x1a\x07\x01\x00", "application/vnd.rar"),
    (b"Rar!\x1a\x07\x00", "application/vnd.rar"),
    (b"\x28\xb5\x2f\xfd", "application/zstd"),
    # Documents
    (b"%PDF-", "application/pdf"),
    (b"\x00asm", "application/wasm"),
    (b"SQLite format 3\x00", "application/x-sqlite3"),
    # Executables
    (b"\x7fELF", "application/x-elf"),
    (b"\xfe\xed\xfa\xce", "application/x-mach-binary"),
    (b"\xfe\xed\xfa\xcf", "application/x-mach-binary"),
    (b"\xce\xfa\xed\xfe", "application/x-mach-binary"),
    (b"\xcf\xfa\xed\xfe", "application/x-mach-binary"),
    (b"MZ", "application/vnd.microsoft.portable-executable"),
    # Fonts
    (b"wOFF", "font/woff"),
    (b"wOF2", "font/woff2"),
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

    # RIFF container — check subtype at bytes 8-11
    if data[:4] == b"RIFF" and len(data) >= 12:
        subtype = _RIFF_SUBTYPES.get(data[8:12])
        if subtype is not None:
            return _make_result(subtype)

    # Fixed-offset magic numbers (all at offset 0)
    for prefix, mime in _MAGIC_NUMBERS:
        if data.startswith(prefix):
            return _make_result(mime)

    # TAR archive — "ustar" at offset 257
    if len(data) >= _TAR_OFFSET + 6:
        tar_sig = data[_TAR_OFFSET : _TAR_OFFSET + 6]
        if tar_sig in _TAR_SIGNATURES:
            return _make_result("application/x-tar")

    return None

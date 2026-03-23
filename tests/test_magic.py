from __future__ import annotations

import pytest

from chardet.pipeline.magic import detect_magic


@pytest.mark.parametrize(
    ("data", "expected_mime"),
    [
        # Images
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 8, "image/jpeg"),
        (b"\xff\xd8\xff\xe1" + b"\x00" * 8, "image/jpeg"),
        (b"GIF87a" + b"\x00" * 8, "image/gif"),
        (b"GIF89a" + b"\x00" * 8, "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBP", "image/webp"),
        (b"BM" + b"\x00" * 12, "image/bmp"),
        (b"MM\x00\x2a" + b"\x00" * 8, "image/tiff"),
        (b"II\x2a\x00" + b"\x00" * 8, "image/tiff"),
        (b"\x00\x00\x01\x00" + b"\x00" * 8, "image/x-icon"),
        (b"\x00\x00\x00\x1cftyp" + b"avif" + b"\x00" * 4, "image/avif"),
        # Audio/Video
        (b"ID3" + b"\x00" * 10, "audio/mpeg"),
        (b"\x00\x00\x00\x1cftypMSNV", "video/mp4"),
        (b"\x00\x00\x00\x18ftypisom", "video/mp4"),
        (b"\x00\x00\x00\x18ftypmp42", "video/mp4"),
        (b"\x00\x00\x00\x20ftypM4A ", "audio/mp4"),
        (b"OggS" + b"\x00" * 10, "audio/ogg"),
        (b"fLaC" + b"\x00" * 10, "audio/flac"),
        (b"RIFF\x00\x00\x00\x00WAVE", "audio/wav"),
        (b"RIFF\x00\x00\x00\x00AVI ", "video/x-msvideo"),
        (b"\x1a\x45\xdf\xa3" + b"\x00" * 8, "video/webm"),
        # Archives
        (b"PK\x03\x04" + b"\x00" * 8, "application/zip"),
        (b"\x1f\x8b" + b"\x00" * 10, "application/gzip"),
        (b"BZh" + b"\x00" * 10, "application/x-bzip2"),
        (b"\xfd7zXZ\x00" + b"\x00" * 8, "application/x-xz"),
        (b"7z\xbc\xaf\x27\x1c" + b"\x00" * 8, "application/x-7z-compressed"),
        (b"Rar!\x1a\x07\x00" + b"\x00" * 8, "application/vnd.rar"),
        (b"Rar!\x1a\x07\x01\x00" + b"\x00" * 8, "application/vnd.rar"),
        (b"\x28\xb5\x2f\xfd" + b"\x00" * 8, "application/zstd"),
        # TAR at offset 257
        (b"\x00" * 257 + b"ustar\x00" + b"\x00" * 8, "application/x-tar"),
        (b"\x00" * 257 + b"ustar " + b"\x00" * 8, "application/x-tar"),
        # Documents
        (b"%PDF-" + b"\x00" * 8, "application/pdf"),
        (b"\x00asm" + b"\x00" * 8, "application/wasm"),
        (b"SQLite format 3\x00" + b"\x00" * 8, "application/x-sqlite3"),
        # Executables
        (b"\x7fELF" + b"\x00" * 8, "application/x-elf"),
        (b"\xfe\xed\xfa\xce" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xfe\xed\xfa\xcf" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xce\xfa\xed\xfe" + b"\x00" * 8, "application/x-mach-binary"),
        (b"\xcf\xfa\xed\xfe" + b"\x00" * 8, "application/x-mach-binary"),
        (b"MZ" + b"\x00" * 12, "application/vnd.microsoft.portable-executable"),
        # Fonts
        (b"wOFF" + b"\x00" * 8, "font/woff"),
        (b"wOF2" + b"\x00" * 8, "font/woff2"),
    ],
    ids=lambda p: p if isinstance(p, str) else None,
)
def test_detect_magic_known_formats(data: bytes, expected_mime: str) -> None:
    result = detect_magic(data)
    assert result is not None
    assert result.encoding is None
    assert result.confidence == 1.0
    assert result.language is None
    assert result.mime_type == expected_mime


def test_detect_magic_no_match() -> None:
    result = detect_magic(b"Hello, world! This is plain text.")
    assert result is None


def test_detect_magic_empty() -> None:
    result = detect_magic(b"")
    assert result is None


def test_detect_magic_truncated_png() -> None:
    """Partial PNG signature should not match."""
    result = detect_magic(b"\x89PN")
    assert result is None


def test_detect_magic_tar_too_short() -> None:
    """Data shorter than offset 257 + signature should not match TAR."""
    result = detect_magic(b"\x00" * 200 + b"ustar\x00")
    assert result is None


def _make_zip_local_entry(filename: bytes, content: bytes = b"") -> bytes:
    """Build a minimal ZIP local file header + content (no compression)."""
    import struct

    return (
        struct.pack(
            "<4sHHHHHIIIHH",
            b"PK\x03\x04",  # signature
            20,  # version needed
            0,  # flags
            0,  # compression (store)
            0,  # mod time
            0,  # mod date
            0,  # crc32
            len(content),  # compressed size
            len(content),  # uncompressed size
            len(filename),  # filename length
            0,  # extra field length
        )
        + filename
        + content
    )


class TestZipSubtypeDetection:
    """Test ZIP-based format sub-detection."""

    # --- Office Open XML ---

    def test_xlsx_detected(self) -> None:
        data = _make_zip_local_entry(b"[Content_Types].xml") + _make_zip_local_entry(
            b"xl/workbook.xml"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_docx_detected(self) -> None:
        data = _make_zip_local_entry(b"[Content_Types].xml") + _make_zip_local_entry(
            b"word/document.xml"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_pptx_detected(self) -> None:
        data = _make_zip_local_entry(b"[Content_Types].xml") + _make_zip_local_entry(
            b"ppt/presentation.xml"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    def test_ooxml_with_rels_first(self) -> None:
        """OOXML where _rels/.rels comes before xl/ — still detected."""
        data = (
            _make_zip_local_entry(b"_rels/.rels")
            + _make_zip_local_entry(b"[Content_Types].xml")
            + _make_zip_local_entry(b"xl/workbook.xml")
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- Java JAR ---

    def test_jar_detected(self) -> None:
        data = _make_zip_local_entry(
            b"META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/java-archive"

    # --- Android APK ---

    def test_apk_detected(self) -> None:
        data = _make_zip_local_entry(b"AndroidManifest.xml", b"\x00" * 20)
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/vnd.android.package-archive"

    # --- EPUB ---

    def test_epub_detected(self) -> None:
        data = _make_zip_local_entry(
            b"mimetype", b"application/epub+zip"
        ) + _make_zip_local_entry(b"META-INF/container.xml")
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/epub+zip"

    def test_epub_via_container_xml(self) -> None:
        """EPUB detected by META-INF/container.xml even without mimetype entry."""
        data = _make_zip_local_entry(b"META-INF/container.xml")
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/epub+zip"

    # --- Python wheel ---

    def test_wheel_detected(self) -> None:
        data = _make_zip_local_entry(
            b"chardet-7.0.0.dist-info/WHEEL", b"Wheel-Version: 1.0\r\n"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/x-wheel+zip"

    def test_wheel_detected_via_metadata(self) -> None:
        data = _make_zip_local_entry(
            b"chardet-7.0.0.dist-info/METADATA", b"Name: chardet\r\n"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/x-wheel+zip"

    # --- OpenDocument ---

    def test_odt_detected(self) -> None:
        data = _make_zip_local_entry(
            b"mimetype", b"application/vnd.oasis.opendocument.text"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/vnd.oasis.opendocument.text"

    def test_ods_detected(self) -> None:
        data = _make_zip_local_entry(
            b"mimetype", b"application/vnd.oasis.opendocument.spreadsheet"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/vnd.oasis.opendocument.spreadsheet"

    def test_odp_detected(self) -> None:
        data = _make_zip_local_entry(
            b"mimetype", b"application/vnd.oasis.opendocument.presentation"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/vnd.oasis.opendocument.presentation"

    def test_odg_detected(self) -> None:
        data = _make_zip_local_entry(
            b"mimetype", b"application/vnd.oasis.opendocument.graphics"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/vnd.oasis.opendocument.graphics"

    # --- Plain ZIP fallbacks ---

    def test_plain_zip(self) -> None:
        data = _make_zip_local_entry(b"readme.txt", b"hello")
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/zip"

    def test_zip_no_matching_entries(self) -> None:
        """ZIP with only non-matching entries is plain ZIP."""
        data = _make_zip_local_entry(b"readme.txt", b"hello") + _make_zip_local_entry(
            b"data.csv", b"a,b,c"
        )
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/zip"

    def test_truncated_zip_is_still_zip(self) -> None:
        """ZIP header with too little data is plain ZIP."""
        data = b"PK\x03\x04" + b"\x00" * 8
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/zip"

    def test_zip_entry_name_truncated(self) -> None:
        """ZIP entry with name_len extending past end of data is plain ZIP."""
        import struct

        # Build a header claiming a 100-byte filename, but only provide 5 bytes
        data = (
            struct.pack(
                "<4sHHHHHIIIHH",
                b"PK\x03\x04",
                20,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                100,  # name_len = 100
                0,
            )
            + b"xl/wo"
        )  # only 5 bytes of the "filename"
        result = detect_magic(data)
        assert result is not None
        assert result.mime_type == "application/zip"

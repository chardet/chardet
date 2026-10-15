#!/usr/bin/env python
"""Generate the supported MIME types RST table.

Extracts MIME types by calling detect_magic() with known signatures
rather than importing private constants from the mypyc-compiled module.
"""

from __future__ import annotations

from chardet.pipeline.magic import detect_magic

# (test_data, expected_mime, description, category)
# Each entry is minimal data that triggers the corresponding detection path.
_KNOWN_FORMATS: list[tuple[bytes, str, str]] = [
    # ftyp-based
    (b"\x00\x00\x00\x1cftyp" + b"avif" + b"\x00" * 16, "ftyp brand (avif)", "Images"),
    (b"\x00\x00\x00\x1cftyp" + b"heic" + b"\x00" * 16, "ftyp brand (heic)", "Images"),
    (b"\x00\x00\x00\x1cftyp" + b"mif1" + b"\x00" * 16, "ftyp brand (mif1)", "Images"),
    (b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 20, "ftyp brand (M4A)", "Audio"),
    (b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 8, "ftyp brand (qt)", "Video"),
    (b"\x00\x00\x00\x18ftypisom" + b"\x00" * 12, "ftyp brand (isom)", "Video"),
    # RIFF
    (b"RIFF\x00\x00\x00\x00WEBP", "RIFF subtype (WEBP)", "Images"),
    (b"RIFF\x00\x00\x00\x00WAVE", "RIFF subtype (WAVE)", "Audio"),
    (b"RIFF\x00\x00\x00\x00AVI ", "RIFF subtype (AVI)", "Video"),
    # FORM
    (b"FORM\x00\x00\x00\x00AIFF", "FORM subtype (AIFF)", "Audio"),
    # Magic numbers - Images
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "Magic (89 50 4e 47)", "Images"),
    (b"\xff\xd8\xff" + b"\x00" * 8, "Magic (ff d8 ff)", "Images"),
    (b"GIF89a" + b"\x00" * 8, "Magic (GIF89a)", "Images"),
    (b"BM" + b"\x00" * 12, "Magic (42 4d)", "Images"),
    (b"MM\x00\x2a" + b"\x00" * 8, "Magic (4d 4d 00 2a)", "Images"),
    (b"II\x2a\x00" + b"\x00" * 8, "Magic (49 49 2a 00)", "Images"),
    (b"8BPS" + b"\x00" * 8, "Magic (38 42 50 53)", "Images"),
    (b"qoif" + b"\x00" * 8, "Magic (71 6f 69 66)", "Images"),
    (
        b"\x00\x00\x00\x0c\x4a\x58\x4c\x20\x0d\x0a\x87\x0a" + b"\x00" * 8,
        "Magic (00 00 00 0c 4a 58 4c 20)",
        "Images",
    ),
    (b"\xff\x0a" + b"\x00" * 8, "Magic (ff 0a)", "Images"),
    (b"\x00\x00\x01\x00" + b"\x00" * 8, "Magic (00 00 01 00)", "Images"),
    # Magic numbers - Audio/Video
    (b"ID3" + b"\x00" * 10, "Magic (49 44 33)", "Audio"),
    (b"MThd" + b"\x00" * 10, "Magic (4d 54 68 64)", "Audio"),
    (b"OggS" + b"\x00" * 10, "Magic (4f 67 67 53)", "Audio"),
    (b"fLaC" + b"\x00" * 10, "Magic (66 4c 61 43)", "Audio"),
    (b"\x1a\x45\xdf\xa3" + b"\x00" * 8, "Magic (1a 45 df a3)", "Video"),
    # Magic numbers - Archives
    (b"PK\x03\x04" + b"\x00" * 26, "Magic (50 4b 03 04)", "Archives & Containers"),
    (b"\x1f\x8b" + b"\x00" * 10, "Magic (1f 8b)", "Archives & Containers"),
    (b"BZh" + b"\x00" * 10, "Magic (42 5a 68)", "Archives & Containers"),
    (
        b"\xfd7zXZ\x00" + b"\x00" * 8,
        "Magic (fd 37 7a 58 5a 00)",
        "Archives & Containers",
    ),
    (
        b"7z\xbc\xaf\x27\x1c" + b"\x00" * 8,
        "Magic (37 7a bc af 27 1c)",
        "Archives & Containers",
    ),
    (b"Rar!\x1a\x07\x00" + b"\x00" * 8, "Magic (52 61 72 21)", "Archives & Containers"),
    (b"\x28\xb5\x2f\xfd" + b"\x00" * 8, "Magic (28 b5 2f fd)", "Archives & Containers"),
    (
        b"\x00" * 257 + b"ustar\x00" + b"\x00" * 8,
        "ustar at offset 257",
        "Archives & Containers",
    ),
    # Magic numbers - Documents & Data
    (b"%PDF-" + b"\x00" * 8, "Magic (25 50 44 46)", "Documents & Data"),
    (
        b"SQLite format 3\x00" + b"\x00" * 8,
        "Magic (53 51 4c 69 74 65)",
        "Documents & Data",
    ),
    (b"ARROW1" + b"\x00" * 8, "Magic (41 52 52 4f 57 31)", "Documents & Data"),
    (b"PAR1" + b"\x00" * 8, "Magic (50 41 52 31)", "Documents & Data"),
    (b"\x00asm" + b"\x00" * 8, "Magic (00 61 73 6d)", "Documents & Data"),
    # Magic numbers - Executables
    (b"dex\n" + b"\x00" * 8, "Magic (64 65 78 0a)", "Executables & Bytecode"),
    (b"\x7fELF" + b"\x00" * 8, "Magic (7f 45 4c 46)", "Executables & Bytecode"),
    (
        b"\xfe\xed\xfa\xce" + b"\x00" * 8,
        "Magic (fe ed fa ce/cf)",
        "Executables & Bytecode",
    ),
    (
        b"\xca\xfe\xba\xbe\x00\x00\x00\x02" + b"\x00" * 8,
        "Magic (ca fe ba be, nfat_arch <= 20)",
        "Executables & Bytecode",
    ),
    (
        b"\xca\xfe\xba\xbe\x00\x00\x00\x37" + b"\x00" * 8,
        "Magic (ca fe ba be, version >= 45)",
        "Executables & Bytecode",
    ),
    (b"MZ" + b"\x00" * 12, "Magic (4d 5a)", "Executables & Bytecode"),
    # Magic numbers - Fonts
    (b"wOFF" + b"\x00" * 8, "Magic (77 4f 46 46)", "Fonts"),
    (b"wOF2" + b"\x00" * 8, "Magic (77 4f 46 32)", "Fonts"),
    (b"OTTO" + b"\x00" * 8, "Magic (4f 54 54 4f)", "Fonts"),
    (b"\x00\x01\x00\x00" + b"\x00" * 8, "Magic (00 01 00 00)", "Fonts"),
]

# ZIP subtypes need real ZIP headers
_ZIP_SUBTYPES: list[tuple[str, str]] = [
    (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ZIP entry (xl/)",
    ),
    (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ZIP entry (word/)",
    ),
    (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ZIP entry (ppt/)",
    ),
    ("application/java-archive", "ZIP entry (META-INF/MANIFEST.MF)"),
    ("application/vnd.android.package-archive", "ZIP entry (AndroidManifest.xml)"),
    ("application/epub+zip", "ZIP entry (META-INF/container.xml)"),
    ("application/x-wheel+zip", "ZIP entry (\\*.dist-info/)"),
    ("application/vnd.oasis.opendocument.text", "ZIP mimetype entry"),
    ("application/vnd.oasis.opendocument.spreadsheet", "ZIP mimetype entry"),
    ("application/vnd.oasis.opendocument.presentation", "ZIP mimetype entry"),
    ("application/vnd.oasis.opendocument.graphics", "ZIP mimetype entry"),
]

# Text MIME types (set by pipeline stages, not magic.py)
_TEXT_MIMES: list[tuple[str, str]] = [
    ("text/plain", "Default for text encodings"),
    ("text/html", "Markup charset (HTML meta tags)"),
    ("text/xml", "Markup charset (XML declaration)"),
    ("text/x-python", "Markup charset (PEP 263 declaration)"),
    ("application/octet-stream", "Default for unknown binary"),
]

CATEGORY_ORDER = [
    "Images",
    "Audio",
    "Video",
    "Archives & Containers",
    "Documents & Data",
    "Executables & Bytecode",
    "Fonts",
    "Text",
]


def main() -> None:
    """Print the supported MIME types RST table to stdout."""
    entries: list[tuple[str, str, str]] = []  # (mime, method, category)
    seen: set[str] = set()

    # Verify each known format against detect_magic and collect results
    for data, method, category in _KNOWN_FORMATS:
        result = detect_magic(data)
        if result is None:
            continue
        mime = result.mime_type
        if mime and mime not in seen:
            seen.add(mime)
            entries.append((mime, method, category))

    # ZIP subtypes (can't easily test without building real ZIP headers)
    for mime, method in _ZIP_SUBTYPES:
        if mime not in seen:
            seen.add(mime)
            entries.append(
                (
                    mime,
                    method,
                    "Archives & Containers"
                    if "oasis" not in mime
                    else "Documents & Data",
                )
            )

    # Text MIME types
    for mime, method in _TEXT_MIMES:
        if mime not in seen:
            seen.add(mime)
            cat = "Text" if mime.startswith("text/") else "Documents & Data"
            entries.append((mime, method, cat))

    print("Supported MIME Types")
    print("====================")
    print()
    print(f"chardet identifies **{len(seen)} MIME types** across binary and text")
    print("content. Binary files are identified by magic number signatures;")
    print("text files get MIME types from the detection pipeline stage that")
    print("identified them, or default to ``text/plain``.")
    print()
    print(".. list-table::")
    print("   :header-rows: 1")
    print("   :widths: 40 40")
    print()
    print("   * - MIME Type")
    print("     - Detection Method")
    for mime, method, _category in sorted(entries):
        print(f"   * - ``{mime}``")
        print(f"     - {method}")
    print()


if __name__ == "__main__":
    main()

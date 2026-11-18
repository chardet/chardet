Supported MIME Types
====================

chardet identifies **62 MIME types** across binary and text
content. Binary files are identified by magic number signatures;
text files get MIME types from the detection pipeline stage that
identified them, or default to ``text/plain``.

.. list-table::
   :header-rows: 1
   :widths: 40 40

   * - MIME Type
     - Detection Method
   * - ``application/epub+zip``
     - ZIP entry (META-INF/container.xml)
   * - ``application/gzip``
     - Magic (1f 8b)
   * - ``application/java-archive``
     - ZIP entry (META-INF/MANIFEST.MF)
   * - ``application/java-vm``
     - Magic (ca fe ba be, version >= 45)
   * - ``application/octet-stream``
     - Default for unknown binary
   * - ``application/pdf``
     - Magic (25 50 44 46)
   * - ``application/vnd.android.dex``
     - Magic (64 65 78 0a)
   * - ``application/vnd.android.package-archive``
     - ZIP entry (AndroidManifest.xml)
   * - ``application/vnd.apache.arrow.file``
     - Magic (41 52 52 4f 57 31)
   * - ``application/vnd.apache.parquet``
     - Magic (50 41 52 31)
   * - ``application/vnd.microsoft.portable-executable``
     - Magic (4d 5a)
   * - ``application/vnd.oasis.opendocument.graphics``
     - ZIP mimetype entry
   * - ``application/vnd.oasis.opendocument.presentation``
     - ZIP mimetype entry
   * - ``application/vnd.oasis.opendocument.spreadsheet``
     - ZIP mimetype entry
   * - ``application/vnd.oasis.opendocument.text``
     - ZIP mimetype entry
   * - ``application/vnd.openxmlformats-officedocument.presentationml.presentation``
     - ZIP entry (ppt/)
   * - ``application/vnd.openxmlformats-officedocument.spreadsheetml.sheet``
     - ZIP entry (xl/)
   * - ``application/vnd.openxmlformats-officedocument.wordprocessingml.document``
     - ZIP entry (word/)
   * - ``application/vnd.rar``
     - Magic (52 61 72 21)
   * - ``application/wasm``
     - Magic (00 61 73 6d)
   * - ``application/x-7z-compressed``
     - Magic (37 7a bc af 27 1c)
   * - ``application/x-bzip2``
     - Magic (42 5a 68)
   * - ``application/x-elf``
     - Magic (7f 45 4c 46)
   * - ``application/x-mach-binary``
     - Magic (fe ed fa ce/cf)
   * - ``application/x-sqlite3``
     - Magic (53 51 4c 69 74 65)
   * - ``application/x-tar``
     - ustar at offset 257
   * - ``application/x-wheel+zip``
     - ZIP entry (\*.dist-info/)
   * - ``application/x-xz``
     - Magic (fd 37 7a 58 5a 00)
   * - ``application/zip``
     - Magic (50 4b 03 04)
   * - ``application/zstd``
     - Magic (28 b5 2f fd)
   * - ``audio/aiff``
     - FORM subtype (AIFF)
   * - ``audio/flac``
     - Magic (66 4c 61 43)
   * - ``audio/midi``
     - Magic (4d 54 68 64)
   * - ``audio/mp4``
     - ftyp brand (M4A)
   * - ``audio/mpeg``
     - Magic (49 44 33)
   * - ``audio/ogg``
     - Magic (4f 67 67 53)
   * - ``audio/wav``
     - RIFF subtype (WAVE)
   * - ``font/otf``
     - Magic (4f 54 54 4f)
   * - ``font/ttf``
     - Magic (00 01 00 00)
   * - ``font/woff``
     - Magic (77 4f 46 46)
   * - ``font/woff2``
     - Magic (77 4f 46 32)
   * - ``image/avif``
     - ftyp brand (avif)
   * - ``image/bmp``
     - Magic (42 4d, known DIB header size)
   * - ``image/gif``
     - Magic (GIF89a)
   * - ``image/heic``
     - ftyp brand (heic)
   * - ``image/heif``
     - ftyp brand (mif1)
   * - ``image/jpeg``
     - Magic (ff d8 ff)
   * - ``image/jxl``
     - Magic (00 00 00 0c 4a 58 4c 20)
   * - ``image/png``
     - Magic (89 50 4e 47)
   * - ``image/qoi``
     - Magic (71 6f 69 66)
   * - ``image/tiff``
     - Magic (4d 4d 00 2a)
   * - ``image/vnd.adobe.photoshop``
     - Magic (38 42 50 53)
   * - ``image/vnd.microsoft.icon``
     - Magic (00 00 01 00)
   * - ``image/webp``
     - RIFF subtype (WEBP)
   * - ``text/html``
     - Markup charset (HTML meta tags)
   * - ``text/plain``
     - Default for text encodings
   * - ``text/x-python``
     - Markup charset (PEP 263 declaration)
   * - ``text/xml``
     - Markup charset (XML declaration)
   * - ``video/mp4``
     - ftyp brand (isom)
   * - ``video/quicktime``
     - ftyp brand (qt)
   * - ``video/webm``
     - Magic (1a 45 df a3)
   * - ``video/x-msvideo``
     - RIFF subtype (AVI)

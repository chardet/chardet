# chardet

Universal character encoding detector.

[![License: 0BSD](https://img.shields.io/badge/License-0BSD-blue.svg)](LICENSE)
[![Documentation](https://readthedocs.org/projects/chardet/badge/?version=latest)](https://chardet.readthedocs.io)
[![codecov](https://codecov.io/github/chardet/chardet/branch/main/graph/badge.svg?token=m5ZQrMd3vk)](https://codecov.io/github/chardet/chardet)

chardet 7 is a ground-up, 0BSD-licensed rewrite of [chardet](https://github.com/chardet/chardet).
Same package name, same public API — drop-in replacement for chardet 5.x/6.x, just much faster and more accurate.
Python 3.10+, zero runtime dependencies, works on PyPy.

## Why chardet 7?

**98.6% accuracy** on 2,518 test files. **44x faster** than chardet 6.0.0
and **1.4x faster** than charset-normalizer. **Language detection** for
every result. **MIME type detection** for binary files. **0BSD licensed.**

|                        | chardet 7.3.0 (mypyc) | chardet 6.0.0 | [charset-normalizer] 3.4.6 |
| ---------------------- | :--------------------: | :-----------: | :-------------------------: |
| Accuracy (2,518 files) |       **98.6%**        |     88.2%     |            85.3%            |
| Speed                  |    **512 files/s**     |  12 files/s   |         363 files/s         |
| Language detection     |       **95.9%**        |     40.0%     |            59.2%            |
| Peak memory            |     **25.9 MiB**       |   29.5 MiB    |          101.3 MiB          |
| Streaming detection    |        **yes**         |      yes      |             no              |
| Encoding era filtering |        **yes**         |      no       |             no              |
| Encoding filters       |        **yes**         |      no       |             no              |
| MIME type detection    |        **yes**         |      no       |             no              |
| Supported encodings    |          99            |      84       |             99              |
| License                |          0BSD          |     LGPL      |            MIT              |

[charset-normalizer]: https://github.com/jawah/charset_normalizer

## Installation

```bash
pip install chardet
```

## Quick Start

```python
import chardet

chardet.detect(b"Hello, world!")
# {'encoding': 'ascii', 'confidence': 1.0, 'language': 'en', 'mime_type': 'text/plain'}

# UTF-8 with typographic punctuation
chardet.detect("It\u2019s a lovely day \u2014 let\u2019s grab coffee.".encode("utf-8"))
# {'encoding': 'utf-8', 'confidence': 0.99, 'language': 'es', 'mime_type': 'text/plain'}

# Japanese EUC-JP
chardet.detect("これは日本語のテストです。文字コードの検出を行います。".encode("euc-jp"))
# {'encoding': 'EUC-JP', 'confidence': 1.0, 'language': 'ja', 'mime_type': 'text/plain'}

# Get all candidate encodings ranked by confidence
text = "Le café est une boisson très populaire en France et dans le monde entier."
results = chardet.detect_all(text.encode("windows-1252"))
for r in results[:4]:
    print(r["encoding"], round(r["confidence"], 2))
# Windows-1252 0.44
# iso8859-15 0.44
# ISO-8859-1 0.44
# MacRoman 0.42
```

### Streaming Detection

For large files or network streams, use `UniversalDetector` to feed data incrementally:

```python
from chardet import UniversalDetector

detector = UniversalDetector()
with open("unknown.txt", "rb") as f:
    for line in f:
        detector.feed(line)
        if detector.done:
            break
result = detector.close()
print(result)
```

### Encoding Era Filtering

Restrict detection to specific encoding eras to reduce false positives:

```python
from chardet import detect_all
from chardet.enums import EncodingEra

data = "Москва является столицей Российской Федерации и крупнейшим городом страны.".encode("windows-1251")

# All encoding eras are considered by default — 4 candidates across eras
for r in detect_all(data):
    print(r["encoding"], round(r["confidence"], 2))
# Windows-1251 0.5
# MacCyrillic 0.47
# KZ1048 0.22
# ptcp154 0.22

# Restrict to modern web encodings — 1 confident result
for r in detect_all(data, encoding_era=EncodingEra.MODERN_WEB):
    print(r["encoding"], round(r["confidence"], 2))
# Windows-1251 0.5
```

### Encoding Filters

Restrict detection to specific encodings, or exclude encodings you don't want:

```python
# Only consider UTF-8 and Windows-1252
chardet.detect(data, include_encodings=["utf-8", "windows-1252"])

# Consider everything except EBCDIC
chardet.detect(data, exclude_encodings=["cp037", "cp500"])
```

## CLI

```bash
chardetect somefile.txt
# somefile.txt: utf-8 with confidence 0.99

chardetect --minimal somefile.txt
# utf-8

# Include detected language
chardetect -l somefile.txt
# somefile.txt: utf-8 en (English) with confidence 0.99

# Only consider specific encodings
chardetect -i utf-8,windows-1252 somefile.txt
# somefile.txt: utf-8 with confidence 0.99

# Pipe from stdin
cat somefile.txt | chardetect
# stdin: utf-8 with confidence 0.99
```

## What's New in chardet 7?

- **0BSD license** (previous versions were LGPL)
- **Ground-up rewrite** — 13-stage detection pipeline using BOM detection, magic number identification, structural probing, byte validity filtering, and bigram statistical models
- **44x faster** than chardet 6.0.0 with mypyc, **1.4x faster** than charset-normalizer
- **98.6% accuracy** — +10.4pp vs chardet 6.0.0, +13.3pp vs charset-normalizer
- **Language detection** — 95.9% accuracy across 49 languages, returned with every result
- **MIME type detection** — identifies 40+ binary file formats (images, audio/video, archives, documents, executables, fonts) via magic number signatures, plus `text/html`, `text/xml`, and `text/x-python` for markup
- **Encoding filters** — `include_encodings` and `exclude_encodings` parameters to restrict or exclude specific encodings from the candidate set
- **99 encodings** — full coverage including EBCDIC, Mac, DOS, and Baltic/Central European families
- **Optional mypyc compilation** — 1.31x additional speedup on CPython
- **Thread-safe** — `detect()` and `detect_all()` are safe to call concurrently; scales on free-threaded Python
- **Same API** — `detect()`, `detect_all()`, `UniversalDetector`, and the `chardetect` CLI all work as before

## Documentation

Full documentation is available at [chardet.readthedocs.io](https://chardet.readthedocs.io).

## License

[0BSD](LICENSE)

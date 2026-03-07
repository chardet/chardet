# chardet

Universal character encoding detector.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Documentation](https://readthedocs.org/projects/chardet/badge/?version=latest)](https://chardet.readthedocs.io)
[![codecov](https://codecov.io/github/chardet/chardet/branch/main/graph/badge.svg?token=m5ZQrMd3vk)](https://codecov.io/github/chardet/chardet)

chardet 7.0 is a ground-up, MIT-licensed rewrite of [chardet](https://github.com/chardet/chardet).
Same package name, same public API — drop-in replacement for chardet 5.x/6.x, just much faster and more accurate.
Python 3.10+, zero runtime dependencies, works on PyPy.

## Why chardet 7.0?

**98.2% accuracy** on 2,510 test files. **46x faster** than chardet 6.0.0
and **4.3x faster** than
charset-normalizer. **Language
detection** for every result. **MIT licensed.**

|                        | chardet 7.0.2 (mypyc) | chardet 7.0.2 (pure) | chardet 6.0.0 | [charset-normalizer] |
| ---------------------- | :--------------------: | :------------------: | :-----------: | :------------------: |
| Accuracy (2,510 files) |       **98.2%**        |      **98.2%**       |     88.2%     |        84.2%         |
| Speed                  |    **555 files/s**     |   **370 files/s**    |  12 files/s   |     130 files/s      |
| Language detection     |       **95.1%**        |      **95.1%**       |     40.0%     |        59.0%         |
| Peak memory            |     **26.2 MiB**       |    **26.3 MiB**      |   29.5 MiB    |      101.2 MiB       |
| Streaming detection    |        **yes**         |       **yes**        |      yes      |          no          |
| Encoding era filtering |        **yes**         |       **yes**        |      no       |          no          |
| Supported encodings    |          99            |         99           |      84       |          99          |
| License                |          MIT           |         MIT          |     LGPL      |         MIT          |

[charset-normalizer]: https://github.com/jawah/charset_normalizer

## Installation

```bash
pip install chardet
```

## Quick Start

```python
import chardet

# Plain ASCII is reported as its superset Windows-1252 by default,
# keeping with WHATWG guidelines for encoding detection.
chardet.detect(b"Hello, world!")
# {'encoding': 'Windows-1252', 'confidence': 1.0, 'language': 'en'}

# UTF-8 with typographic punctuation
chardet.detect("It\u2019s a lovely day \u2014 let\u2019s grab coffee.".encode("utf-8"))
# {'encoding': 'utf-8', 'confidence': 0.99, 'language': 'es'}

# Japanese EUC-JP
chardet.detect("これは日本語のテストです。文字コードの検出を行います。".encode("euc-jp"))
# {'encoding': 'euc-jis-2004', 'confidence': 1.0, 'language': 'ja'}

# Get all candidate encodings ranked by confidence
text = "Le café est une boisson très populaire en France et dans le monde entier."
results = chardet.detect_all(text.encode("windows-1252"))
for r in results:
    print(r["encoding"], r["confidence"])
# windows-1252 0.44
# iso-8859-15 0.44
# mac-roman 0.42
# cp858 0.42
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
# windows-1251 0.5
# mac-cyrillic 0.47
# kz-1048 0.22
# ptcp154 0.22

# Restrict to modern web encodings — 1 confident result
for r in detect_all(data, encoding_era=EncodingEra.MODERN_WEB):
    print(r["encoding"], round(r["confidence"], 2))
# windows-1251 0.5
```

## CLI

```bash
chardetect somefile.txt
# somefile.txt: utf-8 with confidence 0.99

chardetect --minimal somefile.txt
# utf-8

# Pipe from stdin
cat somefile.txt | chardetect
```

## What's New in 7.0

- **MIT license** (previous versions were LGPL)
- **Ground-up rewrite** — 12-stage detection pipeline using BOM detection, structural probing, byte validity filtering, and bigram statistical models
- **46x faster** than chardet 6.0.0 with mypyc (**31x** pure Python), **4.3x faster** than charset-normalizer
- **98.2% accuracy** — +10.0pp vs chardet 6.0.0, +14.0pp vs charset-normalizer
- **Language detection** — 95.1% accuracy across 49 languages, returned with every result
- **99 encodings** — full coverage including EBCDIC, Mac, DOS, and Baltic/Central European families
- **`EncodingEra` filtering** — scope detection to modern web encodings, legacy ISO/Mac/DOS, mainframe, or all
- **Optional mypyc compilation** — 1.42x additional speedup on CPython
- **Thread-safe** — `detect()` and `detect_all()` are safe to call concurrently; scales on free-threaded Python
- **Same API** — `detect()`, `detect_all()`, `UniversalDetector`, and the `chardetect` CLI all work as before

## Documentation

Full documentation is available at [chardet.readthedocs.io](https://chardet.readthedocs.io).

## License

[MIT](LICENSE)

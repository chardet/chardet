chardet documentation
=====================

**chardet** is a universal character encoding detector for Python. Pass it
bytes: get back the encoding, confidence, language, and MIME type.

.. code-block:: python

   import chardet

   result = chardet.detect("It\u2019s a lovely day \u2014 let\u2019s grab coffee.".encode("utf-8"))
   print(result)
   # {'encoding': 'utf-8', 'confidence': 0.99, 'language': 'es', 'mime_type': 'text/plain'}

chardet 7 is a ground-up, 0BSD-licensed rewrite. Same package name, same
public API, drop-in replacement for chardet 5.x/6.x. Python 3.10+, zero
runtime dependencies, works on PyPy.

- **98.6% accuracy** on 2,518 test files
- **44x faster** than chardet 6.0.0 with mypyc
- **1.4x faster** than charset-normalizer with mypyc
- **Language detection** for every result (95.9% accuracy)
- **99 encodings** across six encoding eras
- **Encoding filters** — include/exclude specific encodings
- **Thread-safe** ``detect()`` and ``detect_all()``

.. toctree::
   :maxdepth: 2
   :caption: Contents
   :hidden:

   usage
   supported-encodings
   supported-mime-types
   how-it-works
   performance
   faq
   api/index
   contributing
   changelog

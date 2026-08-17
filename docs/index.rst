chardet documentation
=====================

**chardet** is a universal character encoding detector for Python. Pass it
bytes: get back the encoding, confidence, language, and MIME type.

.. code-block:: python

   import chardet

   result = chardet.detect(
       "It\u2019s a truth universally acknowledged that text arrives "
       "without a declared encoding.".encode("utf-8")
   )
   print(result)
   # {'encoding': 'utf-8', 'confidence': 0.84, 'language': 'en', 'mime_type': 'text/plain'}

chardet 7 is a ground-up, 0BSD-licensed rewrite. Same package name, same
public API, drop-in replacement for chardet 5.x/6.x. Python 3.10+, zero
runtime dependencies, works on PyPy.

- **99.7% accuracy** on 3,138 test files
- **315x faster** than chardet 6.0.0 when compiled
- **+13.1pp more accurate** than charset-normalizer 3.5.1, and 1.2x faster
- **Language detection** for every result (91.8% accuracy)
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

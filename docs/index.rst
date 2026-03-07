chardet documentation
=====================

**chardet** is a universal character encoding detector for Python. It analyzes
byte strings and returns the detected encoding, confidence score, and language.

.. code-block:: python

   import chardet

   result = chardet.detect("It\u2019s a lovely day \u2014 let\u2019s grab coffee.".encode("utf-8"))
   print(result)
   # {'encoding': 'utf-8', 'confidence': 0.99, 'language': 'es'}

chardet 7.0 is a ground-up, MIT-licensed rewrite — same package name, same
public API, drop-in replacement for chardet 5.x/6.x. Python 3.10+, zero
runtime dependencies, works on PyPy.

- **98.2% accuracy** on 2,510 test files
- **46x faster** than chardet 6.0.0 with mypyc, **31x faster** pure Python
- **4.3x faster** than charset-normalizer with mypyc, **5.5x faster** pure Python
- **Language detection** for every result (95.1% accuracy)
- **99 encodings** across six encoding eras
- **Thread-safe** ``detect()`` and ``detect_all()``

.. toctree::
   :maxdepth: 2
   :caption: Contents
   :hidden:

   usage
   supported-encodings
   how-it-works
   performance
   faq
   api/index
   contributing
   changelog

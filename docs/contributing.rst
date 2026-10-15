Contributing
============

Development Setup
-----------------

chardet uses `uv <https://docs.astral.sh/uv/>`_ for dependency management:

.. code-block:: bash

   git clone https://github.com/chardet/chardet.git
   cd chardet
   uv sync                    # install dependencies
   prek install               # set up pre-commit hooks (ruff, ty, sphinx-lint, etc.)

Running Tests
-------------

Tests use pytest. Test data is auto-cloned from the
`chardet/test-data <https://github.com/chardet/test-data>`_ repo on
first run (cached in ``tests/data/``, gitignored).

.. code-block:: bash

   uv run python -m pytest -n auto                      # run all tests
   uv run python -m pytest -n auto tests/test_api.py    # single file
   uv run python -m pytest tests/test_api.py::test_detect_empty  # single test
   uv run python -m pytest -x -n auto                   # stop on first failure
   uv run python -m pytest -m benchmark -n auto         # benchmark tests only

Benchmark tests are deselected by default. Accuracy tests are
dynamically parametrized from the test data via ``conftest.py``. CI
requires 100% coverage, so a change that leaves a line uncovered fails
there.

Linting and Formatting
----------------------

chardet uses `Ruff <https://docs.astral.sh/ruff/>`_ with
``select = ["ALL"]`` and targeted ignores (see ``pyproject.toml``):

.. code-block:: bash

   uv run ruff check .        # lint
   uv run ruff check --fix .  # lint with auto-fix
   uv run ruff format .       # format

The pre-commit hooks run ruff, ``ty`` type checking, ``sphinx-lint`` on
the docs, and the usual whitespace and file checks. CI runs the same
set with ``uv run prek run --all-files``, which is the one lint verdict
that matches it.

Training Models
---------------

Bigram frequency models are trained from the
`CulturaX <https://huggingface.co/datasets/uonlp/CulturaX>`_,
MADLAD-400, and Wikipedia corpora, plus ANSI art packs fetched by
``scripts/fetch_artpacks.py``, with synthetic HTML wrappers added at
training time (all separate from the evaluation test suite):

.. code-block:: bash

   uv run --group training python scripts/train.py

Training data is cached in ``data/`` (gitignored). Training writes
``models.bin``, ``idf.bin``, ``rowmax.bin``, and ``langnorm.bin`` under
``src/chardet/models/`` as one digest-locked set.

Benchmarks and Diagnostics
--------------------------

.. code-block:: bash

   uv run python scripts/benchmark_time.py     # latency benchmarks
   uv run python scripts/benchmark_memory.py   # memory usage benchmarks
   uv run python scripts/diagnose_accuracy.py  # detailed accuracy diagnostics
   uv run python scripts/compare_detectors.py  # compare against other detectors

Building Documentation
----------------------

.. code-block:: bash

   uv sync --group docs                          # install Sphinx, Furo, etc.
   uv run sphinx-build docs docs/_build          # build HTML docs
   uv run sphinx-build -W docs docs/_build       # build with warnings as errors

Docs are published to `ReadTheDocs <https://chardet.readthedocs.io>`_
on tag push.

Architecture Overview
---------------------

All detection flows through ``run_pipeline()`` in
``src/chardet/pipeline/orchestrator.py``, which runs stages in order —
each stage either returns a definitive result or passes to the next:

1. **BOM** (``bom.py``) — byte order mark
2. **UTF-16/32 patterns** (``utf1632.py``) — null-byte patterns
3. **Escape sequences** (``escape.py``) — ISO-2022-JP/KR, HZ-GB-2312
4. **Magic numbers** (``magic.py``) — binary file type identification
5. **Binary detection** (``binary.py``) — null bytes / control chars
6. **Markup charset** (``markup.py``) — ``<meta charset>`` / ``<?xml encoding>`` extraction, plus superset promotion (Shift_JIS→CP932, EUC-KR→CP949) when structural evidence supports it
7. **ASCII** (``ascii.py``) — pure 7-bit check
8. **UTF-8** (``utf8.py``) — structural multi-byte validation
9. **Byte validity** (``validity.py``) — eliminate invalid encodings
10. **CJK gating** (in orchestrator) — eliminate spurious CJK candidates
11. **Structural probing** (``structural.py``) — multi-byte encoding fit
12. **Statistical scoring** (``statistical.py``) — bigram frequency models
13. **Post-processing** (``postprocess.py``) — eight chained rank corrections: Windows-superset and era-prevalence dead-heat promotion, rare-language arbitration, confusion-group resolution (delegated to ``confusion.py``), niche Latin demotion, KOI8-T promotion, classic-Mac CR promotion, and the decode-safety flip
14. **Language detection** (``language.py``) — three-tier fill of the ``language`` field on every result (single-language map → multi-language bigram → UTF-8 fallback), runs after the core pipeline

Accuracy-evaluation tables and predicates (``is_correct``,
``is_equivalent_detection``, ``SUPERSETS``, ``LANGUAGE_EQUIVALENCES``,
etc.) live in ``evaluation.py``.  Public-API encoding-name remapping
(``apply_compat_names``, ``apply_preferred_superset``) lives in
``output_names.py``.  The legacy ``equivalences.py`` module is a
deprecation shim that proxies attribute access to both, warning per
name, scheduled for removal in 8.0.

Key types:

- ``DetectionResult`` — frozen dataclass: ``encoding``, ``confidence``,
  ``language``, ``mime_type``
- ``EncodingInfo`` (``registry.py``) — frozen dataclass: ``name``,
  ``aliases``, ``era``, ``is_multibyte``, ``languages``
- ``EncodingEra`` (``enums.py``) — IntFlag for filtering candidates
- ``BigramProfile`` (``models/__init__.py``) — pre-computed bigram
  frequencies

Model format: ``src/chardet/models/models.bin`` is the v2 dense
zlib-compressed format (magic ``CMD2``): a header of model keys and L2
norms, then one 65,536-byte table per model indexed by
``(b1 << 8) | b2``, decompressed one table at a time. ``rowmax.bin``
(``CRM1``, row maxima for scoring bounds), ``langnorm.bin`` (``CLN1``,
norms for the language tiers' weighted scoring), and ``idf.bin`` are
written with it and digest-locked to it; ``confusion.bin`` holds the
confusion-group data. ``chardet.models._format`` owns both the read
and write sides.

Optional Compiled Builds
------------------------

Hot-path modules can be compiled to C extensions. Two hooks do it, and
both should be enabled. ``MYPYC`` alone compiles the modules but skips
the sweep described below; ``CUSTOM`` alone runs the Cython hook with
nothing to do and produces a pure wheel:

.. code-block:: bash

   HATCH_BUILD_HOOK_ENABLE_MYPYC=true HATCH_BUILD_HOOK_ENABLE_CUSTOM=true uv build

`mypyc <https://mypyc.readthedocs.io>`_ compiles the modules listed
below. `Cython <https://cython.org>`_ compiles ``_kernel.py`` alone ---
the bigram scoring loop --- using the build-time-only declarations in
``_kernel.pxd``. Keep that kernel small: an earlier version also held
the profile builder and the row-max bound, and moving those out of
their mypyc modules made a mypyc-only build *slower* than compiling
nothing, because mypyc stopped seeing those loops.

A build with both hooks enabled leaves nothing in the source tree. The
Cython hook's ``finalize`` deletes every in-tree extension, mypyc's
included; a mypyc-only build does not get that sweep. A
leftover ``.so`` shadows the ``.py`` beside it, is gitignored so
``git status`` stays clean, and quietly makes later edits and
"pure-Python" test runs meaningless.

Compiled modules (fifteen): ``models/__init__.py``,
``models/_format.py``, ``pipeline/structural.py``,
``pipeline/validity.py``, ``pipeline/statistical.py``,
``pipeline/utf1632.py``, ``pipeline/utf8.py``, ``pipeline/escape.py``,
``pipeline/orchestrator.py``, ``pipeline/confusion.py``,
``pipeline/magic.py``, ``pipeline/ascii.py``, ``pipeline/language.py``,
``pipeline/markup.py``, ``pipeline/postprocess.py``. Published Windows
wheels leave ``models/__init__.py`` interpreted.

These modules cannot use ``from __future__ import annotations``
(``FA100`` is ignored for them in ruff config).

Versioning
----------

Version is derived from git tags via ``hatch-vcs``. The tag is the
single source of truth — no hardcoded version strings. The generated
``src/chardet/_version.py`` is gitignored and should never be committed.

Conventions
-----------

- ``from __future__ import annotations`` in all source files (except
  mypyc-compiled modules)
- Frozen dataclasses with ``slots=True`` for data types
- Ruff with ``select = ["ALL"]`` and targeted ignores
- Training data (CulturaX, MADLAD-400, Wikipedia, art packs, and
  synthetic HTML wrappers) is never the same as evaluation data (chardet
  test suite)

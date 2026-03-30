"""PyInstaller hook support for chardet.

Provides ``get_hook_dirs()`` so PyInstaller can discover the bundled hook that
collects mypyc-compiled shared libraries (``*__mypyc.*``).
"""

from __future__ import annotations

from pathlib import Path


def get_hook_dirs() -> list[str]:
    """Return the directory containing PyInstaller hooks for chardet."""
    return [str(Path(__file__).parent)]

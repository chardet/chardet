"""Tests for the PyInstaller hook support module."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from chardet._pyinstaller import get_hook_dirs


def test_get_hook_dirs_returns_package_directory() -> None:
    """get_hook_dirs() should return the _pyinstaller package directory."""
    dirs = get_hook_dirs()
    assert len(dirs) == 1
    hook_dir = Path(dirs[0])
    assert hook_dir.is_dir()
    assert (hook_dir / "hook-chardet.py").is_file()


def test_hook_chardet_hidden_imports() -> None:
    """The hook module should expose hiddenimports and datas."""
    pytest.importorskip("PyInstaller")
    hook = importlib.import_module("chardet._pyinstaller.hook-chardet")
    assert hasattr(hook, "hiddenimports")
    assert isinstance(hook.hiddenimports, list)
    assert "chardet.pipeline.orchestrator" in hook.hiddenimports
    assert "chardet.models" in hook.hiddenimports
    assert hasattr(hook, "datas")
    assert isinstance(hook.datas, list)

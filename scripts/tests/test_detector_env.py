"""Tests for scripts/detector_env.py's safe compiled-wheel build."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from detector_env import _clean_inplace_artifacts, build_compiled_wheel


def _plant_artifacts(project_root: Path) -> list[Path]:
    """Create a fake src tree with compiled extensions beside sources."""
    pkg = project_root / "src" / "chardet"
    sub = pkg / "pipeline"
    sub.mkdir(parents=True)
    (pkg / "models.py").write_text("# source\n")
    planted = [
        pkg / "models.cpython-314-darwin.so",
        sub / "structural.pyd",
    ]
    for p in planted:
        p.write_bytes(b"\x00fake extension")
    return planted


def test_clean_removes_planted_artifacts(tmp_path: Path) -> None:
    """Every .so/.pyd under src/ is removed; sources are untouched."""
    planted = _plant_artifacts(tmp_path)
    removed = _clean_inplace_artifacts(tmp_path)
    assert sorted(removed) == sorted(planted)
    for p in planted:
        assert not p.exists()
    assert (tmp_path / "src" / "chardet" / "models.py").exists()


def test_clean_missing_src_returns_empty(tmp_path: Path) -> None:
    """A project root with no src/ directory is a no-op."""
    assert _clean_inplace_artifacts(tmp_path) == []


def test_build_enables_both_hooks_and_returns_wheel(tmp_path: Path) -> None:
    """The build env must enable BOTH hooks — mypyc-only never ships."""
    out_dir = tmp_path / "wheels"
    out_dir.mkdir()
    seen_env: dict[str, str] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        seen_env.update(kwargs["env"])  # type: ignore[call-overload]
        (out_dir / "chardet-0-py3-none-any.whl").write_bytes(b"wheel")

    with patch("detector_env.subprocess.run", side_effect=fake_run):
        wheel = build_compiled_wheel(tmp_path, out_dir)

    assert wheel.name == "chardet-0-py3-none-any.whl"
    assert seen_env["HATCH_BUILD_HOOK_ENABLE_MYPYC"] == "true"
    assert seen_env["HATCH_BUILD_HOOK_ENABLE_CUSTOM"] == "true"


def test_build_raises_when_no_wheel(tmp_path: Path) -> None:
    """A build that produces no .whl raises instead of returning garbage."""
    out_dir = tmp_path / "wheels"
    out_dir.mkdir()
    with (
        patch("detector_env.subprocess.run"),
        pytest.raises(RuntimeError, match="no .whl file"),
    ):
        build_compiled_wheel(tmp_path, out_dir)


def test_build_sweeps_even_when_build_fails(tmp_path: Path) -> None:
    """The artifact sweep runs in a finally, so a failed build cannot
    leave extensions shadowing the source tree (the 323a7b1 bug)."""
    planted = _plant_artifacts(tmp_path)
    out_dir = tmp_path / "wheels"
    out_dir.mkdir()
    boom = subprocess.CalledProcessError(1, ["uv", "build"])
    with (
        patch("detector_env.subprocess.run", side_effect=boom),
        pytest.raises(subprocess.CalledProcessError),
    ):
        build_compiled_wheel(tmp_path, out_dir)
    for p in planted:
        assert not p.exists()

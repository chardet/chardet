"""Isolated build environments for the detector measurement scripts.

Owns the one safe way to build a compiled chardet wheel from the source
tree.  Both ``compare_detectors.py`` and ``profile_detection.py`` need
one, and building it has two traps this module exists to hide: the build
hooks compile in place, leaving ``.so``/``.pyd`` files in ``src/`` that
silently shadow the ``.py`` sources afterwards, and enabling only the
mypyc hook produces a configuration that never ships (packed buffers
through the interpreter, ~30% slower than the released wheels).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _clean_inplace_artifacts(project_root: Path) -> list[Path]:
    """Delete compiled extensions the build hooks leave in ``src/``.

    hatch-mypyc compiles in place, so building a wheel leaves
    ``.so``/``.pyd`` files sitting next to the ``.py`` sources they
    were built from.  Python imports an extension in preference to the
    module beside it, so anything run from the source tree afterwards
    silently gets the compiled build: a later source edit appears to do
    nothing, a ``--pure`` measurement is not pure, and the files are
    gitignored so ``git status`` stays clean while it happens.

    The wheel already contains its own copies, so removing them here
    costs nothing.  Returns the paths removed, for logging.
    """
    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return []
    removed: list[Path] = []
    for pattern in ("*.so", "*.pyd"):
        for path in sorted(src_dir.rglob(pattern)):
            path.unlink()
            removed.append(path)
    return removed


def build_compiled_wheel(
    project_root: Path,
    out_dir: Path,
    python_version: str | None = None,
) -> Path:
    """Build a compiled chardet wheel into *out_dir* and return its path.

    Enables both build hooks — mypyc for the pipeline modules and the
    custom hook for the Cython scoring kernel — because that is the
    configuration released wheels ship.  Enabling only mypyc runs the
    packed buffers through the interpreter, which benchmarks ~30% slower
    and measures a build that does not exist in the wild.

    The in-place artifact sweep runs in a ``finally``, so even a failed
    build cannot leave extensions shadowing the source tree.

    :raises RuntimeError: If the build produced no ``.whl`` file.
    """
    build_cmd = [
        "uv",
        "build",
        "--wheel",
        "--out-dir",
        str(out_dir),
        str(project_root),
    ]
    if python_version:
        build_cmd.extend(["--python", python_version])
    print("Building compiled chardet wheel (mypyc + Cython kernel) ...")
    try:
        subprocess.run(
            build_cmd,
            check=True,
            env={
                **os.environ,
                "HATCH_BUILD_HOOK_ENABLE_MYPYC": "true",
                "HATCH_BUILD_HOOK_ENABLE_CUSTOM": "true",
            },
        )
    finally:
        stale = _clean_inplace_artifacts(project_root)
        if stale:
            print(
                f"  Removed {len(stale)} in-place build artifact(s) "
                f"from {project_root / 'src'}"
            )
    wheels = list(out_dir.glob("*.whl"))
    if not wheels:
        msg = "compiled wheel build produced no .whl file"
        raise RuntimeError(msg)
    return wheels[0]

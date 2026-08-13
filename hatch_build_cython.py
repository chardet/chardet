"""Wheel build hook that compiles ``src/chardet/_kernel.py`` with Cython.

Runs alongside the mypyc hook: mypyc compiles the 13 pipeline modules, this
compiles the one scoring-loop module whose types live in ``_kernel.pxd``.
Each is opt-in via its own ``HATCH_BUILD_HOOK_ENABLE_*`` variable; a
pure-Python wheel gets neither and ships ``_kernel.py`` as ordinary Python,
which ``models`` detects and scores through its dense in-module loop instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_SETUP = """
import sys
from setuptools import setup
from Cython.Build import cythonize

sys.argv = [sys.argv[0], "build_ext", "--inplace"]
setup(
    name="chardet-kernel",
    ext_modules=cythonize(
        [r"{source}"],
        compiler_directives={{
            "language_level": "3",
            # The .py carries PEP 484 annotations for humans, mypy and ruff;
            # _kernel.pxd is the sole authority for C types.  With this on,
            # "idx: object" would contradict the .pxd's "int[::1] idx".
            "annotation_typing": False,
            # Without this, importing the extension makes CPython re-enable
            # the GIL on free-threaded builds -- with a RuntimeWarning -- and
            # detection stops scaling with threads entirely.  The declaration
            # is honest: these functions take their arguments, touch no shared
            # mutable state, and return a value.
            "freethreading_compatible": True,
        }},
    ),
)
"""


def _compiled_build_requested() -> bool:
    """Return whether a compiled build was asked for.

    Deliberately matches hatchling's own predicate exactly --- an exact,
    case-sensitive membership test against ``{"1", "true"}``.  Accepting more
    than hatchling does (``True``, ``yes``) would let this hook run while the
    mypyc hook stayed disabled, producing a platform-tagged wheel that ships
    the kernel extension but all 13 pipeline modules as plain Python: correct
    output, correct tags, silently unoptimized.
    """
    return os.environ.get("HATCH_BUILD_HOOK_ENABLE_MYPYC", "") in {"1", "true"}


class CythonKernelHook(BuildHookInterface):
    """Compile the hot-loop kernel module with Cython."""

    PLUGIN_NAME = "cython-kernel"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Build ``_kernel`` and force-include the resulting extension."""
        if not _compiled_build_requested():
            return

        root = Path(self.root)
        source = root / "src" / "chardet" / "_kernel.py"
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "setup_kernel.py"
            script.write_text(_SETUP.format(source=source))
            subprocess.run([sys.executable, str(script)], cwd=str(root), check=True)

        suffix = sysconfig.get_config_var("EXT_SUFFIX")
        built = source.with_name(f"_kernel{suffix}")
        if not built.exists():
            msg = f"Cython did not produce {built}"
            raise RuntimeError(msg)
        build_data["infer_tag"] = True
        build_data["pure_python"] = False
        build_data.setdefault("force_include", {})[str(built)] = (
            f"chardet/_kernel{suffix}"
        )

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        """Remove every compiled extension the build left in the source tree.

        Both compilers write their output next to the sources: Cython through
        ``build_ext --inplace``, mypyc through its own hook.  Python imports an
        extension in preference to the ``.py`` beside it, so anything left
        behind silently shadows the source --- a later edit appears to do
        nothing, a pure-Python test run is not pure, and because the files are
        gitignored, ``git status`` stays clean while it happens.  During this
        project's Cython evaluation that produced four wrong results before it
        was noticed each time.

        This deliberately cleans mypyc's output as well as its own.  Scope by
        hook would leave 14 shadowing files behind and preserve the trap; the
        wheel already holds its copies by the time ``finalize`` runs.
        """
        if not _compiled_build_requested():
            # Neither hook ran, so nothing here is ours to remove --- and a
            # developer may have built extensions in place deliberately.
            return
        root = Path(self.root)
        src = root / "src"
        suffix = sysconfig.get_config_var("EXT_SUFFIX")
        for pattern in (f"**/*{suffix}", "**/*.so", "**/*.pyd", "chardet/_kernel.c"):
            for stale in src.glob(pattern):
                stale.unlink(missing_ok=True)
        shutil.rmtree(root / "build", ignore_errors=True)

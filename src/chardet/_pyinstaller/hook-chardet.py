"""PyInstaller hook for chardet.

When chardet is built with mypyc (``HATCH_BUILD_HOOK_ENABLE_MYPYC=true``), the
compiled modules depend on a shared runtime library whose name contains a hash
(e.g. ``4ef79d6367bb14396397__mypyc``).  PyInstaller cannot detect this import
automatically, so this hook collects the shared library and adds it as a hidden
import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Collect all chardet submodules so nothing is missed.
hiddenimports = [
    "chardet.models",
    "chardet.pipeline",
    "chardet.pipeline.ascii",
    "chardet.pipeline.binary",
    "chardet.pipeline.bom",
    "chardet.pipeline.confusion",
    "chardet.pipeline.escape",
    "chardet.pipeline.magic",
    "chardet.pipeline.markup",
    "chardet.pipeline.orchestrator",
    "chardet.pipeline.statistical",
    "chardet.pipeline.structural",
    "chardet.pipeline.utf1632",
    "chardet.pipeline.utf8",
    "chardet.pipeline.validity",
]


def _find_mypyc_hidden_imports() -> list[str]:
    """Discover mypyc runtime modules (``*__mypyc``) inside the chardet package."""
    spec = importlib.util.find_spec("chardet")
    if spec is None or spec.origin is None:
        return []

    pkg_dir = Path(spec.origin).parent
    imports: list[str] = []
    for p in pkg_dir.rglob("*__mypyc*"):
        if p.suffix in (".so", ".pyd") and p.is_file():
            # The module name is the stem up to the first dot
            # (e.g. "4ef79d6367bb14396397__mypyc.cpython-310-x86_64-linux-gnu"
            #  -> "4ef79d6367bb14396397__mypyc")
            module_name = p.name.split(".")[0]
            imports.append(module_name)
    return imports


hiddenimports += _find_mypyc_hidden_imports()

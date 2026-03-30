"""PyInstaller hook for chardet.

Ensures that chardet's data files (``models.bin``) and all submodules are
bundled correctly.  When chardet is built with mypyc, the compiled modules
also depend on a shared runtime library whose name contains a hash
(e.g. ``4ef79d6367bb14396397__mypyc``); this hook collects that as well.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files  # ty: ignore[unresolved-import]

# Bundle non-Python data files (e.g. models/models.bin).
datas = collect_data_files("chardet")

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
    if spec is None or spec.origin is None:  # pragma: no cover
        return []

    pkg_dir = Path(spec.origin).parent
    imports: list[str] = []
    for p in pkg_dir.rglob("*__mypyc*"):
        if p.suffix in (".so", ".pyd") and p.is_file():  # pragma: no cover
            # The module name is the stem up to the first dot
            # (e.g. "4ef79d6367bb14396397__mypyc.cpython-310-x86_64-linux-gnu"
            #  -> "4ef79d6367bb14396397__mypyc")
            module_name = p.name.split(".")[0]
            imports.append(module_name)
    return imports


hiddenimports += _find_mypyc_hidden_imports()

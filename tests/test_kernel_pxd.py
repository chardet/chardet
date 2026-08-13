# tests/test_kernel_pxd.py
"""Guard the one silent way ``_kernel.pxd`` can drift from ``_kernel.py``.

Cython resolves most disagreements between a module and its augmenting
``.pxd`` loudly: a signature that differs in arity or type is a compile
error, a wrong buffer dtype is a ``ValueError``, a non-buffer argument is a
``TypeError``, a too-narrow integer is an ``OverflowError``.  Those are all
caught by building and by running the suite against a compiled wheel.

One class is silent.  A ``@cython.locals`` entry naming a variable the
``.py`` no longer has is ignored: the build is clean, no warning is
emitted, the corpus hash is unchanged, and the loop it was meant to type
quietly goes back to being untyped.  Nothing else in the suite can see
that, which is why it gets its own test --- a dead ``vals``/``v``
declaration survived unnoticed in this kernel until a tool that reads both
files side by side went looking.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src" / "chardet"

#: ``@cython.locals(...)`` block plus the function it decorates.
_LOCALS_RE = re.compile(
    r"@cython\.locals\((?P<body>.*?)\)\s*(?:cp?def|cdef)\s[^\n]*?(?P<func>\w+)\s*\(",
    re.DOTALL,
)
_NAME_RE = re.compile(r"(\w+)\s*=")
_DECL_RE = re.compile(r"^\s*(?:cpdef|cdef)\s+.*?(\w+)\s*\(", re.MULTILINE)


def _names_bound_per_function(source: str) -> dict[str, set[str]]:
    """Map each function name to every name bound in its body, plus its args."""
    out: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        names = {a.arg for a in node.args.args}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                names.add(sub.id)
            elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                names.add(sub.target.id)
        out[node.name] = names
    return out


def _stale_declarations(py_path: Path) -> list[str]:
    """Return every name a ``.pxd`` types that its ``.py`` no longer defines."""
    pxd_path = py_path.with_suffix(".pxd")
    if not pxd_path.exists():
        return []
    bound = _names_bound_per_function(py_path.read_text(encoding="utf-8"))
    pxd = pxd_path.read_text(encoding="utf-8")
    problems: list[str] = []

    for match in _LOCALS_RE.finditer(pxd):
        func = match.group("func")
        if func not in bound:
            problems.append(f"{pxd_path.name} types locals for missing `{func}`")
            continue
        stale = sorted(set(_NAME_RE.findall(match.group("body"))) - bound[func])
        if stale:
            problems.append(
                f"{pxd_path.name}: `{func}` types {stale}, "
                f"absent from {py_path.name} -- the declaration is dead"
            )

    problems.extend(
        f"{pxd_path.name} declares `{func}`, absent from {py_path.name}"
        for func in sorted(set(_DECL_RE.findall(pxd)))
        if func not in bound
    )
    return problems


def _pxd_modules() -> list[Path]:
    return sorted(p.with_suffix(".py") for p in _SRC.rglob("*.pxd"))


def test_repository_has_pxd_modules_to_check():
    """The guard is worthless if it silently checks nothing."""
    assert _pxd_modules(), "no .pxd files found; this test would pass vacuously"


@pytest.mark.parametrize("py_path", _pxd_modules(), ids=lambda p: p.name)
def test_pxd_declares_only_names_the_module_has(py_path: Path):
    """Every name the .pxd types must still exist in the .py beside it."""
    assert py_path.exists(), f"{py_path.name} missing beside its .pxd"
    assert _stale_declarations(py_path) == []


def test_guard_detects_a_dead_local(tmp_path: Path):
    """The check fails on a .pxd typing a local the .py does not have."""
    py = tmp_path / "m.py"
    py.write_text("def f(xs):\n    total = 0\n    return total\n")
    (tmp_path / "m.pxd").write_text(
        "cimport cython\n\n"
        "@cython.locals(total=cython.int, renamed=cython.int)\n"
        "cpdef f(list xs)\n"
    )
    problems = _stale_declarations(py)
    assert len(problems) == 1
    assert "renamed" in problems[0]


def test_guard_detects_a_missing_function(tmp_path: Path):
    """The check fails on a .pxd declaring a function the .py dropped."""
    py = tmp_path / "m.py"
    py.write_text("def kept(x):\n    return x\n")
    (tmp_path / "m.pxd").write_text(
        "cimport cython\n\ncpdef kept(x)\ncpdef removed(x)\n"
    )
    assert any("removed" in p for p in _stale_declarations(py))

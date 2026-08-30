# tests/test_equivalences.py
"""Backward-compatibility shim tests for ``chardet.equivalences``.

The module's contents were split into :mod:`chardet.evaluation` and
:mod:`chardet.output_names` in 7.5.  This file verifies the shim still
resolves every name the pre-split module exposed, keeps reads *and* writes
pointed at the module that now owns each one, and deprecates per accessed
name instead of once at import time.
"""

from __future__ import annotations

import importlib
import warnings
from types import ModuleType
from unittest import mock

import pytest

import chardet
from chardet import equivalences, evaluation, output_names


def test_attribute_access_emits_deprecation_warning():
    """The warning fires on use and names the symbol and its new home."""
    with pytest.warns(
        DeprecationWarning, match="import is_correct from chardet.evaluation"
    ):
        assert equivalences.is_correct("utf-8", "utf-8")


def test_attribute_access_warns_every_time():
    """Not once per process: the second caller must be warned too.

    A single module-level ``warnings.warn`` is consumed by whoever imports
    first, so the code actually using a deprecated name never hears about it.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        _ = equivalences.SUPERSETS
        _ = equivalences.SUPERSETS
    assert len(caught) == 2


def test_import_itself_does_not_warn():
    """Importing the shim is not the deprecated act -- using a name is.

    A module-level warning also turns ``import chardet.equivalences`` into a
    hard failure under ``-W error::DeprecationWarning`` (and the common
    ``filterwarnings = error`` pytest idiom) instead of degrading.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        importlib.reload(equivalences)


def test_package_exposes_the_submodule_without_an_explicit_import(
    monkeypatch: pytest.MonkeyPatch,
):
    """``import chardet`` then ``chardet.equivalences`` keeps working.

    Before the split, ``chardet/__init__.py`` imported the module for its own
    use, which bound the attribute as a side effect.  It imports
    :mod:`chardet.output_names` now, so the package resolves this one lazily.
    """
    monkeypatch.delattr(chardet, "equivalences", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert chardet.equivalences.is_correct("utf-8", "utf-8")


def test_reexports_resolve_to_new_modules():
    """Names the shim exposes are the same objects as in the new modules."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        # Evaluation seam
        assert equivalences.is_correct is evaluation.is_correct
        assert (
            equivalences.is_equivalent_detection is evaluation.is_equivalent_detection
        )
        assert equivalences.is_language_equivalent is evaluation.is_language_equivalent
        assert equivalences.SUPERSETS is evaluation.SUPERSETS
        assert equivalences.BIDIRECTIONAL_GROUPS is evaluation.BIDIRECTIONAL_GROUPS
        assert equivalences.LANGUAGE_EQUIVALENCES is evaluation.LANGUAGE_EQUIVALENCES

        # Output-name seam
        assert equivalences.apply_compat_names is output_names.apply_compat_names
        assert (
            equivalences.apply_preferred_superset
            is output_names.apply_preferred_superset
        )
        assert equivalences.apply_legacy_rename is output_names.apply_legacy_rename
        assert equivalences.PREFERRED_SUPERSET is output_names.PREFERRED_SUPERSET


#: Names the pre-split module exposed beyond its documented surface --- the
#: private tables and helpers, plus the imported names that leaked into its
#: namespace.  Callers reaching for these are already off the documented
#: path, but the shim's whole promise is that existing imports keep working
#: with a warning rather than an ImportError.
_PRIVATE_SURFACE = (
    ("_EQUIVALENT_SYMBOL_PAIRS", evaluation),
    ("_LANGUAGE_EQUIV", evaluation),
    ("_NORMALIZED_BIDIR", evaluation),
    ("_NORMALIZED_SUPERSETS", evaluation),
    ("_build_group_index", evaluation),
    ("_chars_equivalent", evaluation),
    ("_strip_combining", evaluation),
    ("lookup_encoding", evaluation),
    ("unicodedata", evaluation),
    ("Callable", evaluation),
    ("_COMPAT_NAMES", output_names),
    ("_remap_encoding", output_names),
    ("DetectionDict", output_names),
)


@pytest.mark.parametrize(("name", "owner"), _PRIVATE_SURFACE)
def test_undocumented_names_still_resolve(name: str, owner: ModuleType):
    """Every name the pre-split namespace had resolves to its new owner."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert getattr(equivalences, name) is getattr(owner, name)


def test_dir_lists_the_proxied_names():
    """``dir()`` reports what the shim resolves, not just its own globals."""
    listed = dir(equivalences)
    assert "is_correct" in listed
    assert "PREFERRED_SUPERSET" in listed
    assert listed == sorted(listed)


def test_unknown_attribute_raises_attribute_error():
    """A name neither module owns is an AttributeError, not a silent None."""
    with pytest.raises(AttributeError, match="no attribute 'not_a_real_name'"):
        _ = equivalences.not_a_real_name


def test_rebinding_a_table_reaches_the_transforms():
    """A caller patching a table on the shim patches the one that is read.

    Re-exporting by value made this silently ineffective: the patch landed on
    the shim while ``apply_preferred_superset`` went on reading the real
    table, so the caller got a wrong answer rather than an error.
    """
    original = output_names.PREFERRED_SUPERSET
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        equivalences.PREFERRED_SUPERSET = {"iso8859-1": "XXX-PATCHED"}
        try:
            result = equivalences.apply_preferred_superset(
                {"encoding": "iso8859-1", "confidence": 1.0, "language": None}
            )
        finally:
            equivalences.PREFERRED_SUPERSET = original
    assert result["encoding"] == "XXX-PATCHED"
    assert output_names.PREFERRED_SUPERSET is original


def test_rebinding_an_unowned_name_stays_local():
    """A name neither module owns is set on the shim itself, as before."""
    equivalences.a_name_nobody_owns = 42
    try:
        assert equivalences.a_name_nobody_owns == 42
        assert not hasattr(evaluation, "a_name_nobody_owns")
        assert not hasattr(output_names, "a_name_nobody_owns")
    finally:
        del equivalences.a_name_nobody_owns


def test_patch_object_round_trips_through_the_owner():
    """``mock.patch.object`` on the shim patches the owner and restores it.

    On exit the mock deletes the name and, finding it gone, sets the
    original back.  Both steps have to reach the owner: a delete that
    raised left the owner patched for the rest of the process, and a
    re-set that found no owner would have stranded the original here.
    """
    original = evaluation.is_correct

    def fake(*_args: object, **_kwargs: object) -> bool:
        return True

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with mock.patch.object(equivalences, "is_correct", fake):
            assert evaluation.is_correct is fake
    assert evaluation.is_correct is original
    assert "is_correct" not in vars(equivalences)


def test_deleting_an_owned_name_deletes_it_from_the_owner():
    """A delete on the shim is a delete on the module that owns the name."""
    original = evaluation.is_correct
    try:
        with pytest.warns(DeprecationWarning, match="is_correct"):
            del equivalences.is_correct
        assert not hasattr(evaluation, "is_correct")
    finally:
        evaluation.is_correct = original
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert equivalences.is_correct is original


def test_deleting_an_unowned_name_stays_local():
    """A name neither owner has is the shim's own, and so is its deletion."""
    equivalences.locally_bound = 1
    del equivalences.locally_bound
    assert not hasattr(equivalences, "locally_bound")

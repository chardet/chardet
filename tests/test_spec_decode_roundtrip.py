"""Decode round-trip specification compliance.

Verifies that every encoding name chardet can return decodes cleanly
through Python's ``bytes.decode()`` without leaking a U+FEFF character
or raising ``UnicodeDecodeError``.  This is the regression guard for the
class of bug closed by commit 2a54c68 (chardet/chardet#365), where
returning ``utf-16-le``/``utf-16-be`` for BOM-prefixed input produced a
leading U+FEFF in the user's decoded string.

For each entry in :data:`chardet.registry.REGISTRY` the test verifies:

1. Clean decode: ``bytes.decode(name)`` does not raise.
2. No BOM leak: decoded text does not contain U+FEFF.
3. Byte-level round-trip: ``decoded.encode(name) == sample_bytes``.
4. Alias parity: every alias in ``REGISTRY[name].aliases`` resolves to
   the same canonical via ``lookup_encoding``.
5. ``detect()`` top-pick parity: ``chardet.detect(sample)`` returns a
   name that also satisfies (1)-(2).
6. ``compat_names=True`` parity: same, with the chardet 6.x drop-in names.
7. ``detect_all()`` narrow parity: every candidate is a valid Python
   codec name and none leak U+FEFF on decode.

The single-byte samples are generated at test time via
``text.encode(name)`` — this is intentionally circular at the codec level.
The value being tested is that *chardet's returned name* resolves through
Python's codec machinery without error, not Python codec correctness.
CJK and BOM-carrying encodings use explicit language-native samples so
the detection path exercises real multi-byte content.
"""

from __future__ import annotations

import codecs

import pytest

import chardet
from chardet.registry import REGISTRY, lookup_encoding

# ---------------------------------------------------------------------------
# Sample-text strategy
# ---------------------------------------------------------------------------

# Explicit sample text for encodings where the default "Hello, world!" is
# too trivial -- specifically the CJK family, where we want to exercise
# multi-byte sequences with language-native text.  All 86 registry
# encodings can successfully encode "Hello, world!" (including the
# EBCDIC family), so we only override where we want a richer sample.
_ZH_SAMPLE = "你好,世界!"
_JA_SAMPLE = "こんにちは、世界!"
_KO_SAMPLE = "안녕하세요, 세계!"

_ENCODING_TEXT: dict[str, str] = {
    # Chinese
    "gb18030": _ZH_SAMPLE,
    "big5hkscs": _ZH_SAMPLE,
    "hz": _ZH_SAMPLE,
    # Japanese
    "cp932": _JA_SAMPLE,
    "shift_jis_2004": _JA_SAMPLE,
    "euc_jis_2004": _JA_SAMPLE,
    "iso2022_jp_2": _JA_SAMPLE,
    "iso2022_jp_2004": _JA_SAMPLE,
    "iso2022_jp_ext": _JA_SAMPLE,
    # Korean
    "cp949": _KO_SAMPLE,
    "euc_kr": _KO_SAMPLE,
    "johab": _KO_SAMPLE,
    "iso2022_kr": _KO_SAMPLE,
    # UTF-7: mixed ASCII + CJK exercises the +...- escape run, which is
    # what chardet's detector actually looks for.  Pure ASCII would make
    # detect() return "ascii" and the detect-side tests would be tautological.
    "utf-7": "Hello, 世界!",
}

_DEFAULT_TEXT = "Hello, world!"
# All 86 encodings in chardet's registry (including the EBCDIC family)
# can encode the default ASCII text, verified empirically.  No fallback
# chain is needed.


def _make_sample(encoding_name: str) -> tuple[bytes, str]:
    """Return ``(bytes, decoded_text)`` for *encoding_name*.

    Prefers the explicit ``_ENCODING_TEXT`` entry (hand-chosen CJK /
    BOM-carrying samples); otherwise encodes ``_DEFAULT_TEXT``.
    """
    text = _ENCODING_TEXT.get(encoding_name, _DEFAULT_TEXT)
    return text.encode(encoding_name), text


# ---------------------------------------------------------------------------
# Parametrised tests
# ---------------------------------------------------------------------------

ALL_ENCODINGS: list[str] = sorted(REGISTRY.keys())


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_decode_sample_is_clean(encoding_name: str) -> None:
    """The encoding's canonical name decodes its own sample without leaking."""
    sample_bytes, expected_text = _make_sample(encoding_name)
    decoded = sample_bytes.decode(encoding_name)
    assert "\ufeff" not in decoded, (
        f"{encoding_name}: decoded sample leaks U+FEFF: {decoded!r}"
    )
    assert decoded == expected_text, (
        f"{encoding_name}: decoded {decoded!r} != expected {expected_text!r}"
    )


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_bytes_roundtrip(encoding_name: str) -> None:
    """``sample.decode(name).encode(name) == sample`` for every encoding.

    Empirically verified for all 86 registry entries including the
    escape-based stateful codecs (``hz``, ``iso2022_*``, ``utf-7``):
    Python's codec implementations are deterministic enough that
    re-encoding a decoded string produces byte-identical output for the
    sample set used here.  If a future sample change breaks this for a
    specific encoding, exclude that encoding explicitly rather than
    re-introducing a broad "stateful codecs" heuristic.
    """
    sample_bytes, _ = _make_sample(encoding_name)
    decoded = sample_bytes.decode(encoding_name)
    reencoded = decoded.encode(encoding_name)
    assert reencoded == sample_bytes, (
        f"{encoding_name}: re-encode {reencoded!r} != original {sample_bytes!r}"
    )


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_aliases_resolve_to_same_canonical(encoding_name: str) -> None:
    """Every alias in ``REGISTRY[name].aliases`` resolves to *name*.

    Internal-consistency check on chardet's alias table: no alias should
    accidentally route to a different canonical than the entry it's
    listed under.  Also confirms that ``chardet.lookup_encoding()`` can
    resolve every alias in the registry (non-None).
    """
    entry = REGISTRY[encoding_name]
    failures: list[str] = []
    for alias in entry.aliases:
        resolved = lookup_encoding(alias)
        if resolved is None:
            failures.append(f"  {alias!r}: lookup_encoding returned None")
            continue
        if resolved != encoding_name:
            failures.append(
                f"  {alias!r}: resolves to {resolved!r}, expected {encoding_name!r}"
            )
    assert not failures, f"{encoding_name} alias parity failed:\n" + "\n".join(failures)


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_detect_top_pick_decodes_cleanly(encoding_name: str) -> None:
    """``detect(sample)`` returns a name whose codec decodes the sample cleanly.

    Uses ``compat_names=False`` so we see the canonical codec name.  The
    detected name does not have to match ``encoding_name`` -- detection of a
    superset or ASCII-compatible cousin is fine -- but it must decode without
    raising and without leaking U+FEFF.

    For most single-byte encodings the synthetic sample is pure ASCII
    (``"Hello, world!".encode(name)``), so ``detect()`` returns ``"ascii"``
    and this assertion reduces to "ascii decodes ASCII cleanly".  The
    assertion still earns its keep for the non-trivial cases: the
    BOM-carrying encodings (utf-8-sig, utf-16, utf-32), the CJK multi-byte
    encodings with language-native samples, and UTF-7.  It is also a
    defensive guard against any future change that breaks the
    ``"ascii" in REGISTRY`` path.
    """
    sample_bytes, _ = _make_sample(encoding_name)
    result = chardet.detect(sample_bytes, compat_names=False)
    detected = result["encoding"]
    assert detected is not None, f"{encoding_name}: detect returned no encoding"
    try:
        decoded = sample_bytes.decode(detected)
    except (UnicodeDecodeError, LookupError) as exc:
        pytest.fail(
            f"{encoding_name}: detect returned {detected!r}, which raised on "
            f"decode: {exc!r}"
        )
    assert "\ufeff" not in decoded, (
        f"{encoding_name}: detect returned {detected!r}, whose decode leaks "
        f"U+FEFF: {decoded!r}"
    )


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_detect_compat_names_decodes_cleanly(encoding_name: str) -> None:
    """``detect(sample, compat_names=True)`` returns a Python-decodable name.

    This is the chardet 6.x drop-in contract: a user who copy-pastes the
    returned name into ``bytes.decode(name)`` must get clean output.
    Passes *detected* straight to ``bytes.decode`` so Python's own codec
    resolution is exercised end-to-end -- no chardet-side normalisation.
    """
    sample_bytes, _ = _make_sample(encoding_name)
    result = chardet.detect(sample_bytes, compat_names=True)
    detected = result["encoding"]
    assert detected is not None, f"{encoding_name}: detect returned no encoding"
    try:
        decoded = sample_bytes.decode(detected)
    except (UnicodeDecodeError, LookupError) as exc:
        pytest.fail(
            f"{encoding_name}: compat name {detected!r} is not Python-decodable "
            f"(breaks chardet 6.x drop-in contract): {exc!r}"
        )
    assert "\ufeff" not in decoded, (
        f"{encoding_name}: compat name {detected!r} decodes to leaked U+FEFF: "
        f"{decoded!r}"
    )


@pytest.mark.parametrize("encoding_name", ALL_ENCODINGS)
def test_detect_all_candidates_are_safe(encoding_name: str) -> None:
    """Every ``detect_all()`` candidate must be a safe decode target.

    Two invariants are checked per candidate:

    1. **Valid Python codec name.** Catches the specific bug "chardet
       invents an encoding string that isn't a Python codec at all" --
       e.g., a compat-table entry that ``codecs.lookup()`` rejects.
    2. **No silent U+FEFF leak on a successful decode.** Runner-ups are
       allowed to decode to garbage (the sample may not be valid in the
       runner-up's encoding) or raise ``UnicodeDecodeError`` -- those
       outcomes are expected.  The only failure mode is a runner-up that
       decodes *successfully* yet leaks a leading U+FEFF.

    Scope notes:

    * For ~72 of 86 registry encodings, ``detect_all()`` returns exactly
      one candidate (the top pick), so this test is effectively
      redundant with ``test_detect_top_pick_decodes_cleanly``.
    * For the ~14 multi-byte CJK encodings, ``detect_all(ignore_threshold
      =True)`` returns 2--57 candidates and the test has independent
      coverage.
    * For BOM-prefixed samples (utf-8-sig, utf-16, utf-32), BOM detection
      is deterministic and short-circuits the pipeline to a single
      candidate, so the test cannot currently exercise a
      "runner-up BOM leak" scenario.  It remains in place as
      forward-looking protection against a regression that introduces
      BOM-leaking runner-ups through a non-BOM code path.

    Uses ``ignore_threshold=True`` so sub-0.20 candidates are also
    checked -- the "invented codec name" failure mode could otherwise
    hide in a low-confidence candidate that the default filter drops.
    """
    sample_bytes, _ = _make_sample(encoding_name)
    candidates = chardet.detect_all(
        sample_bytes, compat_names=False, ignore_threshold=True
    )
    failures: list[str] = []
    for candidate in candidates:
        name = candidate["encoding"]
        if name is None:
            continue
        try:
            codecs.lookup(name)
        except LookupError:
            failures.append(
                f"  detect_all returned {name!r} which is not a valid Python codec"
            )
            continue
        try:
            decoded = sample_bytes.decode(name, errors="strict")
        except UnicodeDecodeError:
            # A runner-up that can't decode the bytes is an expected
            # outcome for a wrong encoding guess; not a failure.
            continue
        if "\ufeff" in decoded:
            failures.append(
                f"  detect_all candidate {name!r} decodes to leaked U+FEFF: {decoded!r}"
            )
    assert not failures, f"{encoding_name}:\n" + "\n".join(failures)

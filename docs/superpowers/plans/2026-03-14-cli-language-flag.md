# `--language` / `-l` CLI Flag Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--language` / `-l` flag to `chardetect` that includes the detected language (ISO 639-1 code + English name) in CLI output.

**Architecture:** Move `ISO_TO_LANGUAGE` from `scripts/utils.py` to `src/chardet/_utils.py` (adding `"und"` for undetermined). Update `cli.py` to format language into output when the flag is set. Update `scripts/utils.py` to re-import from the new location.

**Tech Stack:** Python 3.10+, argparse, pytest

**Spec:** `docs/superpowers/specs/2026-03-14-cli-language-flag-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/chardet/_utils.py` | Modify (lines 46+) | Add `ISO_TO_LANGUAGE` dict |
| `scripts/utils.py` | Modify (lines 147-197) | Replace inline dict with import from `chardet._utils` |
| `src/chardet/cli.py` | Modify | Add `--language`/`-l` flag, update `_print_result()` |
| `tests/test_cli.py` | Modify | Add tests for `--language` flag |

---

### Task 1: Move `ISO_TO_LANGUAGE` to `src/chardet/_utils.py`

**Files:**
- Modify: `src/chardet/_utils.py:46` (append after existing code)
- Modify: `scripts/utils.py:147-197` (replace dict definition with import)

- [ ] **Step 1: Add `ISO_TO_LANGUAGE` to `src/chardet/_utils.py`**

Append at the end of `src/chardet/_utils.py` (after line 45):

```python
#: Mapping from ISO 639-1 language codes to English names.
#: Includes ``"und"`` (ISO 639-3 "Undetermined") for use when language is unknown.
ISO_TO_LANGUAGE: dict[str, str] = {
    "ar": "arabic",
    "be": "belarusian",
    "bg": "bulgarian",
    "br": "breton",
    "cs": "czech",
    "cy": "welsh",
    "da": "danish",
    "de": "german",
    "el": "greek",
    "en": "english",
    "eo": "esperanto",
    "es": "spanish",
    "et": "estonian",
    "fa": "farsi",
    "fi": "finnish",
    "fr": "french",
    "ga": "irish",
    "gd": "gaelic",
    "he": "hebrew",
    "hr": "croatian",
    "hu": "hungarian",
    "id": "indonesian",
    "is": "icelandic",
    "it": "italian",
    "ja": "japanese",
    "kk": "kazakh",
    "ko": "korean",
    "lt": "lithuanian",
    "lv": "latvian",
    "mk": "macedonian",
    "ms": "malay",
    "mt": "maltese",
    "nl": "dutch",
    "no": "norwegian",
    "pl": "polish",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sr": "serbian",
    "sv": "swedish",
    "tg": "tajik",
    "th": "thai",
    "tr": "turkish",
    "uk": "ukrainian",
    "und": "undetermined",
    "ur": "urdu",
    "vi": "vietnamese",
    "zh": "chinese",
}
```

- [ ] **Step 2: Update `scripts/utils.py` to import instead of defining**

Replace lines 147-197 (the `ISO_TO_LANGUAGE` dict definition) with:

```python
from chardet._utils import ISO_TO_LANGUAGE
```

Keep `_LANGUAGE_NAME_TO_ISO` and `normalize_language()` in place (lines 200-219) — they stay in `scripts/utils.py`. The `_LANGUAGE_NAME_TO_ISO` dict comprehension already references `ISO_TO_LANGUAGE` and will work with the import.

Also add the re-export to the existing imports section or just leave it as a mid-file import (since the file already uses late imports like `import chardet` inside functions). However, since the existing code defines `ISO_TO_LANGUAGE` at module level and `_LANGUAGE_NAME_TO_ISO` immediately after, the cleanest approach is to put the import right where the dict used to be.

- [ ] **Step 3: Run existing tests to verify nothing broke**

Run: `uv run python -m pytest tests/test_cli.py scripts/tests/test_utils.py -v`
Expected: All existing tests PASS (no behavioral change).

- [ ] **Step 4: Commit**

```bash
git add src/chardet/_utils.py scripts/utils.py
git commit -m "refactor: move ISO_TO_LANGUAGE to chardet._utils for shared access"
```

---

### Task 2: Add `--language` flag to CLI and write tests (TDD)

**Files:**
- Modify: `src/chardet/cli.py:1-82`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `--language` flag**

Append to `tests/test_cli.py`:

```python
def test_cli_language_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--language should include language code and name in output."""
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld café résumé naïve".encode())
    main(["--language", str(f)])
    captured = capsys.readouterr()
    # Format: "{filepath}: {encoding} {iso} ({Name}) with confidence {conf}"
    assert "with confidence" in captured.out
    # Should contain a language code and parenthesized name
    assert "(" in captured.out
    assert ")" in captured.out


def test_cli_language_short_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """-l should work as short form of --language."""
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld café résumé naïve".encode())
    main(["-l", str(f)])
    captured = capsys.readouterr()
    assert "(" in captured.out
    assert "with confidence" in captured.out


def test_cli_language_minimal(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--language + --minimal should print encoding and language code."""
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld café résumé naïve".encode())
    main(["--minimal", "--language", str(f)])
    captured = capsys.readouterr()
    parts = captured.out.strip().split()
    # Should be exactly two tokens: encoding and language code
    assert len(parts) == 2
    assert "with confidence" not in captured.out
    assert "(" not in captured.out


def test_cli_language_minimal_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """--language + --minimal on stdin should print encoding and language code."""
    import io

    fake_stdin = io.TextIOWrapper(io.BytesIO("Héllo wörld café résumé naïve".encode()))
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    main(["--minimal", "--language"])
    captured = capsys.readouterr()
    parts = captured.out.strip().split()
    assert len(parts) == 2
    assert "with confidence" not in captured.out


def test_cli_language_none_shows_und(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """When language is None, should display 'und (Undetermined)'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    monkeypatch.setattr(
        chardet,
        "detect",
        lambda *_a, **_kw: {"encoding": "ascii", "confidence": 1.0, "language": None},
    )
    main(["--language", str(f)])
    captured = capsys.readouterr()
    assert "und (Undetermined)" in captured.out


def test_cli_language_none_minimal_shows_und(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """When language is None with --minimal, should display 'encoding und'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    monkeypatch.setattr(
        chardet,
        "detect",
        lambda *_a, **_kw: {"encoding": "ascii", "confidence": 1.0, "language": None},
    )
    main(["--minimal", "--language", str(f)])
    captured = capsys.readouterr()
    assert captured.out.strip() == "ascii und"


def test_cli_language_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """--language on stdin should include language in output."""
    import io

    fake_stdin = io.TextIOWrapper(io.BytesIO("Héllo wörld café résumé naïve".encode()))
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    main(["--language"])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out
    assert "(" in captured.out


def test_cli_without_language_flag_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Without --language, output should not contain language info."""
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld café résumé naïve".encode())
    main([str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out
    # No parenthesized language name
    assert "(" not in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_cli.py::test_cli_language_flag tests/test_cli.py::test_cli_language_short_flag tests/test_cli.py::test_cli_language_minimal -v`
Expected: FAIL — `error: unrecognized arguments: --language` (or `-l`).

- [ ] **Step 3: Implement `--language` flag in `cli.py`**

Update `src/chardet/cli.py` to the following complete content:

```python
"""Command-line interface for chardet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chardet
from chardet._utils import DEFAULT_MAX_BYTES, ISO_TO_LANGUAGE
from chardet.enums import EncodingEra
from chardet.pipeline import DetectionDict

_ERA_NAMES = [e.name.lower() for e in EncodingEra if e.bit_count() == 1] + ["all"]


def _print_result(
    result: DetectionDict, label: str, *, minimal: bool, language: bool
) -> None:
    """Print a detection result to stdout."""
    if minimal:
        if language:
            iso = result["language"] or "und"
            print(f"{result['encoding']} {iso}")
        else:
            print(result["encoding"])
    else:
        if language:
            iso = result["language"] or "und"
            name = ISO_TO_LANGUAGE.get(iso, iso).title()
            print(
                f"{label}: {result['encoding']} {iso} ({name}) "
                f"with confidence {result['confidence']}"
            )
        else:
            print(
                f"{label}: {result['encoding']} with confidence {result['confidence']}"
            )


def main(argv: list[str] | None = None) -> None:
    """Run the ``chardetect`` command-line tool.

    :param argv: Command-line arguments.  Defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description="Detect character encoding of files.")
    parser.add_argument("files", nargs="*", help="Files to detect encoding of")
    parser.add_argument(
        "--minimal", action="store_true", help="Output only the encoding name"
    )
    parser.add_argument(
        "-l",
        "--language",
        action="store_true",
        help="Include detected language in output",
    )
    parser.add_argument(
        "-e",
        "--encoding-era",
        default=None,
        choices=_ERA_NAMES,
        help="Encoding era filter",
    )
    parser.add_argument(
        "--version", action="version", version=f"chardet {chardet.__version__}"
    )

    args = parser.parse_args(argv)

    era = (
        EncodingEra[args.encoding_era.upper()] if args.encoding_era else EncodingEra.ALL
    )

    if args.files:
        errors = 0
        for filepath in args.files:
            try:
                with Path(filepath).open("rb") as f:
                    data = f.read(DEFAULT_MAX_BYTES)
            except OSError as e:
                print(f"chardetect: {filepath}: {e}", file=sys.stderr)
                errors += 1
                continue
            try:
                result = chardet.detect(data, encoding_era=era)
            except Exception as e:  # noqa: BLE001
                print(f"chardetect: {filepath}: detection failed: {e}", file=sys.stderr)
                errors += 1
                continue
            _print_result(result, filepath, minimal=args.minimal, language=args.language)
        if errors == len(args.files):
            sys.exit(1)
    else:
        data = sys.stdin.buffer.read(DEFAULT_MAX_BYTES)
        try:
            result = chardet.detect(data, encoding_era=era)
        except Exception as e:  # noqa: BLE001
            print(f"chardetect: stdin: detection failed: {e}", file=sys.stderr)
            sys.exit(1)
        _print_result(result, "stdin", minimal=args.minimal, language=args.language)


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run all CLI tests to verify they pass**

Run: `uv run python -m pytest tests/test_cli.py -v`
Expected: All tests PASS (both new and existing).

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `uv run python -m pytest -n auto`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chardet/cli.py tests/test_cli.py
git commit -m "feat: add --language / -l flag to chardetect CLI"
```

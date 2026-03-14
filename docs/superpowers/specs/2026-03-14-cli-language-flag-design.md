# Design: `--language` / `-l` flag for `chardetect` CLI

## Summary

Add a `--language` / `-l` flag to the `chardetect` CLI that includes the
detected language in the output. The `detect()` API already returns a
`language` field (ISO 639-1 code); this feature surfaces it in the CLI.

## Output Formats

### With `--language`

| Mode | Format | Example |
|------|--------|---------|
| Normal | `{label}: {encoding} {iso} ({Name}) with confidence {conf}` | `test.txt: utf-8 fr (French) with confidence 0.99` |
| Minimal + language | `{encoding} {iso}` | `utf-8 fr` |

### When language is `None`

Use `und` (ISO 639-2/3 "Undetermined") as a placeholder:

| Mode | Example |
|------|---------|
| Normal | `test.txt: ascii und (Undetermined) with confidence 1.0` |
| Minimal | `ascii und` |

### Without `--language` (unchanged)

| Mode | Format |
|------|--------|
| Normal | `{label}: {encoding} with confidence {conf}` |
| Minimal | `{encoding}` |

## Implementation

### 1. Move `ISO_TO_LANGUAGE` to `src/chardet/_utils.py`

The mapping from ISO 639-1 codes to English language names already exists in
`scripts/utils.py`. Move it to `src/chardet/_utils.py` so the CLI, scripts,
and tests can all import from a single location. Add `"und": "Undetermined"`
to the dict.

Update `scripts/utils.py` to import `ISO_TO_LANGUAGE` from `chardet._utils`
instead of defining its own copy. The derived `_LANGUAGE_NAME_TO_ISO` dict and
`normalize_language()` function remain in `scripts/utils.py` since they are
only used by scripts and tests, not the CLI.

### 2. Update `src/chardet/cli.py`

- Add `--language` / `-l` argument (action `store_true`).
- Update `_print_result()` to accept a `language: bool` parameter.
- When `language=True`:
  - Read `result["language"]`, defaulting to `"und"` if `None`.
  - Look up the display name via `ISO_TO_LANGUAGE.get(iso, iso).title()`.
    If the code is not in the dict, use the raw code as the display name.
  - Format output per the table above.
- Argparse help text: `"Include detected language in output"`.

### 3. Update `tests/test_cli.py`

Add tests for:
- `--language` flag with normal output (file and stdin)
- `--language` + `--minimal` flag (file and stdin)
- `-l` short form
- `None` language → `und (Undetermined)` output

## Non-goals

- No changes to the `detect()` API or `DetectionResult` type.
- No new runtime dependencies.

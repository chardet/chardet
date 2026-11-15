"""Tests for the CLDR quotation-mark generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import quotation_marks
from generate_quotation_marks import main, parse, render, trained_languages


def _package(tmp_path: Path, marks: dict[str, list[str]]) -> Path:
    (tmp_path / "package.json").write_text(json.dumps({"version": "99.0.0"}))
    for language, (start, end, alt_start, alt_end) in marks.items():
        folder = tmp_path / "main" / language
        folder.mkdir(parents=True)
        delimiters = {
            "quotationStart": start,
            "quotationEnd": end,
            "alternateQuotationStart": alt_start,
            "alternateQuotationEnd": alt_end,
        }
        (folder / "delimiters.json").write_text(
            json.dumps({"main": {language: {"delimiters": delimiters}}}),
            encoding="utf-8",
        )
    return tmp_path


def test_parse_reads_version_and_marks_and_skips_missing(tmp_path: Path) -> None:
    package = _package(tmp_path, {"de": ["\u201e", "\u201c", "\u201a", "\u2018"]})
    version, marks = parse(package, ["de", "zxx"])
    assert version == "99.0.0"
    assert marks == {"de": ["\u201e", "\u201c", "\u201a", "\u2018"]}


def test_render_round_trips(tmp_path: Path) -> None:
    package = _package(tmp_path, {"fr": ["\u00ab", "\u00bb", "\u00ab", "\u00bb"]})
    source = render(*parse(package, ["fr"]))
    namespace: dict[str, object] = {}
    exec(source, namespace)  # noqa: S102
    assert namespace["CLDR_VERSION"] == "99.0.0"
    assert namespace["QUOTATION_MARKS"] == {
        "fr": ("\u00ab", "\u00bb", "\u00ab", "\u00bb")
    }
    assert source.isascii()


def test_checked_in_table_covers_the_trained_languages() -> None:
    missing = set(trained_languages()) - set(quotation_marks.QUOTATION_MARKS)
    assert missing <= {"zxx"}


def test_main_writes_the_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path, {"en": ["\u201c", "\u201d", "\u2018", "\u2019"]})
    monkeypatch.setattr("sys.argv", ["generate_quotation_marks.py", str(package)])
    main()
    assert '"en": (' in capsys.readouterr().out


def test_main_without_a_path_prints_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["generate_quotation_marks.py"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert "Usage" in str(excinfo.value)

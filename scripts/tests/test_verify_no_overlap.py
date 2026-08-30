"""Tests for the overlap verification script."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from verify_no_overlap import check_overlap, main


def test_no_overlap(tmp_path: Path) -> None:
    """No overlap when training and test texts differ."""
    test_dir = tmp_path / "test_data" / "utf-8-en"
    test_dir.mkdir(parents=True)
    (test_dir / "culturax_00000.txt").write_bytes(
        b"This is test data content that should not appear in training."
    )

    train_dir = tmp_path / "cache" / "culturax" / "en"
    train_dir.mkdir(parents=True)
    (train_dir / "000000.txt").write_text(
        "This is training data content that is completely different.",
        encoding="utf-8",
    )

    overlaps = check_overlap(tmp_path / "test_data", tmp_path / "cache")
    assert len(overlaps) == 0


def test_overlap_detected(tmp_path: Path) -> None:
    """Overlap is detected when same text appears in both."""
    text = "Identical text appearing in both training and test data sets."

    test_dir = tmp_path / "test_data" / "utf-8-en"
    test_dir.mkdir(parents=True)
    (test_dir / "culturax_00000.txt").write_bytes(text.encode("utf-8"))

    train_dir = tmp_path / "cache" / "culturax" / "en"
    train_dir.mkdir(parents=True)
    (train_dir / "000000.txt").write_text(text, encoding="utf-8")

    overlaps = check_overlap(tmp_path / "test_data", tmp_path / "cache")
    assert len(overlaps) > 0


def _clean_layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a test-data dir, a non-overlapping cache dir, and unverifiable metadata."""
    test_dir = tmp_path / "test_data" / "utf-8-en"
    test_dir.mkdir(parents=True)
    (test_dir / "culturax_00000.txt").write_bytes(b"Test text that is unique.")
    train_dir = tmp_path / "cache" / "culturax" / "en"
    train_dir.mkdir(parents=True)
    (train_dir / "000000.txt").write_text(
        "Training text, also unique.", encoding="utf-8"
    )
    metadata = tmp_path / "training_metadata.yaml"
    metadata.write_text(
        'training_date: "2026-01-01T00:00:00Z"\nmodels:\n', encoding="utf-8"
    )
    return tmp_path / "test_data", tmp_path / "cache", metadata


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["verify_no_overlap.py", *argv])
    with pytest.raises(SystemExit) as excinfo:
        main()
    return int(excinfo.value.code or 0)


def test_unverified_provenance_is_advisory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Metadata without an exclusion record warns but passes."""
    test_data, cache, metadata = _clean_layout(tmp_path)
    code = _run(
        monkeypatch,
        [
            "--test-data-dir",
            str(test_data),
            "--cache-dir",
            str(cache),
            "--metadata",
            str(metadata),
        ],
    )
    assert code == 0
    assert "UNVERIFIED" in capsys.readouterr().out


def test_require_provenance_fails_on_unverified_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The release gate turns the same advisory into a failure."""
    test_data, cache, metadata = _clean_layout(tmp_path)
    code = _run(
        monkeypatch,
        [
            "--test-data-dir",
            str(test_data),
            "--cache-dir",
            str(cache),
            "--metadata",
            str(metadata),
            "--require-provenance",
        ],
    )
    assert code == 1
    assert "--require-provenance" in capsys.readouterr().err

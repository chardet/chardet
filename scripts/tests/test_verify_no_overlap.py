"""Tests for the overlap verification script."""

from __future__ import annotations

from pathlib import Path

from verify_no_overlap import check_overlap


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

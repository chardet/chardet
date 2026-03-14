# tests/test_cli.py
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

import chardet
from chardet.cli import main


def test_cli_detects_file(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli", str(f)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "ascii" in result.stdout.lower()


def test_cli_detects_utf8_file(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld".encode())
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli", str(f)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "utf-8" in result.stdout.lower()


def test_cli_stdin():
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli"],
        input=b"Hello world",
        capture_output=True,
    )
    assert result.returncode == 0
    assert "ascii" in result.stdout.decode().lower()


def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Output is "chardet <version>"; version should start with a digit
    output = result.stdout.strip()
    assert output.startswith("chardet "), output
    version = output.split()[-1]
    assert version[0].isdigit(), version


def test_cli_minimal_flag(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli", "--minimal", str(f)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ascii"


def test_cli_multiple_files(tmp_path: Path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_bytes(b"Hello")
    f2.write_bytes("Héllo".encode())
    result = subprocess.run(
        [sys.executable, "-m", "chardet.cli", str(f1), str(f2)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2


def test_cli_nonexistent_file(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["nonexistent_file_xyz.txt"])
    captured = capsys.readouterr()
    assert "nonexistent_file_xyz.txt" in captured.err


def test_cli_encoding_era_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world, enough text for detection. " * 3)
    main(["-e", "modern_web", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_partial_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """When some files succeed and some fail, exit code should be 0."""
    good = tmp_path / "good.txt"
    good.write_bytes(b"Hello world")
    # Mix of valid and invalid files — should NOT exit with code 1
    main([str(good), "nonexistent_file_xyz.txt"])
    captured = capsys.readouterr()
    assert "nonexistent_file_xyz.txt" in captured.err
    assert "with confidence" in captured.out


def test_main_module_importable():
    """chardet.__main__ should be importable (covers module-level import)."""
    import chardet.__main__  # noqa: F401


def test_cli_python_m_chardet(tmp_path: Path):
    """Python -m chardet should work (exercises __main__.py)."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    result = subprocess.run(
        [sys.executable, "-m", "chardet", str(f)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "with confidence" in result.stdout


def test_cli_detection_failure_on_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Detection exception on file should print error and count as failure."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    monkeypatch.setattr(
        chardet,
        "detect",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(SystemExit, match="1"):
        main([str(f)])
    captured = capsys.readouterr()
    assert "detection failed" in captured.err
    assert "boom" in captured.err


def test_cli_detection_failure_on_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Detection exception on stdin should print error and exit 1."""
    fake_stdin = io.TextIOWrapper(io.BytesIO(b"Hello"))
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        chardet,
        "detect",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(SystemExit, match="1"):
        main([])
    captured = capsys.readouterr()
    assert "detection failed" in captured.err
    assert "stdin" in captured.err


def test_cli_minimal_flag_in_process(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """--minimal should print only the encoding name (in-process)."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello world")
    main(["--minimal", str(f)])
    captured = capsys.readouterr()
    # Just the encoding name, no "with confidence"
    assert "with confidence" not in captured.out
    assert captured.out.strip() != ""


def test_cli_stdin_success_in_process(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Stdin detection success path should print result (in-process)."""
    fake_stdin = io.TextIOWrapper(io.BytesIO(b"Hello world"))
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    main([])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out


def test_cli_language_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--language should include language code and name in output."""
    f = tmp_path / "test.txt"
    f.write_bytes("Héllo wörld café résumé naïve".encode())
    main(["--language", str(f)])
    captured = capsys.readouterr()
    assert "with confidence" in captured.out
    # Should contain a language code and parenthesized name in the output
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

"""Shared utilities for scripts and tests."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from chardet._utils import ISO_TO_LANGUAGE

_TEST_DATA_REPO = "https://github.com/chardet/test-data.git"
_REF_FILE = ".test-data-ref"


def _get_test_data_ref() -> str | None:
    """Derive the test-data git ref from the installed chardet version.

    Returns a tag like ``"7.0.1"`` for release versions, or ``None`` for
    dev builds (which will clone the default branch instead).
    """
    import chardet

    version = chardet.__version__
    if ".dev" in version:
        return None
    return version


def _git_clone_shallow(repo: str, dest: str, *, branch: str | None = None) -> None:
    """Shallow-clone *repo* into *dest*, optionally at a specific *branch*/tag."""
    cmd = ["git", "clone", "--depth=1"]
    if branch:
        cmd.append(f"--branch={branch}")
    cmd.extend([repo, dest])
    subprocess.run(cmd, check=True, capture_output=True)


def _clone_test_data(local_data: Path, *, ref: str | None) -> None:
    """Shallow-clone the test-data repo into *local_data*.

    If *ref* is not ``None``, clone the specific tag/branch. Falls back to
    the default branch if the ref does not exist.
    """
    with tempfile.TemporaryDirectory() as tmp:
        if ref is not None:
            try:
                _git_clone_shallow(_TEST_DATA_REPO, tmp, branch=ref)
            except subprocess.CalledProcessError:
                print(
                    f"WARNING: test-data ref '{ref}' not found, "
                    f"falling back to default branch",
                    file=sys.stderr,
                )
                _git_clone_shallow(_TEST_DATA_REPO, tmp)
                ref = None
        else:
            _git_clone_shallow(_TEST_DATA_REPO, tmp)

        src = Path(tmp)
        local_data.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue
            dest = local_data / item.name
            shutil.copytree(item, dest, dirs_exist_ok=True)
        ref_label = ref if ref is not None else "main"
        (local_data / _REF_FILE).write_text(ref_label + "\n")


def get_data_dir() -> Path:
    """Get the test data directory, cloning from GitHub if needed.

    If ``tests/data`` is a symlink (e.g. to a local ``chardet/test-data``
    checkout), it is used as-is — no staleness check or clone is performed.

    Otherwise, the desired ref is derived from the installed chardet version.
    If the cached data's ``.test-data-ref`` matches the desired ref, it is
    reused; otherwise the cache is cleared and re-cloned.
    """
    repo_root = Path(__file__).parent.parent
    local_data = repo_root / "tests" / "data"
    if local_data.is_symlink():
        return local_data.resolve()

    ref = _get_test_data_ref()
    desired_label = ref if ref is not None else "main"

    if local_data.is_dir() and any(local_data.iterdir()):
        ref_file = local_data / _REF_FILE
        if ref_file.is_file() and ref_file.read_text().strip() == desired_label:
            return local_data
        shutil.rmtree(local_data)

    _clone_test_data(local_data, ref=ref)
    return local_data


def find_chardet_so_files() -> list[Path]:
    """Return any mypyc .so/.pyd files under the chardet package directory.

    Uses ``importlib.util.find_spec`` to locate the package directory without
    triggering a full ``import chardet``, which would make subsequent import
    timing measurements inaccurate.
    """
    import importlib.util

    spec = importlib.util.find_spec("chardet")
    if spec is None or spec.origin is None:
        return []
    pkg_dir = Path(spec.origin).parent
    return sorted(
        p for p in pkg_dir.rglob("*") if p.suffix in (".so", ".pyd") and p.is_file()
    )


def abort_if_mypyc_compiled() -> None:
    """Exit with an error if chardet has mypyc .so/.pyd files present.

    Called when ``--pure`` is passed to ensure benchmarks measure
    pure-Python performance only.
    """
    so_files = find_chardet_so_files()
    if so_files:
        print(
            "ERROR: --pure flag set but mypyc compiled extensions detected:",
            file=sys.stderr,
        )
        for p in so_files:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nRemove these .so/.pyd files before benchmarking pure Python.",
            file=sys.stderr,
        )
        sys.exit(1)


def format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MiB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.1f} KiB"
    return f"{n} B"


# Mapping from English language names (as returned by chardet ≤6 and
# charset-normalizer) to ISO 639-1 codes (used by chardet 7+ and test dirs).
# Derived from ISO_TO_LANGUAGE to avoid maintaining two dicts that must stay
# in sync.
_LANGUAGE_NAME_TO_ISO: dict[str, str] = {v: k for k, v in ISO_TO_LANGUAGE.items()}
# "scottish gaelic" is the full name used by some detectors; ISO_TO_LANGUAGE
# maps gd -> "gaelic" (the short form).
_LANGUAGE_NAME_TO_ISO["scottish gaelic"] = "gd"


def normalize_language(detected_language: str | None) -> str | None:
    """Normalize a detected language to its ISO 639-1 code for comparison.

    Handles both ISO codes (chardet 7+) and English names (chardet ≤6,
    charset-normalizer).
    """
    if not detected_language:
        return None
    lowered = detected_language.lower().rstrip("—")  # charset-normalizer quirk
    return _LANGUAGE_NAME_TO_ISO.get(lowered, lowered)


def collect_test_files(
    data_dir: Path,
) -> list[tuple[str | None, str | None, Path]]:
    """Collect (encoding, language, filepath) tuples from test data.

    Directory name format: "{encoding}-{lang_iso}" e.g. "utf-8-en",
    "iso-8859-1-fr", "hz-gb-2312-zh".

    Since all ISO 639-1 codes are two letters (no hyphens), we can reliably
    split on the last hyphen to separate encoding from language.

    The binary test directory is named "None-None"; its encoding and language
    are returned as Python ``None`` rather than the string ``"None"``.
    """
    test_files: list[tuple[str | None, str | None, Path]] = []
    for encoding_dir in sorted(data_dir.iterdir()):
        if not encoding_dir.is_dir():
            continue
        parts = encoding_dir.name.rsplit("-", 1)
        if len(parts) != 2:
            continue
        encoding_name: str | None = parts[0]
        language: str | None = parts[1]
        if encoding_name == "None":
            encoding_name = None
        if language == "None":
            language = None
        test_files.extend(
            (encoding_name, language, filepath)
            for filepath in sorted(encoding_dir.iterdir())
            if filepath.is_file()
        )
    return test_files


def build_benchmark_parser(description: str) -> argparse.ArgumentParser:
    """Create an argument parser with common benchmark options."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--detector",
        choices=["chardet", "charset-normalizer", "cchardet"],
        default="chardet",
        help="Detector library to benchmark (default: chardet)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("tests/data"),
        help="Path to test data directory (default: tests/data)",
    )
    parser.add_argument(
        "--encoding-era",
        choices=["all", "modern_web", "none"],
        default="all",
        help=(
            "Encoding era for chardet.detect(): "
            "'all' (default) for EncodingEra.ALL, "
            "'modern_web' for EncodingEra.MODERN_WEB, "
            "'none' to omit (for chardet < 6.0)"
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        default=False,
        help="Print only JSON output (for consumption by other scripts)",
    )
    parser.add_argument(
        "--pure",
        action="store_true",
        default=False,
        help="Abort if mypyc .so/.pyd files are present (ensure pure-Python measurement)",
    )
    return parser


def load_benchmark_data(
    args: argparse.Namespace,
) -> list[tuple[str | None, str | None, Path, bytes]]:
    """Validate args, check --pure, load test files, and pre-read bytes."""
    if args.pure and args.detector == "chardet":
        abort_if_mypyc_compiled()

    data_dir: Path = args.data_dir.resolve()
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    test_files = collect_test_files(data_dir)
    if not test_files:
        print("ERROR: no test files found!", file=sys.stderr)
        sys.exit(1)

    return [(enc, lang, fp, fp.read_bytes()) for enc, lang, fp in test_files]

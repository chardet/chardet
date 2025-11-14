#!/usr/bin/env python

######################## BEGIN LICENSE BLOCK ########################
# Contributor(s):
#   11.06.2025 - Dan Blanchard - initial version
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
#
######################### END LICENSE BLOCK #########################

"""
Generate test files from CulturaX dataset for character encoding detection.

This script downloads test data from the CulturaX dataset and creates test files
for each language/charset combination supported by chardet. Test files are sized
to be representative of typical webpages (~3000 characters).

Note: Some legacy encodings have fundamental limitations:
- CP866 (DOS Cyrillic): Lacks Belarusian/Ukrainian 'і' (U+0456/U+0406)
  Workaround: Substitute with Russian 'и' (historically used, linguistically incorrect)
- CP720, CP864, CP1006: Limited Arabic/Urdu character support
- Windows-1258 (Vietnamese): Uses combining diacritics - requires special normalization
  (precomposed base letters â/ê/ô/ă/ơ/ư + combining tone marks)
- Many encodings lack modern Unicode punctuation (en-dash, em-dash, smart quotes)

This script applies appropriate character substitutions where semantically valid,
but may skip documents entirely if they contain characters essential to the
language that cannot be represented in the target encoding.
"""

import os
import re
import sys
import unicodedata
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

try:
    from datasets import load_dataset

    HAVE_DATASETS = True
except Exception:
    HAVE_DATASETS = False
    load_dataset = None  # type: ignore

from chardet import __version__
from chardet.metadata.languages import LANGUAGES
from chardet.universaldetector import UniversalDetector
from create_language_model import (
    get_legacy_char_substitutions,
    normalize_vietnamese_for_windows_1258,
)

# Windows encodings that need bytes in 0x80-0x9F to be detected
# (otherwise ISO equivalent will be detected instead)
WINDOWS_ENCODINGS_NEEDING_HIGH_BYTES = set(UniversalDetector.ISO_WIN_MAP.values())

# Mac encodings that have ISO equivalents and need bytes in 0x80-0x9F to be detected
# (otherwise ISO equivalent will be detected instead)
MAC_ENCODINGS_NEEDING_HIGH_BYTES = {
    "MacRoman",  # ~ ISO-8859-1
    "MacLatin2",  # ~ ISO-8859-2
    "MacCyrillic",  # ~ ISO-8859-5
    "MacGreek",  # ~ ISO-8859-7
    "MacTurkish",  # ~ ISO-8859-9
    "MacIceland",  # ~ ISO-8859-1
}


def strip_hebrew_vowel_points(text: str) -> str:
    """Remove Hebrew vowel points (nikud) and other marks not in DOS encodings.

    DOS Hebrew encodings (CP424, CP856, CP862) only support the 27 Hebrew letters
    (U+05D0-U+05EA). They do not include:
    - Vowel points/nikud (U+05B0-U+05C7): kamatz, patach, tzere, segol, etc.
    - Cantillation marks
    - Other Hebrew diacritics and punctuation marks

    Modern Hebrew text is typically written without vowel points anyway, except
    in religious texts, poetry, and children's books.
    """
    import re

    # Remove Hebrew marks and vowel points (U+0591-U+05CF, excluding letters at U+05D0-U+05EA)
    # Keep only: Hebrew letters (U+05D0-U+05EA) and final forms
    # Remove: vowel points, cantillation marks, punctuation like maqaf
    HEBREW_MARKS_PATTERN = r"[\u0591-\u05BD\u05BF-\u05CF]"

    return re.sub(HEBREW_MARKS_PATTERN, "", text)


def reverse_hebrew_for_visual_encoding(text: str) -> str:
    """Reverse Hebrew character sequences for visual order encodings.

    Visual Hebrew encodings (CP424, CP856, CP862) were used on DOS systems
    without bidirectional rendering. Hebrew text was stored reversed so that
    when displayed left-to-right, it would appear correct.

    Only Hebrew characters are reversed - Latin text, numbers, and punctuation
    maintain their normal left-to-right order.

    Example:
        Input (logical):  "Hello שלום world 123"
        Output (visual):  "Hello םולש world 123"
                          (only Hebrew portion reversed)
    """
    import re

    # Hebrew Unicode range: U+0590 to U+05FF
    # Includes Hebrew letters, final forms, and Hebrew-specific punctuation
    HEBREW_PATTERN = r"[\u0590-\u05FF]+"

    def reverse_match(match):
        """Reverse the matched Hebrew sequence"""
        return match.group(0)[::-1]

    # Find all Hebrew sequences and reverse each one
    return re.sub(HEBREW_PATTERN, reverse_match, text)


def has_windows_high_bytes(text: str, charset_name: str) -> bool:
    """Check if text contains bytes in 0x80-0x9F range when encoded.

    For Windows and Mac encodings that have ISO equivalents, we need to ensure
    the test files contain bytes in the 0x80-0x9F range. This is because:
    - ISO encodings have control codes (not printable) in 0x80-0x9F
    - Windows/Mac encodings have printable chars (letters/punctuation) in 0x80-0x9F
    - Detection logic uses WIN_BYTE_DETECTOR to find these bytes and upgrade ISO → Windows/Mac
    - Without these bytes, ISO will be detected instead of Windows/Mac

    Args:
        text: The text to check
        charset_name: The charset to encode with

    Returns:
        True if encoding produces bytes in 0x80-0x9F range, False otherwise
    """
    try:
        encoded = text.encode(charset_name)
        # Check if any bytes are in 0x80-0x9F range
        return any(0x80 <= byte <= 0x9F for byte in encoded)
    except (UnicodeEncodeError, LookupError):
        return False


def apply_legacy_substitutions(
    text: str, charset_name: str, language_name: str | None = None
) -> str:
    """Apply character substitutions for legacy encodings.

    Replaces modern Unicode characters with legacy-compatible equivalents
    and applies Hebrew-specific transformations for visual encodings.

    See get_legacy_char_substitutions() in create_language_model.py for details
    on which substitutions are applied.

    Additionally handles Hebrew visual encoding transformations:
    - Strips vowel points (nikud) that DOS Hebrew encodings don't support
    - Reverses Hebrew sequences for visual order display
    """
    # Get and apply substitutions (from create_language_model.py)
    substitutions = get_legacy_char_substitutions(charset_name, language_name)
    for old_char, new_char in substitutions.items():
        text = text.replace(old_char, new_char)

    # Hebrew visual encodings: strip vowel points and reverse sequences
    # These transformations are specific to test file generation and NOT
    # applied during model training (the models work with logical Hebrew)
    if charset_name.upper() in ("CP424", "CP856", "CP862"):
        text = strip_hebrew_vowel_points(text)
        text = reverse_hebrew_for_visual_encoding(text)

    return text


def write_culturax_test_files(
    *,
    language: str,
    language_name: str,
    charsets: list[str],
    num_training_docs: int | None,
    test_dir: str = "tests",
    max_chars_per_file: int = 3000,
    num_files: int = 3,
):
    """Write test files from CulturaX dataset (after training docs) for each charset.

    Args:
        language: ISO language code (e.g., 'en', 'fr', 'de')
        language_name: Full language name (e.g., 'English', 'French', 'German')
        charsets: List of charset names to generate test files for
        num_training_docs: Number of documents used for training (to skip past)
        test_dir: Root directory for test files
        max_chars_per_file: Maximum characters per test file (default: 3000,
                           roughly the size of a typical webpage's text content)
        num_files: Number of test files to generate per charset
    """
    if not HAVE_DATASETS:
        print(
            f"Skipping test file generation for {language}: datasets package not available"
        )
        return

    if num_training_docs is None:
        print(
            f"Skipping test file generation for {language}: "
            f"num_training_docs not set in language metadata"
        )
        return

    print(
        f"\nGenerating test files from CulturaX train split for {language}\n"
        f"(Skipping first {num_training_docs:,} documents used for training)"
    )

    # Load train dataset (same as training script uses)
    assert load_dataset is not None
    try:
        dataset = load_dataset(
            "uonlp/CulturaX",
            language,
            split="train",
            streaming=True,
        )
    except Exception as e:
        print(f"Could not load dataset for {language}: {e}")
        return

    # Skip past the training data documents
    # This ensures test files come from data not used in training
    dataset = dataset.skip(num_training_docs)  # type: ignore

    items = []
    for item_idx, item in enumerate(dataset):
        text = item.get("text", "")  # type: ignore

        if not text or len(text) < 500:  # Skip very short texts
            continue

        # Apply charset-specific normalization
        # Most encodings use NFC (precomposed), but Windows-1258 needs special handling
        if any(cs.upper() == "WINDOWS-1258" for cs in charsets):
            # Windows-1258 requires partial decomposition:
            # - Keep precomposed base+diacritic (â, ê, ô, ă, ơ, ư)
            # - Decompose tone marks to combining characters
            text = normalize_vietnamese_for_windows_1258(text)
        else:
            # Use NFC for all other encodings (precomposed characters)
            text = unicodedata.normalize("NFC", text)

        # Clean up repeated whitespace
        text = re.sub(r"(\s)\1+", r"\1", text)

        # Store item with metadata (adjusted index to reflect skip)
        items.append({
            "text": text,
            "idx": num_training_docs + item_idx,
            "url": item.get("url", ""),  # type: ignore
            "source": item.get("source", ""),  # type: ignore
        })

        if len(items) >= num_files * 2:  # Get extra in case some fail to encode
            break

    if not items:
        print(f"No suitable test items found for {language}")
        return

    for charset_name in charsets:
        # Determine the correct directory name (lowercase, with hyphens)
        # Follow existing convention in tests directory
        # Format: encoding-language (e.g., "iso-8859-2-polish", "windows-1251-russian")
        charset_dir_name = charset_name.lower()
        language_suffix = language_name.lower().replace(" ", "")

        # Check if we need to add language suffix by looking for existing directories
        # If multiple languages use the same encoding, we add the language name
        # First check if there's already a language-specific directory
        charset_with_lang = f"{charset_dir_name}-{language_suffix}"
        charset_test_dir = f"{test_dir}/{charset_with_lang}"

        # Create directory if it doesn't exist
        os.makedirs(charset_test_dir, exist_ok=True)

        files_written = 0
        for item in items:
            if files_written >= num_files:
                break

            # Create filename from metadata
            source = item.get("source", "culturax").replace("/", "_").replace("\\", "_")
            idx = item["idx"]
            filename = f"culturax_{source}_{idx}.txt"
            filepath = f"{charset_test_dir}/{filename}"

            # Check if file already exists
            if os.path.exists(filepath):
                print(f"  Skipping {filepath} (already exists)")
                files_written += 1
                continue

            # Try to encode the text in this charset
            try:
                text = item["text"]

                # Apply legacy character substitutions (includes Hebrew handling)
                text = apply_legacy_substitutions(text, charset_name, language_name)

                # Limit to max_chars_per_file
                if len(text) > max_chars_per_file:
                    # Try to break at a reasonable point
                    text = text[:max_chars_per_file]
                    last_newline = text.rfind("\n")
                    if last_newline > max_chars_per_file * 0.8:
                        text = text[: last_newline + 1]

                # For Windows/Mac encodings with ISO equivalents, verify that
                # the text contains bytes in the 0x80-0x9F range
                # Otherwise, the file will be detected as ISO instead of Windows/Mac
                if (
                    charset_name in WINDOWS_ENCODINGS_NEEDING_HIGH_BYTES
                    or charset_name in MAC_ENCODINGS_NEEDING_HIGH_BYTES
                ):
                    if not has_windows_high_bytes(text, charset_name):
                        print(
                            f"  Skipping item {idx} for {charset_name}: "
                            f"No high bytes (0x80-0x9F) found - would be detected as ISO"
                        )
                        continue

                encoded_text = text.encode(charset_name)

                # Write the file
                with open(filepath, "wb") as f:
                    f.write(encoded_text)

                print(f"  Wrote {filepath} ({len(encoded_text)} bytes)")
                files_written += 1

            except (UnicodeEncodeError, LookupError) as e:
                # This text can't be encoded in this charset, skip it
                error_msg = str(e)
                # Try to extract the problematic character and show its UTF-8 representation
                if isinstance(e, UnicodeEncodeError):
                    try:
                        # Extract the character(s) that failed to encode
                        error_msg = f"{error_msg} (Problem character(s): {e.object[e.start : e.end]})"
                    except Exception:
                        pass  # If extraction fails, just use original error message
                print(f"  Skipping item {idx} for {charset_name}: {error_msg}")
                continue

        if files_written == 0:
            print(f"  Warning: Could not write any test files for {charset_name}")
        elif files_written < num_files:
            print(
                f"  Warning: Only wrote {files_written}/{num_files} files for {charset_name}"
            )


def generate_test_files_for_language(
    language: str,
    *,
    test_dir: str,
    max_chars_per_file: int,
    num_files: int,
):
    """Generate test files for a single language."""
    # Validate language
    language = language.title()
    lang_metadata = LANGUAGES.get(language)
    if not lang_metadata:
        print(
            f"Unknown language: {language}. Skipping.\n"
            f"Available languages: {', '.join(sorted(LANGUAGES.keys()))}"
        )
        return

    print(
        f"\n{language}\n"
        f"----------------------------------------------------------------\n"
        f"ISO Code: {lang_metadata.iso_code}\n"
        f"Charsets: {', '.join(lang_metadata.charsets)}"
    )

    write_culturax_test_files(
        language=lang_metadata.iso_code,
        language_name=language,
        charsets=lang_metadata.charsets,
        num_training_docs=lang_metadata.num_training_docs,
        test_dir=test_dir,
        max_chars_per_file=max_chars_per_file,
        num_files=num_files,
    )


def main():
    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "language",
        help="The name of the language to generate test files for. "
        "If no language is specified, test files for all languages "
        "known to chardet will be generated.",
        nargs="*",
        default=list(sorted(LANGUAGES.keys())),
    )
    parser.add_argument(
        "-d",
        "--test-dir",
        help="Root directory for test files.",
        default="tests",
    )
    parser.add_argument(
        "-c",
        "--max-chars",
        help="Maximum number of characters per test file.",
        type=int,
        default=3000,
    )
    parser.add_argument(
        "-n",
        "--num-files",
        help="Number of test files to generate per charset.",
        type=int,
        default=3,
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    # Validate requirements
    if not HAVE_DATASETS:
        print(
            "ERROR: The datasets package is required to use CulturaX.\n"
            "Install with: pip install datasets or uv pip install datasets"
        )
        sys.exit(1)

    for language in args.language:
        generate_test_files_for_language(
            language,
            test_dir=args.test_dir,
            max_chars_per_file=args.max_chars,
            num_files=args.num_files,
        )


if __name__ == "__main__":
    main()

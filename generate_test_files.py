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

        # NFC normalize to reduce characters to single code points where possible
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
                # Limit to max_chars_per_file
                if len(text) > max_chars_per_file:
                    # Try to break at a reasonable point
                    text = text[:max_chars_per_file]
                    last_newline = text.rfind("\n")
                    if last_newline > max_chars_per_file * 0.8:
                        text = text[: last_newline + 1]

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

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
Calculate the number of documents needed to reach 300M characters for each language.

This is a one-off script to populate the num_training_docs field in the Language
metadata. Run this script and it will output the numbers to add to languages.py.
"""

import sys

try:
    from datasets import load_dataset

    HAVE_DATASETS = True
except Exception:
    HAVE_DATASETS = False
    load_dataset = None  # type: ignore

from chardet.metadata.languages import LANGUAGES

TARGET_CHARS = 300_000_000


def calculate_doc_count_for_language(language_name: str, iso_code: str) -> int | None:
    """Calculate how many documents are needed to reach TARGET_CHARS for a language."""
    if not HAVE_DATASETS:
        print("ERROR: datasets package is required", file=sys.stderr)
        return None

    print(f"\n{language_name} (ISO: {iso_code})")
    print("-" * 60)

    try:
        assert load_dataset is not None
        dataset = load_dataset(
            "uonlp/CulturaX",
            iso_code,
            split="train",
            streaming=True,
        )
    except Exception as e:
        print(f"  ERROR: Could not load dataset: {e}")
        return None

    char_count = 0
    doc_count = 0

    for item in dataset:
        text = item.get("text", "")  # type: ignore
        if not text:
            continue

        char_count += len(text)
        doc_count += 1

        # Print progress every 10,000 documents
        if doc_count % 10_000 == 0:
            print(
                f"  Progress: {doc_count:,} docs, {char_count:,} chars ({char_count / TARGET_CHARS * 100:.1f}%)"
            )

        if char_count >= TARGET_CHARS:
            print(
                f"  RESULT: {doc_count:,} documents = {char_count:,} characters\n"
                f"  Add this to languages.py: num_training_docs={doc_count}"
            )
            return doc_count

    # If we reach here, the dataset has fewer than TARGET_CHARS
    print(
        f"  WARNING: Dataset exhausted at {doc_count:,} docs, {char_count:,} chars\n"
        f"  Add this to languages.py: num_training_docs={doc_count}"
    )
    return doc_count


def main():
    if not HAVE_DATASETS:
        print(
            "ERROR: The datasets package is required.\n"
            "Install with: pip install datasets or uv pip install datasets"
        )
        sys.exit(1)

    print("Calculating document counts for each language...")
    print(f"Target: {TARGET_CHARS:,} characters per language\n")

    results = {}
    for language_name, lang_metadata in sorted(LANGUAGES.items()):
        # Skip if already has a count
        if lang_metadata.num_training_docs is not None:
            print(
                f"\n{language_name}: Already has count ({lang_metadata.num_training_docs:,}), skipping"
            )
            continue

        doc_count = calculate_doc_count_for_language(
            language_name, lang_metadata.iso_code
        )
        if doc_count is not None:
            results[language_name] = doc_count

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY - Copy these values to languages.py:")
    print("=" * 60)
    for language_name, doc_count in sorted(results.items()):
        print(f"{language_name}: num_training_docs={doc_count}")


if __name__ == "__main__":
    main()

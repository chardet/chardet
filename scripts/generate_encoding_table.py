#!/usr/bin/env python
"""Generate the supported encodings RST table from the registry."""

from __future__ import annotations

import codecs
import contextlib
import functools

from chardet.enums import EncodingEra
from chardet.registry import REGISTRY

ERA_DISPLAY = {
    EncodingEra.MODERN_WEB: "Modern Web",
    EncodingEra.LEGACY_ISO: "Legacy ISO",
    EncodingEra.LEGACY_MAC: "Legacy Mac",
    EncodingEra.LEGACY_REGIONAL: "Legacy Regional",
    EncodingEra.DOS: "DOS",
    EncodingEra.MAINFRAME: "Mainframe (EBCDIC)",
}

ERA_ORDER = list(ERA_DISPLAY)

# The registry's ``is_multibyte`` flag marks the CJK byte structure that the
# structural stage probes, and it is deliberately off for UTF-8, UTF-16 and
# UTF-32.  Readers of the table want the plain meaning instead, so the column
# asks the codec whether any character takes more than one byte.
_PROBE_CHARS = [chr(c) for c in range(0x20, 0x10000) if not 0xD800 <= c <= 0xDFFF]


@functools.cache
def encodes_multibyte(codec: str) -> bool:
    """Return whether *codec* ever encodes one character as several bytes."""
    for char in _PROBE_CHARS:
        try:
            encoded = char.encode(codec)
        except (UnicodeEncodeError, ValueError):
            continue
        if len(encoded) > 1:
            return True
    return False


def main() -> None:
    """Print the supported encodings RST table to stdout."""
    # Count unique Python codec names reachable via registry names + aliases
    codec_names: set[str] = set()
    for info in REGISTRY.values():
        with contextlib.suppress(LookupError):
            codec_names.add(info.name)
        for alias in info.aliases:
            with contextlib.suppress(LookupError):
                codec_names.add(codecs.lookup(alias).name)
    total_codecs = len(codec_names)

    print("Supported Encodings")
    print("===================")
    print()
    print(f"chardet recognises **{total_codecs} Python text encodings** via")
    print(f"{len(REGISTRY)} detection targets and their aliases, across six")
    print("encoding eras.")
    print("The default :attr:`~chardet.EncodingEra.ALL` era considers every")
    print("encoding below. Pass a narrower era such as")
    print(":attr:`~chardet.EncodingEra.MODERN_WEB` to restrict the candidates.")
    print("The multi-byte column says whether the codec can spend more than one")
    print("byte on a single character.")
    print()

    for era in ERA_ORDER:
        entries = sorted(
            [e for e in REGISTRY.values() if e.era == era],
            key=lambda e: e.name,
        )
        title = ERA_DISPLAY[era]
        print(title)
        print("-" * len(title))
        print()
        print(".. list-table::")
        print("   :header-rows: 1")
        print("   :widths: 25 50 15")
        print()
        print("   * - Encoding")
        print("     - Aliases")
        print("     - Multi-byte")
        for e in entries:
            aliases = ", ".join(e.aliases) if e.aliases else "\u2014"
            mb = "Yes" if encodes_multibyte(e.name) else "No"
            print(f"   * - {e.name}")
            print(f"     - {aliases}")
            print(f"     - {mb}")
        print()


if __name__ == "__main__":
    main()

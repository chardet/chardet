#!/usr/bin/env python
"""Generate the supported encodings RST table from the registry."""

from __future__ import annotations

import codecs
import contextlib

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
            mb = "Yes" if e.is_multibyte else "No"
            print(f"   * - {e.name}")
            print(f"     - {aliases}")
            print(f"     - {mb}")
        print()


if __name__ == "__main__":
    main()

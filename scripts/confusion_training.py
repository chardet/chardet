"""Build-time confusion group computation and serialization.

Used by ``scripts/train.py`` to compute confusion groups from the encoding
registry and serialize them into ``confusion.bin``.  Not imported at runtime.
"""

from __future__ import annotations

import codecs
import struct
import unicodedata
from pathlib import Path

from chardet.pipeline.confusion import _CATEGORY_TO_INT, DistinguishingMaps
from chardet.registry import REGISTRY


def _decode_byte_table(codec_name: str) -> list[str | None]:
    """Decode all 256 byte values through a codec, returning Unicode chars.

    Returns a list of 256 entries. Each entry is the decoded character,
    or None if the byte is not decodable.
    """
    table: list[str | None] = []
    for b in range(256):
        try:
            table.append(bytes([b]).decode(codec_name))
        except (UnicodeDecodeError, LookupError):
            table.append(None)
    return table


def _compute_pairwise_similarity(
    table_a: list[str | None],
    table_b: list[str | None],
) -> tuple[float, frozenset[int]]:
    """Compute similarity between two byte tables.

    Returns (similarity_ratio, distinguishing_bytes) where similarity is
    the fraction of byte positions that decode to the same character.
    """
    same = 0
    diff_bytes: list[int] = []
    for b in range(256):
        if table_a[b] == table_b[b]:
            same += 1
        else:
            diff_bytes.append(b)
    return same / 256, frozenset(diff_bytes)


def compute_confusion_groups(
    threshold: float = 0.80,
) -> list[frozenset[str]]:
    """Compute confusion groups from the encoding registry.

    Returns a list of frozensets, each containing encoding names that
    share more than ``threshold`` fraction of their byte mappings.
    Only single-byte encodings are considered.
    """
    # Collect single-byte encodings with valid codecs
    single_byte = []
    for enc in REGISTRY.values():
        if enc.is_multibyte:
            continue
        try:
            codecs.lookup(enc.name)
            single_byte.append(enc)
        except LookupError:
            continue

    # Compute byte tables
    tables: dict[str, list[str | None]] = {}
    for enc in single_byte:
        tables[enc.name] = _decode_byte_table(enc.name)

    # Build adjacency: which encodings are similar
    adjacency: dict[str, set[str]] = {enc.name: set() for enc in single_byte}
    names = [enc.name for enc in single_byte]

    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            sim, _ = _compute_pairwise_similarity(tables[name_a], tables[name_b])
            if sim >= threshold:
                adjacency[name_a].add(name_b)
                adjacency[name_b].add(name_a)

    # Transitive closure via BFS to form groups
    visited: set[str] = set()
    groups: list[frozenset[str]] = []
    for name in names:
        if name in visited or not adjacency[name]:
            continue
        # BFS
        group: set[str] = set()
        queue = [name]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            group.add(current)
            queue.extend(
                neighbor for neighbor in adjacency[current] if neighbor not in visited
            )
        if len(group) > 1:
            groups.append(frozenset(group))

    return groups


def compute_distinguishing_maps(
    threshold: float = 0.80,
    overlap_threshold: float | None = None,
) -> DistinguishingMaps:
    """Compute distinguishing byte maps and Unicode categories for all confusion pairs.

    Byte-similar siblings — similarity >= *threshold*, the classic
    within-family pairs (DOS vs DOS, EBCDIC vs EBCDIC) — are always
    generated.

    Passing *overlap_threshold* adds a second tier of cross-family
    colliders: similarity >= that value AND the two encodings serve at
    least one common registry language.  Encodings for the same languages
    produce near-tie statistical scores on that language's prose even
    though their byte tables differ wholesale (cp850 vs windows-1252 on
    Spanish), so in principle those near-ties want distinguishing-byte
    arbitration too.  The language-overlap gate keeps cross-script pairs
    out: a Latin and a Cyrillic page share exactly the ASCII half
    (similarity 0.5) but never a language.

    The tier is off by default because it was measured and does not pay.
    At 0.45 it added 141 pairs on top of the 95 siblings and grew
    confusion.bin from 8,214 to 60,623 bytes, and over the whole test
    corpus it changed exactly one file's detection — one that is wrong
    either way.  Lenient and strict accuracy are identical with it on and
    off (3113 and 2571 of 3121), and the full suite passes both ways,
    while it costs 11% of detection wall clock under mypyc because every
    additional pair is one more that arbitrates instead of returning
    early.  Enable it only alongside evidence that some pair earns its
    keep; sweeping 0.45/0.55/0.65/0.75/0.85 moved no accuracy at all.

    Returns a dict mapping (enc_a, enc_b) -> (diff_bytes, categories) where:
    - diff_bytes: frozenset of byte values that decode differently
    - categories: {byte_val: (cat_a, cat_b)} Unicode general categories
    """
    # Collect single-byte encodings with valid codecs
    single_byte = []
    for enc in REGISTRY.values():
        if enc.is_multibyte:
            continue
        try:
            codecs.lookup(enc.name)
            single_byte.append(enc)
        except LookupError:
            continue

    # Compute byte tables
    tables: dict[str, list[str | None]] = {}
    languages: dict[str, frozenset[str]] = {}
    for enc in single_byte:
        tables[enc.name] = _decode_byte_table(enc.name)
        languages[enc.name] = frozenset(enc.languages)

    names = [enc.name for enc in single_byte]
    result: DistinguishingMaps = {}

    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            sim, diff_bytes = _compute_pairwise_similarity(
                tables[name_a], tables[name_b]
            )
            cross_family = (
                overlap_threshold is not None
                and sim >= overlap_threshold
                and bool(languages[name_a] & languages[name_b])
            )
            if sim < threshold and not cross_family:
                continue
            # Serialization stores the diff count as a u8.
            if len(diff_bytes) > 255:
                continue
            # Build category map for distinguishing bytes
            categories: dict[int, tuple[str, str]] = {}
            for b in diff_bytes:
                char_a = tables[name_a][b]
                char_b = tables[name_b][b]
                cat_a = unicodedata.category(char_a) if char_a else "Cn"
                cat_b = unicodedata.category(char_b) if char_b else "Cn"
                categories[b] = (cat_a, cat_b)
            result[(name_a, name_b)] = (diff_bytes, categories)

    return result


def serialize_confusion_data(maps: DistinguishingMaps, output_path: Path) -> int:
    """Serialize confusion group data to binary format.

    Format:
      uint16: number_of_pairs
      Per pair:
        uint8:  name_a_length
        bytes:  name_a (UTF-8)
        uint8:  name_b_length
        bytes:  name_b (UTF-8)
        uint8:  num_distinguishing_bytes
        Per distinguishing byte:
          uint8:  byte_value
          uint8:  cat_a (enum)
          uint8:  cat_b (enum)

    Returns file size in bytes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(struct.pack("!H", len(maps)))
        for (name_a, name_b), (diff_bytes, categories) in sorted(maps.items()):
            a_bytes = name_a.encode("utf-8")
            b_bytes = name_b.encode("utf-8")
            f.write(struct.pack("!B", len(a_bytes)))
            f.write(a_bytes)
            f.write(struct.pack("!B", len(b_bytes)))
            f.write(b_bytes)
            sorted_diffs = sorted(diff_bytes)
            f.write(struct.pack("!B", len(sorted_diffs)))
            for bv in sorted_diffs:
                cat_a, cat_b = categories[bv]
                f.write(
                    struct.pack(
                        "!BBB",
                        bv,
                        _CATEGORY_TO_INT.get(cat_a, 29),
                        _CATEGORY_TO_INT.get(cat_b, 29),
                    )
                )
    return output_path.stat().st_size


def deserialize_confusion_data(input_path: Path) -> DistinguishingMaps:
    """Load confusion group data from binary format."""
    from chardet.pipeline.confusion import (  # noqa: PLC0415
        deserialize_confusion_data_from_bytes,
    )

    data = input_path.read_bytes()
    return deserialize_confusion_data_from_bytes(data)

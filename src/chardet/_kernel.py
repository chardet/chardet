"""Hot numeric kernels, shared by the pure-Python and compiled builds.

This module is ordinary Python with no third-party imports: it runs as-is on
PyPy and in pure-Python installs.  When a compiled wheel is built,
``_kernel.pxd`` supplies C type declarations for these same functions and
Cython compiles this file to native code — the ``.py`` stays the one and only
implementation.

Note: ``from __future__ import annotations`` is intentionally omitted to match
the modules mypyc compiles, which import from here.

``dot_packed`` reads the profile's parallel ``array('i')`` buffers rather than
its dense 65536-entry table.  Compiled, that is the difference between a gather
through a Python list and a C loop over two contiguous int32 buffers.  The
interpreter pays for it — ``array`` indexing boxes an int where a list returns
a cached one — which is the trade this build makes deliberately.
"""

import array


def dot_packed(idx: array.array, vals: array.array, model: bytes) -> int:
    """Return the dot product of a packed bigram profile with a model table.

    :param idx: ``array('i')`` of bigram indices, in first-encounter order.
        Deliberately *not* sorted --- do not add a binary search or an
        early exit over it.
    :param vals: ``array('i')`` of weights, parallel to *idx*.
    :param model: 65536-byte model lookup table.
    :returns: Sum of ``model[idx[k]] * vals[k]`` over all ``k``.
    """
    dot = 0
    n = len(idx)
    for i in range(n):
        dot += model[idx[i]] * vals[i]
    return dot


def build_freq(data: bytes, idf: bytes, whitespace: bytes, freq: list) -> tuple:
    """Fill *freq* with IDF-weighted bigram counts for *data*.

    Repeated-whitespace bigrams are skipped, matching the whitespace-run
    collapsing that training does before counting.

    :param data: Raw bytes to profile (at least two bytes long).
    :param idf: 65536-byte IDF weight table.
    :param whitespace: 256-entry table, non-zero at each skipped byte value.
    :param freq: Zeroed 65536-entry list, filled in place.
    :returns: A ``(nonzero, weight_sum)`` tuple.
    """
    nonzero = []
    w_sum = 0
    n = len(data) - 1
    for i in range(n):
        b1 = data[i]
        b2 = data[i + 1]
        if b1 == b2 and whitespace[b1]:
            continue
        idx = (b1 << 8) | b2
        w = idf[idx]
        c = freq[idx]
        if c == 0:
            nonzero.append(idx)
        freq[idx] = c + w
        w_sum += w
    return nonzero, w_sum


def pack_profile(nonzero: list, freq: list) -> tuple:
    """Return parallel ``array('i')`` index/value buffers for a dense profile.

    ``int32`` holds any weight a truncated input can produce: statistical
    scoring caps its input at 16384 bytes, so no weight exceeds ``255 * 16383``
    (about 4.2 million) against an int32 ceiling of 2.1 billion.  The bound is
    the caller's to keep --- see :class:`~chardet.models.BigramProfile`, which
    documents the input limit that makes it hold.

    :param nonzero: Bigram indices with non-zero weight.
    :param freq: Dense 65536-entry weight table.
    :returns: An ``(idx, vals)`` tuple of ``array('i')`` buffers.
    """
    vals = array.array("i", [0]) * len(nonzero)
    n = len(nonzero)
    for i in range(n):
        vals[i] = freq[nonzero[i]]
    return array.array("i", nonzero), vals


def dot_rowmax(nonzero_rows: list, row_freq: list, rowmax: bytes) -> int:
    """Return the row-maxima upper bound for a profile against one model.

    :param nonzero_rows: Lead bytes with non-zero total weight.
    :param row_freq: 256-entry per-lead-byte weight totals.
    :param rowmax: 256-byte per-lead-byte model maxima.
    :returns: Sum of ``rowmax[b] * row_freq[b]`` over ``b`` in *nonzero_rows*.
    """
    dot = 0
    for b1 in nonzero_rows:
        v = row_freq[b1]
        dot += rowmax[b1] * v
    return dot

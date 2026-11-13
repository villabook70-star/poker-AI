"""Exact Texas Hold'em hand evaluation (5 to 7 cards).

Two implementations share the same lookup tables and produce identical values:

* :func:`evaluate` - pure Python, for single hands.
* :func:`evaluate_many` - NumPy vectorised, for Monte Carlo / enumeration.

The value is an integer where **higher is better**:
``value = category << 20 | packed_ranks`` with five 4-bit rank nibbles
(most significant first). Categories: 0 high card ... 8 straight flush.
This is an *exact* evaluation, not an approximation.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

HIGH_CARD, ONE_PAIR, TWO_PAIR, THREE_OF_A_KIND, STRAIGHT, FLUSH, FULL_HOUSE, FOUR_OF_A_KIND, STRAIGHT_FLUSH = range(9)

CATEGORY_NAMES = [
    "high_card", "one_pair", "two_pair", "three_of_a_kind", "straight",
    "flush", "full_house", "four_of_a_kind", "straight_flush",
]
CATEGORY_NAMES_ES = [
    "Carta alta", "Pareja", "Doble pareja", "Trío", "Escalera",
    "Color", "Full", "Póker", "Escalera de color",
]

# ---------------------------------------------------------------------------
# Lookup tables over 13-bit rank masks (bit r set <=> rank r present)
# ---------------------------------------------------------------------------
_N = 1 << 13


def _build_tables():
    hb = np.zeros(_N, dtype=np.int64)        # highest set bit (rank), -1 for 0
    pc = np.zeros(_N, dtype=np.int64)        # popcount
    top5 = np.zeros(_N, dtype=np.int64)      # top five ranks packed as nibbles
    straight = np.full(_N, -1, dtype=np.int64)  # high rank of best straight or -1
    for m in range(_N):
        bits = [r for r in range(12, -1, -1) if m >> r & 1]
        hb[m] = bits[0] if bits else -1
        pc[m] = len(bits)
        v = 0
        for r in bits[:5]:
            v = (v << 4) | r
        # left-align into 5 nibbles so shorter lists compare consistently
        v <<= 4 * (5 - min(5, len(bits)))
        top5[m] = v
        # straights: ace can play low
        mm = (m << 1) | ((m >> 12) & 1)  # bit0 = ace-low, bit r+1 = rank r
        best = -1
        for high in range(13, 3, -1):     # high in mm indexing (A=13 .. 5=4)
            need = 0b11111 << (high - 4)
            if mm & need == need:
                best = high - 1           # convert back to rank index
                break
        straight[m] = best
    return hb, pc, top5, straight


HB, POPCOUNT, TOP5, STRAIGHT_HIGH = _build_tables()
HB_L, POPCOUNT_L, TOP5_L, STRAIGHT_HIGH_L = HB.tolist(), POPCOUNT.tolist(), TOP5.tolist(), STRAIGHT_HIGH.tolist()


def _pack(*ranks: int) -> int:
    v = 0
    for r in ranks:
        v = (v << 4) | r
    v <<= 4 * (5 - len(ranks))
    return v


# ---------------------------------------------------------------------------
# Pure Python
# ---------------------------------------------------------------------------

def evaluate(cards: Sequence[int]) -> int:
    """Evaluate 5-7 cards (ints 0..51). Returns comparable int, higher wins."""
    n = len(cards)
    if n < 5 or n > 7:
        raise ValueError("evaluate() needs 5 to 7 cards")
    rank_counts = [0] * 13
    suit_masks = [0, 0, 0, 0]
    all_mask = 0
    for c in cards:
        r = c >> 2
        s = c & 3
        rank_counts[r] += 1
        suit_masks[s] |= 1 << r
        all_mask |= 1 << r

    # flush / straight flush
    for sm in suit_masks:
        if POPCOUNT_L[sm] >= 5:
            sh = STRAIGHT_HIGH_L[sm]
            if sh >= 0:
                return (STRAIGHT_FLUSH << 20) | _pack(sh)
            flush_val = (FLUSH << 20) | TOP5_L[sm]
            break
    else:
        flush_val = -1

    m4 = m3 = m2 = 0
    for r in range(13):
        c = rank_counts[r]
        if c == 4:
            m4 |= 1 << r
        elif c == 3:
            m3 |= 1 << r
        elif c == 2:
            m2 |= 1 << r

    if m4:
        q = HB_L[m4]
        kicker = HB_L[all_mask & ~(1 << q)]
        return (FOUR_OF_A_KIND << 20) | _pack(q, kicker)
    if m3 and (POPCOUNT_L[m3] >= 2 or m2):
        t = HB_L[m3]
        p = HB_L[(m3 | m2) & ~(1 << t)]
        return (FULL_HOUSE << 20) | _pack(t, p)
    if flush_val >= 0:
        return flush_val
    sh = STRAIGHT_HIGH_L[all_mask]
    if sh >= 0:
        return (STRAIGHT << 20) | _pack(sh)
    if m3:
        t = HB_L[m3]
        rest = all_mask & ~(1 << t)
        return (THREE_OF_A_KIND << 20) | ((t << 16) | (TOP5_L[rest] >> 12 << 8))
    if POPCOUNT_L[m2] >= 2:
        p1 = HB_L[m2]
        p2 = HB_L[m2 & ~(1 << p1)]
        k = HB_L[all_mask & ~(1 << p1) & ~(1 << p2)]
        return (TWO_PAIR << 20) | _pack(p1, p2, k)
    if m2:
        p = HB_L[m2]
        rest = all_mask & ~(1 << p)
        return (ONE_PAIR << 20) | ((p << 16) | (TOP5_L[rest] >> 8 << 4))
    return (HIGH_CARD << 20) | TOP5_L[all_mask]


def category(value: int) -> int:
    return value >> 20


def describe(value: int, lang: str = "es") -> str:
    """Human readable description of a hand value (category + key ranks)."""
    from .cards import RANK_CHARS

    cat = value >> 20
    nib = [(value >> (16 - 4 * i)) & 0xF for i in range(5)]
    names = CATEGORY_NAMES_ES if lang == "es" else CATEGORY_NAMES
    base = names[cat]
    if cat in (STRAIGHT, STRAIGHT_FLUSH):
        return f"{base} al {RANK_CHARS[nib[0]]}" if lang == "es" else f"{base}, {RANK_CHARS[nib[0]]} high"
    if cat == FOUR_OF_A_KIND:
        return f"{base} de {RANK_CHARS[nib[0]]}" if lang == "es" else f"{base}, {RANK_CHARS[nib[0]]}s"
    if cat == FULL_HOUSE:
        return (f"{base} de {RANK_CHARS[nib[0]]} con {RANK_CHARS[nib[1]]}" if lang == "es"
                else f"{base}, {RANK_CHARS[nib[0]]}s full of {RANK_CHARS[nib[1]]}s")
    if cat == THREE_OF_A_KIND:
        return f"{base} de {RANK_CHARS[nib[0]]}" if lang == "es" else f"{base}, {RANK_CHARS[nib[0]]}s"
    if cat == TWO_PAIR:
        return (f"{base}, {RANK_CHARS[nib[0]]} y {RANK_CHARS[nib[1]]}" if lang == "es"
                else f"{base}, {RANK_CHARS[nib[0]]}s and {RANK_CHARS[nib[1]]}s")
    if cat == ONE_PAIR:
        return f"{base} de {RANK_CHARS[nib[0]]}" if lang == "es" else f"{base}, {RANK_CHARS[nib[0]]}s"
    return f"{base} {RANK_CHARS[nib[0]]}" if lang == "es" else f"{base}, {RANK_CHARS[nib[0]]} high"


# ---------------------------------------------------------------------------
# NumPy vectorised version. ``hands`` is an int array of shape (N, k), k in 5..7
# ---------------------------------------------------------------------------
_BIT = (1 << np.arange(13)).astype(np.int64)


def evaluate_many(hands: np.ndarray) -> np.ndarray:
    hands = np.asarray(hands, dtype=np.int64)
    if hands.ndim != 2 or not 5 <= hands.shape[1] <= 7:
        raise ValueError("hands must have shape (N, 5..7)")
    n = hands.shape[0]
    ranks = hands >> 2
    suits = hands & 3
    rank_onehot = (ranks[:, :, None] == np.arange(13)).astype(np.int8)  # (N,k,13)
    rank_counts = rank_onehot.sum(axis=1)                                  # (N,13)
    all_mask = ((rank_counts > 0) * _BIT).sum(axis=1)

    # suit masks (N,4)
    suit_masks = np.zeros((n, 4), dtype=np.int64)
    for s in range(4):
        sel = (suits == s)
        suit_masks[:, s] = ((rank_onehot * sel[:, :, None]).sum(axis=1) > 0).dot(_BIT)
    suit_pc = POPCOUNT[suit_masks]
    has_flush = suit_pc.max(axis=1) >= 5
    flush_suit = suit_pc.argmax(axis=1)
    flush_mask = suit_masks[np.arange(n), flush_suit]
    sf_high = STRAIGHT_HIGH[flush_mask]

    m4 = ((rank_counts == 4) * _BIT).sum(axis=1)
    m3 = ((rank_counts == 3) * _BIT).sum(axis=1)
    m2 = ((rank_counts == 2) * _BIT).sum(axis=1)

    out = np.zeros(n, dtype=np.int64)
    done = np.zeros(n, dtype=bool)

    def pack(*cols):
        v = np.zeros(n, dtype=np.int64)
        for c in cols:
            v = (v << 4) | c
        return v << (4 * (5 - len(cols)))

    # straight flush
    sel = has_flush & (sf_high >= 0)
    out[sel] = (STRAIGHT_FLUSH << 20) | pack(np.maximum(sf_high, 0))[sel]
    done |= sel

    # quads
    sel = (~done) & (m4 > 0)
    q = HB[m4]
    kick = HB[all_mask & ~(1 << np.maximum(q, 0))]
    out[sel] = (FOUR_OF_A_KIND << 20) | pack(np.maximum(q, 0), np.maximum(kick, 0))[sel]
    done |= sel

    # full house
    sel = (~done) & (m3 > 0) & ((POPCOUNT[m3] >= 2) | (m2 > 0))
    t = HB[m3]
    p = HB[(m3 | m2) & ~(1 << np.maximum(t, 0))]
    out[sel] = (FULL_HOUSE << 20) | pack(np.maximum(t, 0), np.maximum(p, 0))[sel]
    done |= sel

    # flush
    sel = (~done) & has_flush
    out[sel] = (FLUSH << 20) | TOP5[flush_mask][sel]
    done |= sel

    # straight
    sh = STRAIGHT_HIGH[all_mask]
    sel = (~done) & (sh >= 0)
    out[sel] = (STRAIGHT << 20) | pack(np.maximum(sh, 0))[sel]
    done |= sel

    # trips
    sel = (~done) & (m3 > 0)
    t = HB[m3]
    rest = all_mask & ~(1 << np.maximum(t, 0))
    out[sel] = ((THREE_OF_A_KIND << 20) | (np.maximum(t, 0) << 16) | ((TOP5[rest] >> 12) << 8))[sel]
    done |= sel

    # two pair
    sel = (~done) & (POPCOUNT[m2] >= 2)
    p1 = HB[m2]
    p2 = HB[m2 & ~(1 << np.maximum(p1, 0))]
    k = HB[all_mask & ~(1 << np.maximum(p1, 0)) & ~(1 << np.maximum(p2, 0))]
    out[sel] = (TWO_PAIR << 20) | pack(np.maximum(p1, 0), np.maximum(p2, 0), np.maximum(k, 0))[sel]
    done |= sel

    # one pair
    sel = (~done) & (m2 > 0)
    p = HB[m2]
    rest = all_mask & ~(1 << np.maximum(p, 0))
    out[sel] = ((ONE_PAIR << 20) | (np.maximum(p, 0) << 16) | ((TOP5[rest] >> 8) << 4))[sel]
    done |= sel

    # high card
    sel = ~done
    out[sel] = (HIGH_CARD << 20) | TOP5[all_mask][sel]
    return out

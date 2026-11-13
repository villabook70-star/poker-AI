"""Hand ranges.

A *range* maps specific two-card combos (sorted tuple of card ints) to a weight
in ``(0, 1]``. Ranges can be built from standard text notation
(``"22+, A2s+, KTs+, QJs, AJo+, KQo"``), from a list of 169-class labels, or as
the top X% of a *ranking* of the 169 classes.

The ranking used for "top X%" ranges is loaded from
``data/preflop_equity_169.json`` (hands ordered by Monte Carlo equity against a
random hand). This is a **heuristic ordering**, not a GTO range.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .cards import (CLASS_INDEX, HAND_CLASSES, RANK_CHARS, Card, class_combo_count,
                    class_combos, hand_class)

Combo = Tuple[Card, Card]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _combo(c1: Card, c2: Card) -> Combo:
    return (c1, c2) if c1 < c2 else (c2, c1)


@dataclass
class Range:
    weights: Dict[Combo, float] = field(default_factory=dict)
    label: str = ""

    # -- construction -----------------------------------------------------
    @classmethod
    def from_text(cls, text: str) -> "Range":
        r = cls(label=text.strip())
        for token in re.split(r"[,\s]+", text.strip()):
            if not token:
                continue
            weight = 1.0
            if ":" in token:
                token, w = token.split(":", 1)
                weight = float(w)
                if not 0 < weight <= 1:
                    raise ValueError(f"Weight out of range in {token!r}")
            for label in expand_token(token):
                r.add_class(label, weight)
        return r

    @classmethod
    def from_classes(cls, labels: Iterable[str], weight: float = 1.0, label: str = "") -> "Range":
        r = cls(label=label)
        for lab in labels:
            r.add_class(lab, weight)
        return r

    @classmethod
    def from_combos(cls, combos: Iterable[Combo], label: str = "") -> "Range":
        r = cls(label=label)
        for c1, c2 in combos:
            r.weights[_combo(c1, c2)] = 1.0
        return r

    @classmethod
    def single(cls, c1: Card, c2: Card) -> "Range":
        return cls({_combo(c1, c2): 1.0}, label=hand_class(c1, c2))

    @classmethod
    def random_hand(cls) -> "Range":
        return cls.from_classes(HAND_CLASSES, label="random")

    @classmethod
    def top_percent(cls, percent: float, ranking: Optional[List[str]] = None) -> "Range":
        """Top ``percent`` of all 1326 combos by the given class ranking (heuristic)."""
        ranking = ranking or default_ranking()
        target = 1326 * max(0.0, min(100.0, percent)) / 100.0
        r = cls(label=f"top {percent:g}%")
        total = 0
        for lab in ranking:
            n = class_combo_count(lab)
            if total >= target:
                break
            if total + n <= target + 1e-9:
                r.add_class(lab, 1.0)
                total += n
            else:
                # partial weight on the boundary class
                frac = (target - total) / n
                if frac > 0.05:
                    r.add_class(lab, round(frac, 3))
                total = target
        return r

    def add_class(self, label: str, weight: float = 1.0) -> None:
        for c1, c2 in class_combos(label):
            self.weights[_combo(c1, c2)] = weight

    # -- queries ----------------------------------------------------------
    def remove_cards(self, dead: Iterable[Card]) -> "Range":
        dead_set = set(dead)
        return Range({k: v for k, v in self.weights.items() if k[0] not in dead_set and k[1] not in dead_set},
                     label=self.label)

    def total_weight(self) -> float:
        return sum(self.weights.values())

    def combo_count(self) -> int:
        return len(self.weights)

    def percent_of_all(self) -> float:
        return 100.0 * self.total_weight() / 1326.0

    def class_weights(self) -> Dict[str, float]:
        """Average weight per 169-class (0..1) for display in a 13x13 grid."""
        acc: Dict[str, List[float]] = {}
        for (c1, c2), w in self.weights.items():
            acc.setdefault(hand_class(c1, c2), []).append(w)
        return {lab: round(sum(ws) / class_combo_count(lab), 4) for lab, ws in acc.items()}

    def contains(self, c1: Card, c2: Card) -> float:
        return self.weights.get(_combo(c1, c2), 0.0)

    def to_text(self) -> str:
        """Compact textual representation (one token per class with weight)."""
        cw = self.class_weights()
        toks = []
        for lab in HAND_CLASSES:
            if lab in cw:
                toks.append(lab if cw[lab] >= 0.999 else f"{lab}:{cw[lab]:.2f}")
        return ", ".join(toks)

    def __len__(self) -> int:
        return len(self.weights)


# ---------------------------------------------------------------------------
# Notation expansion
# ---------------------------------------------------------------------------

def _ri(ch: str) -> int:
    ch = ch.upper()
    if ch not in RANK_CHARS:
        raise ValueError(f"Invalid rank {ch!r}")
    return RANK_CHARS.index(ch)


def expand_token(token: str) -> List[str]:
    """Expand one notation token into 169-class labels."""
    tok = token.strip()
    if tok.lower() == "random" or tok == "*":
        return list(HAND_CLASSES)
    m = re.fullmatch(r"([2-9TJQKA])([2-9TJQKA])([so]?)(\+?)", tok, re.I)
    if m:
        a, b, kind, plus = m.groups()
        hi, lo = max(_ri(a), _ri(b)), min(_ri(a), _ri(b))
        kinds = [kind.lower()] if kind else (["s", "o"] if hi != lo else [""])
        out = []
        if hi == lo:  # pair, possibly with +
            for r in range(hi, 13 if plus else hi + 1):
                out.append(RANK_CHARS[r] * 2)
            return out
        for k in kinds:
            if plus:  # A2s+ -> A2s..AKs (low rank increases up to hi-1)
                for lo2 in range(lo, hi):
                    out.append(RANK_CHARS[hi] + RANK_CHARS[lo2] + k)
            else:
                out.append(RANK_CHARS[hi] + RANK_CHARS[lo] + k)
        return out
    m = re.fullmatch(r"([2-9TJQKA])([2-9TJQKA])([so]?)-([2-9TJQKA])([2-9TJQKA])([so]?)", tok, re.I)
    if m:
        a1, b1, k1, a2, b2, k2 = m.groups()
        h1, l1, h2, l2 = _ri(a1), _ri(b1), _ri(a2), _ri(b2)
        out = []
        if h1 == l1 and h2 == l2:  # JJ-88
            for r in range(min(h1, h2), max(h1, h2) + 1):
                out.append(RANK_CHARS[r] * 2)
            return out
        kind = (k1 or k2).lower()
        kinds = [kind] if kind else ["s", "o"]
        hi1, lo1 = max(h1, l1), min(h1, l1)
        hi2, lo2 = max(h2, l2), min(h2, l2)
        if hi1 == hi2:  # same high card: AJs-A7s
            for lo in range(min(lo1, lo2), max(lo1, lo2) + 1):
                for k in kinds:
                    out.append(RANK_CHARS[hi1] + RANK_CHARS[lo] + k)
            return out
        if hi1 - lo1 == hi2 - lo2:  # same gap: T9s-54s
            gap = hi1 - lo1
            for hi in range(min(hi1, hi2), max(hi1, hi2) + 1):
                for k in kinds:
                    out.append(RANK_CHARS[hi] + RANK_CHARS[hi - gap] + k)
            return out
        raise ValueError(f"Unsupported range span: {token!r}")
    raise ValueError(f"Invalid range token: {token!r}")


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------
_RANKING_CACHE: Optional[List[str]] = None
_EQUITY_DATA: Optional[dict] = None


def load_equity_data() -> Optional[dict]:
    """Load the precomputed 169x169 equity matrix if available (else None)."""
    global _EQUITY_DATA
    if _EQUITY_DATA is None:
        path = os.path.join(DATA_DIR, "preflop_equity_169.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                _EQUITY_DATA = json.load(fh)
        else:
            _EQUITY_DATA = {}
    return _EQUITY_DATA or None


def default_ranking() -> List[str]:
    """169 classes ordered best-first by equity vs a random hand (heuristic)."""
    global _RANKING_CACHE
    if _RANKING_CACHE is not None:
        return _RANKING_CACHE
    data = load_equity_data()
    if data and "vs_random" in data:
        vs = data["vs_random"]
        _RANKING_CACHE = sorted(HAND_CLASSES, key=lambda h: -vs[CLASS_INDEX[h]])
    else:
        _RANKING_CACHE = _fallback_ranking()
    return _RANKING_CACHE


def _fallback_ranking() -> List[str]:
    """Deterministic fallback ordering when the equity data file is missing.

    Uses a simple score (pairs first, then high-card strength with a suited and
    connectivity bonus). Only used if ``preflop_equity_169.json`` is absent.
    """
    def score(lab: str) -> float:
        hi, lo = _ri(lab[0]), _ri(lab[1])
        if hi == lo:
            return 100 + hi * 2
        s = hi * 2 + lo * 1.1
        if lab[2] == "s":
            s += 2.2
        gap = hi - lo
        s += max(0, 3 - gap) * 0.5
        return s
    return sorted(HAND_CLASSES, key=lambda h: -score(h))


def percentile_of_class(label: str, ranking: Optional[List[str]] = None) -> float:
    """Cumulative percent of combos at or above this class in the ranking."""
    ranking = ranking or default_ranking()
    total = 0
    for lab in ranking:
        total += class_combo_count(lab)
        if lab == label:
            return 100.0 * total / 1326.0
    return 100.0

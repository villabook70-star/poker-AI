"""Card primitives.

A card is an ``int`` in ``0..51``: ``rank = card // 4`` (0 = deuce ... 12 = ace)
and ``suit = card % 4`` (0 = clubs, 1 = diamonds, 2 = hearts, 3 = spades).
Strings use the common two-character notation (``"As"``, ``"Td"``, ``"7c"``).
"""
from __future__ import annotations

import random
from typing import Iterable, List, Sequence

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"
RANK_NAMES_ES = {
    "2": "dos", "3": "tres", "4": "cuatro", "5": "cinco", "6": "seis", "7": "siete",
    "8": "ocho", "9": "nueve", "T": "diez", "J": "jota", "Q": "reina", "K": "rey", "A": "as",
}

Card = int


def make_card(rank: int, suit: int) -> Card:
    if not 0 <= rank <= 12 or not 0 <= suit <= 3:
        raise ValueError(f"Invalid rank/suit: {rank}/{suit}")
    return rank * 4 + suit


def rank_of(card: Card) -> int:
    return card // 4


def suit_of(card: Card) -> int:
    return card % 4


def parse_card(text: str) -> Card:
    """Parse ``"As"`` -> 51. Accepts upper/lower case and ``"10"`` for ten."""
    s = text.strip().replace("10", "T")
    if len(s) != 2:
        raise ValueError(f"Invalid card: {text!r}")
    r, su = s[0].upper(), s[1].lower()
    if r not in RANK_CHARS or su not in SUIT_CHARS:
        raise ValueError(f"Invalid card: {text!r}")
    return make_card(RANK_CHARS.index(r), SUIT_CHARS.index(su))


def parse_cards(text: str | Sequence[str]) -> List[Card]:
    """Parse ``"AsKd"``, ``"As Kd"``, ``"As,Kd"`` or a list of card strings."""
    if isinstance(text, str):
        cleaned = text.replace(",", " ").replace("10", "T")
        tokens = cleaned.split()
        if len(tokens) == 1 and len(tokens[0]) > 2:
            tok = tokens[0]
            tokens = [tok[i:i + 2] for i in range(0, len(tok), 2)]
    else:
        tokens = list(text)
    cards = [parse_card(t) for t in tokens if t]
    if len(set(cards)) != len(cards):
        raise ValueError(f"Duplicate cards in {text!r}")
    return cards


def card_str(card: Card) -> str:
    return RANK_CHARS[rank_of(card)] + SUIT_CHARS[suit_of(card)]


def cards_str(cards: Iterable[Card]) -> str:
    return " ".join(card_str(c) for c in cards)


FULL_DECK: List[Card] = list(range(52))


class Deck:
    """A shuffled deck supporting deterministic seeding (for tests / replays)."""

    def __init__(self, seed: int | None = None, exclude: Iterable[Card] = ()):
        self._rng = random.Random(seed)
        excluded = set(exclude)
        self.cards: List[Card] = [c for c in FULL_DECK if c not in excluded]
        self._rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> List[Card]:
        if n > len(self.cards):
            raise ValueError("Not enough cards in deck")
        out = self.cards[:n]
        del self.cards[:n]
        return out

    def remove(self, cards: Iterable[Card]) -> None:
        s = set(cards)
        self.cards = [c for c in self.cards if c not in s]

    def __len__(self) -> int:
        return len(self.cards)


# ---------------------------------------------------------------------------
# 169 starting-hand classes ("AKs", "T9o", "77")
# ---------------------------------------------------------------------------

def hand_class(c1: Card, c2: Card) -> str:
    """Return the 169-class label of a two-card hand (e.g. ``"AKs"``)."""
    r1, r2 = rank_of(c1), rank_of(c2)
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        return RANK_CHARS[hi] * 2
    suffix = "s" if suit_of(c1) == suit_of(c2) else "o"
    return RANK_CHARS[hi] + RANK_CHARS[lo] + suffix


def all_hand_classes() -> List[str]:
    """All 169 classes ordered: pairs AA..22, then suited/offsuit by high rank."""
    out: List[str] = []
    for hi in range(12, -1, -1):
        for lo in range(hi, -1, -1):
            if hi == lo:
                out.append(RANK_CHARS[hi] * 2)
            else:
                out.append(RANK_CHARS[hi] + RANK_CHARS[lo] + "s")
                out.append(RANK_CHARS[hi] + RANK_CHARS[lo] + "o")
    return out


HAND_CLASSES: List[str] = all_hand_classes()
CLASS_INDEX = {h: i for i, h in enumerate(HAND_CLASSES)}


def class_combos(label: str) -> List[tuple[Card, Card]]:
    """All specific two-card combos belonging to a 169-class label."""
    label = label.strip()
    if len(label) == 2:
        r = RANK_CHARS.index(label[0].upper())
        cs = [make_card(r, s) for s in range(4)]
        return [(cs[i], cs[j]) for i in range(4) for j in range(i + 1, 4)]
    if len(label) != 3:
        raise ValueError(f"Invalid hand class: {label!r}")
    r1, r2 = RANK_CHARS.index(label[0].upper()), RANK_CHARS.index(label[1].upper())
    if r1 == r2:
        raise ValueError(f"Invalid hand class: {label!r}")
    kind = label[2].lower()
    if kind == "s":
        return [(make_card(r1, s), make_card(r2, s)) for s in range(4)]
    if kind == "o":
        return [(make_card(r1, s1), make_card(r2, s2)) for s1 in range(4) for s2 in range(4) if s1 != s2]
    raise ValueError(f"Invalid hand class: {label!r}")


def class_combo_count(label: str) -> int:
    if len(label) == 2:
        return 6
    return 4 if label[2].lower() == "s" else 12

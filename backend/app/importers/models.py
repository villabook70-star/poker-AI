"""Neutral hand-history model produced by every importer."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class HHAction:
    street: str          # preflop | flop | turn | river
    player: str
    action: str          # fold | check | call | bet | raise | post_sb | post_bb | post_ante
    amount: int = 0      # for bet/raise: total bet-to amount on that street; for call: amount called
    all_in: bool = False


@dataclass
class HHPlayer:
    name: str
    seat: int
    stack: int
    position: str = ""   # BTN | SB | BB | BTN/SB
    hole_cards: List[str] = field(default_factory=list)


@dataclass
class HandHistory:
    hand_id: str
    source: str
    hero: str
    small_blind: int
    big_blind: int
    ante: int
    button_seat: int
    players: List[HHPlayer]
    actions: List[HHAction]
    board: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    tournament_id: Optional[str] = None
    payouts: Optional[List[float]] = None
    winners: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

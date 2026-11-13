"""Tournament structure configuration for Twister (3-max Spin & Go) games.

Nothing here assumes a single operator's rules: blind levels, antes, level
duration, starting stacks and payout structure are all configurable. The
``default_twister_structure`` is a *typical* structure, provided as a starting
point only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class BlindLevel:
    level: int
    small_blind: int
    big_blind: int
    ante: int = 0
    duration_seconds: int = 120

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TwisterConfig:
    name: str = "Twister estándar (3-max, 500 fichas, 10/20, niveles de 2 min)"
    players: int = 3
    starting_stack: int = 500
    levels: List[BlindLevel] = field(default_factory=list)
    # Payouts as fractions of the prize pool, ordered 1st, 2nd, 3rd. [1.0] = winner takes all.
    payouts: List[float] = field(default_factory=lambda: [1.0])
    buy_in: float = 1.0
    prize_multiplier: float = 2.0      # prize pool = buy_in * multiplier (Twister jackpots scale this)
    # Level progression: "time" (virtual/real clock) or "hands" (fixed hands per level)
    level_mode: str = "time"
    hands_per_level: int = 6
    seconds_per_hand: int = 25          # virtual seconds added per hand when level_mode == "time"
    real_time: bool = False             # if True, elapsed time follows the wall clock (pausable)

    def __post_init__(self) -> None:
        if not self.levels:
            self.levels = default_levels()
        if abs(sum(self.payouts) - 1.0) > 1e-6:
            raise ValueError("payouts must sum to 1.0")
        if self.players not in (2, 3):
            raise ValueError("Twister supports 2 or 3 players")

    @property
    def prize_pool(self) -> float:
        return self.buy_in * self.prize_multiplier

    def payout_amounts(self) -> List[float]:
        return [round(self.prize_pool * p, 2) for p in self.payouts]

    def level_at(self, index: int) -> BlindLevel:
        return self.levels[min(index, len(self.levels) - 1)]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["levels"] = [l.to_dict() for l in self.levels]
        d["prize_pool"] = self.prize_pool
        d["payout_amounts"] = self.payout_amounts()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "TwisterConfig":
        data = dict(data)
        levels = data.pop("levels", None)
        data.pop("prize_pool", None)
        data.pop("payout_amounts", None)
        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if levels:
            cfg.levels = [BlindLevel(**{k: v for k, v in l.items() if k in BlindLevel.__dataclass_fields__}) for l in levels]
        return cfg


def default_levels(duration_seconds: int = 120) -> List[BlindLevel]:
    """A typical fast Twister blind schedule. Antes kick in from level 5 in this default."""
    table = [
        (10, 20, 0), (15, 30, 0), (20, 40, 0), (30, 60, 0), (40, 80, 8), (50, 100, 10),
        (60, 120, 12), (80, 160, 16), (100, 200, 20), (125, 250, 25), (150, 300, 30),
        (200, 400, 40), (250, 500, 50), (300, 600, 60), (400, 800, 80), (500, 1000, 100),
    ]
    return [BlindLevel(i + 1, sb, bb, ante, duration_seconds) for i, (sb, bb, ante) in enumerate(table)]


def default_twister_structure() -> TwisterConfig:
    return TwisterConfig()

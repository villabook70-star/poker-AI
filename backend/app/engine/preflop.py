"""Preflop opening/defending ranges by position and effective stack.

**Heuristic tables**, documented as such. They encode common short-stack 3-max
practice (wider on the button, push/fold when shallow) but they are *not*
solver outputs. For effective stacks at or below ``PUSH_FOLD_MAX_BB`` the
recommender hands over to the Nash push/fold solver (``pushfold.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .ranges import Range

PUSH_FOLD_MAX_BB = 13.0   # at/below this effective stack, open-raising is replaced by push/fold analysis

# percent of hands opened (raise) by position, keyed by stack bucket (bb). Heuristic.
OPEN_PERCENT: Dict[str, Dict[str, float]] = {
    # 3-handed
    "BTN": {"deep": 48.0, "mid": 42.0, "short": 36.0},
    "SB":  {"deep": 44.0, "mid": 40.0, "short": 34.0},   # SB opening after BTN fold (HU-like but 3 players alive)
    # heads-up: the button (small blind) opens very wide
    "BTN/SB": {"deep": 75.0, "mid": 68.0, "short": 60.0},
}
# percent of hands that 3-bet (all-in when short) vs an open, by position. Heuristic.
THREE_BET_PERCENT: Dict[str, Dict[str, float]] = {
    "SB": {"deep": 10.0, "mid": 13.0, "short": 18.0},
    "BB": {"deep": 12.0, "mid": 15.0, "short": 20.0},
    "BTN/SB": {"deep": 12.0, "mid": 14.0, "short": 18.0},
    "BTN": {"deep": 10.0, "mid": 12.0, "short": 16.0},
}
# percent of hands that call an open (not 3-bet), by position. Heuristic.
CALL_PERCENT: Dict[str, Dict[str, float]] = {
    "SB": {"deep": 12.0, "mid": 10.0, "short": 6.0},
    "BB": {"deep": 35.0, "mid": 28.0, "short": 15.0},
    "BTN/SB": {"deep": 15.0, "mid": 12.0, "short": 8.0},
    "BTN": {"deep": 14.0, "mid": 12.0, "short": 8.0},
}


def stack_bucket(effective_bb: float) -> str:
    if effective_bb >= 30:
        return "deep"
    if effective_bb >= 18:
        return "mid"
    return "short"


@dataclass
class PreflopAdvice:
    open_range: Range
    open_percent: float
    three_bet_range: Range
    three_bet_percent: float
    call_range: Range
    call_percent: float
    raise_size_bb: float
    bucket: str

    def to_dict(self) -> dict:
        return {
            "bucket": self.bucket,
            "open_percent": self.open_percent,
            "open_range": self.open_range.to_text(),
            "three_bet_percent": self.three_bet_percent,
            "three_bet_range": self.three_bet_range.to_text(),
            "call_percent": self.call_percent,
            "call_range": self.call_range.to_text(),
            "raise_size_bb": self.raise_size_bb,
            "source": "heuristic",
        }


def preflop_advice(position: str, effective_bb: float) -> PreflopAdvice:
    b = stack_bucket(effective_bb)
    pos = position if position in OPEN_PERCENT or position in THREE_BET_PERCENT else "BTN"
    op = OPEN_PERCENT.get(pos, OPEN_PERCENT["BTN"])[b]
    tb = THREE_BET_PERCENT.get(pos, THREE_BET_PERCENT["BB"])[b]
    cp = CALL_PERCENT.get(pos, CALL_PERCENT["BB"])[b]
    raise_size = 2.0 if effective_bb < 25 else 2.5
    return PreflopAdvice(Range.top_percent(op), op, Range.top_percent(tb), tb, Range.top_percent(cp), cp, raise_size, b)

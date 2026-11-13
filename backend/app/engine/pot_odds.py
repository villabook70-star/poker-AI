"""Pot odds, required equity and expected value of simple actions.

All functions here are **exact arithmetic** given their inputs. The inputs
themselves (equity, fold probability) may be estimates - the caller must
propagate that uncertainty when presenting results.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PotOdds:
    pot: float          # pot before hero acts (includes villain's bet)
    to_call: float
    ratio: float        # pot : call, e.g. 3.0 means 3:1
    required_equity: float  # to_call / (pot + to_call)

    @property
    def ratio_text(self) -> str:
        return "∞" if self.ratio == float("inf") else f"{self.ratio:.2f}:1"

    def to_dict(self) -> dict:
        return {
            "pot": self.pot,
            "to_call": self.to_call,
            "ratio": None if self.ratio == float("inf") else round(self.ratio, 3),
            "ratio_text": self.ratio_text,
            "required_equity": round(self.required_equity, 5),
        }


def pot_odds(pot: float, to_call: float) -> PotOdds:
    """``pot`` is the total already in the middle (including the bet hero faces)."""
    if to_call <= 0:
        return PotOdds(pot, 0.0, float("inf"), 0.0)
    return PotOdds(pot, to_call, pot / to_call, to_call / (pot + to_call))


def ev_call(equity: float, pot: float, to_call: float) -> float:
    """EV of calling (chips), relative to folding.

    ``pot`` is everything already in the middle (including the bet hero faces);
    hero wins ``pot`` with probability ``equity`` and loses ``to_call`` otherwise.
    """
    return equity * pot - (1 - equity) * to_call


def ev_call_allin(equity: float, pot_before: float, to_call: float) -> float:
    """Same as :func:`ev_call`; explicit name for all-in calls (no further action)."""
    return ev_call(equity, pot_before, to_call)


def ev_shove(equity_when_called: float, pot: float, shove_size: float, villain_call_size: float,
             p_fold: float) -> float:
    """EV (relative to folding) of an all-in bet of ``shove_size``.

    * villain folds with probability ``p_fold``: hero wins ``pot``.
    * villain calls: hero risks ``shove_size`` to win ``pot + villain_call_size``.
    ``villain_call_size`` is the amount villain adds (may be less than shove_size if covered).
    """
    win_if_called = equity_when_called * (pot + villain_call_size) - (1 - equity_when_called) * min(shove_size, villain_call_size)
    return p_fold * pot + (1 - p_fold) * win_if_called


def breakeven_fold_frequency(bet: float, pot: float) -> float:
    """Fold frequency needed for a pure bluff of ``bet`` into ``pot`` to break even."""
    return bet / (pot + bet)


def implied_bluff_catch_frequency(bet: float, pot: float) -> float:
    """Minimum defence frequency (MDF) vs a bet: 1 - bet/(pot+bet)."""
    return 1 - breakeven_fold_frequency(bet, pot)

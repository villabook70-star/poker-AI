"""Opponent profiling with explicit sample-size uncertainty.

Each statistic is a proportion estimated from ``n`` opportunities. We report
the point estimate together with a Wilson score interval (95%). A profile with
few hands is *not* claimed to identify a style: ``style`` is only assigned when
the interval is narrow enough, otherwise it is "insuficiente".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Tuple

# Population baselines for 3-max hyper-turbo play used ONLY as neutral priors when
# no data exists. They are heuristics, not measured facts about any specific opponent.
POPULATION_DEFAULTS = {
    "vpip": 0.42, "pfr": 0.30, "three_bet": 0.10, "fold_to_three_bet": 0.55,
    "fold_to_cbet": 0.45, "cbet": 0.60, "aggression_factor": 2.0, "wtsd": 0.30,
}


def wilson_interval(successes: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass
class Stat:
    successes: float = 0.0
    opportunities: int = 0

    @property
    def value(self) -> Optional[float]:
        return self.successes / self.opportunities if self.opportunities else None

    def interval(self) -> Tuple[float, float]:
        return wilson_interval(self.successes, self.opportunities)

    def to_dict(self, prior: Optional[float] = None) -> dict:
        lo, hi = self.interval()
        return {
            "value": None if self.value is None else round(self.value, 3),
            "n": self.opportunities,
            "ci95": [round(lo, 3), round(hi, 3)],
            "prior": prior,
            "shrunk": None if prior is None else round(self.shrunk(prior), 3),
        }

    def shrunk(self, prior: float, prior_weight: float = 20.0) -> float:
        """Bayesian-style shrinkage toward the population prior (pseudo-count = prior_weight)."""
        return (self.successes + prior * prior_weight) / (self.opportunities + prior_weight)


@dataclass
class OpponentProfile:
    name: str
    hands: int = 0
    vpip: Stat = field(default_factory=Stat)
    pfr: Stat = field(default_factory=Stat)
    three_bet: Stat = field(default_factory=Stat)
    fold_to_three_bet: Stat = field(default_factory=Stat)
    cbet: Stat = field(default_factory=Stat)
    fold_to_cbet: Stat = field(default_factory=Stat)
    wtsd: Stat = field(default_factory=Stat)      # went to showdown when saw flop
    aggressive_actions: int = 0                   # bets + raises postflop
    passive_actions: int = 0                      # calls postflop
    notes: str = ""
    # betting tendencies: count of bet sizes by bucket (fraction of pot)
    bet_sizes: Dict[str, int] = field(default_factory=lambda: {"small(<40%)": 0, "medium(40-80%)": 0, "large(>80%)": 0, "allin": 0})

    def aggression_factor(self) -> Optional[float]:
        if self.passive_actions == 0:
            return None if self.aggressive_actions == 0 else float("inf")
        return self.aggressive_actions / self.passive_actions

    def record_bet_size(self, bet: float, pot: float, all_in: bool = False) -> None:
        if all_in:
            self.bet_sizes["allin"] += 1
        elif pot <= 0:
            self.bet_sizes["medium(40-80%)"] += 1
        else:
            frac = bet / pot
            key = "small(<40%)" if frac < 0.4 else ("medium(40-80%)" if frac <= 0.8 else "large(>80%)")
            self.bet_sizes[key] += 1

    def confidence(self) -> str:
        if self.hands < 20:
            return "muy baja"
        if self.hands < 60:
            return "baja"
        if self.hands < 150:
            return "media"
        return "alta"

    def style(self) -> str:
        """Only assign a style when VPIP and PFR intervals are narrow enough."""
        v, p = self.vpip, self.pfr
        if v.opportunities < 30 or v.value is None or p.value is None:
            return "insuficiente (menos de 30 manos)"
        lo, hi = v.interval()
        if hi - lo > 0.30:
            return "insuficiente (intervalo demasiado amplio)"
        loose = v.value >= 0.45
        aggressive = (p.value / v.value) >= 0.6 if v.value else False
        return ("loose-" if loose else "tight-") + ("agresivo" if aggressive else "pasivo")

    def estimated(self, key: str) -> float:
        """Point estimate shrunk toward the population prior (used by the range model)."""
        stat: Stat = getattr(self, key)
        return stat.shrunk(POPULATION_DEFAULTS[key])

    def to_dict(self) -> dict:
        af = self.aggression_factor()
        return {
            "name": self.name,
            "hands": self.hands,
            "confidence": self.confidence(),
            "style": self.style(),
            "vpip": self.vpip.to_dict(POPULATION_DEFAULTS["vpip"]),
            "pfr": self.pfr.to_dict(POPULATION_DEFAULTS["pfr"]),
            "three_bet": self.three_bet.to_dict(POPULATION_DEFAULTS["three_bet"]),
            "fold_to_three_bet": self.fold_to_three_bet.to_dict(POPULATION_DEFAULTS["fold_to_three_bet"]),
            "cbet": self.cbet.to_dict(POPULATION_DEFAULTS["cbet"]),
            "fold_to_cbet": self.fold_to_cbet.to_dict(POPULATION_DEFAULTS["fold_to_cbet"]),
            "wtsd": self.wtsd.to_dict(POPULATION_DEFAULTS["wtsd"]),
            "aggression_factor": None if af is None else (None if af == float("inf") else round(af, 2)),
            "aggressive_actions": self.aggressive_actions,
            "passive_actions": self.passive_actions,
            "bet_sizes": self.bet_sizes,
            "notes": self.notes,
            "warning": None if self.hands >= 60 else "Muestra pequeña: las estimaciones tienen una incertidumbre alta.",
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OpponentProfile":
        p = cls(name=d["name"], hands=d.get("hands", 0), notes=d.get("notes", ""))
        for key in ("vpip", "pfr", "three_bet", "fold_to_three_bet", "cbet", "fold_to_cbet", "wtsd"):
            v = d.get(key)
            if isinstance(v, dict) and "n" in v:
                n = int(v["n"])
                val = v.get("value")
                setattr(p, key, Stat(successes=(val or 0.0) * n, opportunities=n))
            elif isinstance(v, dict) and "successes" in v:
                setattr(p, key, Stat(**v))
        p.aggressive_actions = d.get("aggressive_actions", 0)
        p.passive_actions = d.get("passive_actions", 0)
        if d.get("bet_sizes"):
            p.bet_sizes.update(d["bet_sizes"])
        return p

    def to_storage(self) -> dict:
        return {
            "name": self.name, "hands": self.hands, "notes": self.notes,
            **{k: asdict(getattr(self, k)) for k in ("vpip", "pfr", "three_bet", "fold_to_three_bet", "cbet", "fold_to_cbet", "wtsd")},
            "aggressive_actions": self.aggressive_actions, "passive_actions": self.passive_actions,
            "bet_sizes": self.bet_sizes,
        }

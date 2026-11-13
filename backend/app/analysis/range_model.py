"""Estimate an opponent's range from their preflop actions and profile.

**Heuristic model.** The range is the top X% of hands (ordered by equity vs a
random hand) where X comes from the opponent's (shrunk) VPIP / PFR / 3-bet
statistics, adjusted for position. Postflop actions are not used to narrow
the range in this version (documented limitation). Every estimate returns
the assumptions and a confidence label derived from the sample size.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..engine.ranges import Range
from .profiles import POPULATION_DEFAULTS, OpponentProfile

POSITION_FACTOR = {"BTN": 1.15, "SB": 1.0, "BB": 1.0, "BTN/SB": 1.1}


@dataclass
class RangeEstimate:
    range: Range
    percent: float
    basis: str
    confidence: str
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "percent": round(self.percent, 1),
            "combos": self.range.combo_count(),
            "text": self.range.to_text(),
            "grid": self.range.class_weights(),
            "basis": self.basis,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
        }


def estimate_preflop_range(
    action: str,
    position: str,
    profile: Optional[OpponentProfile] = None,
    stack_bb: float = 25.0,
    facing_raise: bool = False,
) -> RangeEstimate:
    """``action`` in {"open_raise", "limp", "call", "3bet", "shove", "call_shove", "unknown"}."""
    assumptions = ["Orden de manos por equity contra mano aleatoria (heurístico, no GTO).",
                   "Las acciones postflop no estrechan el rango en esta versión."]
    if profile is None or profile.hands == 0:
        vpip, pfr, tb = POPULATION_DEFAULTS["vpip"], POPULATION_DEFAULTS["pfr"], POPULATION_DEFAULTS["three_bet"]
        basis = "sin datos del rival: medias poblacionales 3-max (heurística)"
        confidence = "muy baja"
        assumptions.append("Sin perfil del rival: se usan medias poblacionales orientativas.")
    else:
        vpip, pfr, tb = profile.estimated("vpip"), profile.estimated("pfr"), profile.estimated("three_bet")
        basis = f"perfil de {profile.name} ({profile.hands} manos, estimaciones contraídas hacia la media poblacional)"
        confidence = profile.confidence()
        assumptions.append(f"VPIP≈{vpip:.0%}, PFR≈{pfr:.0%}, 3-bet≈{tb:.0%} tras contracción bayesiana (peso 20 manos).")

    pf = POSITION_FACTOR.get(position, 1.0)
    if action == "open_raise":
        pct = pfr * 100 * pf
    elif action == "limp":
        pct = max(5.0, (vpip - pfr) * 100 * pf)
        assumptions.append("Rango de limp = VPIP - PFR (manos que entran sin subir).")
    elif action == "call":
        pct = max(5.0, (vpip - pfr) * 100)
        assumptions.append("Rango de call = VPIP - PFR aprox.; las manos más fuertes se asumen subidas.")
    elif action == "3bet":
        pct = tb * 100
    elif action == "shove":
        # short-stack shove: wider than PFR when very short
        pct = pfr * 100 * pf * (1.3 if stack_bb <= 10 else 1.0)
        assumptions.append("All-in corto: se ensancha un 30% respecto al PFR si el stack ≤ 10bb.")
    elif action == "call_shove":
        pct = max(5.0, min(vpip, 0.5 * vpip + 0.1) * 100)
        assumptions.append("Rango de call a un all-in: aprox. la mitad del VPIP más un 10%.")
    else:
        pct = vpip * 100
    pct = max(2.0, min(100.0, pct))
    rng = Range.top_percent(pct)
    rng.label = f"{action} {position} ~{pct:.0f}%"
    return RangeEstimate(rng, pct, basis, confidence, assumptions)

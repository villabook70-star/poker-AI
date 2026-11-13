"""Strategic recommendation engine.

Given a fully described situation it returns the recommended action, the EV of
every alternative it could evaluate, the mathematics behind it and a confidence
level. Every number is tagged with its provenance:

* ``exact``      - enumeration / arithmetic (pot odds, exact equity, ICM arithmetic)
* ``monte_carlo``- statistical estimate with standard error
* ``nash``       - Nash equilibrium of the restricted push/fold game
* ``heuristic``  - rule of thumb / assumed ranges / assumed fold frequencies

Heuristics are never presented as optimal play.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..engine.cards import Card, card_str, hand_class
from ..engine.equity import calculate_equity
from ..engine.icm import icm_equities
from ..engine.pot_odds import ev_call, ev_shove, pot_odds
from ..engine.preflop import PUSH_FOLD_MAX_BB, preflop_advice
from ..engine.pushfold import btn_shove_analysis, hu_call_decision, hu_push_decision, solve_hu_push_fold
from ..engine.ranges import Range, load_equity_data, percentile_of_class
from .profiles import OpponentProfile
from .range_model import RangeEstimate, estimate_preflop_range


@dataclass
class VillainInfo:
    name: str
    position: str
    stack: int                 # chips behind
    committed: int = 0         # chips in the pot this hand
    folded: bool = False
    all_in: bool = False
    preflop_action: str = "unknown"   # open_raise | limp | call | 3bet | shove | call_shove | check | unknown
    profile: Optional[OpponentProfile] = None


@dataclass
class Situation:
    hero_cards: List[Card]
    board: List[Card]
    hero_position: str
    hero_stack: int            # chips behind
    hero_committed: int
    pot: int                   # total chips in the middle (all players' commitments)
    to_call: int
    bb_size: int
    ante: int
    street: str
    villains: List[VillainInfo]
    legal: Optional[dict] = None
    payouts: Optional[List[float]] = None   # prize fractions; None or [1.0] = winner-take-all
    players_remaining: int = 3
    hero_preflop_action: str = "none"       # none | open_raise | limp | call | 3bet
    raise_count_preflop: int = 0            # number of raises before hero's decision (preflop)


@dataclass
class Alternative:
    action: str
    amount: int
    ev_bb: Optional[float]
    ev_type: str      # exact | monte_carlo | nash | heuristic | n/a
    note: str = ""
    ev_icm: Optional[float] = None

    def to_dict(self) -> dict:
        return {"action": self.action, "amount": self.amount,
                "ev_bb": None if self.ev_bb is None else round(self.ev_bb, 3),
                "ev_icm": None if self.ev_icm is None else round(self.ev_icm, 5),
                "ev_type": self.ev_type, "note": self.note}


@dataclass
class Recommendation:
    action: str
    amount: int
    confidence: str
    confidence_score: float
    alternatives: List[Alternative]
    explanation: List[str]
    equity: Optional[dict] = None
    pot_odds: Optional[dict] = None
    villain_ranges: List[dict] = field(default_factory=list)
    gto_comparison: Optional[dict] = None
    sources: List[str] = field(default_factory=list)
    hero_hand_class: str = ""
    hero_hand_percentile: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "amount": self.amount,
            "confidence": self.confidence,
            "confidence_score": round(self.confidence_score, 2),
            "alternatives": [a.to_dict() for a in self.alternatives],
            "explanation": self.explanation,
            "equity": self.equity,
            "pot_odds": self.pot_odds,
            "villain_ranges": self.villain_ranges,
            "gto_comparison": self.gto_comparison,
            "sources": sorted(set(self.sources)),
            "hero_hand_class": self.hero_hand_class,
            "hero_hand_percentile": self.hero_hand_percentile,
            "warnings": self.warnings,
        }


def _confidence(score: float) -> str:
    if score >= 0.75:
        return "alta"
    if score >= 0.45:
        return "media"
    return "baja"


def _active_villains(s: Situation) -> List[VillainInfo]:
    return [v for v in s.villains if not v.folded]


def _effective_stack_chips(s: Situation, vill: List[VillainInfo]) -> int:
    hero_total = s.hero_stack + s.hero_committed
    if not vill:
        return hero_total
    return min(hero_total, max(v.stack + v.committed for v in vill))


def _villain_range(s: Situation, v: VillainInfo, eff_bb: float) -> RangeEstimate:
    action = v.preflop_action
    if action in ("unknown", "check", "none"):
        action = "unknown" if s.street != "preflop" else "unknown"
    est = estimate_preflop_range(action, v.position, v.profile, eff_bb, facing_raise=s.raise_count_preflop > 0)
    return est


def _icm_values(s: Situation, hero_after: float, villains_after: Dict[str, float]) -> float:
    """ICM equity of hero given resulting stacks (fractions of prize pool)."""
    stacks = [hero_after] + [villains_after.get(v.name, v.stack + v.committed) for v in s.villains]
    return icm_equities(stacks, s.payouts or [1.0])[0]


def _use_icm(s: Situation) -> bool:
    return bool(s.payouts) and len(s.payouts) > 1 and s.players_remaining >= 3


def recommend(s: Situation) -> Recommendation:
    hero_class = hand_class(s.hero_cards[0], s.hero_cards[1])
    percentile = round(percentile_of_class(hero_class), 1) if load_equity_data() else None
    if s.street == "preflop":
        rec = _recommend_preflop(s)
    else:
        rec = _recommend_postflop(s)
    rec.hero_hand_class = hero_class
    rec.hero_hand_percentile = percentile
    rec.action, rec.amount = _clamp_to_legal(s, rec.action, rec.amount, rec)
    return rec


def _clamp_to_legal(s: Situation, action: str, amount: int, rec: Recommendation):
    la = s.legal
    if not la:
        return action, amount
    if action == "check" and not la.get("can_check"):
        action = "call" if la.get("can_call") else "fold"
    if action == "call" and not la.get("can_call"):
        action = "check" if la.get("can_check") else "fold"
    if action == "allin":
        if la.get("can_raise"):
            action, amount = "raise", la["max_raise_to"]
        elif la.get("can_bet"):
            action, amount = "bet", la["max_bet"]
        elif la.get("can_call"):
            action, amount = "call", la["call_amount"]
            rec.explanation.append("No es posible subir: la opción all-in equivale a pagar.")
    if action == "raise":
        if not la.get("can_raise"):
            action, amount = ("call", la.get("call_amount", 0)) if la.get("can_call") else ("check", 0)
        else:
            amount = max(la["min_raise_to"], min(la["max_raise_to"], amount))
    if action == "bet":
        if not la.get("can_bet"):
            action, amount = ("raise", la.get("min_raise_to", 0)) if la.get("can_raise") else ("check", 0)
        else:
            amount = max(la["min_bet"], min(la["max_bet"], amount))
    if action == "fold" and la.get("can_check"):
        action, amount = "check", 0
    return action, amount


# ---------------------------------------------------------------------------
# Preflop
# ---------------------------------------------------------------------------

def _recommend_preflop(s: Situation) -> Recommendation:
    vill = _active_villains(s)
    bb = s.bb_size
    eff_chips = _effective_stack_chips(s, vill)
    eff_bb = eff_chips / bb
    ante_bb = s.ante / bb
    hero_class = hand_class(s.hero_cards[0], s.hero_cards[1])
    explanation: List[str] = []
    sources: List[str] = []
    warnings: List[str] = []
    alternatives: List[Alternative] = []
    villain_ranges: List[dict] = []
    hero_total = s.hero_stack + s.hero_committed
    has_data = load_equity_data() is not None
    if not has_data:
        warnings.append("Matriz de equity preflop no disponible: no se puede usar el solver push/fold.")

    facing_raise = s.raise_count_preflop > 0 and s.to_call > 0
    facing_allin = facing_raise and any(v.all_in or (v.stack == 0) for v in vill) or (
        facing_raise and s.to_call >= s.hero_stack)
    nobody_raised = s.raise_count_preflop == 0
    hu_spot = len(vill) == 1

    # ---------------- unopened pot ----------------
    if nobody_raised:
        if eff_bb <= PUSH_FOLD_MAX_BB and has_data:
            if hu_spot and s.hero_position in ("BTN/SB", "SB", "BTN"):
                d = hu_push_decision(hero_class, round(eff_bb, 1), round(ante_bb, 3))
                sources.append("nash")
                ev_fold = d["ev_fold_bb"]
                alternatives = [Alternative("allin", hero_total + 0, d["ev_push_bb"], "nash", "all-in (Nash push/fold)"),
                                Alternative("fold", 0, ev_fold, "exact", "pierde la ciega/ante ya puesta")]
                if s.legal and s.legal.get("can_check"):
                    alternatives[1] = Alternative("check", 0, None, "n/a", "no evaluado por el solver")
                explanation += [
                    f"Stack efectivo {eff_bb:.1f}bb: zona push/fold. Equilibrio de Nash del juego restringido (SB all-in o fold, BB call o fold).",
                    f"{hero_class}: frecuencia de push en equilibrio {d['push_frequency']:.0%}. EV(push) = {d['ev_push_bb']:+.2f}bb vs EV(fold) = {ev_fold:+.2f}bb.",
                    f"El rango de push Nash a este stack es el {d['nash_push_percent']:.0f}% de manos; el de call, el {d['nash_call_percent']:.0f}%.",
                ]
                if s.players_remaining == 3:
                    warnings.append("Quedan 3 jugadores: el equilibrio HU ignora el ICM a tres bandas (aproximación).")
                action = "allin" if d["action"] == "push" else "fold"
                gain = abs(d["ev_gain_bb"])
                score = min(1.0, 0.55 + gain / 1.5)
                gto = {"available": True, "source": "Nash push/fold (juego restringido) calculado localmente",
                       "nash_action": d["action"], "push_frequency": d["push_frequency"]}
                return Recommendation(action, hero_total if action == "allin" else 0, _confidence(score), score,
                                      alternatives, explanation, None, None, villain_ranges, gto, sources, warnings=warnings)
            if not hu_spot and s.hero_position == "BTN":
                stacks = [hero_total] + [v.stack + v.committed for v in sorted(vill, key=lambda v: 0 if v.position == "SB" else 1)]
                if len(stacks) == 3:
                    d = btn_shove_analysis(hero_class, stacks, bb, s.ante, s.payouts if _use_icm(s) else None)
                    sources += ["heuristic", "monte_carlo"]
                    ev_fold = -ante_bb
                    alternatives = [Alternative("allin", hero_total, d["ev_shove_bb"], "heuristic",
                                                "EV estimado vs rangos de call asumidos", d["ev_shove_icm"]),
                                    Alternative("fold", 0, ev_fold, "exact", "pierde solo el ante")]
                    explanation += [
                        f"Stack efectivo {eff_bb:.1f}bb en el botón con 3 jugadores: análisis de open-shove.",
                        f"P(SB paga)≈{d['p_sb_call']:.0%} (rango {d['sb_call_range_percent']:.0f}%), P(BB paga)≈{d['p_bb_call']:.0%} (rango {d['bb_call_range_percent']:.0f}%), ambos fold ≈{d['p_both_fold']:.0%}.",
                        f"Equity si paga SB {d['equity_vs_sb_call']:.1%}, si paga BB {d['equity_vs_bb_call']:.1%}.",
                        f"EV(all-in) ≈ {d['ev_shove_bb']:+.2f}bb" + (f"; EV ICM ≈ {d['ev_shove_icm']:+.4f} del bote de premios" if _use_icm(s) else "") + ". Esto es una ESTIMACIÓN con rangos de call asumidos, no un equilibrio.",
                    ]
                    warnings += d["assumptions"]
                    action = "allin" if d["action"] == "push" else "fold"
                    margin = abs(d["ev_shove_bb"] - ev_fold)
                    score = min(0.8, 0.4 + margin / 2.0)
                    return Recommendation(action, hero_total if action == "allin" else 0, _confidence(score), score,
                                          alternatives, explanation, None, None, villain_ranges,
                                          {"available": False, "reason": "No existe solución GTO verificada para open-shove 3-max en esta app; se usa estimación."},
                                          sources, warnings=warnings)
        # deeper (or no data): heuristic opening ranges
        adv = preflop_advice(s.hero_position, eff_bb)
        sources.append("heuristic")
        in_open = adv.open_range.contains(s.hero_cards[0], s.hero_cards[1])
        pct = percentile_of_class(hero_class)
        raise_to = int(round(adv.raise_size_bb * bb))
        if s.legal and s.legal.get("can_raise"):
            raise_to = max(s.legal["min_raise_to"], min(s.legal["max_raise_to"], raise_to))
        limpers = [v for v in vill if v.preflop_action == "limp"]
        explanation += [
            f"Bote sin abrir, stack efectivo {eff_bb:.1f}bb ({adv.bucket}). Rango de apertura heurístico en {s.hero_position}: {adv.open_percent:.0f}% de manos.",
            f"{hero_class} está en el {pct:.0f}% superior de manos (ordenadas por equity vs mano aleatoria)." if has_data else f"{hero_class}: percentil no disponible sin la matriz de equity.",
        ]
        if limpers:
            explanation.append(f"Hay {len(limpers)} limper(s): se recomienda subir más (aislar) con manos del rango de apertura.")
            raise_to = int(round(raise_to + bb * len(limpers)))
        if in_open:
            action, amount = "raise", raise_to
            explanation.append(f"La mano está dentro del rango de apertura: subir a {raise_to} ({raise_to / bb:.1f}bb).")
        elif s.legal and s.legal.get("can_check"):
            action, amount = "check", 0
            explanation.append("La mano está fuera del rango de apertura; con opción de pasar, pasar.")
        else:
            action, amount = "fold", 0
            explanation.append("La mano está fuera del rango de apertura heurístico: fold.")
        alternatives = [Alternative("raise", raise_to, None, "heuristic", "apertura estándar"),
                        Alternative("fold" if not (s.legal and s.legal.get("can_check")) else "check", 0, None, "heuristic", "")]
        dist = abs(pct - adv.open_percent) / 100.0
        score = min(0.7, 0.35 + dist * 2)
        warnings.append("Rangos de apertura heurísticos: no son una solución GTO.")
        return Recommendation(action, amount, _confidence(score), score, alternatives, explanation, None, None, villain_ranges,
                              {"available": False, "reason": "Sin datos GTO verificables para esta profundidad de stack."}, sources, warnings=warnings)

    # ---------------- facing a raise / all-in ----------------
    aggressor = _find_aggressor(vill)
    po = pot_odds(s.pot, min(s.to_call, s.hero_stack))
    sources.append("exact")
    ranges: List[Range] = []
    for v in vill:
        act = v.preflop_action
        if v is aggressor:
            act = "shove" if facing_allin else ("3bet" if s.raise_count_preflop >= 2 else "open_raise")
            if facing_allin and has_data and (v.stack + v.committed) / bb <= PUSH_FOLD_MAX_BB and hu_spot and s.hero_position in ("BB",):
                sol = solve_hu_push_fold(round(eff_bb, 1), round(ante_bb, 3))
                r = sol.push_range()
                est = RangeEstimate(r, r.percent_of_all(), "rango de push Nash heads-up (juego restringido)", "media",
                                    ["Se asume que el rival empuja según el equilibrio de Nash; los rivales reales se desvían."])
                sources.append("nash")
            else:
                est = _villain_range(s, v, eff_bb)
                sources.append("heuristic")
        else:
            est = _villain_range(s, v, eff_bb)
            sources.append("heuristic")
        rr = est.range.remove_cards(s.hero_cards)
        ranges.append(rr)
        d = est.to_dict()
        d["villain"] = v.name
        d["position"] = v.position
        villain_ranges.append(d)

    eq = calculate_equity(s.hero_cards, ranges, [], mode="auto", samples=12000, seed=11)
    sources.append(eq.method)
    call_amt = min(s.to_call, s.hero_stack)
    ev_c = ev_call(eq.equity, s.pot, call_amt) / bb  # chips relative to fold, only exact if all-in (no further streets)
    explanation.append(f"Pot odds: {po.ratio_text} → equity mínima para pagar {po.required_equity:.1%}.")
    explanation.append(f"Equity de {hero_class} vs rango(s) estimado(s): {eq.equity:.1%} ({'exacta' if eq.method == 'exact' else f'Monte Carlo ±{eq.ci95:.1%}'}).")

    alternatives.append(Alternative("fold", 0, 0.0, "exact", "referencia: EV 0 (lo ya puesto está perdido)"))
    if facing_allin or call_amt >= s.hero_stack:
        ev_type = eq.method
        note = "all-in: sin acción posterior, EV = equity×bote − coste"
        ev_icm = None
        if _use_icm(s):
            hero_total = s.hero_stack + s.hero_committed
            others = {v.name: v.stack + v.committed for v in s.villains}
            # winner gets pot; approximate single-opponent all-in
            agg = aggressor or vill[0]
            win_stacks = dict(others)
            win_stacks[agg.name] = max(0, others[agg.name] - (s.pot - s.hero_committed - sum(x.committed for x in vill if x is not agg)) + 0)
            v_fold = _icm_values(s, s.hero_stack, others)
            v_win = _icm_values(s, s.hero_stack - call_amt + s.pot + call_amt, {**others, agg.name: others[agg.name] - (agg.committed)})
            v_lose = _icm_values(s, s.hero_stack - call_amt, {**others, agg.name: others[agg.name] + s.hero_committed + call_amt})
            ev_icm = eq.equity * v_win + (1 - eq.equity) * v_lose - v_fold
            explanation.append(f"ICM ({len(s.payouts)} premios): ΔEV$ de pagar ≈ {ev_icm:+.4f} del bote de premios (modelo Malmuth-Harville).")
        alternatives.append(Alternative("call", call_amt, ev_c, ev_type, note, ev_icm))
        decide_icm = _use_icm(s) and ev_icm is not None
        good = (ev_icm > 0) if decide_icm else (eq.equity > po.required_equity)
        action = "call" if good else "fold"
        margin = abs(eq.equity - po.required_equity)
        score = min(1.0, 0.45 + margin * 4 - eq.ci95 * 2)
        explanation.append(
            f"EV(call) = {eq.equity:.3f}×{s.pot} − {1 - eq.equity:.3f}×{call_amt} = {ev_c * bb:+.0f} fichas ({ev_c:+.2f}bb)." +
            (" Pagar es rentable." if ev_c > 0 else " Pagar pierde valor."))
        gto = None
        if hu_spot and has_data and (eff_bb <= PUSH_FOLD_MAX_BB) and s.hero_position == "BB":
            d = hu_call_decision(hero_class, round(eff_bb, 1), round(ante_bb, 3))
            sources.append("nash")
            gto = {"available": True, "source": "Nash call vs push (juego restringido)", "nash_action": d["action"],
                   "call_frequency": d["call_frequency"], "ev_call_bb": d["ev_call_bb"]}
            explanation.append(f"Comparación Nash: vs un rango de push en equilibrio, {hero_class} debería {'pagar' if d['action']=='call' else 'foldear'} (EV {d['ev_call_bb']:+.2f}bb vs fold {d['ev_fold_bb']:+.2f}bb).")
        return Recommendation(action, call_amt if action == "call" else 0, _confidence(max(0.2, score)), max(0.2, score),
                              alternatives, explanation, eq.to_dict(), po.to_dict(), villain_ranges, gto, sources, warnings=warnings)

    # facing a non-all-in raise: consider fold / call / 3-bet shove
    ev_call_rough = ev_c
    alternatives.append(Alternative("call", call_amt, ev_call_rough, "heuristic",
                                    "aproximación: equity bruta × bote, sin ajustar por jugabilidad postflop"))
    agg = aggressor
    p_fold = 0.55
    if agg is not None and agg.profile is not None and agg.profile.hands > 0:
        p_fold = agg.profile.estimated("fold_to_three_bet")
    shove_to = hero_total
    if shove_to / bb <= 25 and agg is not None:
        # villain continues with top part of their range: (1-p_fold) of their opening range
        base = villain_ranges[0]["percent"] if villain_ranges else 40.0
        cont = Range.top_percent(max(2.0, base * (1 - p_fold))).remove_cards(s.hero_cards)
        eq_cont = calculate_equity(s.hero_cards, [cont], [], mode="auto", samples=15000, seed=12)
        villain_call_size = min(agg.stack, shove_to - agg.committed)
        risk = s.hero_stack
        ev_sh = ev_shove(eq_cont.equity, s.pot, risk, villain_call_size, p_fold) / bb
        alternatives.append(Alternative("allin", shove_to, ev_sh, "heuristic",
                                        f"asume que el rival foldea {p_fold:.0%} y paga con el {max(2.0, base * (1 - p_fold)):.0f}% superior (equity {eq_cont.equity:.1%})"))
        sources.append("heuristic")
        explanation.append(f"3-bet all-in: si el rival foldea ≈{p_fold:.0%} (dato de perfil o media), EV ≈ {ev_sh:+.2f}bb.")
    adv = preflop_advice(s.hero_position, eff_bb)
    in_3b = adv.three_bet_range.contains(*s.hero_cards)
    in_call = adv.call_range.contains(*s.hero_cards)
    best = max(alternatives, key=lambda a: (a.ev_bb if a.ev_bb is not None else -99))
    if best.action == "allin" and best.ev_bb is not None and best.ev_bb > 0.15:
        action, amount = "allin", shove_to
        explanation.append("La re-subida all-in tiene el mayor EV estimado.")
    elif in_3b and shove_to / bb <= 25:
        action, amount = "allin", shove_to
        explanation.append(f"{hero_class} está en el rango heurístico de 3-bet ({adv.three_bet_percent:.0f}%).")
    elif eq.equity > po.required_equity + 0.08 or in_call:
        action, amount = "call", call_amt
        explanation.append("Equity suficiente frente al rango estimado para pagar (aproximación sin jugabilidad).")
    else:
        action, amount = "fold", 0
        explanation.append("Ni la equity ni el rango heurístico justifican continuar: fold.")
    score = 0.45
    warnings.append("Spot con acción postflop pendiente: los EV son aproximaciones, no cálculos exactos.")
    return Recommendation(action, amount, _confidence(score), score, alternatives, explanation, eq.to_dict(), po.to_dict(),
                          villain_ranges, {"available": False, "reason": "Sin datos GTO verificables para este spot."}, sources, warnings=warnings)


def _find_aggressor(vill: List[VillainInfo]) -> Optional[VillainInfo]:
    for v in vill:
        if v.preflop_action in ("3bet", "shove"):
            return v
    for v in vill:
        if v.preflop_action == "open_raise":
            return v
    return vill[0] if vill else None


# ---------------------------------------------------------------------------
# Postflop
# ---------------------------------------------------------------------------

def _recommend_postflop(s: Situation) -> Recommendation:
    vill = _active_villains(s)
    bb = s.bb_size
    eff_bb = _effective_stack_chips(s, vill) / bb
    explanation: List[str] = []
    sources: List[str] = []
    warnings: List[str] = ["Los rangos postflop no se estrechan por las acciones postflop del rival (limitación documentada)."]
    villain_ranges: List[dict] = []
    ranges: List[Range] = []
    for v in vill:
        est = _villain_range(s, v, eff_bb)
        rr = est.range.remove_cards(list(s.hero_cards) + list(s.board))
        if rr.combo_count() == 0:
            rr = Range.random_hand().remove_cards(list(s.hero_cards) + list(s.board))
        ranges.append(rr)
        d = est.to_dict()
        d["villain"] = v.name
        d["position"] = v.position
        villain_ranges.append(d)
        sources.append("heuristic")
    eq = calculate_equity(s.hero_cards, ranges, s.board, mode="auto", samples=12000, seed=21)
    sources.append(eq.method)
    hero_total = s.hero_stack + s.hero_committed
    call_amt = min(s.to_call, s.hero_stack)
    po = pot_odds(s.pot, call_amt)
    alternatives: List[Alternative] = []
    eq_txt = f"{eq.equity:.1%} ({'exacta' if eq.method == 'exact' else f'Monte Carlo ±{eq.ci95:.1%}'})"
    explanation.append(f"Equity en {s.street} vs {len(ranges)} rango(s) estimado(s): {eq_txt}.")
    main_v = vill[0] if vill else None
    p_fold = 0.45
    if main_v and main_v.profile and main_v.profile.hands > 0:
        p_fold = main_v.profile.estimated("fold_to_cbet")
    spr = s.hero_stack / max(1, s.pot)

    if s.to_call > 0:
        explanation.append(f"Pot odds {po.ratio_text}: equity mínima {po.required_equity:.1%}.")
        ev_c = ev_call(eq.equity, s.pot, call_amt) / bb
        is_allin_call = call_amt >= s.hero_stack or all(v.all_in or v.stack == 0 for v in vill)
        ev_type = eq.method if (is_allin_call or s.street == "river") else "heuristic"
        alternatives.append(Alternative("fold", 0, 0.0, "exact", "referencia"))
        alternatives.append(Alternative("call", call_amt, ev_c, ev_type,
                                        "EV exacto dada la equity" if ev_type != "heuristic" else "aprox.: hay calles por jugar"))
        if s.legal and s.legal.get("can_raise") and eff_bb <= 30:
            cont_eq = eq.equity  # vs same range (no narrowing) - conservative for value, optimistic for bluffs
            villain_call = min(max(v.stack for v in vill), s.hero_stack)
            ev_sh = ev_shove(cont_eq, s.pot, s.hero_stack, villain_call, p_fold) / bb
            alternatives.append(Alternative("allin", hero_total, ev_sh, "heuristic",
                                            f"asume fold del rival {p_fold:.0%} (perfil/media) y misma equity si paga"))
            sources.append("heuristic")
        best = max(alternatives, key=lambda a: a.ev_bb if a.ev_bb is not None else -99)
        if best.action == "allin" and best.ev_bb is not None and best.ev_bb > ev_c + 0.3 and eq.equity > 0.35:
            action, amount = "allin", hero_total
            explanation.append(f"Subir all-in domina en EV estimado ({best.ev_bb:+.2f}bb) gracias a la equity de fold asumida.")
        elif eq.equity > po.required_equity:
            action, amount = "call", call_amt
            explanation.append(f"Equity {eq.equity:.1%} > {po.required_equity:.1%} requerida: pagar tiene EV {ev_c:+.2f}bb.")
        else:
            action, amount = "fold", 0
            explanation.append(f"Equity {eq.equity:.1%} < {po.required_equity:.1%} requerida: pagar pierde {ev_c:+.2f}bb.")
        margin = abs(eq.equity - po.required_equity)
        score = min(0.9, 0.4 + margin * 4 - eq.ci95 * 2) if ev_type != "heuristic" else min(0.65, 0.35 + margin * 3)
    else:
        # no bet to face: check or bet
        alternatives.append(Alternative("check", 0, None, "n/a", "sin EV cerrado: depende de la acción posterior"))
        bet_size = int(round(min(s.hero_stack, max(bb, 0.5 * s.pot))))
        if spr < 1.5:
            bet_size = s.hero_stack
        villain_call = min(max((v.stack for v in vill), default=0), bet_size)
        ev_b = ev_shove(eq.equity, s.pot, bet_size, villain_call, p_fold) / bb
        alternatives.append(Alternative("bet" if bet_size < s.hero_stack else "allin", bet_size if bet_size < s.hero_stack else hero_total, ev_b, "heuristic",
                                        f"asume fold del rival {p_fold:.0%} y equity {eq.equity:.0%} si paga; ignora calles futuras"))
        sources.append("heuristic")
        if eq.equity >= 0.60:
            action, amount = ("allin", hero_total) if bet_size >= s.hero_stack else ("bet", bet_size)
            explanation.append(f"Equity alta ({eq.equity:.1%}): apostar por valor. Tamaño ≈ {'all-in (SPR bajo)' if bet_size >= s.hero_stack else '50% del bote'}.")
        elif eq.equity >= 0.40 and p_fold >= 0.5 and spr > 1.5:
            action, amount = "bet", bet_size
            explanation.append(f"Equity media ({eq.equity:.1%}) y rival que foldea ≈{p_fold:.0%}: apuesta semi-bluff con EV estimado {ev_b:+.2f}bb.")
        else:
            action, amount = "check", 0
            explanation.append(f"Equity {eq.equity:.1%}: pasar; apostar no está justificado con la equity de fold asumida.")
        score = min(0.6, 0.3 + abs(eq.equity - 0.5))
        warnings.append("Sin apuesta que afrontar, la decisión apostar/pasar es heurística: no existe EV exacto sin modelar las calles siguientes.")
    return Recommendation(action, amount, _confidence(score), score, alternatives, explanation, eq.to_dict(), po.to_dict() if s.to_call > 0 else None,
                          villain_ranges, {"available": False, "reason": "No hay soluciones GTO postflop verificadas integradas."}, sources, warnings=warnings)

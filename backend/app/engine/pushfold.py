"""Push/fold analysis.

Two distinct tools, clearly separated:

1. :func:`solve_hu_push_fold` - **Nash equilibrium of the restricted heads-up
   game** (small blind jams or folds; big blind calls or folds) computed by
   fictitious play from the 169x169 preflop equity matrix. The equilibrium is
   exact for the restricted game given the equity matrix; the matrix itself is
   a Monte Carlo estimate, so results carry that statistical uncertainty.
   Heads-up, ICM is linear in chips (2 players) so chip-EV decisions coincide
   with $EV decisions for any prize structure.

2. :func:`btn_shove_analysis` - **3-handed estimate**: EV (chip or ICM) of a
   button open-shove for one hand against *assumed* calling ranges of SB/BB.
   Not an equilibrium - the calling ranges are inputs (defaults: Nash HU calling
   ranges vs the effective stack, which is an approximation 3-handed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .cards import CLASS_INDEX, HAND_CLASSES, class_combo_count
from .icm import icm_equities
from .ranges import Range, load_equity_data

N_CLASSES = 169


def _matrix() -> Tuple[np.ndarray, np.ndarray]:
    data = load_equity_data()
    if not data:
        raise RuntimeError(
            "Falta data/preflop_equity_169.json. Genera la matriz con "
            "`python scripts/build_equity_matrix.py`."
        )
    return np.array(data["equity"], dtype=np.float64), np.array(data["combo_counts"], dtype=np.float64)


@dataclass
class HUPushFoldSolution:
    stack_bb: float
    ante_bb: float
    push: np.ndarray     # 169 push frequencies (SB)
    call: np.ndarray     # 169 call frequencies (BB) vs a push
    push_ev: np.ndarray  # EV (bb) of pushing each class vs equilibrium calling range (relative to start of hand)
    call_ev: np.ndarray  # EV (bb) of calling each class vs equilibrium pushing range
    iterations: int
    exploitability: float   # max gain by deviating (bb), convergence measure

    def push_range(self, threshold: float = 0.5) -> Range:
        return Range.from_classes([HAND_CLASSES[i] for i in range(N_CLASSES) if self.push[i] >= threshold],
                                  label=f"Nash push {self.stack_bb:g}bb")

    def call_range(self, threshold: float = 0.5) -> Range:
        return Range.from_classes([HAND_CLASSES[i] for i in range(N_CLASSES) if self.call[i] >= threshold],
                                  label=f"Nash call {self.stack_bb:g}bb")

    def push_percent(self) -> float:
        return 100.0 * sum(self.push[i] * class_combo_count(HAND_CLASSES[i]) for i in range(N_CLASSES)) / 1326.0

    def call_percent(self) -> float:
        return 100.0 * sum(self.call[i] * class_combo_count(HAND_CLASSES[i]) for i in range(N_CLASSES)) / 1326.0

    def to_dict(self) -> dict:
        return {
            "stack_bb": self.stack_bb,
            "ante_bb": self.ante_bb,
            "push": {HAND_CLASSES[i]: round(float(self.push[i]), 3) for i in range(N_CLASSES) if self.push[i] > 0.001},
            "call": {HAND_CLASSES[i]: round(float(self.call[i]), 3) for i in range(N_CLASSES) if self.call[i] > 0.001},
            "push_ev_bb": {HAND_CLASSES[i]: round(float(self.push_ev[i]), 3) for i in range(N_CLASSES)},
            "call_ev_bb": {HAND_CLASSES[i]: round(float(self.call_ev[i]), 3) for i in range(N_CLASSES)},
            "push_percent": round(self.push_percent(), 1),
            "call_percent": round(self.call_percent(), 1),
            "iterations": self.iterations,
            "exploitability_bb": round(float(self.exploitability), 4),
            "source": "nash_equilibrium_restricted_game",
            "assumptions": [
                "Juego restringido: SB solo puede ir all-in o foldear; BB solo puede pagar o foldear.",
                "Equities preflop de la matriz 169x169 (estimación Monte Carlo).",
                "Heads-up el ICM es lineal en fichas, por lo que la decisión es idéntica en EV de fichas y en EV de premio.",
            ],
        }


@lru_cache(maxsize=256)
def solve_hu_push_fold(stack_bb: float, ante_bb: float = 0.0, iterations: int = 400) -> HUPushFoldSolution:
    """Nash equilibrium for SB push/fold vs BB call/fold, effective stack ``stack_bb`` (in big blinds).

    Stacks are measured *before* posting blinds/antes. ``ante_bb`` is the ante
    each player posts (in bb). Both players are assumed to have ``stack_bb``
    (effective stack); the shorter stack determines the all-in size.
    """
    E, C = _matrix()
    S = float(stack_bb)
    a = float(ante_bb)
    # P(villain class j | hero class i): proportional to non-conflicting combo pairs
    P = C / C.sum(axis=1, keepdims=True)

    # Payoffs for SB (relative to stack at start of hand, in bb):
    sb_fold = -0.5 - a                         # loses SB + ante
    sb_win_blinds = 1.0 + a                    # wins BB's blind + BB's ante
    sb_showdown = (2 * S) * E - S              # equity*(total pot) - own stack  (total pot = 2S)
    # Payoffs for BB (caller), row = pusher class i, col = caller class j
    bb_fold = -1.0 - a
    bb_showdown = (2 * S) * (1 - E) - S

    push = np.ones(N_CLASSES)   # start: push everything
    call = np.ones(N_CLASSES)   # start: call everything
    push_avg = push.copy()
    call_avg = call.copy()
    for k in range(1, iterations + 1):
        # SB best response vs current BB average calling strategy
        ev_push = (P * ((1 - call_avg)[None, :] * sb_win_blinds + call_avg[None, :] * sb_showdown)).sum(axis=1)
        br_push = (ev_push > sb_fold).astype(np.float64)
        # BB best response vs current SB average pushing strategy
        # P(pusher class i | BB has class j, SB pushed) ∝ C[i,j] * push[i]
        w = C * push_avg[:, None]
        denom = w.sum(axis=0)
        safe = denom > 0
        ev_call = np.full(N_CLASSES, bb_fold)
        ev_call[safe] = (w[:, safe] * bb_showdown[:, safe]).sum(axis=0) / denom[safe]
        br_call = (ev_call > bb_fold).astype(np.float64)
        # fictitious play averaging
        push_avg += (br_push - push_avg) / (k + 1)
        call_avg += (br_call - call_avg) / (k + 1)

    # final EVs and exploitability vs averaged strategies
    ev_push = (P * ((1 - call_avg)[None, :] * sb_win_blinds + call_avg[None, :] * sb_showdown)).sum(axis=1)
    w = C * push_avg[:, None]
    denom = w.sum(axis=0)
    ev_call = np.full(N_CLASSES, bb_fold)
    safe = denom > 0
    ev_call[safe] = (w[:, safe] * bb_showdown[:, safe]).sum(axis=0) / denom[safe]
    # exploitability: how much each side gains by best-responding instead of using avg strategy
    freq = C.sum(axis=1) / C.sum()
    sb_gain = (freq * (np.maximum(ev_push, sb_fold) - (push_avg * ev_push + (1 - push_avg) * sb_fold))).sum()
    bb_gain = (freq * (np.maximum(ev_call, bb_fold) - (call_avg * ev_call + (1 - call_avg) * bb_fold))).sum()
    # clean near-pure strategies
    push_clean = np.where(push_avg > 0.97, 1.0, np.where(push_avg < 0.03, 0.0, push_avg))
    call_clean = np.where(call_avg > 0.97, 1.0, np.where(call_avg < 0.03, 0.0, call_avg))
    return HUPushFoldSolution(S, a, push_clean, call_clean, ev_push, ev_call, iterations, float(sb_gain + bb_gain))


def hu_push_decision(hand_label: str, stack_bb: float, ante_bb: float = 0.0) -> dict:
    sol = solve_hu_push_fold(round(stack_bb, 2), round(ante_bb, 3))
    i = CLASS_INDEX[hand_label]
    return {
        "hand": hand_label,
        "action": "push" if sol.push[i] >= 0.5 else "fold",
        "push_frequency": round(float(sol.push[i]), 3),
        "ev_push_bb": round(float(sol.push_ev[i]), 3),
        "ev_fold_bb": round(-0.5 - ante_bb, 3),
        "ev_gain_bb": round(float(sol.push_ev[i]) - (-0.5 - ante_bb), 3),
        "nash_push_percent": round(float(sol.push_percent()), 1),
        "nash_call_percent": round(float(sol.call_percent()), 1),
        "source": "nash_equilibrium_restricted_game",
    }


def hu_call_decision(hand_label: str, stack_bb: float, ante_bb: float = 0.0) -> dict:
    sol = solve_hu_push_fold(round(stack_bb, 2), round(ante_bb, 3))
    i = CLASS_INDEX[hand_label]
    return {
        "hand": hand_label,
        "action": "call" if sol.call[i] >= 0.5 else "fold",
        "call_frequency": round(float(sol.call[i]), 3),
        "ev_call_bb": round(float(sol.call_ev[i]), 3),
        "ev_fold_bb": round(-1.0 - ante_bb, 3),
        "ev_gain_bb": round(float(sol.call_ev[i]) - (-1.0 - ante_bb), 3),
        "nash_push_percent": round(float(sol.push_percent()), 1),
        "nash_call_percent": round(float(sol.call_percent()), 1),
        "source": "nash_equilibrium_restricted_game",
    }


# ---------------------------------------------------------------------------
# 3-handed button shove estimate
# ---------------------------------------------------------------------------

def class_equity_vs_range(hand_label: str, calling: np.ndarray) -> Tuple[float, float]:
    """(P(call), equity when called) for a 169-class hand vs a 169-vector of calling frequencies.

    Uses the equity matrix (Monte Carlo estimate) with card-removal weights.
    """
    E, C = _matrix()
    i = CLASS_INDEX[hand_label]
    w = C[i] * calling
    p_call = w.sum() / C[i].sum()
    if w.sum() <= 0:
        return 0.0, 0.0
    eq = (w * E[i]).sum() / w.sum()
    return float(p_call), float(eq)


def range_to_vector(rng: Range) -> np.ndarray:
    cw = rng.class_weights()
    return np.array([cw.get(h, 0.0) for h in HAND_CLASSES], dtype=np.float64)


def btn_shove_analysis(
    hand_label: str,
    stacks: Sequence[float],          # [BTN, SB, BB] chips before posting
    bb_size: float,
    ante: float = 0.0,
    payouts: Optional[Sequence[float]] = None,
    sb_call_range: Optional[Range] = None,
    bb_call_range: Optional[Range] = None,
    overcall_tighten: float = 0.5,
) -> dict:
    """Estimate EV of a button open-shove 3-handed.

    Scenarios: both fold / SB calls only / BB calls only / both call. The
    both-call scenario is approximated with pairwise equities (hero equity
    vs two callers ~ product-normalised), labelled as an approximation.
    ``overcall_tighten`` scales the BB's calling frequency when SB already called.
    Returns chip EV and (if payouts given) ICM $EV, relative to folding.
    """
    btn, sb, bb = [float(s) for s in stacks]
    eff_sb = min(btn, sb)
    eff_bb = min(btn, bb)
    pay = list(payouts) if payouts else [1.0]  # winner-take-all by default -> ICM equals chip share
    sol_sb = solve_hu_push_fold(round(eff_sb / bb_size, 1), round(ante / bb_size, 3))
    sol_bb = solve_hu_push_fold(round(eff_bb / bb_size, 1), round(ante / bb_size, 3))
    sb_vec = range_to_vector(sb_call_range) if sb_call_range else sol_sb.call
    bb_vec = range_to_vector(bb_call_range) if bb_call_range else sol_bb.call

    p_sb, eq_sb = class_equity_vs_range(hand_label, sb_vec)
    p_bb, eq_bb = class_equity_vs_range(hand_label, bb_vec)
    p_bb_over = p_bb * overcall_tighten  # BB tightens after SB call (assumption)

    blinds_pot = 0.5 * bb_size + bb_size + 3 * ante
    # chip outcomes for BTN (stack after hand)
    def icm_value(st: Sequence[float]) -> float:
        return icm_equities(st, pay)[0] if payouts else st[0] / sum(st)

    start = [btn - ante, sb - ante - 0.5 * bb_size, bb - ante - bb_size]
    v_fold = icm_value([btn - ante, sb - ante - 0.5 * bb_size, bb - ante - bb_size])
    v_fold_chips = btn - ante

    # both fold
    s_bothfold = [btn - ante + blinds_pot, sb - ante - 0.5 * bb_size, bb - ante - bb_size]
    # SB calls only, BB folds
    pot_sb = 2 * eff_sb + bb_size + 3 * ante - 0.0  # BTN & SB all-in (eff), BB's blind, antes
    win_sb = [btn - ante + (eff_sb + bb_size + 2 * ante), sb - eff_sb - ante, bb - ante - bb_size]
    lose_sb = [btn - eff_sb - ante, sb - ante + eff_sb + bb_size + 2 * ante, bb - ante - bb_size]
    # BB calls only, SB folds
    win_bb = [btn - ante + (eff_bb + 0.5 * bb_size + 2 * ante), sb - ante - 0.5 * bb_size, bb - eff_bb - ante]
    lose_bb = [btn - eff_bb - ante, sb - ante - 0.5 * bb_size, bb - ante + eff_bb + 0.5 * bb_size + 2 * ante]
    # both call (approximation: hero wins whole main pot vs both or loses; side pots ignored)
    eq_both = (eq_sb * eq_bb) / max(1e-9, (eq_sb * eq_bb + (1 - eq_sb) * (1 - eq_bb) + 0.5 * ((1 - eq_sb) * eq_bb + eq_sb * (1 - eq_bb))))
    eff3 = min(btn, sb, bb)
    win_both = [btn - ante + 2 * eff3 + 2 * ante, sb - eff3 - ante, bb - eff3 - ante]
    lose_both = [btn - eff3 - ante, (sb - ante) + eff3 * 1.0 + ante, (bb - ante) + eff3 * 1.0 + ante]  # split approx.

    p_bothfold = (1 - p_sb) * (1 - p_bb)
    p_sb_only = p_sb * (1 - p_bb_over)
    p_bb_only = (1 - p_sb) * p_bb
    p_both = p_sb * p_bb_over

    def expected(valuefn) -> float:
        return (p_bothfold * valuefn(s_bothfold)
                + p_sb_only * (eq_sb * valuefn(win_sb) + (1 - eq_sb) * valuefn(lose_sb))
                + p_bb_only * (eq_bb * valuefn(win_bb) + (1 - eq_bb) * valuefn(lose_bb))
                + p_both * (eq_both * valuefn(win_both) + (1 - eq_both) * valuefn(lose_both)))

    ev_chips = expected(lambda st: st[0]) - v_fold_chips
    ev_icm = expected(icm_value) - v_fold
    return {
        "hand": hand_label,
        "action": "push" if (ev_icm if payouts else ev_chips) > 0 else "fold",
        "ev_shove_chips": round(ev_chips, 2),
        "ev_shove_bb": round(ev_chips / bb_size, 3),
        "ev_shove_icm": round(ev_icm, 5),
        "p_sb_call": round(p_sb, 3),
        "p_bb_call": round(p_bb, 3),
        "p_both_fold": round(p_bothfold, 3),
        "equity_vs_sb_call": round(eq_sb, 4),
        "equity_vs_bb_call": round(eq_bb, 4),
        "equity_vs_both_approx": round(eq_both, 4),
        "sb_call_range_percent": round(100 * float((sb_vec * np.array([class_combo_count(h) for h in HAND_CLASSES])).sum() / 1326), 1),
        "bb_call_range_percent": round(100 * float((bb_vec * np.array([class_combo_count(h) for h in HAND_CLASSES])).sum() / 1326), 1),
        "source": "estimate_vs_assumed_ranges",
        "assumptions": [
            "Rangos de call de SB/BB asumidos (por defecto: rango de call Nash heads-up al stack efectivo).",
            f"La BB se asume {int((1-overcall_tighten)*100)}% más estrecha si SB ya ha pagado.",
            "La equity a tres bandas se aproxima a partir de equities por parejas; los botes secundarios se ignoran.",
            "Equities preflop de la matriz 169x169 (Monte Carlo).",
            "ICM (Malmuth-Harville) con la estructura de premios indicada." if payouts else "Sin estructura de premios: se usa EV en fichas.",
        ],
    }

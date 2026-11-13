"""Bot opponents for the training simulator.

Bots reuse the deterministic engine (equity, Nash push/fold, heuristic ranges)
with style parameters so the user can practise against different tendencies.
They are intentionally *not* perfect: ``mistake_rate`` injects deviations.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple

from ..engine.cards import hand_class
from ..engine.equity import calculate_equity
from ..engine.preflop import PUSH_FOLD_MAX_BB, preflop_advice
from ..engine.pushfold import hu_call_decision, hu_push_decision
from ..engine.ranges import Range, load_equity_data, percentile_of_class
from .engine import Game, LegalActions

BOT_STYLES = {
    # open multiplier, call multiplier, bluff frequency, mistake rate
    "balanced":   {"open": 1.0, "call": 1.0, "bluff": 0.10, "mistake": 0.05, "label": "Equilibrado"},
    "tight":      {"open": 0.7, "call": 0.75, "bluff": 0.04, "mistake": 0.05, "label": "Tight-pasivo"},
    "loose":      {"open": 1.4, "call": 1.5, "bluff": 0.12, "mistake": 0.08, "label": "Loose-pasivo"},
    "aggressive": {"open": 1.3, "call": 1.0, "bluff": 0.30, "mistake": 0.08, "label": "Loose-agresivo"},
    "maniac":     {"open": 1.8, "call": 1.8, "bluff": 0.45, "mistake": 0.12, "label": "Maníaco"},
}


def bot_decide(game: Game, seat: int, rng: random.Random) -> Tuple[str, int]:
    p = game.players[seat]
    style = BOT_STYLES.get(p.bot_profile, BOT_STYLES["balanced"])
    la = game.legal_actions(seat)
    bb = game.big_blind
    live = [q for q in game.players if not q.folded and not q.eliminated and q.seat != seat and q.hole_cards]
    eff_bb = min(p.stack + p.committed, max([q.stack + q.committed for q in live] + [0])) / bb
    to_call = max(0, game.current_bet - p.bet_this_street)
    hclass = hand_class(*p.hole_cards)
    has_data = load_equity_data() is not None

    # occasional random mistake (keeps bots exploitable / realistic)
    if rng.random() < style["mistake"]:
        return _random_legal(la, rng)

    if game.street == "preflop":
        raises = sum(1 for a in game.actions if a.street == "preflop" and a.action in ("raise", "bet"))
        if raises == 0:
            if eff_bb <= PUSH_FOLD_MAX_BB and has_data and len(live) == 1 and p.position != "BB":
                d = hu_push_decision(hclass, round(eff_bb, 1), round(game.ante / bb, 3))
                push = d["ev_gain_bb"] > -0.25 * (style["open"] - 1) if style["open"] > 1 else d["action"] == "push" and d["ev_gain_bb"] > 0.15 * (1 - style["open"])
                if d["action"] == "push" or push:
                    return _allin(la)
                return ("check", 0) if la.can_check else ("fold", 0)
            adv = preflop_advice(p.position, eff_bb)
            pct = percentile_of_class(hclass)
            if pct <= adv.open_percent * style["open"]:
                target = int(round(adv.raise_size_bb * bb))
                if eff_bb <= PUSH_FOLD_MAX_BB:
                    return _allin(la)
                return _raise(la, target)
            if la.can_check:
                return ("check", 0)
            # SB sometimes limps with speculative hands when loose
            if p.position in ("SB", "BTN/SB") and rng.random() < 0.3 * style["call"] and pct <= 70 and la.can_call:
                return ("call", la.call_amount)
            return ("fold", 0)
        # facing a raise
        aggressor_allin = any(a.stack_after == 0 and a.action in ("raise", "bet") for a in game.actions if a.street == "preflop")
        if aggressor_allin or to_call >= p.stack:
            if has_data and len(live) == 1 and eff_bb <= PUSH_FOLD_MAX_BB:
                d = hu_call_decision(hclass, round(eff_bb, 1), round(game.ante / bb, 3))
                call = d["action"] == "call" if style["call"] <= 1 else d["ev_gain_bb"] > -0.3
                return ("call", la.call_amount) if call and la.can_call else ("fold", 0)
            villain = Range.top_percent(min(100, 35 * style["call"])).remove_cards(p.hole_cards)
            eq = calculate_equity(p.hole_cards, [villain], [], mode="mc", samples=4000, seed=rng.randrange(1 << 30)).equity
            need = min(to_call, p.stack) / (game.pot + min(to_call, p.stack))
            return ("call", la.call_amount) if eq > need + 0.03 / style["call"] else ("fold", 0)
        adv = preflop_advice(p.position, eff_bb)
        pct = percentile_of_class(hclass)
        if pct <= adv.three_bet_percent * style["open"] and la.can_raise:
            if eff_bb <= 22:
                return _allin(la)
            return _raise(la, int(round(game.current_bet * 2.5)))
        if pct <= (adv.three_bet_percent + adv.call_percent) * style["call"] and la.can_call:
            return ("call", la.call_amount)
        return ("check", 0) if la.can_check else ("fold", 0)

    # postflop: equity vs a generic range
    villain = Range.top_percent(min(100, 45 * style["call"])).remove_cards(list(p.hole_cards) + list(game.board))
    eq = calculate_equity(p.hole_cards, [villain], game.board, mode="auto", samples=3000, seed=rng.randrange(1 << 30)).equity
    if to_call > 0:
        need = min(to_call, p.stack) / (game.pot + min(to_call, p.stack))
        if eq > 0.70 and la.can_raise:
            return _allin(la) if p.stack <= 2 * game.pot else _raise(la, min(la.max_raise_to, game.current_bet * 3))
        if eq > need + (0.05 / style["call"]) and la.can_call:
            return ("call", la.call_amount)
        if rng.random() < style["bluff"] * 0.3 and la.can_raise:
            return _allin(la)
        return ("fold", 0)
    if eq > 0.62 or rng.random() < style["bluff"] * (0.6 if eq > 0.3 else 0.3):
        size = int(round(max(bb, 0.55 * game.pot)))
        if p.stack <= 1.5 * game.pot or size >= p.stack:
            return _allin(la)
        return _bet(la, size)
    return ("check", 0) if la.can_check else ("fold", 0)


def _allin(la: LegalActions) -> Tuple[str, int]:
    if la.can_raise:
        return ("raise", la.max_raise_to)
    if la.can_bet:
        return ("bet", la.max_bet)
    if la.can_call:
        return ("call", la.call_amount)
    return ("check", 0) if la.can_check else ("fold", 0)


def _raise(la: LegalActions, target: int) -> Tuple[str, int]:
    if la.can_raise:
        return ("raise", max(la.min_raise_to, min(la.max_raise_to, target)))
    if la.can_bet:
        return ("bet", max(la.min_bet, min(la.max_bet, target)))
    if la.can_call:
        return ("call", la.call_amount)
    return ("check", 0) if la.can_check else ("fold", 0)


def _bet(la: LegalActions, size: int) -> Tuple[str, int]:
    if la.can_bet:
        return ("bet", max(la.min_bet, min(la.max_bet, size)))
    return _raise(la, size)


def _random_legal(la: LegalActions, rng: random.Random) -> Tuple[str, int]:
    opts = []
    if la.can_check:
        opts.append(("check", 0))
    if la.can_call:
        opts.append(("call", la.call_amount))
    if la.can_fold and not la.can_check:
        opts.append(("fold", 0))
    if la.can_bet:
        opts.append(("bet", la.min_bet))
    if la.can_raise:
        opts.append(("raise", la.min_raise_to))
    return rng.choice(opts) if opts else ("fold", 0)

"""Replay imported hands and analyse every hero decision with the recommender."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..analysis.profiles import OpponentProfile
from ..analysis.recommender import Situation, VillainInfo, recommend
from ..engine.cards import parse_cards
from .models import HandHistory


def _street_order(s: str) -> int:
    return ["preflop", "flop", "turn", "river"].index(s)


def analyze_hand(hh: HandHistory, profiles: Optional[Dict[str, OpponentProfile]] = None) -> dict:
    profiles = profiles or {}
    hero = next((p for p in hh.players if p.name == hh.hero), None)
    if hero is None or len(hero.hole_cards) != 2:
        return {"hand_id": hh.hand_id, "decisions": [], "skipped": "sin cartas del héroe"}
    hero_cards = parse_cards(hero.hole_cards)
    stacks = {p.name: p.stack for p in hh.players}
    committed = {p.name: 0 for p in hh.players}
    street_bet = {p.name: 0 for p in hh.players}
    folded = {p.name: False for p in hh.players}
    allin = {p.name: False for p in hh.players}
    preflop_label = {p.name: "unknown" for p in hh.players}
    current_bet = 0
    raises_preflop = 0
    street = "preflop"
    decisions: List[dict] = []
    board_by_street = {"preflop": [], "flop": hh.board[:3], "turn": hh.board[:4], "river": hh.board[:5]}
    total_ev_loss = 0.0

    def commit(name: str, amt: int) -> None:
        amt = min(amt, stacks[name])
        stacks[name] -= amt
        committed[name] += amt
        street_bet[name] += amt
        if stacks[name] == 0:
            allin[name] = True

    for a in hh.actions:
        if a.street != street:
            street = a.street
            for k in street_bet:
                street_bet[k] = 0
            current_bet = 0
        if a.action == "post_sb" or a.action == "post_bb":
            commit(a.player, a.amount)
            current_bet = max(current_bet, a.amount)
            continue
        if a.action == "post_ante":
            stacks[a.player] -= min(a.amount, stacks[a.player])
            committed[a.player] += a.amount
            continue
        if a.player == hh.hero and a.action in ("fold", "check", "call", "bet", "raise"):
            board = parse_cards(board_by_street.get(street, []))
            to_call = max(0, current_bet - street_bet[hh.hero])
            villains = [VillainInfo(p.name, p.position, stacks[p.name], committed[p.name], folded[p.name], allin[p.name],
                                    preflop_label[p.name], profiles.get(p.name)) for p in hh.players if p.name != hh.hero]
            legal = {"can_fold": True, "can_check": to_call == 0, "can_call": to_call > 0,
                     "call_amount": min(to_call, stacks[hh.hero]), "can_bet": current_bet == 0,
                     "can_raise": current_bet > 0 and stacks[hh.hero] > to_call,
                     "min_raise_to": current_bet * 2 if current_bet else hh.big_blind,
                     "max_raise_to": street_bet[hh.hero] + stacks[hh.hero], "min_bet": hh.big_blind,
                     "max_bet": stacks[hh.hero]}
            sit = Situation(hero_cards, board, hero.position, stacks[hh.hero], committed[hh.hero],
                            sum(committed.values()), to_call, hh.big_blind, hh.ante, street, villains, legal,
                            hh.payouts, sum(1 for p in hh.players if stacks[p.name] > 0 or committed[p.name] > 0),
                            preflop_label[hh.hero], raises_preflop)
            try:
                rec = recommend(sit).to_dict()
            except Exception as exc:  # noqa: BLE001
                rec = {"error": str(exc)}
            taken = {"action": a.action, "amount": a.amount}
            agree, ev_loss = _compare(rec, taken, hh.big_blind)
            if ev_loss:
                total_ev_loss += ev_loss
            decisions.append({"street": street, "board": board_by_street.get(street, []), "pot": sum(committed.values()),
                              "to_call": to_call, "taken": taken, "recommendation": rec, "agrees": agree,
                              "ev_loss_bb": ev_loss})
        # apply the action to the state
        if a.action == "fold":
            folded[a.player] = True
        elif a.action == "call":
            amt = a.amount if a.amount else max(0, current_bet - street_bet[a.player])
            commit(a.player, amt)
            if street == "preflop":
                preflop_label[a.player] = "limp" if raises_preflop == 0 else ("call_shove" if any(allin.values()) else "call")
        elif a.action in ("bet", "raise"):
            add = a.amount - street_bet[a.player]
            commit(a.player, max(0, add))
            current_bet = max(current_bet, a.amount)
            if street == "preflop":
                raises_preflop += 1
                preflop_label[a.player] = "shove" if allin[a.player] or a.all_in else ("3bet" if raises_preflop >= 2 else "open_raise")
        elif a.action == "check" and street == "preflop":
            preflop_label[a.player] = "check"
    return {"hand_id": hh.hand_id, "hero": hh.hero, "hero_cards": hero.hole_cards, "board": hh.board,
            "blinds": f"{hh.small_blind}/{hh.big_blind}" + (f" ante {hh.ante}" if hh.ante else ""),
            "decisions": decisions, "total_ev_loss_bb": round(total_ev_loss, 2),
            "mistakes": sum(1 for d in decisions if d["agrees"] is False and (d["ev_loss_bb"] or 0) >= 0.3),
            "winners": hh.winners}


def _compare(rec: dict, taken: dict, bb: int):
    """Return (agrees, ev_loss_bb). EV loss only when both EVs are available (same provenance)."""
    if "action" not in rec:
        return None, None
    norm = {"allin": "raise", "bet": "bet", "raise": "raise", "call": "call", "fold": "fold", "check": "check"}
    rec_act = norm.get(rec["action"], rec["action"])
    tk = norm.get(taken["action"], taken["action"])
    if rec["action"] == "allin" and taken["action"] in ("raise", "bet"):
        agrees = True  # user shoved/raised; treat as agreement on aggression
    else:
        agrees = rec_act == tk
    ev = {alt["action"]: alt for alt in rec.get("alternatives", [])}
    rec_ev = ev.get(rec["action"], {}).get("ev_bb")
    taken_key = "allin" if taken["action"] in ("raise", "bet") and "allin" in ev and taken["action"] not in ev else taken["action"]
    tk_ev = ev.get(taken_key, {}).get("ev_bb")
    if rec_ev is None or tk_ev is None or agrees:
        return agrees, None
    return agrees, round(max(0.0, rec_ev - tk_ev), 2)


def update_profiles_from_hands(hands: List[HandHistory], profiles: Dict[str, OpponentProfile]) -> Dict[str, OpponentProfile]:
    """Accumulate VPIP/PFR/3-bet/aggression stats for every non-hero player seen."""
    for hh in hands:
        names = [p.name for p in hh.players if p.name != hh.hero]
        for n in names:
            profiles.setdefault(n, OpponentProfile(name=n)).hands += 1
        raises = 0
        vpip_done, pfr_done, tb_done = set(), set(), set()
        faced_3bet: Dict[str, bool] = {}
        pot = 0
        for a in hh.actions:
            if a.player not in names and a.player != hh.hero:
                continue
            if a.action in ("post_sb", "post_bb", "post_ante"):
                pot += a.amount
                continue
            prof = profiles.get(a.player)
            if a.street == "preflop":
                if a.action in ("call", "raise", "bet") and prof and a.player not in vpip_done:
                    prof.vpip.successes += 1
                    vpip_done.add(a.player)
                if a.action in ("raise", "bet"):
                    raises += 1
                    if prof and a.player not in pfr_done:
                        prof.pfr.successes += 1
                        pfr_done.add(a.player)
                    if raises == 2 and prof:
                        prof.three_bet.successes += 1
                        tb_done.add(a.player)
            else:
                if prof:
                    if a.action in ("bet", "raise"):
                        prof.aggressive_actions += 1
                        prof.record_bet_size(a.amount, pot, a.all_in)
                    elif a.action == "call":
                        prof.passive_actions += 1
            if a.action in ("call", "bet", "raise"):
                pot += a.amount
        for n in names:
            prof = profiles[n]
            prof.vpip.opportunities += 1
            prof.pfr.opportunities += 1
            prof.three_bet.opportunities += 1 if raises >= 1 else 0
    return profiles

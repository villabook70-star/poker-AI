"""Build a :class:`Situation` for the recommender from a live :class:`Game`."""
from __future__ import annotations

from typing import Dict, Optional

from ..analysis.profiles import OpponentProfile
from ..analysis.recommender import Situation, VillainInfo
from .engine import Game


def preflop_action_label(game: Game, seat: int) -> str:
    """Summarise a player's preflop action so far: open_raise / limp / call / 3bet / shove / check / unknown."""
    raises = 0
    label = "unknown"
    for a in game.actions:
        if a.street != "preflop":
            break
        if a.action in ("raise", "bet"):
            raises += 1
            if a.seat == seat:
                p = game.players[seat]
                is_allin = a.stack_after == 0
                if is_allin:
                    label = "shove"
                elif raises >= 2:
                    label = "3bet"
                else:
                    label = "open_raise"
        elif a.seat == seat and a.action == "call":
            if raises == 0:
                label = "limp"
            else:
                aggressor_allin = any(x.stack_after == 0 and x.action in ("raise", "bet") for x in game.actions if x.street == "preflop")
                label = "call_shove" if aggressor_allin else "call"
        elif a.seat == seat and a.action == "check":
            label = "check"
    return label


def build_situation(game: Game, seat: Optional[int] = None, profiles: Optional[Dict[str, OpponentProfile]] = None) -> Situation:
    seat = game.to_act if seat is None else seat
    if seat is None:
        raise ValueError("No player to act")
    hero = game.players[seat]
    profiles = profiles or {}
    villains = []
    for p in game.players:
        if p.seat == seat or p.eliminated:
            continue
        villains.append(VillainInfo(
            name=p.name, position=p.position, stack=p.stack, committed=p.committed,
            folded=p.folded, all_in=p.all_in, preflop_action=preflop_action_label(game, p.seat),
            profile=profiles.get(p.name),
        ))
    raise_count = sum(1 for a in game.actions if a.street == "preflop" and a.action in ("raise", "bet"))
    la = game.legal_actions(seat)
    return Situation(
        hero_cards=list(hero.hole_cards), board=list(game.board), hero_position=hero.position,
        hero_stack=hero.stack, hero_committed=hero.committed, pot=game.pot,
        to_call=max(0, game.current_bet - hero.bet_this_street), bb_size=game.big_blind, ante=game.ante,
        street=game.street, villains=villains, legal=la.to_dict(),
        payouts=game.config.payouts, players_remaining=len(game.active_players()),
        hero_preflop_action=preflop_action_label(game, seat), raise_count_preflop=raise_count,
    )

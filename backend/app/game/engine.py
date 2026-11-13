"""Texas Hold'em No-Limit engine for 2-3 player Twister tournaments.

Handles: blinds/antes, level changes, dealing, betting rounds with correct
min-raise and short all-in rules, side pots, showdown, eliminations, the
automatic heads-up transition (button posts the small blind) and payouts.
The engine is deterministic given a seed, which allows replaying a decision
with the same run-out when comparing alternatives.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..engine.cards import Card, Deck, card_str, cards_str
from ..engine.evaluator import describe, evaluate
from .structure import TwisterConfig

STREETS = ["preflop", "flop", "turn", "river", "showdown"]


class IllegalAction(Exception):
    pass


@dataclass
class Player:
    seat: int
    name: str
    stack: int
    is_hero: bool = False
    bot_profile: str = "balanced"
    hole_cards: List[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    bet_this_street: int = 0
    committed: int = 0          # total chips put in during this hand (incl. antes)
    acted_this_street: bool = False
    eliminated: bool = False
    finish_place: Optional[int] = None
    position: str = ""

    def in_hand(self) -> bool:
        return not self.folded and not self.eliminated and (self.stack > 0 or self.all_in or self.committed > 0)

    def can_act(self) -> bool:
        return not self.folded and not self.eliminated and not self.all_in and self.stack > 0

    def to_dict(self, reveal: bool = False) -> dict:
        return {
            "seat": self.seat,
            "name": self.name,
            "stack": self.stack,
            "is_hero": self.is_hero,
            "bot_profile": self.bot_profile,
            "hole_cards": [card_str(c) for c in self.hole_cards] if (reveal or self.is_hero) else (["??", "??"] if self.hole_cards else []),
            "folded": self.folded,
            "all_in": self.all_in,
            "bet_this_street": self.bet_this_street,
            "committed": self.committed,
            "eliminated": self.eliminated,
            "finish_place": self.finish_place,
            "position": self.position,
        }


@dataclass
class ActionRecord:
    hand_no: int
    street: str
    seat: int
    name: str
    action: str
    amount: int = 0           # total bet-to amount for bet/raise, call amount for call
    pot_after: int = 0
    stack_after: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class LegalActions:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int
    can_bet: bool
    can_raise: bool
    min_raise_to: int
    max_raise_to: int
    min_bet: int
    max_bet: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class HandResult:
    hand_no: int
    board: List[str]
    winners: List[dict]
    showdown: List[dict]
    eliminated: List[int]
    pots: List[dict]

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class Game:
    """One Twister tournament."""

    def __init__(self, config: TwisterConfig, names: List[str], hero_seat: int = 0, seed: Optional[int] = None,
                 bot_profiles: Optional[List[str]] = None):
        self.config = config
        self.seed = seed
        self._rng_counter = 0
        self.players: List[Player] = []
        for i, name in enumerate(names[: config.players]):
            prof = (bot_profiles[i] if bot_profiles and i < len(bot_profiles) else "balanced")
            self.players.append(Player(seat=i, name=name, stack=config.starting_stack, is_hero=(i == hero_seat), bot_profile=prof))
        self.hand_no = 0
        self.level_index = 0
        self.elapsed_seconds = 0.0
        self._real_time_anchor: Optional[float] = None
        self.paused = True
        self.button_seat = 0
        self.finished = False
        self.payouts: Dict[int, float] = {}
        # hand state
        self.deck: Optional[Deck] = None
        self.board: List[Card] = []
        self.street = "preflop"
        self.current_bet = 0
        self.last_raise_size = 0
        self.to_act: Optional[int] = None
        self.last_aggressor: Optional[int] = None
        self.hand_in_progress = False
        self.actions: List[ActionRecord] = []
        self.history: List[ActionRecord] = []
        self.last_result: Optional[HandResult] = None
        self.results: List[HandResult] = []
        self.hands_this_level = 0
        self.last_level_change_hand = 0
        self.event_log: List[str] = []
        self._reopened_for: Dict[int, bool] = {}

    # ------------------------------------------------------------------ clock
    def level(self):
        return self.config.level_at(self.level_index)

    @property
    def big_blind(self) -> int:
        return self.level().big_blind

    @property
    def small_blind(self) -> int:
        return self.level().small_blind

    @property
    def ante(self) -> int:
        return self.level().ante

    def _sync_real_time(self) -> None:
        if self.config.real_time and not self.paused and self._real_time_anchor is not None:
            now = time.time()
            self.elapsed_seconds += now - self._real_time_anchor
            self._real_time_anchor = now

    def pause(self) -> None:
        self._sync_real_time()
        self.paused = True
        self._real_time_anchor = None

    def resume(self) -> None:
        self.paused = False
        self._real_time_anchor = time.time()

    def advance_time(self, seconds: float) -> None:
        self.elapsed_seconds += seconds
        self._update_level()

    def _update_level(self) -> None:
        if self.config.level_mode == "hands":
            target = (self.hand_no - 1) // max(1, self.config.hands_per_level)
        else:
            self._sync_real_time()
            acc = 0.0
            target = 0
            for i, lvl in enumerate(self.config.levels):
                acc += lvl.duration_seconds
                if self.elapsed_seconds < acc:
                    target = i
                    break
            else:
                target = len(self.config.levels) - 1
        if target != self.level_index:
            self.level_index = target
            lvl = self.level()
            self.event_log.append(f"Nivel {lvl.level}: ciegas {lvl.small_blind}/{lvl.big_blind}" + (f", ante {lvl.ante}" if lvl.ante else ""))

    def time_to_next_level(self) -> Optional[float]:
        if self.config.level_mode == "hands":
            return None
        acc = sum(l.duration_seconds for l in self.config.levels[: self.level_index + 1])
        return max(0.0, acc - self.elapsed_seconds)

    # ------------------------------------------------------------------ helpers
    def active_players(self) -> List[Player]:
        return [p for p in self.players if not p.eliminated]

    def players_in_hand(self) -> List[Player]:
        return [p for p in self.players if not p.folded and not p.eliminated and (p.hole_cards)]

    def hero(self) -> Player:
        return next(p for p in self.players if p.is_hero)

    def _next_active_seat(self, seat: int, condition=None) -> int:
        n = len(self.players)
        for k in range(1, n + 1):
            s = (seat + k) % n
            p = self.players[s]
            if not p.eliminated and (condition is None or condition(p)):
                return s
        raise IllegalAction("No active player found")

    @property
    def pot(self) -> int:
        return sum(p.committed for p in self.players)

    def is_heads_up(self) -> bool:
        return len(self.active_players()) == 2

    # ------------------------------------------------------------------ hand lifecycle
    def start_hand(self) -> None:
        if self.finished:
            raise IllegalAction("Tournament finished")
        if self.hand_in_progress:
            raise IllegalAction("Hand already in progress")
        self.hand_no += 1
        self._update_level()
        if self.config.level_mode == "time" and not self.config.real_time and self.hand_no > 1:
            self.advance_time(self.config.seconds_per_hand)
        active = self.active_players()
        if len(active) < 2:
            self._finish()
            return
        # button moves to next active player (first hand: seat 0 or the configured button)
        if self.hand_no > 1:
            self.button_seat = self._next_active_seat(self.button_seat)
        elif self.players[self.button_seat].eliminated:
            self.button_seat = self._next_active_seat(self.button_seat)

        seed = None if self.seed is None else self.seed * 1000003 + self.hand_no
        self.deck = Deck(seed=seed)
        self.board = []
        self.street = "preflop"
        self.actions = []
        self.current_bet = 0
        self.last_aggressor = None
        self._reopened_for = {}
        for p in self.players:
            p.hole_cards = []
            p.folded = p.eliminated
            p.all_in = False
            p.bet_this_street = 0
            p.committed = 0
            p.acted_this_street = False
            p.position = ""

        # positions
        if self.is_heads_up():
            sb_seat = self.button_seat
            bb_seat = self._next_active_seat(sb_seat)
            self.players[sb_seat].position = "BTN/SB"
            self.players[bb_seat].position = "BB"
        else:
            sb_seat = self._next_active_seat(self.button_seat)
            bb_seat = self._next_active_seat(sb_seat)
            self.players[self.button_seat].position = "BTN"
            self.players[sb_seat].position = "SB"
            self.players[bb_seat].position = "BB"

        # antes then blinds
        lvl = self.level()
        for p in active:
            if lvl.ante:
                self._commit(p, min(lvl.ante, p.stack), counts_as_bet=False)
        self._post_blind(self.players[sb_seat], lvl.small_blind)
        self._post_blind(self.players[bb_seat], lvl.big_blind)
        self.current_bet = lvl.big_blind
        self.last_raise_size = lvl.big_blind
        # deal
        for p in active:
            p.hole_cards = self.deck.deal(2)
        self.hand_in_progress = True
        # first to act preflop: left of BB (3-handed: BTN; HU: BTN/SB)
        self.to_act = self._first_to_act_preflop(bb_seat)
        self.event_log.append(f"Mano {self.hand_no}: ciegas {lvl.small_blind}/{lvl.big_blind}" + (f" ante {lvl.ante}" if lvl.ante else ""))
        self._maybe_auto_advance()

    def _first_to_act_preflop(self, bb_seat: int) -> Optional[int]:
        s = self._next_active_seat(bb_seat)
        for _ in range(len(self.players)):
            if self.players[s].can_act():
                return s
            s = self._next_active_seat(s)
        return None

    def _post_blind(self, p: Player, amount: int) -> None:
        amt = min(amount, p.stack)
        self._commit(p, amt, counts_as_bet=True)

    def _commit(self, p: Player, amount: int, counts_as_bet: bool) -> None:
        amount = min(amount, p.stack)
        p.stack -= amount
        p.committed += amount
        if counts_as_bet:
            p.bet_this_street += amount
        if p.stack == 0:
            p.all_in = True

    # ------------------------------------------------------------------ legal actions
    def legal_actions(self, seat: Optional[int] = None) -> LegalActions:
        if not self.hand_in_progress or self.to_act is None:
            return LegalActions(False, False, False, 0, False, False, 0, 0, 0, 0)
        seat = self.to_act if seat is None else seat
        if seat != self.to_act:
            return LegalActions(False, False, False, 0, False, False, 0, 0, 0, 0)
        p = self.players[seat]
        to_call = max(0, self.current_bet - p.bet_this_street)
        call_amount = min(to_call, p.stack)
        can_check = to_call == 0
        can_call = to_call > 0 and p.stack > 0
        others_can_act = any(q.can_act() for q in self.players if q.seat != seat and not q.folded)
        max_to = p.bet_this_street + p.stack
        if self.current_bet == 0:
            min_bet = min(self.big_blind, max_to)
            can_bet = p.stack > 0 and others_can_act
            return LegalActions(True, can_check, False, 0, can_bet, False, 0, 0, min_bet, max_to)
        min_raise_to = self.current_bet + self.last_raise_size
        can_raise = p.stack > to_call and others_can_act and self._raise_allowed(p)
        min_raise_to = min(min_raise_to, max_to)
        return LegalActions(True, can_check, can_call, call_amount, False, can_raise, min_raise_to, max_to, 0, 0)

    def _raise_allowed(self, p: Player) -> bool:
        # A player who already acted may re-raise only if a full raise happened since.
        return not p.acted_this_street or self._reopened_for.get(p.seat, True)

    # ------------------------------------------------------------------ acting
    def act(self, seat: int, action: str, amount: int = 0) -> ActionRecord:
        """Apply an action. ``amount`` is the *total* bet-to amount for bet/raise."""
        if not self.hand_in_progress or self.to_act != seat:
            raise IllegalAction("Not this player's turn")
        p = self.players[seat]
        la = self.legal_actions(seat)
        action = action.lower()
        if action == "fold":
            if not la.can_fold:
                raise IllegalAction("Cannot fold")
            p.folded = True
            rec_amount = 0
        elif action == "check":
            if not la.can_check:
                raise IllegalAction("Cannot check: there is a bet to call")
            rec_amount = 0
        elif action == "call":
            if not la.can_call:
                raise IllegalAction("Nothing to call")
            self._commit(p, la.call_amount, counts_as_bet=True)
            rec_amount = la.call_amount
        elif action in ("bet", "raise", "allin", "all_in", "all-in"):
            if action in ("allin", "all_in", "all-in"):
                amount = p.bet_this_street + p.stack
                action = "bet" if self.current_bet == 0 else "raise"
                if action == "raise" and not la.can_raise:
                    # short all-in as a call when raising isn't allowed
                    if la.can_call:
                        self._commit(p, la.call_amount, counts_as_bet=True)
                        action, rec_amount = "call", la.call_amount
                        return self._finish_action(p, action, rec_amount)
                    raise IllegalAction("Cannot go all-in")
            if action == "bet":
                if not la.can_bet:
                    raise IllegalAction("Cannot bet")
                if amount < la.min_bet and amount != la.max_bet:
                    raise IllegalAction(f"Bet below minimum ({la.min_bet})")
                if amount > la.max_bet:
                    raise IllegalAction("Bet above stack")
                self._apply_raise_to(p, amount)
            else:
                if not la.can_raise:
                    raise IllegalAction("Cannot raise")
                if amount < la.min_raise_to and amount != la.max_raise_to:
                    raise IllegalAction(f"Raise below minimum ({la.min_raise_to})")
                if amount > la.max_raise_to:
                    raise IllegalAction("Raise above stack")
                self._apply_raise_to(p, amount)
            rec_amount = amount
        else:
            raise IllegalAction(f"Unknown action {action!r}")
        return self._finish_action(p, action, rec_amount)

    def _apply_raise_to(self, p: Player, amount: int) -> None:
        add = amount - p.bet_this_street
        raise_size = amount - self.current_bet
        full_raise = raise_size >= self.last_raise_size
        self._commit(p, add, counts_as_bet=True)
        if full_raise:
            self.last_raise_size = raise_size
            # action reopened for everyone
            self._reopened_for = {q.seat: True for q in self.players}
        else:
            # short all-in: players who already acted cannot re-raise
            self._reopened_for = {q.seat: (not q.acted_this_street) for q in self.players}
        self.current_bet = amount
        self.last_aggressor = p.seat

    def _finish_action(self, p: Player, action: str, amount: int) -> ActionRecord:
        p.acted_this_street = True
        rec = ActionRecord(self.hand_no, self.street, p.seat, p.name, action, amount, self.pot, p.stack)
        self.actions.append(rec)
        self.history.append(rec)
        self._advance()
        return rec

    # ------------------------------------------------------------------ flow
    def _betting_round_complete(self) -> bool:
        live = [q for q in self.players if not q.folded and not q.eliminated and q.hole_cards]
        if len(live) <= 1:
            return True
        actors = [q for q in live if q.can_act()]
        if not actors:
            return True
        for q in actors:
            if not q.acted_this_street:
                return False
            if q.bet_this_street < self.current_bet:
                return False
        # special preflop case: BB option when everyone limped is covered by acted_this_street
        return True

    def _advance(self) -> None:
        live = [q for q in self.players if not q.folded and not q.eliminated and q.hole_cards]
        if len(live) == 1:
            self._award_uncontested(live[0])
            return
        if self._betting_round_complete():
            self._next_street()
            return
        # next player to act
        s = self.to_act
        for _ in range(len(self.players)):
            s = (s + 1) % len(self.players)
            if self.players[s].can_act():
                self.to_act = s
                return
        self._next_street()

    def _next_street(self) -> None:
        for q in self.players:
            q.bet_this_street = 0
            q.acted_this_street = False
        self.current_bet = 0
        self.last_raise_size = self.big_blind
        self._reopened_for = {q.seat: True for q in self.players}
        idx = STREETS.index(self.street)
        self.street = STREETS[idx + 1]
        if self.street == "flop":
            self.board += self.deck.deal(3)
        elif self.street in ("turn", "river"):
            self.board += self.deck.deal(1)
        elif self.street == "showdown":
            self._showdown()
            return
        actors = [q for q in self.players if q.can_act() and not q.folded and q.hole_cards]
        if len(actors) <= 1 and len([q for q in self.players if not q.folded and q.hole_cards]) >= 2:
            # all-in situation: run out the board
            self.to_act = None
            self._next_street()
            return
        # first to act postflop: left of button
        s = self.button_seat
        for _ in range(len(self.players)):
            s = (s + 1) % len(self.players)
            if self.players[s].can_act() and not self.players[s].folded:
                self.to_act = s
                return
        self.to_act = None

    def _maybe_auto_advance(self) -> None:
        # if nobody can act preflop (everyone all-in from blinds), run out
        if self.to_act is None and self.hand_in_progress:
            self._next_street()

    def _award_uncontested(self, winner: Player) -> None:
        total = self.pot
        # refund any excess the winner put in beyond what others matched
        others_max = max([q.committed for q in self.players if q.seat != winner.seat] + [0])
        excess = max(0, winner.committed - others_max)
        winner.stack += total
        self._end_hand(HandResult(self.hand_no, [card_str(c) for c in self.board],
                                  [{"seat": winner.seat, "name": winner.name, "amount": total - excess, "hand": None}],
                                  [], [], [{"amount": total, "eligible": [winner.seat], "winners": [winner.seat]}]))

    def _showdown(self) -> None:
        contenders = [q for q in self.players if not q.folded and not q.eliminated and q.hole_cards]
        values = {q.seat: evaluate(q.hole_cards + self.board) for q in contenders}
        # side pots from committed amounts
        levels = sorted(set(q.committed for q in self.players if q.committed > 0))
        pots: List[dict] = []
        prev = 0
        winners_total: Dict[int, int] = {}
        for lvl in levels:
            contrib = sum(min(q.committed, lvl) - min(q.committed, prev) for q in self.players)
            eligible = [q.seat for q in contenders if q.committed >= lvl]
            if contrib <= 0:
                prev = lvl
                continue
            if not eligible:
                # money from folded players beyond any contender's commitment: goes to the best remaining contender(s)
                eligible = [q.seat for q in contenders]
            best = max(values[s] for s in eligible)
            win = [s for s in eligible if values[s] == best]
            share, rem = divmod(contrib, len(win))
            # odd chips to the first winner left of the button
            order = sorted(win, key=lambda s: (s - self.button_seat - 1) % len(self.players))
            for i, s in enumerate(order):
                amt = share + (1 if i < rem else 0)
                self.players[s].stack += amt
                winners_total[s] = winners_total.get(s, 0) + amt
            pots.append({"amount": contrib, "eligible": eligible, "winners": win})
            prev = lvl
        showdown = [{"seat": q.seat, "name": q.name, "cards": [card_str(c) for c in q.hole_cards],
                     "hand": describe(values[q.seat]), "value": values[q.seat]} for q in contenders]
        winners = [{"seat": s, "name": self.players[s].name, "amount": amt, "hand": describe(values[s])}
                   for s, amt in winners_total.items()]
        self._end_hand(HandResult(self.hand_no, [card_str(c) for c in self.board], winners, showdown, [], pots))

    def _end_hand(self, result: HandResult) -> None:
        self.hand_in_progress = False
        self.to_act = None
        self.street = "showdown"
        eliminated = []
        remaining = [p for p in self.players if not p.eliminated]
        busted = [p for p in remaining if p.stack <= 0]
        # finishing places: more chips committed this hand finishes higher among simultaneous busts
        busted.sort(key=lambda p: p.committed)
        places_left = len(remaining)
        for p in busted:
            p.eliminated = True
            p.finish_place = places_left
            places_left -= 1
            eliminated.append(p.seat)
            self.event_log.append(f"{p.name} eliminado en {p.finish_place}º lugar")
        result.eliminated = eliminated
        self.last_result = result
        self.results.append(result)
        if len(self.active_players()) == 1:
            self._finish()
        elif eliminated and len(self.active_players()) == 2:
            self.event_log.append("Transición a heads-up: el botón paga la ciega pequeña.")

    def _finish(self) -> None:
        self.finished = True
        self.hand_in_progress = False
        winner = self.active_players()[0]
        winner.finish_place = 1
        amounts = self.config.payout_amounts()
        for p in self.players:
            if p.finish_place is not None and p.finish_place - 1 < len(amounts):
                self.payouts[p.seat] = amounts[p.finish_place - 1]
            else:
                self.payouts[p.seat] = 0.0
        self.event_log.append(f"Torneo terminado. Ganador: {winner.name}")

    # ------------------------------------------------------------------ snapshots
    def snapshot(self) -> "Game":
        return copy.deepcopy(self)

    # ------------------------------------------------------------------ serialisation
    def to_dict(self, reveal_all: bool = False) -> dict:
        lvl = self.level()
        reveal = reveal_all or not self.hand_in_progress
        return {
            "hand_no": self.hand_no,
            "level": lvl.to_dict(),
            "level_index": self.level_index,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "time_to_next_level": self.time_to_next_level(),
            "paused": self.paused,
            "button_seat": self.button_seat,
            "street": self.street,
            "board": [card_str(c) for c in self.board],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "min_raise_size": self.last_raise_size,
            "to_act": self.to_act,
            "hand_in_progress": self.hand_in_progress,
            "finished": self.finished,
            "heads_up": self.is_heads_up(),
            "players": [p.to_dict(reveal=reveal) for p in self.players],
            "legal_actions": self.legal_actions().to_dict() if self.to_act is not None else None,
            "actions": [a.to_dict() for a in self.actions],
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "payouts": {str(k): v for k, v in self.payouts.items()},
            "event_log": self.event_log[-12:],
            "config": self.config.to_dict(),
        }

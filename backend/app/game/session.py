"""Simulator session: a Game plus bots, snapshots (pause/undo/replay) and recommendations."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..analysis.profiles import OpponentProfile
from ..analysis.recommender import Recommendation, recommend
from .bots import bot_decide
from .engine import Game, IllegalAction
from .situation import build_situation
from .structure import TwisterConfig


@dataclass
class DecisionPoint:
    hand_no: int
    street: str
    snapshot: Game
    recommendation: Optional[dict] = None
    taken: Optional[dict] = None


@dataclass
class SimSession:
    id: str
    game: Game
    rng: random.Random
    profiles: Dict[str, OpponentProfile] = field(default_factory=dict)
    decisions: List[DecisionPoint] = field(default_factory=list)
    auto_deal: bool = True
    last_recommendation: Optional[dict] = None

    # ------------------------------------------------------------------ creation
    @classmethod
    def create(cls, config: TwisterConfig, hero_name: str = "Héroe", bot_profiles: Optional[List[str]] = None,
               seed: Optional[int] = None) -> "SimSession":
        names = [hero_name, "Rival A", "Rival B"][: config.players]
        profiles = ["balanced"] + (bot_profiles or ["balanced", "aggressive"])
        seed = seed if seed is not None else random.randrange(1 << 30)
        game = Game(config, names, hero_seat=0, seed=seed, bot_profiles=profiles)
        sess = cls(id=uuid.uuid4().hex[:12], game=game, rng=random.Random(seed))
        sess.game.resume()
        return sess

    # ------------------------------------------------------------------ flow
    def hero_seat(self) -> int:
        return self.game.hero().seat

    def run_until_hero(self, max_steps: int = 200) -> None:
        """Advance bots (and deal new hands) until the hero must act or the game ends."""
        g = self.game
        for _ in range(max_steps):
            if g.finished:
                return
            if not g.hand_in_progress:
                if not self.auto_deal:
                    return
                g.start_hand()
                continue
            if g.to_act is None:
                return
            if g.to_act == self.hero_seat():
                self._record_decision_point()
                return
            action, amount = bot_decide(g, g.to_act, self.rng)
            try:
                g.act(g.to_act, action, amount)
            except IllegalAction:
                la = g.legal_actions()
                g.act(g.to_act, "check" if la.can_check else ("call" if la.can_call else "fold"), 0)

    def _record_decision_point(self) -> None:
        g = self.game
        if self.decisions and self.decisions[-1].hand_no == g.hand_no and self.decisions[-1].street == g.street \
                and self.decisions[-1].taken is None:
            return
        self.decisions.append(DecisionPoint(g.hand_no, g.street, g.snapshot()))

    def recommendation(self) -> Optional[dict]:
        g = self.game
        if not g.hand_in_progress or g.to_act != self.hero_seat():
            return None
        sit = build_situation(g, self.hero_seat(), self.profiles)
        rec: Recommendation = recommend(sit)
        d = rec.to_dict()
        self.last_recommendation = d
        if self.decisions and self.decisions[-1].taken is None:
            self.decisions[-1].recommendation = d
        return d

    def hero_act(self, action: str, amount: int = 0) -> dict:
        g = self.game
        if g.to_act != self.hero_seat():
            raise IllegalAction("No es el turno del héroe")
        rec = self.last_recommendation or self.recommendation()
        g.act(self.hero_seat(), action, amount)
        if self.decisions and self.decisions[-1].taken is None:
            self.decisions[-1].taken = {"action": action, "amount": amount}
        self.run_until_hero()
        return self.state()

    def undo(self) -> dict:
        """Return to the most recent hero decision point (same cards and run-out)."""
        completed = [d for d in self.decisions if d.taken is not None]
        if not completed:
            raise IllegalAction("No hay decisiones que deshacer")
        dp = completed[-1]
        self.decisions = self.decisions[: self.decisions.index(dp)]
        self.game = dp.snapshot.snapshot()
        self.game.resume()
        self._record_decision_point()
        self.last_recommendation = None
        return self.state()

    def compare(self, actions: List[dict]) -> List[dict]:
        """Replay the current decision point with each alternative; same deck → same run-out."""
        g = self.game
        if g.to_act != self.hero_seat():
            raise IllegalAction("No es el turno del héroe")
        base_stack = g.hero().stack + g.hero().committed
        out = []
        for alt in actions:
            sim = g.snapshot()
            sim_rng = random.Random(self.rng.getstate()[1][0])
            try:
                sim.act(self.hero_seat(), alt["action"], int(alt.get("amount", 0)))
            except IllegalAction as e:
                out.append({"action": alt, "error": str(e)})
                continue
            steps = 0
            while sim.hand_in_progress and steps < 100:
                steps += 1
                if sim.to_act is None:
                    break
                if sim.to_act == self.hero_seat():
                    la = sim.legal_actions()
                    # hero plays passively afterwards (check/call) for the comparison
                    sim.act(sim.to_act, "check" if la.can_check else "call", 0)
                else:
                    a, amt = bot_decide(sim, sim.to_act, sim_rng)
                    sim.act(sim.to_act, a, amt)
            hero = sim.hero()
            out.append({
                "action": alt,
                "hero_stack_after": hero.stack,
                "chip_delta": hero.stack - base_stack,
                "board": sim.last_result.board if sim.last_result else [],
                "result": sim.last_result.to_dict() if sim.last_result else None,
                "note": "Resultado de UNA repetición con el mismo reparto; no es el EV. Los bots juegan igual que en la mesa.",
            })
        return out

    # ------------------------------------------------------------------ state
    def state(self) -> dict:
        d = self.game.to_dict()
        d["session_id"] = self.id
        d["hero_seat"] = self.hero_seat()
        d["hero_to_act"] = self.game.hand_in_progress and self.game.to_act == self.hero_seat()
        d["decisions"] = len(self.decisions)
        d["bot_styles"] = {p.name: p.bot_profile for p in self.game.players if not p.is_hero}
        return d

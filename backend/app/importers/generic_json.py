"""Generic JSON hand-history format (documented in docs/IMPORT_FORMAT.md).

Also the target format for external tools (e.g. a screen-capture / OCR
adapter) that want to feed hands into PokerMind AI.
"""
from __future__ import annotations

import json
from typing import List, Tuple

from .models import HandHistory, HHAction, HHPlayer


def parse_generic_json(text: str) -> Tuple[List[HandHistory], List[str]]:
    data = json.loads(text)
    hands_raw = data.get("hands", data if isinstance(data, list) else [data])
    hands: List[HandHistory] = []
    warnings: List[str] = []
    for i, h in enumerate(hands_raw):
        try:
            players = [HHPlayer(p["name"], int(p.get("seat", k + 1)), int(p["stack"]), p.get("position", ""),
                                list(p.get("hole_cards", []))) for k, p in enumerate(h["players"])]
            actions = [HHAction(a["street"], a["player"], a["action"], int(a.get("amount", 0)), bool(a.get("all_in", False)))
                       for a in h.get("actions", [])]
            button = int(h.get("button_seat", players[0].seat))
            if not all(p.position for p in players):
                from .pokerstars import _assign_positions
                _assign_positions(players, button)
            hands.append(HandHistory(
                hand_id=str(h.get("hand_id", i + 1)), source=h.get("source", "json"), hero=h["hero"],
                small_blind=int(h["small_blind"]), big_blind=int(h["big_blind"]), ante=int(h.get("ante", 0)),
                button_seat=button, players=players, actions=actions, board=list(h.get("board", [])),
                timestamp=h.get("timestamp"), tournament_id=h.get("tournament_id"), payouts=h.get("payouts"),
                winners=list(h.get("winners", [])),
            ))
        except (KeyError, ValueError, TypeError) as exc:
            warnings.append(f"Mano {i + 1} omitida: {exc}")
    return hands, warnings

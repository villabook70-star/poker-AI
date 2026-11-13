"""Parser for PokerStars-style text hand histories (Spin & Go / Twister-like formats).

The parser is tolerant: it handles the common line shapes
(``Seat 1: Name (500 in chips)``, ``Name: raises 40 to 60``, ``*** FLOP *** [..]``).
Lines it cannot interpret are ignored and reported in ``warnings``.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import HandHistory, HHAction, HHPlayer

HAND_SPLIT = re.compile(r"\n(?=PokerStars (?:Hand|Game) #)|\n(?=\S+ Hand #)")
HEADER = re.compile(r"(?:PokerStars )?(?:Hand|Game) #(?P<id>\d+):\s*(?:Tournament #(?P<tid>\d+),.*?)?.*?Level\s*\w+\s*\((?P<sb>\d+)/(?P<bb>\d+)\)", re.S)
HEADER_SIMPLE = re.compile(r"#(?P<id>\d+)")
BLINDS = re.compile(r"\((?P<sb>\d+)/(?P<bb>\d+)\)")
SEAT = re.compile(r"^Seat (?P<seat>\d+): (?P<name>.+?) \((?P<stack>[\d,]+) in chips\)")
BUTTON = re.compile(r"Seat #(?P<seat>\d+) is the button")
POST = re.compile(r"^(?P<name>.+?): posts (?P<kind>small blind|big blind|the ante|ante) (?P<amt>[\d,]+)")
DEALT = re.compile(r"^Dealt to (?P<name>.+?) \[(?P<cards>[^\]]+)\]")
ACTION = re.compile(r"^(?P<name>.+?): (?P<act>folds|checks|calls|bets|raises)(?: (?P<a1>[\d,]+))?(?: to (?P<a2>[\d,]+))?(?P<allin> and is all-in)?")
STREET = re.compile(r"^\*\*\* (?P<street>FLOP|TURN|RIVER|SHOW DOWN|SUMMARY) \*\*\*(?: \[(?P<cards>[^\]]+)\])?(?: \[(?P<extra>[^\]]+)\])?")
SHOWS = re.compile(r"^(?P<name>.+?): shows \[(?P<cards>[^\]]+)\]")
COLLECTED = re.compile(r"^(?P<name>.+?) collected (?P<amt>[\d,]+) from")
SUMMARY_CARDS = re.compile(r"Seat \d+: (?P<name>.+?) (?:\(.*?\) )?(?:showed|mucked) \[(?P<cards>[^\]]+)\]")


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def parse_pokerstars(text: str, hero_name: str | None = None) -> Tuple[List[HandHistory], List[str]]:
    hands: List[HandHistory] = []
    warnings: List[str] = []
    text = text.replace("\r\n", "\n")
    chunks = [c.strip() for c in HAND_SPLIT.split("\n" + text) if c.strip()]
    for chunk in chunks:
        try:
            hh = _parse_one(chunk, hero_name)
            if hh:
                hands.append(hh)
        except Exception as exc:  # noqa: BLE001 - report and continue
            warnings.append(f"Mano omitida: {exc}")
    return hands, warnings


def _parse_one(chunk: str, hero_name: str | None) -> HandHistory | None:
    lines = chunk.split("\n")
    head = lines[0]
    m = HEADER.search(chunk)
    hand_id = m.group("id") if m else (HEADER_SIMPLE.search(head).group("id") if HEADER_SIMPLE.search(head) else "?")
    tid = m.group("tid") if m else None
    b = BLINDS.search(head)
    sb, bb = (int(b.group("sb")), int(b.group("bb"))) if b else (0, 0)
    players: List[HHPlayer] = []
    actions: List[HHAction] = []
    board: List[str] = []
    button = 1
    ante = 0
    hero = hero_name or ""
    street = "preflop"
    winners: List[str] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        mm = SEAT.match(line)
        if mm and street == "preflop" and not any(a.action not in ("post_sb", "post_bb", "post_ante") for a in actions):
            if not any(p.name == mm.group("name") for p in players):
                players.append(HHPlayer(mm.group("name"), int(mm.group("seat")), _int(mm.group("stack"))))
            continue
        mm = BUTTON.search(line)
        if mm:
            button = int(mm.group("seat"))
            continue
        mm = POST.match(line)
        if mm:
            kind = mm.group("kind")
            amt = _int(mm.group("amt"))
            if kind == "small blind":
                actions.append(HHAction("preflop", mm.group("name"), "post_sb", amt))
            elif kind == "big blind":
                actions.append(HHAction("preflop", mm.group("name"), "post_bb", amt))
            else:
                ante = max(ante, amt)
                actions.append(HHAction("preflop", mm.group("name"), "post_ante", amt))
            continue
        mm = DEALT.match(line)
        if mm:
            name = mm.group("name")
            hero = hero or name
            for p in players:
                if p.name == name:
                    p.hole_cards = mm.group("cards").split()
            continue
        mm = STREET.match(line)
        if mm:
            st = mm.group("street")
            if st in ("FLOP", "TURN", "RIVER"):
                street = st.lower()
                cards = (mm.group("cards") or "").split()
                if st == "FLOP":
                    board = cards
                else:
                    board = cards + ((mm.group("extra") or "").split())
            elif st == "SHOW DOWN":
                street = "showdown"
            else:
                street = "summary"
            continue
        mm = ACTION.match(line)
        if mm and street in ("preflop", "flop", "turn", "river"):
            name, act = mm.group("name"), mm.group("act")
            allin = bool(mm.group("allin"))
            if act == "folds":
                actions.append(HHAction(street, name, "fold"))
            elif act == "checks":
                actions.append(HHAction(street, name, "check"))
            elif act == "calls":
                actions.append(HHAction(street, name, "call", _int(mm.group("a1") or "0"), allin))
            elif act == "bets":
                actions.append(HHAction(street, name, "bet", _int(mm.group("a1") or "0"), allin))
            elif act == "raises":
                actions.append(HHAction(street, name, "raise", _int(mm.group("a2") or mm.group("a1") or "0"), allin))
            continue
        mm = SHOWS.match(line) or SUMMARY_CARDS.match(line)
        if mm:
            for p in players:
                if p.name == mm.group("name") and not p.hole_cards:
                    p.hole_cards = mm.group("cards").split()
            continue
        mm = COLLECTED.match(line)
        if mm:
            winners.append(mm.group("name"))
            continue
    if not players:
        return None
    _assign_positions(players, button)
    return HandHistory(hand_id=hand_id, source="pokerstars", hero=hero, small_blind=sb, big_blind=bb, ante=ante,
                       button_seat=button, players=players, actions=actions, board=board, tournament_id=tid,
                       winners=list(dict.fromkeys(winners)))


def _assign_positions(players: List[HHPlayer], button_seat: int) -> None:
    players.sort(key=lambda p: p.seat)
    seats = [p.seat for p in players]
    if button_seat not in seats:
        button_seat = seats[0]
    idx = seats.index(button_seat)
    n = len(players)
    if n == 2:
        players[idx].position = "BTN/SB"
        players[(idx + 1) % n].position = "BB"
    else:
        players[idx].position = "BTN"
        players[(idx + 1) % n].position = "SB"
        players[(idx + 2) % n].position = "BB"

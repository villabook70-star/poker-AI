import os

import pytest

from app.analysis.profiles import OpponentProfile, Stat, wilson_interval
from app.analysis.range_model import estimate_preflop_range
from app.analysis.recommender import Situation, VillainInfo, recommend
from app.engine.cards import parse_cards
from app.engine.ranges import load_equity_data
from app.game.session import SimSession
from app.game.structure import default_twister_structure
from app.importers.analyzer import analyze_hand, update_profiles_from_hands
from app.importers.generic_json import parse_generic_json
from app.importers.pokerstars import parse_pokerstars

HAS_MATRIX = load_equity_data() is not None

PS_TEXT = """PokerStars Hand #123456789: Tournament #987654, $1.00+$0.00 USD Hold'em No Limit - Level I (10/20) - 2024/01/01 12:00:00 ET
Table '987654 1' 3-max Seat #1 is the button
Seat 1: Hero (500 in chips)
Seat 2: VillainA (500 in chips)
Seat 3: VillainB (500 in chips)
VillainA: posts small blind 10
VillainB: posts big blind 20
*** HOLE CARDS ***
Dealt to Hero [As Kd]
Hero: raises 20 to 40
VillainA: folds
VillainB: calls 20
*** FLOP *** [Ks 7h 2c]
VillainB: checks
Hero: bets 40
VillainB: folds
Uncalled bet (40) returned to Hero
Hero collected 90 from pot
*** SUMMARY ***
Total pot 90 | Rake 0
Board [Ks 7h 2c]
Seat 1: Hero (button) collected (90)
Seat 2: VillainA (small blind) folded before Flop
Seat 3: VillainB (big blind) folded on the Flop
"""


def test_wilson_and_profile_uncertainty():
    lo, hi = wilson_interval(5, 10)
    assert lo < 0.5 < hi and hi - lo > 0.5
    lo2, hi2 = wilson_interval(500, 1000)
    assert hi2 - lo2 < 0.07
    p = OpponentProfile("X")
    assert p.style().startswith("insuficiente")
    p.vpip = Stat(12, 20)
    p.pfr = Stat(8, 20)
    assert p.style().startswith("insuficiente")   # fewer than 30 hands
    p.vpip = Stat(60, 100)
    p.pfr = Stat(45, 100)
    p.hands = 100
    assert p.style() == "loose-agresivo"
    d = p.to_dict()
    assert d["vpip"]["ci95"][0] < 0.6 < d["vpip"]["ci95"][1]
    assert d["warning"] is None


def test_range_estimate_uses_profile_and_reports_confidence():
    est = estimate_preflop_range("open_raise", "BTN", None, 25)
    assert est.confidence == "muy baja" and est.percent > 0
    prof = OpponentProfile("Tight", hands=200)
    prof.vpip, prof.pfr = Stat(30, 200), Stat(20, 200)
    est2 = estimate_preflop_range("open_raise", "BTN", prof, 25)
    assert est2.percent < est.percent
    assert est2.confidence == "alta"


def _facing_shove_situation(cards="AsKd"):
    return Situation(parse_cards(cards), [], "BB", 280, 20, 550, 280, 20, 0, "preflop",
                     [VillainInfo("V", "SB", 0, 530, False, True, "shove")], None, None, 2, "none", 1)


def test_recommend_facing_allin_uses_pot_odds():
    rec = recommend(_facing_shove_situation("AsKd")).to_dict()
    assert rec["action"] == "call"
    assert rec["pot_odds"]["required_equity"] == pytest.approx(280 / 830, abs=1e-6)
    assert rec["equity"]["method"] in ("exact", "monte_carlo")
    assert "exact" in rec["sources"]
    rec2 = recommend(_facing_shove_situation("7c2d")).to_dict()
    assert rec2["action"] == "fold"


def test_recommend_postflop_facing_bet():
    s = Situation(parse_cards("AhKh"), parse_cards("Qh 7h 2c"), "BTN", 400, 60, 240, 120, 20, 0, "flop",
                  [VillainInfo("V", "BB", 300, 180, False, False, "call")], None, None, 3, "open_raise", 1)
    rec = recommend(s).to_dict()
    assert rec["action"] in ("call", "allin", "raise")
    assert rec["equity"]["equity"] > 0.4
    assert any(a["action"] == "fold" for a in rec["alternatives"])
    assert rec["gto_comparison"]["available"] is False


@pytest.mark.skipif(not HAS_MATRIX, reason="equity matrix not built")
def test_pushfold_nash_properties():
    from app.engine.pushfold import solve_hu_push_fold, hu_push_decision

    s10 = solve_hu_push_fold(10.0)
    s5 = solve_hu_push_fold(5.0)
    assert s5.push_percent() > s10.push_percent()           # shorter stack pushes wider
    assert s10.push[0] == 1.0 and s10.call[0] == 1.0        # AA always pushes and calls
    assert hu_push_decision("72o", 15.0)["action"] == "fold"
    assert hu_push_decision("AKs", 15.0)["action"] == "push"
    assert s10.exploitability < 0.05                         # converged


@pytest.mark.skipif(not HAS_MATRIX, reason="equity matrix not built")
def test_recommend_short_stack_uses_nash():
    s = Situation(parse_cards("As5d"), [], "BTN/SB", 150, 10, 30, 10, 20, 0, "preflop",
                  [VillainInfo("V", "BB", 300, 20, False, False, "unknown")], None, None, 2, "none", 0)
    rec = recommend(s).to_dict()
    assert "nash" in rec["sources"]
    assert rec["gto_comparison"]["available"] is True
    assert rec["action"] in ("allin", "fold")


def test_simulator_session_flow_and_undo():
    s = SimSession.create(default_twister_structure(), seed=3)
    s.run_until_hero()
    assert s.state()["hero_to_act"]
    cards = list(s.game.hero().hole_cards)
    rec = s.recommendation()
    assert rec["action"] in ("fold", "call", "raise", "allin", "check", "bet")
    la = s.game.legal_actions()
    s.hero_act("fold" if not la.can_check else "check", 0)
    s.undo()
    assert list(s.game.hero().hole_cards) == cards
    results = s.compare([{"action": "fold"}])
    assert results and results[0]["chip_delta"] <= 0
    # play a whole tournament following the recommendations
    n = 0
    while not s.game.finished and n < 300:
        rec = s.recommendation()
        s.hero_act(rec["action"], rec["amount"])
        n += 1
    assert s.game.finished
    assert sum(p.stack for p in s.game.players) == 1500


def test_pokerstars_import_and_analysis():
    hands, warnings = parse_pokerstars(PS_TEXT)
    assert len(hands) == 1 and not warnings
    h = hands[0]
    assert h.hero == "Hero" and h.big_blind == 20 and h.board == ["Ks", "7h", "2c"]
    pos = {p.name: p.position for p in h.players}
    assert pos == {"Hero": "BTN", "VillainA": "SB", "VillainB": "BB"}
    assert [a.action for a in h.actions] == ["post_sb", "post_bb", "raise", "fold", "call", "check", "bet", "fold"]
    profiles = update_profiles_from_hands(hands, {})
    assert profiles["VillainB"].vpip.successes == 1 and profiles["VillainA"].vpip.successes == 0
    analysis = analyze_hand(h, profiles)
    assert len(analysis["decisions"]) == 2
    assert analysis["decisions"][0]["street"] == "preflop" and analysis["decisions"][1]["street"] == "flop"
    assert "action" in analysis["decisions"][0]["recommendation"]


def test_generic_json_import():
    doc = {"hands": [{"hand_id": "1", "hero": "Me", "small_blind": 10, "big_blind": 20, "button_seat": 1,
                      "players": [{"name": "Me", "seat": 1, "stack": 500, "hole_cards": ["Ah", "Ad"]},
                                  {"name": "V1", "seat": 2, "stack": 500}, {"name": "V2", "seat": 3, "stack": 500}],
                      "actions": [{"street": "preflop", "player": "V1", "action": "post_sb", "amount": 10},
                                  {"street": "preflop", "player": "V2", "action": "post_bb", "amount": 20},
                                  {"street": "preflop", "player": "Me", "action": "raise", "amount": 500, "all_in": True},
                                  {"street": "preflop", "player": "V1", "action": "fold"},
                                  {"street": "preflop", "player": "V2", "action": "fold"}]}]}
    import json
    hands, warnings = parse_generic_json(json.dumps(doc))
    assert len(hands) == 1 and not warnings
    a = analyze_hand(hands[0])
    assert len(a["decisions"]) == 1 and a["decisions"][0]["taken"]["action"] == "raise"

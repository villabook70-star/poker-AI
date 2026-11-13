import random

import pytest

from app.game.engine import Game, IllegalAction
from app.game.structure import BlindLevel, TwisterConfig, default_twister_structure


def make_game(seed=1, **kw):
    cfg = default_twister_structure()
    for k, v in kw.items():
        setattr(cfg, k, v)
    return Game(cfg, ["Hero", "A", "B"], hero_seat=0, seed=seed)


def test_initial_blinds_and_positions():
    g = make_game()
    g.start_hand()
    pos = {p.position: p for p in g.players}
    assert set(pos) == {"BTN", "SB", "BB"}
    assert pos["SB"].committed == 10 and pos["BB"].committed == 20 and pos["BTN"].committed == 0
    assert g.pot == 30
    assert g.to_act == pos["BTN"].seat   # BTN acts first preflop 3-handed
    assert all(len(p.hole_cards) == 2 for p in g.players)


def test_legal_actions_preflop_btn():
    g = make_game()
    g.start_hand()
    la = g.legal_actions()
    assert la.can_fold and la.can_call and la.can_raise and not la.can_check and not la.can_bet
    assert la.call_amount == 20 and la.min_raise_to == 40 and la.max_raise_to == 500


def test_min_raise_rules_and_illegal_actions():
    g = make_game()
    g.start_hand()
    btn = g.to_act
    with pytest.raises(IllegalAction):
        g.act(btn, "check")
    with pytest.raises(IllegalAction):
        g.act(btn, "raise", 30)        # below min raise (40)
    with pytest.raises(IllegalAction):
        g.act((btn + 1) % 3, "fold")    # not their turn
    g.act(btn, "raise", 60)             # raise of 40 -> next min raise to 100
    la = g.legal_actions()
    assert la.min_raise_to == 100 and la.call_amount == 50  # SB has 10 in


def test_bb_option_when_limped():
    g = make_game()
    g.start_hand()
    btn = g.to_act
    g.act(btn, "call")
    g.act(g.to_act, "call")   # SB completes
    la = g.legal_actions()
    bb = g.to_act
    assert g.players[bb].position == "BB" and la.can_check and la.can_raise
    g.act(bb, "check")
    assert g.street == "flop" and len(g.board) == 3 and g.pot == 60
    # first to act postflop is SB (left of button)
    assert g.players[g.to_act].position == "SB"


def test_uncontested_pot_awarded():
    g = make_game()
    g.start_hand()
    g.act(g.to_act, "raise", 60)
    g.act(g.to_act, "fold")
    g.act(g.to_act, "fold")
    assert not g.hand_in_progress
    btn = next(p for p in g.players if p.position == "BTN")
    assert btn.stack == 500 + 30
    assert sum(p.stack for p in g.players) == 1500


def test_side_pots_and_chip_conservation():
    cfg = default_twister_structure()
    g = Game(cfg, ["Hero", "A", "B"], hero_seat=0, seed=3)
    g.players[1].stack = 100   # short stack
    g.start_hand()
    # everyone all-in
    for _ in range(3):
        if not g.hand_in_progress:
            break
        la = g.legal_actions()
        g.act(g.to_act, "raise" if la.can_raise else "call", la.max_raise_to if la.can_raise else 0)
    assert not g.hand_in_progress
    assert sum(p.stack for p in g.players) == 1100
    res = g.last_result
    assert len(res.pots) >= 1
    assert sum(p["amount"] for p in res.pots) == 1100
    # at most one player can win more than the main pot capped by the short stack's involvement
    short = g.players[1]
    assert short.stack <= 300  # 100 * 3 max for the short stack


def test_heads_up_transition_button_is_small_blind():
    g = make_game(seed=4)
    g.players[2].stack = 20  # B will be all-in from the BB
    # arrange positions: seat 0 BTN, 1 SB, 2 BB on hand 1
    g.start_hand()
    assert g.players[2].position == "BB" and g.players[2].all_in
    # BTN and SB call to see the board; chips are conserved
    g.act(g.to_act, "call")
    g.act(g.to_act, "call")
    while g.hand_in_progress:
        la = g.legal_actions()
        g.act(g.to_act, "check" if la.can_check else "call")
    assert sum(p.stack for p in g.players) == 1020
    if g.players[2].eliminated:
        assert g.players[2].finish_place == 3
        assert g.is_heads_up()
        g.start_hand()
        positions = {p.position for p in g.players if not p.eliminated}
        assert positions == {"BTN/SB", "BB"}
        btn = g.players[g.button_seat]
        assert btn.position == "BTN/SB" and btn.committed == g.small_blind
        # heads-up: button (SB) acts first preflop
        assert g.to_act == g.button_seat


def test_level_progression_by_hands_and_antes():
    cfg = TwisterConfig(level_mode="hands", hands_per_level=2,
                        levels=[BlindLevel(1, 10, 20, 0), BlindLevel(2, 15, 30, 0), BlindLevel(3, 20, 40, 5)])
    g = Game(cfg, ["H", "A", "B"], seed=9)
    seen = []
    for _ in range(6):
        g.start_hand()
        seen.append((g.big_blind, g.ante))
        while g.hand_in_progress:
            la = g.legal_actions()
            g.act(g.to_act, "check" if la.can_check else "call")
        if g.finished:
            break
    assert seen[:2] == [(20, 0), (20, 0)] and seen[2:4] == [(30, 0), (30, 0)] and seen[4] == (40, 5)
    g.start_hand()
    assert g.ante == 5 and all(p.committed >= 5 for p in g.active_players())


def test_level_progression_by_virtual_time():
    cfg = TwisterConfig(level_mode="time", seconds_per_hand=60)
    g = Game(cfg, ["H", "A", "B"], seed=2)
    g.start_hand()
    assert g.level_index == 0
    g.advance_time(130)
    assert g.level_index == 1 and g.time_to_next_level() == pytest.approx(110)


def test_payouts_and_finish_places():
    cfg = TwisterConfig(payouts=[0.8, 0.2], buy_in=10, prize_multiplier=3)
    assert cfg.payout_amounts() == [24.0, 6.0]
    with pytest.raises(ValueError):
        TwisterConfig(payouts=[0.5, 0.3])
    rng = random.Random(1)
    g = Game(cfg, ["H", "A", "B"], seed=11)
    hands = 0
    while not g.finished and hands < 500:
        g.start_hand()
        hands += 1
        while g.hand_in_progress:
            la = g.legal_actions()
            opts = [("check", 0)] if la.can_check else []
            if la.can_call:
                opts.append(("call", 0))
            if la.can_fold and not la.can_check:
                opts.append(("fold", 0))
            if la.can_raise and rng.random() < 0.3:
                opts.append(("raise", la.max_raise_to))
            if la.can_bet and rng.random() < 0.3:
                opts.append(("bet", rng.randint(la.min_bet, la.max_bet)))
            a, amt = rng.choice(opts)
            g.act(g.to_act, a, amt)
        assert sum(p.stack for p in g.players) == 1500
    assert g.finished
    places = sorted(p.finish_place for p in g.players)
    assert places == [1, 2, 3]
    winner = next(p for p in g.players if p.finish_place == 1)
    assert g.payouts[winner.seat] == 24.0 and winner.stack == 1500
    second = next(p for p in g.players if p.finish_place == 2)
    assert g.payouts[second.seat] == 6.0


def test_short_allin_does_not_reopen_action():
    g = make_game(seed=6)
    g.players[1].stack = 45  # SB short: after posting 10 has 35 behind, can only shove to 45 (< min raise 80 after a raise to 60)
    g.start_hand()
    btn = g.to_act
    g.act(btn, "raise", 60)
    sb = g.to_act
    g.act(sb, "raise", 45) if g.legal_actions().can_raise else g.act(sb, "call")
    # SB's all-in for 45 is below the raise to 60, so it is a call; BB can still raise (hasn't acted)
    assert g.players[sb].all_in
    la = g.legal_actions()
    assert g.players[g.to_act].position == "BB" and la.can_raise

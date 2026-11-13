import pytest

from app.engine.cards import parse_cards
from app.engine.equity import calculate_equity, hand_vs_hand_exact
from app.engine.pot_odds import breakeven_fold_frequency, ev_call, ev_shove, pot_odds
from app.engine.ranges import Range, expand_token
from app.engine.icm import icm_equities


def test_exact_river_equity():
    # river: hero has the nuts
    r = calculate_equity(parse_cards("AsKs"), [Range.single(*parse_cards("QdQc"))], parse_cards("Qs Js Ts 2c 3d"))
    assert r.method == "exact" and r.equity == 1.0 and r.win == 1.0


def test_exact_river_tie():
    r = calculate_equity(parse_cards("AhKh"), [Range.single(*parse_cards("AsKs"))], parse_cards("2c 7d 9s Jc 3h"))
    assert r.method == "exact" and r.equity == 0.5 and r.tie == 1.0


def test_exact_turn_outs():
    # flush draw on the turn: 9 outs of 44 -> 9/44
    r = calculate_equity(parse_cards("Ah Kh"), [Range.single(*parse_cards("7c 7d"))], parse_cards("Qh 2h 7s 9c"))
    # villain has trips; hero wins only with a heart that does not pair the board (7h -> quads, 9h -> full house): 7 outs of 44
    assert r.method == "exact"
    assert abs(r.equity - 7 / 44) < 1e-9


def test_exact_preflop_aa_vs_kk_known_value():
    r = hand_vs_hand_exact(parse_cards("AsAd"), parse_cards("KhKd"))
    assert r.method == "exact"
    assert abs(r.equity - 0.8195) < 0.001  # well-known 81.95%


def test_monte_carlo_is_close_to_exact():
    exact = calculate_equity(parse_cards("AhKh"), [Range.single(*parse_cards("7c7d"))], parse_cards("Qh 2h 7s"), mode="exact")
    mc = calculate_equity(parse_cards("AhKh"), [Range.single(*parse_cards("7c7d"))], parse_cards("Qh 2h 7s"), mode="mc", samples=40000, seed=3)
    assert mc.method == "monte_carlo" and mc.samples == 40000
    assert abs(mc.equity - exact.equity) < 4 * mc.std_error + 0.005


def test_three_way_equities_sum_to_one():
    r = calculate_equity(parse_cards("AhKh"), [Range.random_hand(), Range.random_hand()], samples=10000, seed=5)
    assert r.opponents == 2
    assert abs(r.equity + sum(r.villain_equities) - 1.0) < 1e-6


def test_range_vs_range_removes_conflicts():
    r = calculate_equity(parse_cards("AsAd"), [Range.from_text("AA, KK")], mode="mc", samples=5000, seed=2)
    assert 0.7 < r.equity < 0.85  # AhAc (1 combo, 50%) and six KK combos (~82%) remain -> ~77%


def test_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_equity(parse_cards("AsAd"), [Range.single(*parse_cards("AsKd"))])
    with pytest.raises(ValueError):
        calculate_equity(parse_cards("As"), [Range.random_hand()])


def test_range_notation():
    assert expand_token("22+") == [r * 2 for r in "23456789TJQKA"]
    assert expand_token("A2s+") == [f"A{r}s" for r in "23456789TJQK"]
    assert expand_token("T9s-54s") == ["54s", "65s", "76s", "87s", "98s", "T9s"]
    assert expand_token("JJ-88") == ["88", "99", "TT", "JJ"]
    assert expand_token("AK") == ["AKs", "AKo"]
    r = Range.from_text("AA, AKs:0.5")
    assert r.combo_count() == 10 and abs(r.total_weight() - 8.0) < 1e-9
    assert Range.random_hand().combo_count() == 1326
    assert Range.from_text("22+, A2s+, KQo").percent_of_all() == pytest.approx(10.41, abs=0.01)


def test_pot_odds_and_ev():
    po = pot_odds(300, 100)
    assert po.ratio == 3.0 and po.required_equity == 0.25
    assert ev_call(0.25, 300, 100) == pytest.approx(0.0)   # break-even exactly at the required equity
    assert ev_call(0.5, 300, 100) == pytest.approx(100.0)
    assert breakeven_fold_frequency(100, 100) == 0.5
    # shove: villain always folds -> win pot
    assert ev_shove(0.0, 150, 400, 400, 1.0) == 150
    # shove: villain always calls, 50% equity, pot 150, risk 400 win 550 -> 0.5*550 - 0.5*400 = 75
    assert ev_shove(0.5, 150, 400, 400, 0.0) == pytest.approx(75.0)


def test_icm():
    eq = icm_equities([500, 500, 500], [1.0])
    assert all(abs(e - 1 / 3) < 1e-9 for e in eq)
    eq = icm_equities([1000, 400, 100], [0.7, 0.3])
    assert abs(sum(eq) - 1.0) < 1e-9
    assert eq[0] > eq[1] > eq[2]
    # ICM: chip leader's share of prizes is less than their share of chips with a 2nd place payout
    assert eq[0] < 1000 / 1500
    assert icm_equities([0, 300, 200], [1.0])[0] == 0.0

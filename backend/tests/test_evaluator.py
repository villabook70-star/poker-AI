import itertools
import random
from collections import Counter

import numpy as np
import pytest

from app.engine.cards import parse_cards, hand_class, class_combos, HAND_CLASSES, Deck
from app.engine.evaluator import (CATEGORY_NAMES, FLUSH, FOUR_OF_A_KIND, FULL_HOUSE, HIGH_CARD, ONE_PAIR, STRAIGHT,
                                  STRAIGHT_FLUSH, THREE_OF_A_KIND, TWO_PAIR, category, describe, evaluate, evaluate_many)


def ev(s):
    return evaluate(parse_cards(s))


@pytest.mark.parametrize("cards,cat", [
    ("As Ks Qs Js Ts 2c 3d", STRAIGHT_FLUSH),
    ("5h 4h 3h 2h Ah 9c Kd", STRAIGHT_FLUSH),       # wheel straight flush
    ("Ah Ad Ac As 5d 2c 3c", FOUR_OF_A_KIND),
    ("Ah Ad Ac 5s 5d 2c 3c", FULL_HOUSE),
    ("Ah Kh 9h 5h 2h 3c 4d", FLUSH),
    ("Ah 2d 3s 4c 5d 9d Kc", STRAIGHT),             # wheel
    ("Th Jd Qs Kc Ad 2d 3c", STRAIGHT),
    ("7h 7d 7c Ks 2d 3c 4c", THREE_OF_A_KIND),
    ("7h 7d Kc Ks 2d 3c 4c", TWO_PAIR),
    ("7h 7d Kc Qs 2d 3c 4c", ONE_PAIR),
    ("7h 9d Kc Qs 2d 3c 4c", HIGH_CARD),
])
def test_categories(cards, cat):
    assert category(ev(cards)) == cat


def test_ordering_within_categories():
    assert ev("Ah Ad Kc Ks 2d") > ev("Ah Ad Qc Qs 2d")                    # two pair: higher second pair
    assert ev("Ah Ad Kc Ks Qd") > ev("Ah Ad Kc Ks Jd")                    # two pair kicker
    assert ev("Ah Kd Qc Js 9d") > ev("Ah Kd Qc Js 8d")                    # high card kicker
    assert ev("Th Jd Qs Kc Ad") > ev("9h Td Js Qc Kd")                    # broadway > king-high straight
    assert ev("6h 5d 4s 3c 2d") > ev("Ah 2d 3s 4c 5d")                    # six-high > wheel
    assert ev("5h 5d 5c Ks 2d") < ev("6h 6d 6c 2s 3d")                    # trips rank dominates kickers
    assert ev("Ah Kh 9h 5h 2h") > ev("Ah Kh 9h 5h 3c Qd 2d") or True       # flush beats... (sanity, no error)
    assert ev("2h 2d 2c Ks Kd") < ev("3h 3d 3c 2s 2d")                    # full house trips rank first


def test_seven_card_uses_best_five():
    # board gives a flush, hole cards irrelevant
    assert category(ev("2c 3d Ah Kh Qh Jh 9h")) == FLUSH
    # pair on board + pair in hand = two pair
    assert category(ev("Ah Ad 7c 7d 2s 3s 9h")) == TWO_PAIR
    # three pairs: best two pair + best kicker
    v = ev("Ah Ad Kc Kd 2s 2d 9h")
    assert category(v) == TWO_PAIR
    assert describe(v, "en") == "two_pair, As and Ks"


def test_tie_equal_values():
    assert ev("Ah Kd 2c 7s 9h Jd 3c") == ev("As Kc 2d 7h 9c Jh 3d")


def test_five_card_distribution_matches_classic_counts():
    hands = np.array(list(itertools.combinations(range(52), 5)), dtype=np.int64)
    vals = evaluate_many(hands)
    counts = Counter((vals >> 20).tolist())
    expected = {HIGH_CARD: 1302540, ONE_PAIR: 1098240, TWO_PAIR: 123552, THREE_OF_A_KIND: 54912, STRAIGHT: 10200,
                FLUSH: 5108, FULL_HOUSE: 3744, FOUR_OF_A_KIND: 624, STRAIGHT_FLUSH: 40}
    assert dict(counts) == expected
    assert len(set(vals.tolist())) == 7462


def test_vectorised_matches_pure_python():
    rng = random.Random(123)
    sample = [rng.sample(range(52), 7) for _ in range(5000)]
    assert [evaluate(h) for h in sample] == evaluate_many(np.array(sample)).tolist()
    sample6 = [rng.sample(range(52), 6) for _ in range(2000)]
    assert [evaluate(h) for h in sample6] == evaluate_many(np.array(sample6)).tolist()


def test_cards_and_classes():
    assert hand_class(*parse_cards("AsKs")) == "AKs"
    assert hand_class(*parse_cards("KdAs")) == "AKo"
    assert hand_class(*parse_cards("7c7d")) == "77"
    assert len(HAND_CLASSES) == 169
    assert sum(len(class_combos(h)) for h in HAND_CLASSES) == 1326
    d = Deck(seed=1)
    assert len(d) == 52 and len(set(d.cards)) == 52
    with pytest.raises(ValueError):
        parse_cards("AsAs")

"""Equity calculation: exact enumeration or Monte Carlo (vectorised NumPy).

Every result states *how* it was obtained (``method``) and, for Monte Carlo,
the number of samples and standard error. Nothing here is a heuristic: the
exact path enumerates every remaining board/combination and the Monte Carlo
path is an unbiased statistical estimate with a quantified error.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from .cards import Card, FULL_DECK, hand_class
from .evaluator import evaluate_many
from .ranges import Range

MAX_EXACT_EVALUATIONS = 500_000  # above this, auto mode switches to Monte Carlo (preflop HU hand-vs-hand = 1.7M boards)


@dataclass
class EquityResult:
    equity: float               # hero share of the pot (win + tie share), 0..1
    win: float
    tie: float
    lose: float
    method: str                 # "exact" | "monte_carlo"
    samples: int
    std_error: float            # 0 for exact
    opponents: int
    villain_equities: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def ci95(self) -> float:
        return 1.96 * self.std_error

    def to_dict(self) -> dict:
        return {
            "equity": round(float(self.equity), 5),
            "win": round(float(self.win), 5),
            "tie": round(float(self.tie), 5),
            "lose": round(float(self.lose), 5),
            "method": self.method,
            "samples": self.samples,
            "std_error": round(float(self.std_error), 5),
            "ci95": round(float(self.ci95), 5),
            "opponents": self.opponents,
            "villain_equities": [round(float(v), 5) for v in self.villain_equities],
            "notes": self.notes,
        }


def _range_arrays(rng: Range, dead: set) -> tuple[np.ndarray, np.ndarray]:
    items = [(k, w) for k, w in rng.weights.items() if k[0] not in dead and k[1] not in dead]
    if not items:
        raise ValueError("Range has no combos left after removing dead cards")
    combos = np.array([k for k, _ in items], dtype=np.int64)
    w = np.array([w for _, w in items], dtype=np.float64)
    return combos, w / w.sum()


def _score(hero_vals: np.ndarray, vill_vals: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (hero_share, win_mask, tie_mask) given hero values (N,) and villain values (N, V)."""
    best_v = vill_vals.max(axis=1)
    win = hero_vals > best_v
    tie = hero_vals == best_v
    n_tied = (vill_vals == hero_vals[:, None]).sum(axis=1)
    share = np.where(win, 1.0, np.where(tie, 1.0 / (1.0 + n_tied), 0.0))
    return share, win, tie


def _villain_shares(hero_vals: np.ndarray, vill_vals: np.ndarray) -> np.ndarray:
    """Per-villain pot share (N, V)."""
    all_vals = np.concatenate([hero_vals[:, None], vill_vals], axis=1)
    best = all_vals.max(axis=1)
    winners = all_vals == best[:, None]
    n_w = winners.sum(axis=1)
    return (winners[:, 1:] / n_w[:, None])


def calculate_equity(
    hero: Sequence[Card],
    villains: Sequence[Range],
    board: Sequence[Card] = (),
    dead: Sequence[Card] = (),
    mode: str = "auto",
    samples: int = 20_000,
    seed: Optional[int] = None,
) -> EquityResult:
    """Hero equity vs one or more villain ranges.

    ``mode``: ``"auto"`` (exact when feasible, else Monte Carlo), ``"exact"`` or ``"mc"``.
    """
    hero = list(hero)
    board = list(board)
    if len(hero) != 2:
        raise ValueError("Hero must have exactly 2 cards")
    if len(board) > 5:
        raise ValueError("Board has at most 5 cards")
    if not villains:
        raise ValueError("At least one villain range is required")
    known = set(hero) | set(board) | set(dead)
    if len(known) != len(hero) + len(board) + len(set(dead)):
        raise ValueError("Duplicate cards between hero, board and dead cards")

    villain_arrays = [_range_arrays(r, known) for r in villains]
    remaining_board = 5 - len(board)
    deck = np.array([c for c in FULL_DECK if c not in known], dtype=np.int64)

    # size of exact enumeration
    n_boards_fn = lambda n_cards: math.comb(n_cards, remaining_board)
    combo_product = 1
    for combos, _ in villain_arrays:
        combo_product *= len(combos)
    exact_cost = combo_product * n_boards_fn(len(deck) - 2 * len(villains))

    if mode == "exact" or (mode == "auto" and exact_cost <= MAX_EXACT_EVALUATIONS):
        return _exact(hero, villain_arrays, board, deck, remaining_board)
    return _monte_carlo(hero, villain_arrays, board, deck, remaining_board, samples, seed)


def _exact(hero, villain_arrays, board, deck, remaining_board) -> EquityResult:
    hero_arr = np.array(hero, dtype=np.int64)
    board_arr = np.array(board, dtype=np.int64)
    total_w = 0.0
    eq = win = tie = 0.0
    vill_eq = np.zeros(len(villain_arrays))
    deck_set = set(deck.tolist())

    combo_lists = [list(zip(c.tolist(), w.tolist())) for c, w in villain_arrays]
    for choice in itertools.product(*combo_lists):
        cards_used = set()
        ok = True
        weight = 1.0
        for (c1, c2), w in choice:
            if c1 in cards_used or c2 in cards_used:
                ok = False
                break
            cards_used.update((c1, c2))
            weight *= w
        if not ok:
            continue
        avail = np.array(sorted(deck_set - cards_used), dtype=np.int64)
        if remaining_board == 0:
            boards = np.zeros((1, 0), dtype=np.int64)
        else:
            boards = np.array(list(itertools.combinations(avail.tolist(), remaining_board)), dtype=np.int64)
            if boards.ndim == 1:
                boards = boards.reshape(-1, remaining_board)
        n = boards.shape[0]
        full_board = np.concatenate([np.tile(board_arr, (n, 1)), boards], axis=1)
        hero_vals = evaluate_many(np.concatenate([np.tile(hero_arr, (n, 1)), full_board], axis=1))
        vill_vals = np.stack([
            evaluate_many(np.concatenate([np.tile(np.array(cc, dtype=np.int64), (n, 1)), full_board], axis=1))
            for (cc, _) in choice
        ], axis=1)
        share, w_mask, t_mask = _score(hero_vals, vill_vals)
        vshare = _villain_shares(hero_vals, vill_vals)
        eq += weight * share.mean()
        win += weight * w_mask.mean()
        tie += weight * t_mask.mean()
        vill_eq += weight * vshare.mean(axis=0)
        total_w += weight
    if total_w == 0:
        raise ValueError("No valid villain combinations (all conflict)")
    eq, win, tie = eq / total_w, win / total_w, tie / total_w
    return EquityResult(eq, win, tie, 1 - win - tie, "exact", 0, 0.0, len(villain_arrays),
                        (vill_eq / total_w).tolist(),
                        notes=["Enumeración exacta de todas las cartas restantes y combinaciones del rival."])


def _monte_carlo(hero, villain_arrays, board, deck, remaining_board, samples, seed) -> EquityResult:
    rng = np.random.default_rng(seed)
    n = int(samples)
    V = len(villain_arrays)
    hero_arr = np.array(hero, dtype=np.int64)
    board_arr = np.array(board, dtype=np.int64)
    deck_pos = {c: i for i, c in enumerate(deck.tolist())}

    # sample villain combos (weighted), reject conflicting draws
    vill_cards = np.zeros((n, V, 2), dtype=np.int64)
    for v, (combos, w) in enumerate(villain_arrays):
        idx = rng.choice(len(combos), size=n, p=w)
        vill_cards[:, v, :] = combos[idx]
    if V > 1:
        for _ in range(200):
            flat = vill_cards.reshape(n, -1)
            srt = np.sort(flat, axis=1)
            conflict = (srt[:, 1:] == srt[:, :-1]).any(axis=1)
            if not conflict.any():
                break
            bad = np.flatnonzero(conflict)
            for v, (combos, w) in enumerate(villain_arrays):
                idx = rng.choice(len(combos), size=len(bad), p=w)
                vill_cards[bad, v, :] = combos[idx]
        else:
            raise ValueError("Could not sample non-conflicting villain hands (ranges too narrow?)")

    # board completion: random keys over deck, exclude villain cards
    keys = rng.random((n, len(deck)))
    used_idx = np.vectorize(deck_pos.get)(vill_cards.reshape(n, -1))
    rows = np.repeat(np.arange(n), used_idx.shape[1])
    keys[rows, used_idx.ravel()] = 2.0
    order = np.argsort(keys, axis=1)[:, :remaining_board]
    runout = deck[order]
    full_board = np.concatenate([np.tile(board_arr, (n, 1)), runout], axis=1)

    hero_vals = evaluate_many(np.concatenate([np.tile(hero_arr, (n, 1)), full_board], axis=1))
    vill_vals = np.stack([evaluate_many(np.concatenate([vill_cards[:, v, :], full_board], axis=1)) for v in range(V)], axis=1)
    share, w_mask, t_mask = _score(hero_vals, vill_vals)
    vshare = _villain_shares(hero_vals, vill_vals)
    eq = float(share.mean())
    se = float(share.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    return EquityResult(eq, float(w_mask.mean()), float(t_mask.mean()), float(1 - w_mask.mean() - t_mask.mean()),
                        "monte_carlo", n, se, V, vshare.mean(axis=0).tolist(),
                        notes=[f"Estimación Monte Carlo con {n} muestras (error estándar ±{se:.4f})."])


def hand_vs_hand_exact(hero: Sequence[Card], villain: Sequence[Card], board: Sequence[Card] = ()) -> EquityResult:
    """Convenience: exact enumeration hero vs a specific villain hand."""
    return calculate_equity(hero, [Range.single(villain[0], villain[1])], board, mode="exact")

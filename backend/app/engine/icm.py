"""Independent Chip Model (Malmuth-Harville) for tournament equity.

Exact given the model's assumption (probability of finishing first is
proportional to stack size, recursively for later places). ICM is itself a
model, not a certainty - label results accordingly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Sequence, Tuple


def icm_equities(stacks: Sequence[float], payouts: Sequence[float]) -> List[float]:
    """Return the prize-money equity of each stack under Malmuth-Harville ICM.

    ``payouts`` is ordered 1st, 2nd, ... ; missing places pay zero.
    Players with a zero stack get zero equity.
    """
    n = len(stacks)
    pays = list(payouts)[:n] + [0.0] * max(0, n - len(payouts))
    total = float(sum(stacks))
    if total <= 0:
        return [0.0] * n
    stacks_t: Tuple[float, ...] = tuple(float(s) for s in stacks)

    @lru_cache(maxsize=None)
    def prob_place(player: int, place: int, remaining: Tuple[int, ...]) -> float:
        """P(player finishes in `place` (0-based) among `remaining` players)."""
        rem_total = sum(stacks_t[i] for i in remaining)
        if rem_total <= 0:
            return 0.0
        if place == 0:
            return stacks_t[player] / rem_total
        p = 0.0
        for other in remaining:
            if other == player or stacks_t[other] <= 0:
                continue
            p_first = stacks_t[other] / rem_total
            rest = tuple(i for i in remaining if i != other)
            p += p_first * prob_place(player, place - 1, rest)
        return p

    everyone = tuple(range(n))
    out = []
    for i in range(n):
        if stacks_t[i] <= 0:
            out.append(0.0)
            continue
        eq = 0.0
        for place in range(n):
            if pays[place] == 0:
                continue
            eq += pays[place] * prob_place(i, place, everyone)
        out.append(eq)
    return out


def icm_delta(stacks_before: Sequence[float], stacks_after: Sequence[float], payouts: Sequence[float],
              player: int) -> float:
    before = icm_equities(stacks_before, payouts)[player]
    after = icm_equities(stacks_after, payouts)[player]
    return after - before

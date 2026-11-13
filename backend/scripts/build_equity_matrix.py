"""Build the 169x169 preflop equity matrix by Monte Carlo simulation.

Usage: python scripts/build_equity_matrix.py [--samples 20000] [--seed 7]

Output: data/preflop_equity_169.json with
  classes      : the 169 labels (same order as app.engine.cards.HAND_CLASSES)
  equity       : E[i][j] = share of the pot class i wins vs class j all-in preflop
  combo_counts : number of non-conflicting combo pairs (i, j) (exact, by enumeration)
  vs_random    : equity of each class vs a uniformly random hand (weighted by combo_counts)
  meta         : samples per pair, seed, worst-case standard error, method

This is a statistical estimate (unbiased), NOT a GTO output and NOT exact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.engine.cards import HAND_CLASSES, class_combos  # noqa: E402
from app.engine.evaluator import evaluate_many  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "preflop_equity_169.json"))
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    n_cls = len(HAND_CLASSES)
    combos = [np.array(class_combos(h), dtype=np.int64) for h in HAND_CLASSES]

    # exact non-conflicting combo-pair counts
    counts = np.zeros((n_cls, n_cls), dtype=np.int64)
    for i in range(n_cls):
        a = combos[i]
        for j in range(n_cls):
            b = combos[j]
            conflict = (a[:, None, 0] == b[None, :, 0]) | (a[:, None, 0] == b[None, :, 1]) | \
                       (a[:, None, 1] == b[None, :, 0]) | (a[:, None, 1] == b[None, :, 1])
            counts[i, j] = (~conflict).sum()

    eq = np.full((n_cls, n_cls), 0.5, dtype=np.float64)
    N = args.samples
    deck = np.arange(52, dtype=np.int64)
    t0 = time.time()
    for i in range(n_cls):
        a = combos[i]
        for j in range(i + 1, n_cls):
            b = combos[j]
            # sample non-conflicting combo pairs uniformly
            ai = rng.integers(0, len(a), size=N)
            bi = rng.integers(0, len(b), size=N)
            ha, hb = a[ai], b[bi]
            for _ in range(50):
                conf = (ha[:, 0] == hb[:, 0]) | (ha[:, 0] == hb[:, 1]) | (ha[:, 1] == hb[:, 0]) | (ha[:, 1] == hb[:, 1])
                if not conf.any():
                    break
                k = conf.sum()
                ha[conf] = a[rng.integers(0, len(a), size=k)]
                hb[conf] = b[rng.integers(0, len(b), size=k)]
            keys = rng.random((N, 52))
            rows = np.arange(N)
            for col in range(2):
                keys[rows, ha[:, col]] = 2.0
                keys[rows, hb[:, col]] = 2.0
            board = deck[np.argsort(keys, axis=1)[:, :5]]
            va = evaluate_many(np.concatenate([ha, board], axis=1))
            vb = evaluate_many(np.concatenate([hb, board], axis=1))
            share = np.where(va > vb, 1.0, np.where(va == vb, 0.5, 0.0))
            e = share.mean()
            eq[i, j] = e
            eq[j, i] = 1.0 - e
        if i % 10 == 0:
            print(f"{i + 1}/{n_cls} rows done, {time.time() - t0:.0f}s", flush=True)

    w = counts.astype(np.float64)
    vs_random = (eq * w).sum(axis=1) / w.sum(axis=1)
    out = {
        "classes": HAND_CLASSES,
        "equity": np.round(eq, 5).tolist(),
        "combo_counts": counts.tolist(),
        "vs_random": np.round(vs_random, 5).tolist(),
        "meta": {
            "method": "monte_carlo",
            "samples_per_pair": N,
            "seed": args.seed,
            "max_std_error": round(float(0.5 / np.sqrt(N)), 5),
            "generated_seconds": round(time.time() - t0, 1),
            "note": "Estimación Monte Carlo (no exacta, no GTO). Diagonal fijada en 0.5 por simetría.",
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("written", args.out, f"in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

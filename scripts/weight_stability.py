"""Issue #6: how noisy are entropy / CRITIC weights at small n, and does it change rankings?

Design: for each trial draw a random correlated criteria structure, generate a large synthetic
population (the 'truth'), take weights from it, then draw n alternatives and recompute weights
from the sample alone. Compare (a) weights (total-variation distance) and (b) rankings of the
SAME sample under sample-weights vs population-weights (Kendall tau), for TOPSIS and SAW.
Synthetic data only: results show the mechanism, not real-company behavior.
"""
import sys

import numpy as np
from scipy.stats import kendalltau

from maid.mcdm import critic_weights, entropy_weights, saw, topsis

M, POP, TRIALS = 7, 5000, 300
NS = [8, 12, 20, 50, 200]


def population(rng, skewed: bool) -> np.ndarray:
    L = rng.normal(size=(M, M)) * rng.uniform(0.2, 1.0, size=(M, 1))
    Z = rng.normal(size=(POP, M)) @ L.T
    X = np.exp(0.7 * Z / Z.std(axis=0)) if skewed else Z
    return X + 1e-9  # tiny offset; Gaussian data still has negative values (fine for TOPSIS/SAW, not for sum-entropy)


def tv(a, b) -> float:
    return 0.5 * np.abs(a - b).sum()


def tau(a, b) -> float:
    t = kendalltau(a, b)[0]
    return 1.0 if np.isnan(t) else t


def run(skewed: bool):
    rng = np.random.default_rng(42)
    rows = []
    for n in NS:
        out = {k: [] for k in ["ent_tv", "cri_tv", "ent_topsis", "ent_saw", "cri_topsis", "cri_saw"]}
        if skewed:
            out.update({k: [] for k in ["sum_tv", "sum_topsis", "sum_saw"]})
        for _ in range(TRIALS):
            P = population(rng, skewed)
            true_e, true_c = entropy_weights(P), critic_weights(P)
            S = P[rng.choice(POP, n, replace=False)]
            e, c = entropy_weights(S), critic_weights(S)
            out["ent_tv"].append(tv(e, true_e))
            out["cri_tv"].append(tv(c, true_c))
            out["ent_topsis"].append(tau(topsis(S, e), topsis(S, true_e)))
            out["ent_saw"].append(tau(saw(S, e), saw(S, true_e)))
            out["cri_topsis"].append(tau(topsis(S, c), topsis(S, true_c)))
            out["cri_saw"].append(tau(saw(S, c), saw(S, true_c)))
            if skewed:  # sum-normalized entropy needs strictly positive data
                true_s, s = entropy_weights(P, "sum"), entropy_weights(S, "sum")
                out["sum_tv"].append(tv(s, true_s))
                out["sum_topsis"].append(tau(topsis(S, s), topsis(S, true_s)))
                out["sum_saw"].append(tau(saw(S, s), saw(S, true_s)))
        rows.append((n, {k: float(np.mean(v)) for k, v in out.items()}))
    return rows


def table(rows) -> str:
    extra = "sum_tv" in rows[0][1]
    h = "| n | entropy TV | CRITIC TV | entropy→TOPSIS tau | entropy→SAW tau | CRITIC→TOPSIS tau | CRITIC→SAW tau |"
    sep = "|---|---|---|---|---|---|---|"
    if extra:
        h += " sum-entropy TV | sum-entropy→TOPSIS tau | sum-entropy→SAW tau |"
        sep += "---|---|---|"
    h += "\n" + sep + "\n"
    lines = []
    for n, r in rows:
        line = f"| {n} | {r['ent_tv']:.3f} | {r['cri_tv']:.3f} | {r['ent_topsis']:.3f} | {r['ent_saw']:.3f} | {r['cri_topsis']:.3f} | {r['cri_saw']:.3f} |"
        if extra:
            line += f" {r['sum_tv']:.3f} | {r['sum_topsis']:.3f} | {r['sum_saw']:.3f} |"
        lines.append(line)
    return h + "\n".join(lines)


if __name__ == "__main__":
    for name, skewed in [("Gaussian criteria", False), ("Log-normal (skewed) criteria", True)]:
        print(f"### {name}\n\n{table(run(skewed))}\n")
    print(f"m={M} criteria, {TRIALS} trials per n, population={POP}, seed=42", file=sys.stderr)

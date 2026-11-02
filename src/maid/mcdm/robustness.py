"""Rank intervals from two separate sources: bootstrap (weight-estimation noise) and Dirichlet perturbation (weight choice).
Ranks use the convention 1 = best; ties share the better rank."""

from dataclasses import dataclass

import numpy as np
from scipy.stats import rankdata


@dataclass(frozen=True)
class RankIntervals:
    point: np.ndarray  # (n,) rank under the point weights
    median: np.ndarray  # (n,) median rank over draws
    lo: np.ndarray  # (n,) 5th percentile rank (best plausible)
    hi: np.ndarray  # (n,) 95th percentile rank (worst plausible)
    acceptability: np.ndarray  # (n, n): [i, r-1] = share of draws where i got rank r
    n_draws: int


def ranks(scores: np.ndarray) -> np.ndarray:
    """Rank scores, 1 = best (highest); ties share the better rank."""
    return rankdata(-np.asarray(scores), method="min").astype(int)


def dirichlet_weights(
    w: np.ndarray, n_draws: int, concentration: float, rng: np.random.Generator
) -> np.ndarray:
    """Draw weight vectors from Dirichlet(concentration * w); zero weights floored to 1e-6."""
    alpha = concentration * np.maximum(np.asarray(w, dtype=float), 1e-6)
    return rng.dirichlet(alpha, size=n_draws)


def bootstrap_weights(
    X: np.ndarray, weight_fn, n_draws: int, rng: np.random.Generator
) -> np.ndarray:
    """Recompute weights on row-resamples of X (with replacement)."""
    n = X.shape[0]
    return np.stack([weight_fn(X[rng.integers(0, n, size=n)]) for _ in range(n_draws)])


def rank_intervals(
    X: np.ndarray, weight_draws: np.ndarray, rank_fn, point_w: np.ndarray
) -> RankIntervals:
    """Rank the (original) X under each weight draw and summarize the rank distribution."""
    R = np.stack([ranks(rank_fn(X, w)) for w in weight_draws])  # (n_draws, n)
    n = X.shape[0]
    acceptability = np.empty((n, n))
    for r in range(1, n + 1):
        acceptability[:, r - 1] = (R == r).mean(axis=0)
    return RankIntervals(
        point=ranks(rank_fn(X, point_w)),
        median=np.median(R, axis=0),
        lo=np.percentile(R, 5, axis=0, method="lower"),
        hi=np.percentile(R, 95, axis=0, method="higher"),
        acceptability=acceptability,
        n_draws=len(weight_draws),
    )


def robust_ranking(
    X, weight_fn, rank_fn, n_draws: int = 1000, concentration: float = 100.0, seed: int = 0
) -> dict[str, RankIntervals]:
    """Return {"bootstrap": ..., "dirichlet": ...}; point weights = weight_fn(X).

    The default concentration=100 is a placeholder for the maintainer to calibrate
    (weight sd ~0.035 when m=7, w=1/7); see docs/architecture/robustness.md.
    """
    X = np.asarray(X, dtype=float)
    rng = np.random.default_rng(seed)
    w = weight_fn(X)
    boot = bootstrap_weights(X, weight_fn, n_draws, rng)
    dirich = dirichlet_weights(w, n_draws, concentration, rng)
    return {
        "bootstrap": rank_intervals(X, boot, rank_fn, w),
        "dirichlet": rank_intervals(X, dirich, rank_fn, w),
    }

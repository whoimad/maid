"""Rank intervals from three separate sources: bootstrap (weight-estimation noise), Dirichlet perturbation
(weight choice) and score noise (bootstrap of the K LLM samples per cell). Ranks: 1 = best; ties share the better rank."""

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


def median_half_up(values) -> float:
    """Median with halves rounded up; the same rule as maid.scoring.aggregate."""
    return float(np.floor(np.median(values) + 0.5))


def score_noise_matrices(
    X: np.ndarray, cell_samples: dict, n_draws: int, rng: np.random.Generator
) -> np.ndarray:
    """(n_draws, n, m) copies of X; each cell (i, j) in cell_samples becomes the half-up median of a
    with-replacement resample of its K samples (bootstrap of the aggregated score). Other cells stay fixed."""
    n, m = X.shape
    out = np.repeat(X[None, :, :], n_draws, axis=0)
    for (i, j), s in sorted(cell_samples.items()):
        s = np.asarray(s, dtype=float)
        if not (0 <= i < n and 0 <= j < m):
            raise ValueError(f"cell ({i}, {j}) is outside X with shape {X.shape}")
        if s.ndim != 1 or s.size == 0 or not np.isfinite(s).all():
            raise ValueError(f"cell ({i}, {j}) needs a non-empty 1-D list of finite samples")
        idx = rng.integers(0, s.size, size=(n_draws, s.size))
        out[:, i, j] = np.floor(np.median(s[idx], axis=1) + 0.5)
    return out


def score_noise_intervals(
    X: np.ndarray, cell_samples: dict, weight_fn, rank_fn, n_draws: int, rng: np.random.Generator
) -> RankIntervals:
    """Rank each score-noise draw of X with weights recomputed on that draw; point = rank of X under weight_fn(X)."""
    X = np.asarray(X, dtype=float)
    draws = score_noise_matrices(X, cell_samples, n_draws, rng)
    R = np.stack([ranks(rank_fn(Xd, weight_fn(Xd))) for Xd in draws])
    return _summarize(R, ranks(rank_fn(X, weight_fn(X))))


def _summarize(R: np.ndarray, point: np.ndarray) -> RankIntervals:
    """Summarize a (n_draws, n) rank matrix: median, 90% interval and acceptability around the point ranks."""
    n = R.shape[1]
    acceptability = np.empty((n, n))
    for r in range(1, n + 1):
        acceptability[:, r - 1] = (R == r).mean(axis=0)
    return RankIntervals(
        point=point,
        median=np.median(R, axis=0),
        lo=np.percentile(R, 5, axis=0, method="lower"),
        hi=np.percentile(R, 95, axis=0, method="higher"),
        acceptability=acceptability,
        n_draws=R.shape[0],
    )


def rank_intervals(
    X: np.ndarray, weight_draws: np.ndarray, rank_fn, point_w: np.ndarray
) -> RankIntervals:
    """Rank the (original) X under each weight draw and summarize the rank distribution."""
    R = np.stack([ranks(rank_fn(X, w)) for w in weight_draws])  # (n_draws, n)
    return _summarize(R, ranks(rank_fn(X, point_w)))


def robust_ranking(
    X, weight_fn, rank_fn, n_draws: int = 1000, concentration: float = 100.0, seed: int = 0,
    cell_samples: dict | None = None,
) -> dict[str, RankIntervals]:
    """Return {"bootstrap": ..., "dirichlet": ...} plus "score_noise" when cell_samples is given; point weights = weight_fn(X).

    cell_samples maps (row, column) of X to that cell's K sampled scores. The default concentration=100 is a
    placeholder for the maintainer to calibrate (weight sd ~0.035 when m=7, w=1/7); see docs/architecture/robustness.md.
    """
    X = np.asarray(X, dtype=float)
    rng = np.random.default_rng(seed)
    w = weight_fn(X)
    boot = bootstrap_weights(X, weight_fn, n_draws, rng)
    dirich = dirichlet_weights(w, n_draws, concentration, rng)
    out = {
        "bootstrap": rank_intervals(X, boot, rank_fn, w),
        "dirichlet": rank_intervals(X, dirich, rank_fn, w),
    }
    if cell_samples is not None:
        out["score_noise"] = score_noise_intervals(X, cell_samples, weight_fn, rank_fn, n_draws, rng)
    return out

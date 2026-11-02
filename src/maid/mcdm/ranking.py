"""Ranking methods. Return a score per alternative (higher = better)."""
import numpy as np

from maid.mcdm.weights import _check_matrix, _minmax


def _check_weights(X: np.ndarray, w: np.ndarray) -> None:
    _check_matrix(X)
    if w.shape != (X.shape[1],):
        raise ValueError(f"w must have shape ({X.shape[1]},), got {w.shape}")
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1.0, atol=1e-6):
        raise ValueError("w must be finite, non-negative and sum to 1")


def saw(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Simple Additive Weighting on min-max normalized values."""
    _check_weights(X, w)
    return _minmax(X) @ w


def topsis(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """TOPSIS: relative closeness to the ideal solution (vector normalization)."""
    _check_weights(X, w)
    norm = np.sqrt((X**2).sum(axis=0))
    V = (X / np.where(norm < 1e-12, 1.0, norm)) * w
    best, worst = V.max(axis=0), V.min(axis=0)
    d_best = np.sqrt(((V - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((V - worst) ** 2).sum(axis=1))
    denom = d_best + d_worst
    return np.where(denom < 1e-12, 0.5, d_worst / np.where(denom < 1e-12, 1.0, denom))

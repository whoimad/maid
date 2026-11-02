"""Ranking methods. Return a score per alternative (higher = better)."""
import numpy as np

from maid.mcdm.weights import _minmax


def saw(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Simple Additive Weighting on min-max normalized values."""
    return _minmax(X) @ w


def topsis(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """TOPSIS: relative closeness to the ideal solution (vector normalization)."""
    norm = np.sqrt((X**2).sum(axis=0))
    V = (X / np.where(norm < 1e-12, 1.0, norm)) * w
    best, worst = V.max(axis=0), V.min(axis=0)
    d_best = np.sqrt(((V - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((V - worst) ** 2).sum(axis=1))
    denom = d_best + d_worst
    return np.where(denom < 1e-12, 0.5, d_worst / np.where(denom < 1e-12, 1.0, denom))

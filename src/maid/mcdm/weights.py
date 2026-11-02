"""Objective (data-driven) criterion weighting. All criteria are assumed benefit-type
(higher is better); flip cost criteria before calling. Input: matrix X, shape (n_alternatives, m_criteria)."""
import numpy as np

_EPS = 1e-12


def _minmax(X: np.ndarray) -> np.ndarray:
    lo, hi = X.min(axis=0), X.max(axis=0)
    return (X - lo) / np.where(hi - lo < _EPS, 1.0, hi - lo)


def equal_weights(X: np.ndarray) -> np.ndarray:
    m = X.shape[1]
    return np.full(m, 1.0 / m)


def entropy_weights(X: np.ndarray, normalization: str = "minmax") -> np.ndarray:
    """Shannon-entropy weights: criteria whose values vary more across alternatives get more weight.
    normalization: "minmax" (default; sensitive to the sample min/max) or "sum" (textbook column-sum, positive data only)."""
    n = X.shape[0]
    if normalization == "minmax":
        P = _minmax(X) + _EPS  # shift to strictly positive so ln() is defined
        P = P / P.sum(axis=0)
    elif normalization == "sum":
        if not np.all(X > 0):
            raise ValueError("sum-normalized entropy needs strictly positive values")
        P = X / X.sum(axis=0)
    else:
        raise ValueError(f"unknown normalization: {normalization!r}")
    e = -(P * np.log(P)).sum(axis=0) / np.log(n)
    d = 1.0 - e
    return d / d.sum() if d.sum() > _EPS else equal_weights(X)


def critic_weights(X: np.ndarray) -> np.ndarray:
    """CRITIC: weight = contrast (std) x conflict (1 - correlation with other criteria)."""
    N = _minmax(X)
    std = N.std(axis=0, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.corrcoef(N, rowvar=False)
    R = np.nan_to_num(R, nan=0.0)  # constant columns -> no correlation info
    c = std * (1.0 - R).sum(axis=0)
    return c / c.sum() if c.sum() > _EPS else equal_weights(X)

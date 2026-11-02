import numpy as np

from maid.mcdm import critic_weights, equal_weights, saw, topsis
from maid.mcdm.robustness import (
    bootstrap_weights,
    dirichlet_weights,
    rank_intervals,
    ranks,
    robust_ranking,
)


def test_ranks_one_is_best_and_ties_share_rank():
    assert ranks(np.array([0.2, 0.9, 0.9, 0.1])).tolist() == [3, 1, 1, 4]


def test_dirichlet_draws_are_valid_and_centered():
    w = np.array([0.5, 0.3, 0.2, 0.0])
    draws = dirichlet_weights(w, 5000, 100.0, np.random.default_rng(0))
    assert draws.shape == (5000, 4)
    assert (draws >= 0).all()
    assert np.allclose(draws.sum(axis=1), 1)
    assert np.allclose(draws.mean(axis=0), w, atol=0.01)


def test_bootstrap_draws_shape_and_sum():
    X = np.random.default_rng(1).random((12, 5))
    draws = bootstrap_weights(X, critic_weights, 200, np.random.default_rng(0))
    assert draws.shape == (200, 5)
    assert np.allclose(draws.sum(axis=1), 1)


def test_dominant_alternative_is_always_first():
    X = np.array([[9, 9, 9], [5, 5, 5], [1, 1, 1]], float)
    out = robust_ranking(X, equal_weights, topsis, n_draws=300)
    for ri in out.values():
        assert ri.acceptability[0, 0] == 1.0
        assert ri.lo[0] == ri.hi[0] == 1


def test_acceptability_rows_sum_to_one():
    X = np.random.default_rng(2).random((10, 6))
    out = robust_ranking(X, critic_weights, topsis, n_draws=200)
    for ri in out.values():
        assert np.allclose(ri.acceptability.sum(axis=1), 1)


def test_bounds_are_ordered():
    X = np.random.default_rng(2).random((10, 6))
    out = robust_ranking(X, critic_weights, topsis, n_draws=200)
    for ri in out.values():
        assert (ri.lo <= ri.median).all() and (ri.median <= ri.hi).all()
        assert (ri.lo >= 1).all() and (ri.hi <= 10).all()


def test_point_rank_matches_direct_ranking():
    X = np.random.default_rng(2).random((10, 6))
    out = robust_ranking(X, critic_weights, topsis, n_draws=50)
    expected = ranks(topsis(X, critic_weights(X)))
    for ri in out.values():
        assert np.array_equal(ri.point, expected)


def test_huge_concentration_collapses_interval():
    X = np.random.default_rng(0).random((8, 4))
    w = critic_weights(X)
    rng = np.random.default_rng(0)
    ri = rank_intervals(X, dirichlet_weights(w, 200, 1e10, rng), topsis, w)
    assert np.array_equal(ri.lo, ri.point)
    assert np.array_equal(ri.hi, ri.point)


def test_reproducible_with_seed():
    X = np.random.default_rng(2).random((10, 6))
    a = robust_ranking(X, critic_weights, saw, n_draws=200, seed=7)
    b = robust_ranking(X, critic_weights, saw, n_draws=200, seed=7)
    c = robust_ranking(X, critic_weights, saw, n_draws=200, seed=8)
    for k in ("bootstrap", "dirichlet"):
        assert np.array_equal(a[k].acceptability, b[k].acceptability)
    assert not np.array_equal(a["bootstrap"].acceptability, c["bootstrap"].acceptability)

import numpy as np
import pytest

from maid.mcdm import critic_weights, equal_weights, saw, topsis
from maid.mcdm.robustness import (
    bootstrap_weights,
    dirichlet_weights,
    median_half_up,
    rank_intervals,
    ranks,
    robust_ranking,
    score_noise_intervals,
    score_noise_matrices,
)
from maid.scoring import aggregate
from maid.state import CriterionScore


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


def _noise_case():
    X = np.random.default_rng(5).integers(1, 10, (10, 4)).astype(float)
    cells = {(i, 3): [max(1, X[i, 3] - 2), X[i, 3], min(9, X[i, 3] + 2)] for i in range(10)}
    return X, cells


def test_median_half_up_matches_pipeline_aggregate():
    for v in ([3, 4], [2, 3, 4, 5], [1, 9], [5], [1, 2, 2, 9, 9]):
        samples = [CriterionScore(company="Company A", criterion="x", score=s, evidence="e") for s in v]
        assert median_half_up(v) == aggregate(samples)[0].score


def test_score_noise_matrices_touch_only_listed_cells():
    X = np.random.default_rng(3).random((5, 3))
    cells = {(0, 1): [1, 5, 9], (2, 0): [3, 3, 3]}
    D = score_noise_matrices(X, cells, 200, np.random.default_rng(0))
    assert D.shape == (200, 5, 3)
    mask = np.ones(X.shape, dtype=bool)
    mask[0, 1] = mask[2, 0] = False
    assert all((d[mask] == X[mask]).all() for d in D)
    assert (D[:, 2, 0] == 3).all()
    assert set(D[:, 0, 1]) <= {1.0, 5.0, 9.0} and len(set(D[:, 0, 1])) > 1


def test_score_noise_matrices_use_half_up_median():
    X = np.random.default_rng(1).random((2, 2))
    D = score_noise_matrices(X, {(0, 0): [4, 5]}, 500, np.random.default_rng(0))
    assert set(D[:, 0, 0]) <= {4.0, 5.0}
    share = (D[:, 0, 0] == 5.0).mean()
    assert 0.65 < share < 0.85


def test_constant_samples_give_point_intervals():
    X = np.random.default_rng(4).integers(1, 10, (8, 4)).astype(float)
    cells = {(i, j): [X[i, j]] * 5 for i in range(8) for j in (2, 3)}
    ri = score_noise_intervals(X, cells, critic_weights, topsis, 100, np.random.default_rng(0))
    assert np.array_equal(ri.lo, ri.point) and np.array_equal(ri.hi, ri.point)


def test_score_noise_bounds_and_acceptability():
    X, cells = _noise_case()
    ri = robust_ranking(X, critic_weights, topsis, n_draws=200, cell_samples=cells)["score_noise"]
    assert (ri.lo <= ri.median).all() and (ri.median <= ri.hi).all()
    assert ri.lo.min() >= 1 and ri.hi.max() <= 10
    assert np.allclose(ri.acceptability.sum(axis=1), 1)
    assert np.array_equal(ri.point, ranks(topsis(X, critic_weights(X))))
    assert (ri.hi - ri.lo).max() > 0


def test_score_noise_does_not_change_other_sources():
    X, cells = _noise_case()
    a = robust_ranking(X, critic_weights, saw, n_draws=200, seed=7)
    b = robust_ranking(X, critic_weights, saw, n_draws=200, seed=7, cell_samples=cells)
    assert "score_noise" not in a and "score_noise" in b
    for k in ("bootstrap", "dirichlet"):
        for f in ("acceptability", "lo", "hi"):
            assert np.array_equal(getattr(a[k], f), getattr(b[k], f))


def test_score_noise_reproducible_and_order_independent():
    X, cells = _noise_case()
    a = robust_ranking(X, critic_weights, topsis, n_draws=200, seed=7, cell_samples=cells)
    b = robust_ranking(X, critic_weights, topsis, n_draws=200, seed=7,
                       cell_samples=dict(reversed(list(cells.items()))))
    assert np.array_equal(a["score_noise"].acceptability, b["score_noise"].acceptability)


def test_score_noise_rejects_bad_cells():
    X, _ = _noise_case()
    with pytest.raises(ValueError):
        score_noise_matrices(X, {(10, 0): [1, 2]}, 10, np.random.default_rng(0))
    with pytest.raises(ValueError):
        score_noise_matrices(X, {(0, 0): []}, 10, np.random.default_rng(0))

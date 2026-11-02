import numpy as np
import pytest

from maid.mcdm import critic_weights, entropy_weights, saw, topsis


def test_weights_sum_to_one_and_nonnegative():
    X = np.random.default_rng(0).random((12, 6))
    for fn in (entropy_weights, critic_weights):
        w = fn(X)
        assert np.isclose(w.sum(), 1) and (w >= 0).all()
    w = entropy_weights(X, "sum")
    assert np.isclose(w.sum(), 1) and (w >= 0).all()


def test_entropy_gives_zero_weight_to_constant_criterion():
    X = np.column_stack([[3, 3, 3, 3, 3], [1, 2, 3, 4, 5]]).astype(float)
    assert entropy_weights(X)[0] < 1e-6
    assert entropy_weights(X, "sum")[0] < 1e-6


def test_minmax_entropy_rewards_single_outlier():
    # Min-max variant: the outlier is mapped to 1 and the rest to ~0, so the column looks maximally concentrated.
    X = np.column_stack([[1, 1, 1, 1, 2], [1, 2, 3, 4, 5]]).astype(float)
    assert entropy_weights(X)[0] > entropy_weights(X)[1]


def test_sum_entropy_prefers_spread_on_same_data():
    X = np.column_stack([[1, 1, 1, 1, 2], [1, 2, 3, 4, 5]]).astype(float)
    assert entropy_weights(X, "sum")[1] > entropy_weights(X, "sum")[0]
    assert np.allclose(entropy_weights(X, "sum"), [0.289, 0.711], atol=1e-3)


def test_sum_entropy_rejects_nonpositive():
    X = np.array([[1.0, 2.0], [0.0, 3.0], [2.0, 4.0]])
    with pytest.raises(ValueError):
        entropy_weights(X, "sum")


def test_entropy_unknown_normalization_raises():
    with pytest.raises(ValueError):
        entropy_weights(np.ones((3, 2)), "bogus")


def test_critic_downweights_duplicated_criterion():
    rng = np.random.default_rng(1)
    a = rng.random(30)
    X = np.column_stack([a, a, rng.random(30)])  # first two identical
    w = critic_weights(X)
    assert w[2] > w[0]


def test_dominant_alternative_ranks_first():
    X = np.array([[9, 9, 9], [5, 5, 5], [1, 1, 1]], dtype=float)
    w = np.full(3, 1 / 3)
    assert topsis(X, w).argmax() == 0 and saw(X, w).argmax() == 0


def test_single_alternative_is_rejected():
    for fn in (entropy_weights, critic_weights):
        with pytest.raises(ValueError):
            fn(np.ones((1, 3)))


def test_nan_in_matrix_is_rejected():
    X = np.array([[1.0, 2.0], [np.nan, 3.0], [4.0, 5.0]])
    with pytest.raises(ValueError):
        entropy_weights(X)


def test_one_dimensional_matrix_is_rejected():
    with pytest.raises(ValueError):
        critic_weights(np.arange(5.0))


def test_rankers_reject_bad_weights():
    X = np.random.default_rng(1).random((3, 3))
    for fn in (saw, topsis):
        for w in (np.full(2, 0.5), np.array([1.5, -0.25, -0.25]), np.full(3, 0.5)):
            with pytest.raises(ValueError):
                fn(X, w)


def test_all_constant_matrix_still_falls_back_to_equal_weights():
    X = np.ones((4, 3))
    for fn in (entropy_weights, critic_weights):
        assert np.allclose(fn(X), np.full(3, 1 / 3))

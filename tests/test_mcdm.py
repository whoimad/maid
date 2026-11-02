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

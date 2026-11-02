import numpy as np

from maid.mcdm import critic_weights, entropy_weights, saw, topsis


def test_weights_sum_to_one_and_nonnegative():
    X = np.random.default_rng(0).random((12, 6))
    for fn in (entropy_weights, critic_weights):
        w = fn(X)
        assert np.isclose(w.sum(), 1) and (w >= 0).all()


def test_entropy_gives_zero_weight_to_constant_criterion():
    X = np.column_stack([[3, 3, 3, 3, 3], [1, 2, 3, 4, 5]]).astype(float)
    assert entropy_weights(X)[0] < 1e-6


def test_entropy_rewards_concentration_not_spread():
    # Known property: one outlier value (low entropy) outweighs an evenly spread criterion.
    X = np.column_stack([[1, 1, 1, 1, 2], [1, 2, 3, 4, 5]]).astype(float)
    assert entropy_weights(X)[0] > entropy_weights(X)[1]


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

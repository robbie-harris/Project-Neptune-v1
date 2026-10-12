"""Pure unit tests for S2.6 structure; no ROS or simulator imports."""

from neptune_state_estimation.eskf_state import (
    DELTA_B_A, DELTA_B_G, DELTA_P, DELTA_THETA, DELTA_V, ERROR_DIM,
    initial_covariance, NOMINAL_DIM, NominalState, normalize_quaternion,
    small_angle_quaternion, validate_covariance, validate_error_state,
)
import numpy as np
import pytest


FIELDS = ('p_WB', 'v_WB', 'q_WB', 'b_g', 'b_a')


def test_dimensions_and_order():
    state = NominalState()
    assert [getattr(state, f).shape for f in FIELDS] == [(3,), (3,), (4,), (3,), (3,)]
    assert NOMINAL_DIM == 16
    assert ERROR_DIM == 15
    error = validate_error_state(np.arange(15))
    for index, block in enumerate((DELTA_P, DELTA_V, DELTA_THETA, DELTA_B_G, DELTA_B_A)):
        np.testing.assert_array_equal(error[block], np.arange(3 * index, 3 * index + 3))


def test_initial_covariance():
    p = initial_covariance()
    assert p.shape == (15, 15)
    np.testing.assert_array_equal(p, p.T)
    assert np.all(np.diag(p) > 0)
    expected = np.repeat([1., .01, (np.pi / 180.) ** 2, 1e-4, .01], 3)
    np.testing.assert_array_equal(p, np.diag(expected))
    np.testing.assert_array_equal(validate_covariance(p), p)


def test_configurable_covariance_and_copy():
    axes = np.array([1., 2., 3.])
    p = initial_covariance(position_variance=axes, velocity_variance=4.)
    axes[:] = 99
    np.testing.assert_array_equal(np.diag(p)[:6], [1, 2, 3, 4, 4, 4])
    copied = validate_covariance(p)
    copied[0, 0] = 99
    assert p[0, 0] == 1


@pytest.mark.parametrize('scale', [2., 1e300, 1e-300])
def test_quaternion_normalization(scale):
    q = np.array([0., 0., scale, scale])
    original = q.copy()
    state = NominalState(q_WB=q)
    np.testing.assert_allclose(state.q_WB, [0., 0., 2 ** -.5, 2 ** -.5])
    np.testing.assert_array_equal(q, original)
    assert np.linalg.norm(state.q_WB) == pytest.approx(1.)


def test_zero_injection():
    state = NominalState([1, 2, 3], [4, 5, 6], [1, 2, 3, 4], [7, 8, 9], [10, 11, 12])
    result = state.inject_error(np.zeros(15))
    for field in FIELDS:
        np.testing.assert_allclose(getattr(result, field), getattr(state, field), atol=1e-15)


@pytest.mark.parametrize('field,block', [
    ('p_WB', DELTA_P), ('v_WB', DELTA_V), ('b_g', DELTA_B_G), ('b_a', DELTA_B_A),
])
def test_additive_injection(field, block):
    state = NominalState()
    delta = np.zeros(15)
    delta[block] = [1., -2., 3.]
    original = delta.copy()
    result = state.inject_error(delta)
    np.testing.assert_array_equal(getattr(result, field), [1, -2, 3])
    for other in FIELDS:
        np.testing.assert_array_equal(getattr(state, other), getattr(NominalState(), other))
        if other != field:
            np.testing.assert_array_equal(getattr(result, other), getattr(state, other))
    np.testing.assert_array_equal(delta, original)


def test_small_angle_orientation():
    angle = 1e-6
    delta = np.zeros(15)
    delta[DELTA_THETA] = [0, 0, angle]
    result = NominalState().inject_error(delta)
    np.testing.assert_allclose(result.q_WB, [0, 0, np.sin(angle / 2), np.cos(angle / 2)])
    assert np.linalg.norm(result.q_WB) == pytest.approx(1.)
    np.testing.assert_array_equal(small_angle_quaternion([0, 0, 0]), [0, 0, 0, 1])


def test_right_multiplication_in_body_frame():
    # Existing body->world convention: +90 deg z maps body x to world y.
    s = np.sqrt(.5)
    state = NominalState(q_WB=[0, 0, s, s])
    angle = .02
    error = np.zeros(15)
    error[DELTA_THETA] = [angle, 0, 0]
    q = state.inject_error(error).q_WB
    # q_z Hamilton q_x; reversed multiplication would have negative y.
    np.testing.assert_allclose(q, [s * np.sin(angle / 2), s * np.sin(angle / 2),
                                   s * np.cos(angle / 2), s * np.cos(angle / 2)])
    x, y, z, w = state.q_WB
    rotated_x = [1 - 2 * (y*y + z*z), 2 * (x*y + z*w), 2 * (x*z - y*w)]
    np.testing.assert_allclose(rotated_x, [0, 1, 0], atol=1e-15)


def test_no_array_aliases():
    vectors = [np.ones(3), np.ones(3), np.array([0., 0., 0., 1.]),
               np.ones(3), np.ones(3)]
    state = NominalState(*vectors)
    copies = [state.copy(), state.inject_error(np.zeros(15))]
    for index, field in enumerate(FIELDS):
        assert not np.shares_memory(getattr(state, field), vectors[index])
        for copied in copies:
            assert not np.shares_memory(getattr(state, field), getattr(copied, field))
            getattr(copied, field)[0] = 99
        assert getattr(state, field)[0] != 99
    a, b = NominalState(), NominalState()
    a.p_WB[0] = 42
    assert b.p_WB[0] == 0
    error = np.zeros(15)
    assert not np.shares_memory(validate_error_state(error), error)


@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('value', [[1, 2], [[1, 2, 3]], [np.nan] * 3])
def test_invalid_nominal_vectors(field, value):
    with pytest.raises(ValueError):
        NominalState(**{field: value})


@pytest.mark.parametrize('value', [np.zeros(14), np.zeros(16), np.zeros((15, 1)),
                                   np.full(15, np.inf)])
def test_invalid_error_vectors(value):
    with pytest.raises(ValueError):
        NominalState().inject_error(value)


@pytest.mark.parametrize('value', [[0, 0, 0, 0], [0, 0, np.nan, 1], [0, 0, 1]])
def test_invalid_quaternion(value):
    with pytest.raises(ValueError):
        normalize_quaternion(value)


@pytest.mark.parametrize('shape', [(14, 14), (15,), (15, 16)])
def test_invalid_covariance_dimensions(shape):
    with pytest.raises(ValueError):
        validate_covariance(np.zeros(shape))


@pytest.mark.parametrize('kind', ['nonfinite', 'asymmetric', 'negative', 'indefinite'])
def test_invalid_covariance_values(kind):
    p = np.eye(15)
    if kind == 'nonfinite':
        p[0, 0] = np.nan
    elif kind == 'asymmetric':
        p[0, 1] = .1
    elif kind == 'negative':
        p[0, 0] = -1
    else:
        p[0, 1] = p[1, 0] = 2
    with pytest.raises(ValueError):
        validate_covariance(p)


@pytest.mark.parametrize('value', [0, -1, np.inf, [1, 2], [[1, 2, 3]]])
def test_invalid_initial_variance(value):
    with pytest.raises(ValueError):
        initial_covariance(position_variance=value)


def test_validate_mutated_state():
    state = NominalState()
    state.v_WB = np.zeros(2)
    with pytest.raises(ValueError):
        state.copy()
    state = NominalState()
    state.q_WB *= 2
    with pytest.raises(ValueError):
        state.inject_error(np.zeros(15))

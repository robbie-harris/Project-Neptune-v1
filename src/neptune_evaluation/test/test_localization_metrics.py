"""Focused tests of the ROS-independent localization calculations."""

import math

import pytest

from neptune_evaluation.localization_metrics import (
    LocalizationMetrics, quaternion_yaw, wrapped_yaw_error)


def test_initial_frame_alignment():
    metrics = LocalizationMetrics()
    metrics.add_sample((0, 0, 2), (100, -50, 7))
    assert metrics.summary()['position_3d_error'] == 0
    metrics.add_sample((1, 2, 5), (101, -48, 10))
    assert metrics.summary()['position_3d_error'] == 0


def test_zero_error_trajectory():
    metrics = LocalizationMetrics()
    for point in ((0, 0, 0), (3, 4, 5), (-2, 1, -3), (0, 0, 0)):
        metrics.add_sample(point, point, 0.5, 0.5)
    result = metrics.summary()
    assert result['sample_count'] == 4
    for key in ('horizontal_rmse', 'position_3d_rmse', 'depth_rmse',
                'max_horizontal_error', 'max_3d_error', 'yaw_rmse'):
        assert result[key] == 0


def test_known_position_offsets():
    metrics = LocalizationMetrics()
    metrics.add_sample((0, 0, 0), (0, 0, 0))
    metrics.add_sample((3, 4, -12), (0, 0, 0))
    result = metrics.summary()
    assert result['horizontal_error'] == 5
    assert result['position_3d_error'] == 13
    assert result['z_error'] == -12
    assert result['depth_rmse'] == pytest.approx(math.sqrt(144 / 2))


def test_rmse_max_and_final_accumulation():
    metrics = LocalizationMetrics()
    for point in ((0, 0, 0), (3, 4, 12), (0, 0, 0), (0, 2, 0)):
        metrics.add_sample(point, (0, 0, 0))
    result = metrics.summary()
    assert result['sample_count'] == 4
    assert result['horizontal_rmse'] == pytest.approx(math.sqrt(29 / 4))
    assert result['position_3d_rmse'] == pytest.approx(math.sqrt(173 / 4))
    assert result['depth_rmse'] == 6
    assert result['max_horizontal_error'] == 5
    assert result['max_3d_error'] == 13
    assert result['final_horizontal_error'] == 2
    assert result['final_3d_error'] == 2


def test_yaw_wrap_and_rmse():
    assert wrapped_yaw_error(math.radians(-179), math.radians(179)) == pytest.approx(
        math.radians(2))
    assert wrapped_yaw_error(math.radians(179), math.radians(-179)) == pytest.approx(
        math.radians(-2))
    metrics = LocalizationMetrics()
    metrics.add_sample((0, 0, 0), (0, 0, 0), 0, 0)
    metrics.add_sample((0, 0, 0), (0, 0, 0), math.radians(-179), math.radians(179))
    assert metrics.summary()['yaw_rmse'] == pytest.approx(math.radians(2) / math.sqrt(2))
    metrics.add_sample((0, 0, 0), (0, 0, 0))
    assert metrics.summary()['yaw_sample_count'] == 2
    assert metrics.summary()['yaw_error'] is None


def test_quaternion_yaw():
    assert quaternion_yaw(0, 0, 2, 2) == pytest.approx(math.pi / 2)
    with pytest.raises(ValueError):
        quaternion_yaw(0, 0, 0, 0)
    with pytest.raises(ValueError):
        quaternion_yaw(0, 0, math.nan, 1)


def test_empty_summary_and_invalid_samples():
    metrics = LocalizationMetrics()
    assert metrics.summary()['final_3d_error'] is None
    assert metrics.summary()['horizontal_rmse'] is None
    for point in ((math.nan, 0, 0), (math.inf, 0, 0), (0, 0)):
        with pytest.raises(ValueError):
            metrics.add_sample(point, (0, 0, 0))
    with pytest.raises(ValueError):
        metrics.add_sample((0, 0, 0), (0, 0, 0), 1, None)
    assert metrics.sample_count == 0

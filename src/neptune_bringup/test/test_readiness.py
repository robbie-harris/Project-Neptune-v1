"""Validate startup qualification, source validity, and moving-state freshness."""

import math

import pytest

from neptune_bringup.readiness import DemoReadiness


def feed(gate, at, depth=0.45, yaw_rate=0.0):
    gate.pressure(at, at, (depth - 0.4) * 997 * 9.81)
    gate.imu(at, at, yaw_rate)
    gate.observe('dvl', at, at)
    gate.observe('state', at, at)
    return gate.snapshot(at, at)


def test_missing_and_fresh_but_unsettled_inputs_do_not_start():
    gate = DemoReadiness(minimum_startup=1, stable_window=1)
    assert not gate.snapshot(0, 0)['ready']
    for index in range(31):
        assert not feed(gate, index*0.1, depth=0.45+index*0.02)['ready']


def test_stationary_window_and_minimum_startup_are_both_required():
    gate = DemoReadiness(minimum_startup=2, stable_window=1)
    for index in range(20):
        assert not feed(gate, index*0.1)['ready']
    assert feed(gate, 2.0)['ready']


def test_motion_after_qualification_does_not_pause_the_mission():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    assert gate.qualified
    assert feed(gate, 1.2, depth=1.5, yaw_rate=0.8)['ready']


def test_sensor_receipt_silence_fails_closed_then_recovers():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    assert not gate.snapshot(2.0, 2.0)['ready']
    assert feed(gate, 2.1)['ready']
    assert gate.snapshot(2.1, 3.0)['ready']
    assert not any(gate.snapshot(2.1, 3.0)['source_time_health'].values())


@pytest.mark.parametrize('stamp', [0.0, 1.1, math.nan, 1000.0])
def test_source_time_anomalies_are_diagnostic_only(stamp):
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    for name in gate.required:
        gate.observe(name, 1.2, stamp)
    status = gate.snapshot(1.2, 1.2)
    assert status['ready']
    assert all(status['sensor_health'].values())
    assert not any(status['source_time_health'].values())
    assert not gate.snapshot(1.7, 1.7)['ready']  # Receipt age == timeout fails.


def test_startup_pressure_stability_uses_receipt_intervals():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(15):
        at = index*0.1
        gate.pressure(at, -at, 0.05*997*9.81)
        gate.imu(at, -at, 0.0)
        gate.observe('dvl', at, -at)
        gate.observe('state', at, -at)
    assert gate.snapshot(1.41, 1.41)['ready']


@pytest.mark.parametrize('missing', DemoReadiness.required)
def test_one_silent_or_invalid_stream_still_fails(missing):
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    for name in gate.required:
        if name != missing:
            gate.observe(name, 1.6, 1.6)
    assert not gate.snapshot(1.6, 1.6)['ready']
    gate.observe(missing, 1.6, 1.6, valid=False)
    assert not gate.snapshot(1.6, 1.6)['ready']
    gate.observe(missing, 1.6, 1.6, valid=True)
    assert gate.snapshot(1.6, 1.6)['ready']


def test_gyro_stability_is_required_at_startup():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        assert not feed(gate, index*0.1, yaw_rate=0.04)['ready']


def test_gaps_in_physical_window_do_not_qualify():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    feed(gate, 0)
    assert not feed(gate, 2)['ready']
    assert not feed(gate, 2.1)['ready']

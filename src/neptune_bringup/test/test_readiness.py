"""Validate startup qualification, source validity, and moving-state freshness."""

import math

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


def test_sensor_receipt_and_source_silence_fail_closed_then_recover():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    assert not gate.snapshot(2.0, 2.0)['ready']
    assert feed(gate, 2.1)['ready']
    assert not gate.snapshot(2.1, 3.0)['ready']


def test_invalid_and_duplicate_source_stamps_are_not_rejuvenated():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        feed(gate, index*0.1)
    assert not feed(gate, 1.1)['ready']
    assert feed(gate, 1.2)['ready']
    gate.observe('state', 1.3, math.nan)
    assert not gate.snapshot(1.3, 1.3)['ready']
    assert feed(gate, 1.4)['ready']


def test_gyro_stability_is_required_at_startup():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    for index in range(12):
        assert not feed(gate, index*0.1, yaw_rate=0.04)['ready']


def test_gaps_in_physical_window_do_not_qualify():
    gate = DemoReadiness(minimum_startup=0, stable_window=1)
    feed(gate, 0)
    assert not feed(gate, 2)['ready']
    assert not feed(gate, 2.1)['ready']

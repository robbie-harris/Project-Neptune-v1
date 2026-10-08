"""Callback checks without DDS; prefer generated DVL messages when installed."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS

import pytest
from sensor_msgs.msg import FluidPressure, Imu

from neptune_sim.degradation import SensorDegradation


@pytest.fixture
def node_class(monkeypatch):
    # The real DVL schema was inspected in external/stonefish_ros2/msg/DVL.msg.
    # These tests do not claim to exercise its generated ROS type support.
    try:
        from stonefish_ros2.msg import DVL
    except ModuleNotFoundError as error:
        if error.name not in ('stonefish_ros2', 'stonefish_ros2.msg'):
            raise
        DVL = NS
        msg_module = ModuleType('stonefish_ros2.msg')
        msg_module.DVL = DVL
        package = ModuleType('stonefish_ros2')
        package.msg = msg_module
        monkeypatch.setitem(sys.modules, 'stonefish_ros2', package)
        monkeypatch.setitem(sys.modules, 'stonefish_ros2.msg', msg_module)
    path = Path(__file__).parents[1] / 'neptune_sim' / 'sensor_degrader.py'
    spec = importlib.util.spec_from_file_location('callback_test_module', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SensorDegrader, DVL


@pytest.mark.parametrize('probability', [0.0, 1.0])
def test_publish_drop_counters_and_diagnostics(node_class, probability):
    node_class, dvl_type = node_class
    published = {s: [] for s in ('dvl', 'imu', 'pressure')}
    logs = []
    node = NS(
        degradation=SensorDegradation(dvl_dropout_probability=probability,
                                      pressure_dropout_probability=probability),
        counts={s: dict(received=0, published=0, dropped=0) for s in published},
        publishers_={s: NS(publish=items.append) for s, items in published.items()},
        get_logger=lambda: NS(info=logs.append))
    if dvl_type is NS:
        dvl = NS(header=NS(stamp=123, frame_id='dvl'),
                 velocity=NS(x=1., y=2., z=3.), altitude=2.0,
                 beams=[], velocity_covariance=[0.0]*9)
    else:
        dvl = dvl_type()
        dvl.velocity.x, dvl.velocity.y, dvl.velocity.z = 1., 2., 3.
        dvl.altitude = 2.0
    messages = dict(dvl=dvl, imu=Imu(), pressure=FluidPressure())
    for sensor, msg in messages.items():
        msg.header.frame_id = sensor
        node_class.receive(node, sensor, msg)
        dropped = int(probability == 1 and sensor != 'imu')
        assert node.counts[sensor] == dict(received=1, published=1-dropped, dropped=dropped)
        assert len(published[sensor]) == 1-dropped
        if not dropped:
            assert published[sensor][0] == msg
    node_class.print_diagnostics(node)
    for sensor in messages:
        assert f'{sensor} received=1 published=' in logs[0]

"""Exercise degradation without ROS, DDS, or Stonefish."""

from copy import deepcopy
import math
from types import SimpleNamespace as NS

import pytest

from neptune_sim.degradation import SensorDegradation


def message():
    return NS(header=NS(stamp=NS(sec=123, nanosec=456), frame_id='sensor'),
              velocity=NS(x=1.0, y=-2.0, z=3.0),
              velocity_covariance=list(range(9)), altitude=4.0, beams=[NS(range=5)],
              angular_velocity=NS(x=0.1, y=0.2, z=0.3),
              linear_acceleration=NS(x=1.0, y=2.0, z=9.81),
              orientation=NS(x=0.0, y=0.0, z=0.0, w=1.0),
              orientation_covariance=[0.0]*9,
              angular_velocity_covariance=list(range(9)),
              linear_acceleration_covariance=list(range(9)),
              fluid_pressure=30000.0, variance=2.0)


@pytest.mark.parametrize('sensor', ['dvl', 'imu', 'pressure'])
def test_clean_passthrough(sensor):
    msg = message()
    msg.orientation.w = 0.99  # Zero configuration must not normalize input.
    msg.velocity.x = -0.0
    output = getattr(SensorDegradation(), sensor)(msg)
    assert output == msg
    assert output is not msg
    assert output.header is not msg.header
    assert math.copysign(1, output.velocity.x) == -1


def test_dvl_bias_and_preservation():
    msg = message()
    original = deepcopy(msg)
    out = SensorDegradation(dvl_bias_x=0.1, dvl_bias_y=-0.2,
                            dvl_bias_z=0.3).dvl(msg)
    assert (out.velocity.x, out.velocity.y, out.velocity.z) == pytest.approx((1.1, -2.2, 3.3))
    out.velocity = deepcopy(msg.velocity)
    assert out == original
    assert msg == original


def test_imu_bias():
    msg = message()
    out = SensorDegradation(imu_gyro_bias_x=1.0, imu_gyro_bias_y=2.0,
                            imu_gyro_bias_z=3.0, imu_accel_bias_x=-1.0,
                            imu_accel_bias_y=-2.0, imu_accel_bias_z=-3.0).imu(msg)
    assert (out.angular_velocity.x, out.angular_velocity.y,
            out.angular_velocity.z) == pytest.approx((1.1, 2.2, 3.3))
    assert (out.linear_acceleration.x, out.linear_acceleration.y,
            out.linear_acceleration.z) == pytest.approx((0, 0, 6.81))
    out.angular_velocity = deepcopy(msg.angular_velocity)
    out.linear_acceleration = deepcopy(msg.linear_acceleration)
    assert out == msg


def test_pressure_bias():
    msg = message()
    out = SensorDegradation(pressure_bias=100.0).pressure(msg)
    assert out.fluid_pressure == 30100.0
    out.fluid_pressure = msg.fluid_pressure
    assert out == msg


@pytest.mark.parametrize('sensor', ['dvl', 'pressure'])
@pytest.mark.parametrize('probability', [0.0, 1.0])
def test_dropout_endpoints(sensor, probability):
    engine = SensorDegradation(**{f'{sensor}_dropout_probability': probability})
    for _ in range(100):
        assert (getattr(engine, sensor)(message()) is None) == (probability == 1)


def random_sequence(seed):
    engine = SensorDegradation(
        seed=seed, dvl_noise_std_x=0.1, dvl_noise_std_y=0.2, dvl_noise_std_z=0.3,
        dvl_dropout_probability=0.4, pressure_dropout_probability=0.3,
        pressure_noise_std=10.0, imu_gyro_noise_std_x=0.1,
        imu_accel_noise_std_z=0.2, imu_orientation_noise_std_y=0.1)
    return [tuple(getattr(engine, sensor)(message()) for sensor in
                  ('dvl', 'imu', 'pressure')) for _ in range(100)]


def test_seed_reproducibility():
    samples = random_sequence(42)
    assert samples == random_sequence(42)
    assert samples != random_sequence(43)
    assert any(dvl is None for dvl, _, _ in samples)
    assert any(dvl is not None for dvl, _, _ in samples)


def test_sensor_streams_independent_of_interleaving():
    params = dict(seed=5, dvl_noise_std_x=1.0, imu_gyro_noise_std_x=1.0)
    a, b = SensorDegradation(**params), SensorDegradation(**params)
    for _ in range(20):
        a.imu(message())
        assert a.dvl(message()) == b.dvl(message())


def test_orientation_convention_and_normalization():
    msg = message()
    msg.orientation = NS(x=0.0, y=0.0, z=math.sqrt(0.5), w=math.sqrt(0.5))
    out = SensorDegradation(imu_orientation_bias_x=math.pi/2).imu(msg)
    # World yaw 90 degrees followed by a body x rotation of 90 degrees.
    assert (out.orientation.x, out.orientation.y, out.orientation.z,
            out.orientation.w) == pytest.approx((0.5, 0.5, 0.5, 0.5))
    engine = SensorDegradation(imu_orientation_noise_std_x=0.2,
                               imu_orientation_noise_std_y=0.3,
                               imu_orientation_noise_std_z=0.4)
    for _ in range(100):
        q = engine.imu(msg).orientation
        assert math.hypot(q.x, q.y, q.z, q.w) == pytest.approx(1.0)


def test_unavailable_and_invalid_orientation():
    engine = SensorDegradation(imu_orientation_bias_x=0.1)
    msg = message()
    msg.orientation.w = 0.0
    with pytest.raises(ValueError):
        engine.imu(msg)
    msg.orientation_covariance[0] = -1.0
    assert engine.imu(msg) == msg


@pytest.mark.parametrize('parameters', [
    {'dvl_noise_std_x': -0.1}, {'pressure_dropout_probability': -0.1},
    {'dvl_dropout_probability': 1.1}, {'pressure_bias': math.inf},
    {'imu_accel_noise_std_x': math.nan}, {'seed': 1.5}, {'unknown': 0},
])
def test_invalid_parameters(parameters):
    with pytest.raises(ValueError):
        SensorDegradation(**parameters)

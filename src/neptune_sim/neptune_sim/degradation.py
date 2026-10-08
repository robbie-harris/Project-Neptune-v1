"""Deterministic sensor degradation without ROS imports or simulator access."""

from copy import deepcopy
import math
import random


PARAMETER_DEFAULTS = {'seed': 0}
for group in ('dvl', 'imu_gyro', 'imu_accel', 'imu_orientation'):
    for kind in ('noise_std', 'bias'):
        for axis in 'xyz':
            PARAMETER_DEFAULTS[f'{group}_{kind}_{axis}'] = 0.0
for sensor in ('dvl', 'pressure'):
    PARAMETER_DEFAULTS[f'{sensor}_dropout_probability'] = 0.0
PARAMETER_DEFAULTS.update(pressure_noise_std=0.0, pressure_bias=0.0)


class SensorDegradation:
    """Copy incoming message-shaped objects; alter only configured measurements."""

    def __init__(self, **parameters):
        unknown = parameters.keys() - PARAMETER_DEFAULTS.keys()
        if unknown:
            raise ValueError(f'Unknown parameters: {sorted(unknown)}')
        self.parameters = {**PARAMETER_DEFAULTS, **parameters}
        seed = self.parameters['seed']
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError('seed must be an integer')
        for name, value in self.parameters.items():
            if name == 'seed':
                continue
            if not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
            if 'noise_std' in name and value < 0:
                raise ValueError(f'{name} must be nonnegative')
            if 'dropout_probability' in name and not 0 <= value <= 1:
                raise ValueError(f'{name} must be in [0, 1]')
        # Stable explicit seeds, independent of callback interleaving and Python hash.
        self.random = {sensor: random.Random(f'{seed}:{sensor}')
                       for sensor in ('dvl', 'imu', 'pressure')}

    def _drop(self, sensor):
        probability = self.parameters[f'{sensor}_dropout_probability']
        return probability == 1 or (
            probability > 0 and self.random[sensor].random() < probability)

    def _offset(self, sensor, group, axis=None):
        suffix = f'_{axis}' if axis else ''
        bias = self.parameters[f'{group}_bias{suffix}']
        std = self.parameters[f'{group}_noise_std{suffix}']
        return bias + (self.random[sensor].gauss(0.0, std) if std else 0.0)

    def _vector(self, sensor, group, vector):
        for axis in 'xyz':
            offset = self._offset(sensor, group, axis)
            if offset != 0:
                setattr(vector, axis, getattr(vector, axis) + offset)

    def dvl(self, message):
        """Apply sensor-frame velocity offsets in m/s, or return None on dropout."""
        if self._drop('dvl'):
            return None
        output = deepcopy(message)
        self._vector('dvl', 'dvl', output.velocity)
        return output

    def imu(self, message):
        """Perturb gyro, acceleration and optionally body-frame orientation."""
        output = deepcopy(message)
        self._vector('imu', 'imu_gyro', output.angular_velocity)
        self._vector('imu', 'imu_accel', output.linear_acceleration)
        # Honor the Imu unavailable-orientation sentinel without inventing attitude.
        if output.orientation_covariance[0] == -1:
            return output
        if any(self.parameters[f'imu_orientation_{kind}_{axis}'] != 0
               for kind in ('bias', 'noise_std') for axis in 'xyz'):
            rotation = tuple(self._offset('imu', 'imu_orientation', a) for a in 'xyz')
            q = output.orientation
            values = (q.x, q.y, q.z, q.w)
            norm = math.hypot(*values)
            if not math.isfinite(norm) or norm == 0:
                raise ValueError('Orientation perturbation requires a finite nonzero quaternion')
            x, y, z, w = (v / norm for v in values)
            angle = math.hypot(*rotation)
            scale = math.sin(angle / 2) / angle if angle else 0.5
            dx, dy, dz = (v * scale for v in rotation)
            dw = math.cos(angle / 2)
            # Right multiplication q_out = q_in * exp(rotation / 2).
            result = (w*dx + x*dw + y*dz - z*dy,
                      w*dy - x*dz + y*dw + z*dx,
                      w*dz + x*dy - y*dx + z*dw,
                      w*dw - x*dx - y*dy - z*dz)
            norm = math.hypot(*result)
            q.x, q.y, q.z, q.w = (v / norm for v in result)
        return output

    def pressure(self, message):
        """Apply pressure offsets in Pa, or return None on dropout."""
        if self._drop('pressure'):
            return None
        output = deepcopy(message)
        offset = self._offset('pressure', 'pressure')
        if offset != 0:
            output.fluid_pressure += offset
        return output

"""Displacement-based localization metrics, independent of ROS."""

import math


def wrapped_yaw_error(estimate, truth):
    """Return signed estimate-minus-truth yaw error in [-pi, pi]."""
    difference = estimate - truth
    return math.atan2(math.sin(difference), math.cos(difference))


def quaternion_yaw(x, y, z, w):
    """Extract yaw from a finite, nonzero quaternion after normalization."""
    if not all(math.isfinite(value) for value in (x, y, z, w)):
        raise ValueError('Quaternion must be finite')
    norm = math.hypot(x, y, z, w)
    if norm == 0:
        raise ValueError('Quaternion must be nonzero')
    x, y, z, w = (value / norm for value in (x, y, z, w))
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


class LocalizationMetrics:
    """Accumulate one equally weighted sample per accepted odometry pair."""

    def __init__(self):
        self.initial_estimate = None
        self.initial_truth = None
        self.sample_count = 0
        self.yaw_sample_count = 0
        self.horizontal_error = self.position_3d_error = self.z_error = None
        self.yaw_error = None
        self.horizontal_squared_sum = self.position_3d_squared_sum = 0.0
        self.z_squared_sum = self.yaw_squared_sum = 0.0
        self.max_horizontal_error = self.max_3d_error = 0.0

    def add_sample(self, estimate, truth, estimate_yaw=None, truth_yaw=None):
        """Align first positions, then accumulate displacement errors in metres."""
        estimate, truth = tuple(estimate), tuple(truth)
        if len(estimate) != 3 or len(truth) != 3:
            raise ValueError('Positions must have three components')
        if not all(math.isfinite(value) for value in estimate + truth):
            raise ValueError('Positions must be finite')
        if (estimate_yaw is None) != (truth_yaw is None):
            raise ValueError('Supply both yaw values or neither')
        if estimate_yaw is not None and not all(
                math.isfinite(value) for value in (estimate_yaw, truth_yaw)):
            raise ValueError('Yaw must be finite')
        if self.initial_estimate is None:
            self.initial_estimate, self.initial_truth = estimate, truth
        error = tuple(
            (e - e0) - (t - t0) for e, e0, t, t0 in zip(
                estimate, self.initial_estimate, truth, self.initial_truth))
        self.horizontal_error = math.hypot(error[0], error[1])
        self.position_3d_error = math.hypot(*error)
        self.z_error = error[2]
        self.sample_count += 1
        self.horizontal_squared_sum += self.horizontal_error ** 2
        self.position_3d_squared_sum += self.position_3d_error ** 2
        self.z_squared_sum += self.z_error ** 2
        self.max_horizontal_error = max(
            self.max_horizontal_error, self.horizontal_error)
        self.max_3d_error = max(self.max_3d_error, self.position_3d_error)
        self.yaw_error = None
        if estimate_yaw is not None:
            self.yaw_error = wrapped_yaw_error(estimate_yaw, truth_yaw)
            self.yaw_squared_sum += self.yaw_error ** 2
            self.yaw_sample_count += 1

    def summary(self):
        """Return current metrics; final errors refer to the latest sample."""
        def rmse(total, count):
            return math.sqrt(total / count) if count else None

        return {
            'sample_count': self.sample_count,
            'horizontal_error': self.horizontal_error,
            'position_3d_error': self.position_3d_error,
            'z_error': self.z_error,
            'horizontal_rmse': rmse(self.horizontal_squared_sum, self.sample_count),
            'position_3d_rmse': rmse(self.position_3d_squared_sum, self.sample_count),
            'depth_rmse': rmse(self.z_squared_sum, self.sample_count),
            'max_horizontal_error': self.max_horizontal_error,
            'max_3d_error': self.max_3d_error,
            'final_horizontal_error': self.horizontal_error,
            'final_3d_error': self.position_3d_error,
            'yaw_error': self.yaw_error,
            'yaw_rmse': rmse(self.yaw_squared_sum, self.yaw_sample_count),
            'yaw_sample_count': self.yaw_sample_count,
        }

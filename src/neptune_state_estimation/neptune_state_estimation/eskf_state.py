"""
ROS-independent S2.6 nominal state and error covariance structures.

W is Neptune's local world_ned frame (positive-down z); B is base_link.
q_WB uses ROS [x, y, z, w] ordering and Hamilton multiplication, rotating
body vectors into world coordinates. Velocity here is world-frame velocity,
whereas the existing Odometry output's twist is body-frame velocity.
Biases and the right-multiplicative attitude error are expressed in B.

Injection changes only the nominal state. Covariance reset/recentering after
attitude injection is deliberately deferred to S2.8+ measurement updates:
do not treat injection alone as a complete Kalman update or reuse an old P
as though it had been reset. No operational filter is provided here.
"""

from dataclasses import dataclass, field

import numpy as np


NOMINAL_DIM = 16  # Quaternion has four coordinates but three degrees of freedom.
ERROR_DIM = 15
DELTA_P = slice(0, 3)
DELTA_V = slice(3, 6)
DELTA_THETA = slice(6, 9)
DELTA_B_G = slice(9, 12)
DELTA_B_A = slice(12, 15)


def _vector(value, size, name):
    """Return a finite, dimension-checked owned float array."""
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f'{name} must be a finite vector of shape ({size},)')
    return result


def normalize_quaternion(value):
    """Normalize a nonzero ROS-order quaternion without aliasing its input."""
    q = _vector(value, 4, 'quaternion')
    scale = np.max(np.abs(q))
    if scale == 0.0:
        raise ValueError('quaternion must be nonzero')
    q /= scale  # Avoid norm overflow/underflow for finite nonzero inputs.
    return q / np.linalg.norm(q)


def small_angle_quaternion(delta_theta):
    """
    Map a body rotation vector in radians to a unit quaternion.

    Use the exponential map, whose small-angle limit is [delta_theta/2, 1].
    np.sinc provides the continuous zero-angle limit without division by zero.
    This helper does not impose a measurement-gating threshold.
    """
    theta = _vector(delta_theta, 3, 'delta_theta')
    angle = np.linalg.norm(theta)
    if not np.isfinite(angle):
        raise ValueError('rotation-vector norm must be finite')
    xyz = theta * (0.5 * np.sinc(angle / (2.0 * np.pi)))
    return normalize_quaternion(np.r_[xyz, np.cos(angle / 2.0)])


def validate_error_state(delta_x):
    """Return an owned 15D error in p, v, theta, gyro-bias, accel-bias order."""
    return _vector(delta_x, ERROR_DIM, 'delta_x')


def validate_covariance(value):
    """
    Copy and validate a finite symmetric positive-semidefinite 15x15 P.

    Numerical symmetry/PSD tolerance is 1e-12 relative to matrix scale.
    Zero uncertainty is allowed by validation, but initialization defaults
    and configurable initialization variances must be strictly positive.
    """
    p = np.array(value, dtype=float, copy=True)
    if p.shape != (ERROR_DIM, ERROR_DIM) or not np.all(np.isfinite(p)):
        raise ValueError('covariance must be finite with shape (15, 15)')
    tolerance = 1e-12 * max(1.0, float(np.max(np.abs(p))))
    if np.max(np.abs(p - p.T)) > tolerance:
        raise ValueError('covariance must be symmetric')
    if np.any(np.diag(p) < 0.0):
        raise ValueError('covariance diagonal must be nonnegative')
    if np.linalg.eigvalsh(0.5 * p + 0.5 * p.T)[0] < -tolerance:
        raise ValueError('covariance must be positive semidefinite')
    return p


def initial_covariance(
    position_variance=1.0,
    velocity_variance=0.01,
    attitude_variance=(np.pi / 180.0) ** 2,
    gyro_bias_variance=1e-4,
    accel_bias_variance=0.01,
):
    """
    Construct diagonal engineering defaults, not tuned sensor values.

    Each argument is one positive scalar variance or three axis variances.
    Units/defaults: position 1 m^2; velocity 0.01 (m/s)^2;
    attitude (pi/180)^2 rad^2; gyro bias 1e-4 (rad/s)^2;
    accelerometer bias 0.01 (m/s^2)^2. Arguments are variances, not sigmas.
    """
    diagonal = []
    for value in (position_variance, velocity_variance, attitude_variance,
                  gyro_bias_variance, accel_bias_variance):
        array = np.array(value, dtype=float, copy=True)
        if array.shape == ():
            array = np.full(3, float(array))
        array = _vector(array, 3, 'initial variance')
        if np.any(array <= 0.0):
            raise ValueError('initial variances must be strictly positive')
        diagonal.extend(array)
    return np.diag(diagonal)


@dataclass
class NominalState:
    """
    Owned nominal arrays: p_WB[3], v_WB[3], q_WB[4], b_g[3], b_a[3].

    Defaults are zero position, velocity and biases, with identity attitude.
    Arrays are mutable for future filter use; validate() checks any later edits.
    """

    p_WB: np.ndarray = field(default_factory=lambda: np.zeros(3))
    v_WB: np.ndarray = field(default_factory=lambda: np.zeros(3))
    q_WB: np.ndarray = field(default_factory=lambda: np.array([0., 0., 0., 1.]))
    b_g: np.ndarray = field(default_factory=lambda: np.zeros(3))
    b_a: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def __post_init__(self):
        """Copy all inputs, check dimensions, and normalize orientation."""
        for name in ('p_WB', 'v_WB', 'b_g', 'b_a'):
            setattr(self, name, _vector(getattr(self, name), 3, name))
        self.q_WB = normalize_quaternion(self.q_WB)

    def validate(self):
        """Reject malformed, nonfinite or nonunit mutable state fields."""
        for name in ('p_WB', 'v_WB', 'b_g', 'b_a'):
            _vector(getattr(self, name), 3, name)
        q = _vector(self.q_WB, 4, 'q_WB')
        if not np.isclose(np.linalg.norm(q), 1.0, rtol=0., atol=1e-12):
            raise ValueError('q_WB must be unit length')

    def copy(self):
        """Return a state sharing no mutable arrays with this state."""
        self.validate()
        return NominalState(self.p_WB, self.v_WB, self.q_WB, self.b_g, self.b_a)

    def inject_error(self, delta_x):
        """
        Return a new nominal state with q_new = q_WB Hamilton delta_q.

        p/v errors are world-frame, theta/bias errors are body-frame. The input
        state and error array remain unchanged; P is neither accepted nor reset.
        """
        self.validate()
        error = validate_error_state(delta_x)
        delta_q = small_angle_quaternion(error[DELTA_THETA])
        xyz, w = self.q_WB[:3], self.q_WB[3]
        dxyz, dw = delta_q[:3], delta_q[3]
        q = np.r_[w * dxyz + dw * xyz + np.cross(xyz, dxyz),
                  w * dw - np.dot(xyz, dxyz)]
        return NominalState(
            self.p_WB + error[DELTA_P], self.v_WB + error[DELTA_V], q,
            self.b_g + error[DELTA_B_G], self.b_a + error[DELTA_B_A],
        )

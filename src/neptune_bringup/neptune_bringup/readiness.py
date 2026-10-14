"""Sensor-derived demo startup qualification; no simulator truth or commands."""

from collections import deque
import math


class DemoReadiness:
    """Require fresh finite inputs and a stationary startup window once."""

    required = ('pressure', 'imu', 'dvl', 'state')

    def __init__(self, minimum_startup=15.0, stable_window=3.0, timeout=0.5):
        self.minimum_startup = minimum_startup
        self.stable_window = stable_window
        self.timeout = timeout
        self.samples = {}
        self.depth_rates = deque(maxlen=100)
        self.yaw_rates = deque(maxlen=200)
        self.first_sample = None
        self.previous_pressure = None
        self.qualified = False

    def observe(self, name, receipt, stamp, valid=True):
        """Reject nonadvancing source stamps while allowing later recovery."""
        previous = self.samples.get(name)
        valid = (valid and math.isfinite(stamp)
                 and (previous is None or not math.isfinite(previous['stamp'])
                      or stamp > previous['stamp']))
        self.samples[name] = dict(receipt=receipt, stamp=stamp, valid=valid)
        if self.first_sample is None:
            self.first_sample = receipt
        return valid

    def pressure(self, receipt, stamp, pressure):
        """Use the existing pressure_depth calibration for startup depth rate."""
        valid = self.observe('pressure', receipt, stamp, math.isfinite(pressure))
        depth = pressure / (997.0 * 9.81) + 0.40
        rate = None
        if valid and self.previous_pressure is not None:
            old_stamp, old_depth = self.previous_pressure
            dt = stamp - old_stamp
            if 0 < dt < 1.0:
                rate = (depth - old_depth) / dt
        self.previous_pressure = (stamp, depth) if valid else None
        self.depth_rates.append((receipt, rate))

    def imu(self, receipt, stamp, yaw_rate, orientation_valid=True):
        """Record IMU angular-Z rate without inferring stability from truth."""
        valid = self.observe(
            'imu', receipt, stamp, orientation_valid and math.isfinite(yaw_rate),
        )
        self.yaw_rates.append((receipt, yaw_rate if valid else None))

    def _stable(self, history, now, limit):
        start = now - self.stable_window
        # Retain one sample before the window to establish coverage.
        while len(history) > 1 and history[1][0] <= start:
            history.popleft()
        if not history or history[0][0] > start:
            return False
        values = [(at, value) for at, value in history if at >= start]
        if not values or any(value is None or abs(value) >= limit for _, value in values):
            return False
        edges = [start] + [at for at, _ in values] + [now]
        return max(b - a for a, b in zip(edges, edges[1:])) < self.timeout

    def snapshot(self, now, ros_now):
        """After startup, monitor freshness without requiring a moving robot to settle."""
        health = {}
        for name in self.required:
            s = self.samples.get(name)
            health[name] = bool(
                s and s['valid'] and 0 <= now - s['receipt'] < self.timeout
                and -0.05 <= ros_now - s['stamp'] < self.timeout
            )
        reason = 'State and required sensors are live'
        if not all(health.values()):
            reason = 'Waiting for live ' + ', '.join(k for k, v in health.items() if not v)
        elif not self.qualified:
            if now - self.first_sample < self.minimum_startup:
                reason = 'Allowing initial vehicle transient to settle'
            elif not self._stable(self.depth_rates, now, 0.05):
                reason = 'Waiting for stable pressure-derived depth'
            elif not self._stable(self.yaw_rates, now, 0.03):
                reason = 'Waiting for stable IMU yaw rate'
            else:
                self.qualified = True
        ready = all(health.values()) and self.qualified
        return dict(ready=ready, startup_qualified=self.qualified,
                    sensor_health=health, reason=reason,
                    freshness_s=self.timeout, stable_window_s=self.stable_window)

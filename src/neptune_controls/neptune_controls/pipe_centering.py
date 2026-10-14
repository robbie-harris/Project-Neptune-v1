"""Bounded lateral centering of P4c observations, independent of ROS."""

import math


ASSOCIATIONS = {'CONSENSUS', 'INSPECTION_ONLY', 'ORIENTATION_A_ONLY'}
MODELS = {
    'inspection': 'projects-zwfft/neptune-inspection-objects-2-yolo11n-t1',
    'orientation_a': 'projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1',
}


def finite(value):
    """Reject booleans and nonfinite numeric fields."""
    return type(value) in (int, float) and math.isfinite(value)


class PipeCentering:
    """Reuse fresh frames at control rate; confirm only distinct source stamps."""

    def __init__(self, kp=0.5, max_sway=0.25, deadband=0.05,
                 freshness_s=0.5, confirmation_count=3, sway_sign=0.0):
        if (not all(finite(v) for v in (kp, max_sway, deadband, freshness_s, sway_sign))
                or kp < 0 or not 0 < max_sway <= 1 or not 0 <= deadband < 1
                or freshness_s <= 0 or sway_sign not in (-1, 0, 1)
                or type(confirmation_count) is not int or confirmation_count < 1):
            raise ValueError('Invalid centering parameters')
        self.kp, self.max_sway, self.deadband = kp, max_sway, deadband
        self.freshness_s, self.confirmation_count = freshness_s, confirmation_count
        self.sway_sign = sway_sign
        self.state = 'WAITING_FOR_TARGET'
        self.count = 0
        self.key = self.target = self.received = self.stamp = None
        self.initial_age = 0.0
        self.confirmed_key = None

    def reject(self, state):
        """Clear motion eligibility and consecutive confirmation on loss."""
        self.state, self.count, self.target = state, 0, None

    def receive(self, status, now, ros_now):
        """Validate the existing authoritative JSON contract, failing closed."""
        try:
            state = status['state']
            if state == 'AMBIGUOUS':
                self.reject('AMBIGUOUS')
                return
            if state in ('STALE', 'CAMERA_STALE'):
                self.reject('STALE')
                return
            if state == 'MODEL_UNAVAILABLE':
                self.reject('PERCEPTION_UNAVAILABLE')
                return
            if state == 'NO_PIPE':
                self.reject('TARGET_LOST')
                return
            target = status['selected_target']
            if (state not in ASSOCIATIONS or status['valid'] is not True
                    or target is None or target['valid'] is not True
                    or target['state'] != state):
                raise ValueError('Invalid target')
            header = status['source_header']
            sec, nsec = header['stamp']['sec'], header['stamp']['nanosec']
            if (type(sec) is not int or not 0 <= sec <= 2147483647 or type(nsec) is not int
                    or not 0 <= nsec < 10**9 or not isinstance(header['frame_id'], str)
                    or not header['frame_id']):
                raise ValueError('Invalid stamp')
            key = (sec, nsec)
            stamp = sec+nsec/1e9
            ages = [ros_now-stamp, status['observation_age_s'], status['receipt_age_s']]
            if not all(finite(age) and 0 <= age <= self.freshness_s for age in ages):
                self.reject('STALE')
                return
            width, height = status['image_width'], status['image_height']
            u, v = target['center']
            error = target['horizontal_error']
            if (type(width) is not int or width <= 0 or type(height) is not int or height <= 0
                    or not all(finite(x) for x in (u, v, error))
                    or not 0 <= u <= width or not 0 <= v <= height
                    or not math.isclose(error, (u-width/2)/(width/2), abs_tol=1e-6)):
                raise ValueError('Invalid geometry')
            source = target['bbox_source']
            if (source not in MODELS or target['selected_source'] != MODELS[source]
                    or MODELS[source] not in target['model_provenance']
                    or status['model_states'][source] not in ('READY', 'NO_DETECTION')):
                self.reject('PERCEPTION_UNAVAILABLE')
                return
            if self.key is not None and key < self.key:
                raise ValueError('Out-of-order observation')
            if key != self.key:
                self.key, self.received, self.stamp = key, now, stamp
                self.initial_age = max(ages)
            # Watchdog repeats cannot rejuvenate a frame or confirm alignment.
            if max(self.initial_age+now-self.received, ros_now-self.stamp) > self.freshness_s:
                self.reject('STALE')
                return
            self.target = target
            if key != self.confirmed_key:
                self.confirmed_key = key
                self.count = self.count+1 if abs(error) <= self.deadband else 0
            self.state = ('ALIGNED' if self.count >= self.confirmation_count else 'ALIGNING')
        except (KeyError, ValueError, TypeError, IndexError):
            self.reject('INVALID_TARGET')

    def command(self, now, ros_now):
        """Return sway only; both source and steady elapsed clocks bound reuse."""
        if self.target is None:
            return 0.0
        if (ros_now < self.stamp or ros_now-self.stamp > self.freshness_s
                or self.initial_age+now-self.received > self.freshness_s):
            self.reject('STALE')
            return 0.0
        if self.sway_sign == 0:
            self.state = 'SIGN_UNCALIBRATED'
            return 0.0
        error = self.target['horizontal_error']
        if abs(error) <= self.deadband:
            return 0.0
        return max(-self.max_sway, min(self.max_sway, self.sway_sign*self.kp*error))

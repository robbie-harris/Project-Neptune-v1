"""No motion eligibility without simultaneous continuous physical/perception gates."""
from copy import deepcopy

from perception_p5a_settling import perception_window, physical_window


def physical_samples():
    p = [{'receipt': i/5, 'depth': 0.45, 'depth_rate': 0.01} for i in range(26)]
    imu = [{'receipt': i/20, 'yaw_rate': 0.001} for i in range(101)]
    return p, imu


def perception_samples():
    camera = [i/5 for i in range(26)]
    fused = [(t, {'sequence': i, 'valid': True, 'state': 'CONSENSUS',
                  'observation_age_s': 0.1, 'receipt_age_s': 0.05})
             for i, t in enumerate(camera)]
    models = [(1, m, {'state': 'READY'}) for m in ('inspection', 'orientation_a')]
    return camera, fused, models


def test_continuous_physical_window():
    p, imu = physical_samples()
    assert physical_window(p, imu, 0, 5)['physical_settled']
    assert not physical_window(p, imu, 0, 4)['physical_settled']
    p[12]['depth_rate'] = 0.05
    assert not physical_window(p, imu, 0, 5)['physical_settled']


def test_yaw_motion_missing_rate_and_sensor_gap():
    p, imu = physical_samples()
    bad = deepcopy(imu)
    bad[20]['yaw_rate'] = 0.03
    assert not physical_window(p, bad, 0, 5)['physical_settled']
    p[3]['depth_rate'] = None
    assert not physical_window(p, imu, 0, 5)['physical_settled']
    p, imu = physical_samples()
    p = [s for s in p if not 1 <= s['receipt'] <= 2]
    assert not physical_window(p, imu, 0, 5)['physical_settled']


def test_perception_window_and_invalid_watchdog():
    c, f, m = perception_samples()
    assert perception_window(c, f, m, 0, 5)[0]
    f.insert(5, (0.81, {'sequence': 4, 'valid': False, 'state': 'STALE'}))
    assert not perception_window(c, f, m, 0, 5)[0]


def test_camera_gap_and_age_and_camera_stale():
    c, f, m = perception_samples()
    bad_camera = [t for t in c if t not in (1.0, 1.2)]
    assert not perception_window(bad_camera, f, m, 0, 5)[0]
    f[3][1]['observation_age_s'] = 0.5
    assert not perception_window(c, f, m, 0, 5)[0]
    c, f, m = perception_samples()
    m.append((4, 'inspection', {'state': 'CAMERA_STALE'}))
    assert not perception_window(c, f, m, 0, 5)[0]


def test_no_targets_cannot_pass():
    c, f, m = perception_samples()
    for _, s in f:
        s.update(valid=False, state='NO_PIPE')
    assert not perception_window(c, f, m, 0, 5)[0]

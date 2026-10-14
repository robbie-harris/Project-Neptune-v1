"""Safety and bounded control contracts for P5a."""
from neptune_controls.pipe_centering import MODELS, PipeCentering
import pytest


def observation(error=0.3, sec=100, **changes):
    s = {
        'state': 'CONSENSUS', 'valid': True,
        'source_header': {'stamp': {'sec': sec, 'nanosec': 0}, 'frame_id': 'camera'},
        'observation_age_s': 0.1, 'receipt_age_s': 0.05,
        'image_width': 320, 'image_height': 240,
        'model_states': {'inspection': 'READY', 'orientation_a': 'READY'},
        'selected_target': {
            'valid': True, 'state': 'CONSENSUS', 'center': [160*(1+error), 120],
            'horizontal_error': error, 'bbox_source': 'inspection',
            'selected_source': MODELS['inspection'], 'model_provenance': list(MODELS.values())}}
    s.update(changes)
    return s


def controller(error=0.3, **parameters):
    c = PipeCentering(sway_sign=1.0, **parameters)
    c.receive(observation(error), 0, 100.1)
    return c


@pytest.mark.parametrize('error,expected', [
    (0.3, 0.15), (-0.3, -0.15), (0, 0), (0.04, 0), (1, 0.25), (-1, -0.25)])
def test_proportional(error, expected):
    assert controller(error).command(0, 100.1) == pytest.approx(expected)


@pytest.mark.parametrize('state,expected', [
    ('AMBIGUOUS', 'AMBIGUOUS'), ('STALE', 'STALE'),
    ('MODEL_UNAVAILABLE', 'PERCEPTION_UNAVAILABLE'), ('NO_PIPE', 'TARGET_LOST')])
def test_loss(state, expected):
    c = controller()
    c.receive(observation(state=state, valid=False, selected_target=None), 0.1, 100.2)
    assert c.command(0.1, 100.2) == 0
    assert c.state == expected


def test_invalid():
    c = controller()
    c.receive(observation(valid=False), 0.1, 100.2)
    assert c.command(0.1, 100.2) == 0


def test_stale_reuse_and_clock_stall():
    c = controller()
    assert c.command(0.2, 100.1) > 0
    assert c.command(0.41, 100.1) == 0
    assert c.state == 'STALE'


def test_watchdog_duplicates_never_rejuvenate():
    c = controller()
    for now in [0.1, 0.2, 0.3, 0.4, 0.5]:
        c.receive(observation(), now, 100.1)
    assert c.command(0.5, 100.1) == 0


def test_multiple_fresh_sources_required():
    c = controller(0)
    for _ in range(10):
        c.receive(observation(0), 0.1, 100.2)
        c.command(0.1, 100.2)
    assert c.count == 1
    assert c.state == 'ALIGNING'
    for sec in [101, 102]:
        c.receive(observation(0, sec=sec), sec-100, sec+0.1)
    assert c.state == 'ALIGNED'
    c.receive(observation(0.2, sec=103), 3, 103.1)
    assert c.state == 'ALIGNING' and c.count == 0


def test_confirmation_reset_on_loss():
    c = controller(0)
    c.receive(observation(state='NO_PIPE'), 0.1, 100.2)
    c.receive(observation(0), 0.2, 100.3)
    assert c.count == 0


@pytest.mark.parametrize('error', [1e300, -1e300, float('nan'), float('inf')])
def test_extreme_geometry_fails_closed(error):
    assert controller(error).command(0, 100.1) == 0


def test_source_age_and_future():
    for age in [0.6, -0.01]:
        c = PipeCentering(sway_sign=1)
        c.receive(observation(), 0, 100+age)
        assert c.command(0, 100+age) == 0


def test_unavailable_selected_model():
    c = controller()
    s = observation()
    s['model_states']['inspection'] = 'MODEL_UNAVAILABLE'
    c.receive(s, 0, 100.1)
    assert c.command(0, 100.1) == 0


def test_sign_uncalibrated_and_reverse():
    c = PipeCentering()
    c.receive(observation(), 0, 100.1)
    assert c.command(0, 100.1) == 0
    c = PipeCentering(sway_sign=-1)
    c.receive(observation(), 0, 100.1)
    assert c.command(0, 100.1) == pytest.approx(-0.15)


@pytest.mark.parametrize('parameters', [
    {'kp': -1}, {'max_sway': 2}, {'deadband': 2},
    {'freshness_s': 0}, {'confirmation_count': 0}, {'sway_sign': 2}])
def test_bad_configuration(parameters):
    with pytest.raises(ValueError):
        PipeCentering(**parameters)


def test_extreme_gain_stays_bounded():
    assert controller(1, kp=1e300).command(0, 100.1) == 0.25


def test_ros_clock_expiry_and_backward_jump():
    assert controller().command(0.1, 100.6) == 0
    assert controller().command(0.1, 99.9) == 0


def test_malformed_stamp_and_geometry():
    bad_header = {'stamp': {'sec': 10**400, 'nanosec': 0}, 'frame_id': 'camera'}
    for field, value in [('source_header', bad_header), ('image_width', 0)]:
        c = controller()
        s = observation(**{field: value})
        c.receive(s, 0, 100.1)
        assert c.command(0, 100.1) == 0

import pytest
from neptune_sim.autonomous_power import power_profile,validate_power


def test_power_scales_translation_without_cumulative_scaling_or_stabilization_changes():
    base=dict(cruise_speed_m_s=1.,sway_cruise_speed_m_s=.5,max_surge=.8,max_sway=.9,max_yaw=.4,max_heave=.5,timeout_s=60)
    half=power_profile(base,50)
    assert half['cruise_speed_m_s']==.5 and half['sway_cruise_speed_m_s']==.25
    assert half['max_surge']**2==pytest.approx(base['max_surge']**2*.5)
    assert all(half[k]==base[k] for k in ['max_yaw','max_heave','timeout_s'])
    assert power_profile(base,100)==base and base['cruise_speed_m_s']==1.


@pytest.mark.parametrize('value',[True,False,None,'50',float('nan'),float('inf'),19,101])
def test_invalid_power_is_rejected(value):
    with pytest.raises(ValueError):validate_power(value)

"""Relative autonomous translation setting; not measured electrical wattage."""
import copy
import math


def validate_power(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 20<=value<=100:
        raise ValueError('Autonomous power must be a finite number from 20 to 100')
    return float(value)


def power_profile(base,percent):
    settings=copy.deepcopy(base);fraction=validate_power(percent)/100
    settings['cruise_speed_m_s']=base.get('cruise_speed_m_s',.18)*fraction
    if 'sway_cruise_speed_m_s' in base:settings['sway_cruise_speed_m_s']=base['sway_cruise_speed_m_s']*fraction
    for key in ('max_surge','max_sway'):
        if key in base:settings[key]=base[key]*math.sqrt(fraction)
    return settings

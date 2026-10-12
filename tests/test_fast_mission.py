import json
from pathlib import Path
import numpy as np
from neptune_sim.mission import InspectionMission,inspection_route
from neptune_sim.navigation import DeadReckoning,thrust_commands

ROOT=Path(__file__).resolve().parents[1]
FAST=json.loads((ROOT/'Simulation/config/mission_fast.json').read_text())
RIG=json.loads((ROOT/'Simulation/config/rig.json').read_text())
RETURN=json.loads((ROOT/'Simulation/config/errors.json').read_text())['return']

def test_allocation_keeps_surge_and_yaw_forces_independent():
    p,s,_=thrust_commands(.3,.1,0)
    assert np.isclose(p*abs(p)+s*abs(s),.6)
    assert np.isclose(p*abs(p)-s*abs(s),.2)
    assert max(abs(v) for v in thrust_commands(2,1,0))<=1

def test_fast_profile_has_full_component_route_and_hard_deadline_even_on_return():
    route=inspection_route(np.array(RIG['spawn']['xyz']),FAST)
    assert [r['class'] for r in route]==['pipe','valve','flange','pipe']
    m=InspectionMission(FAST,RIG['spawn'],RETURN);e=DeadReckoning(RIG['spawn']);m.start(e,0)
    m.state='returning';m.returner.start(59)
    assert m.step(e,60.1,True)==[0,0,0,0] and not m.active and m.reason=='Mission timed out'

def test_fast_return_initial_to_translate_transition_produces_bounded_command():
    m=InspectionMission(FAST,RIG['spawn'],RETURN);e=DeadReckoning(RIG['spawn'])
    e.position=np.array([1.,1.85,1.5]);m.returner.start(0)
    cmd=m.returner.step(e,.1,True)
    assert len(cmd)==4 and np.isfinite(cmd).all() and max(abs(v) for v in cmd)<=1


def test_side_translation_preserves_heading_and_stale_navigation_stops_every_axis():
    m=InspectionMission(FAST,RIG['spawn'],RETURN);e=DeadReckoning(RIG['spawn'])
    e.position=np.array([.6,-.85,1.5]);m.state='travel'
    cmd,_,_=m.motion(e,[.6,.85,1.5])
    assert cmd[3]>0 and np.isclose(cmd[0],cmd[1]) and abs(cmd[0])<1e-8
    assert m.step(e,0,False)==[0,0,0,0] and not m.active


def test_fast_rig_native_motor_order_and_counter_rotating_sway_pair():
    import xml.etree.ElementTree as ET
    robot=ET.parse(ROOT/'Simulation/scenarios/inspection_fast.scn').getroot().find('robot')
    thrusters=robot.findall("actuator[@type='thruster']")
    assert [t.get('name') for t in thrusters]==['ThrusterPort','ThrusterStarboard','ThrusterHeave','ThrusterSwayFront','ThrusterSwayRear']
    assert [t.find('propeller').get('right') for t in thrusters[-2:]]==['true','false']
    assert thrusters[-1].find('specs').get('inverted_setpoint')=='true'
    assert all(t.find('rotor_dynamics/time_constant').get('value')=='0.15' for t in thrusters)


def test_holonomic_return_success_and_envelope_stop_all_four_commands():
    m=InspectionMission(FAST,RIG['spawn'],RETURN);e=DeadReckoning(RIG['spawn']);m.returner.start(0)
    m.returner.step(e,.1,True);m.returner.step(e,.2,True)
    assert m.returner.step(e,.3,True)==[0,0,0,0] and m.returner.state=='complete'
    m.returner.start(1);e.position[1]=2.6
    assert m.returner.step(e,1.1,True)==[0,0,0,0] and not m.returner.active

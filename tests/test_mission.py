import json
from pathlib import Path
import numpy as np
from neptune_sim.mission import InspectionMission,inspection_route,lateral_transit
from neptune_sim.navigation import DeadReckoning

ROOT=Path(__file__).resolve().parents[1]
SETTINGS=json.loads((ROOT/'Simulation/config/mission.json').read_text())
RIG=json.loads((ROOT/'Simulation/config/rig.json').read_text())
RETURN=json.loads((ROOT/'Simulation/config/errors.json').read_text())['return']

def fixture():
    m=InspectionMission(SETTINGS,RIG['spawn'],RETURN);e=DeadReckoning(RIG['spawn'])
    m.detector_ready=True;m.capture_seen=0;m.camera_seen=0;m.last_stamp=(0,0);m.start(e,0)
    return m,e

def observe(m,now,classes):
    m.camera(now,now,now)
    m.detection({'state':'ready','stamp':{'sec':int(now),'nanosec':int((now%1)*1e9)},
                 'detections':[{'class':c,'confidence':.8} for c in classes]},now,now)

def test_route_nearest_end_and_component_order_both_directions():
    for position,expected in [([-3.8,-1,1.5],['valve','flange']),([-3.8,1,1.5],['flange','valve'])]:
        route=inspection_route(np.array(position),SETTINGS)
        assert [r['class'] for r in route if r['class']!='pipe']==expected
        assert route[0]['label']=='closest pipe end' and route[-1]['label']=='far pipe end'
        assert all(np.isclose(r['position'][0],4.4-SETTINGS['body_standoff_m']) for r in route)
        assert all(abs(r['position'][1])<=1.85 for r in route)

def test_unique_fresh_detections_required_to_start_travel():
    m,e=fixture()
    for _ in range(10):observe(m,.2,['pipe'])
    m.step(e,.2,True);assert m.state=='acquire_pipe'
    observe(m,.4,['pipe']);observe(m,.6,['pipe']);m.step(e,.6,True)
    assert m.state=='travel'

def test_stale_sensor_and_detector_stop_immediately():
    m,e=fixture();assert m.step(e,.1,False)==[0,0,0] and not m.active
    m,e=fixture();assert m.step(e,4,True)==[0,0,0] and m.active and 'camera' in m.hold_reason
    assert m.step(e,30,True)==[0,0,0] and not m.active and 'timed out' in m.reason

def test_missing_component_never_marked_visited_or_skipped():
    m,e=fixture();m.index=next(i for i,r in enumerate(m.route) if r['class']=='valve')
    e.position=np.array(m.route[m.index]['position']);m.transition('observe',0)
    for t in (1,2,3):observe(m,t,['pipe']);m.step(e,t,True)
    assert not m.visits and m.state=='observe'
    observe(m,27,['pipe']);assert m.step(e,27,True)==[0,0,0]
    assert not m.active and 'valve' in m.reason

def test_all_visits_then_return_completion_and_cancel():
    m,e=fixture();m.transition('observe',0)
    for i,r in enumerate(m.route):
        m.index=i;e.position=np.array(r['position']);m.transition('observe',i*3)
        for t in (i*3+.2,i*3+.4,i*3+.6):observe(m,t,[r['class']]);m.step(e,t,True)
    assert m.state=='returning' and len(m.visits)==len(m.route)
    e.position=np.array(RIG['spawn']['xyz']);e.attitude=np.array(RIG['spawn']['rpy'])
    for t in (50,51,52):m.step(e,t,True)
    assert m.state=='complete' and m.step(e,53,True)==[0,0,0]
    m.cancel('GUI disconnected');assert m.state=='complete'
    m.start(e,54);m.cancel('Operator stop');assert m.step(e,55,True)==[0,0,0]

def test_envelope_blocks_motion_into_pipe_and_tank_wall():
    m,e=fixture();e.position[0]=3.7
    assert m.step(e,.1,True)==[0,0,0] and 'envelope' in m.reason

def test_visual_timeout_starts_only_after_heading_alignment():
    m,e=fixture();e.position=np.array(m.route[0]['position']);e.attitude[2]=1
    m.transition('observe',0)
    observe(m,30,['pipe']);m.step(e,30,True)
    assert m.active and m.observe_started is None
    e.attitude[2]=0;observe(m,31,['pipe']);m.step(e,31,True)
    assert m.observe_started==31

def test_start_readiness_requires_fresh_perception():
    m,e=fixture();assert m.ready(1) and not m.ready(4)
    m.detector_ready=False;assert not m.ready(1)

def test_transient_error_holds_then_resumes_same_waypoint_without_old_confirmations():
    m,e=fixture();m.state='travel';m.index=2
    m.detection({'state':'error','reason':'Local Inference timed out'},1,1)
    assert m.step(e,1,True)==[0,0,0] and m.active
    m.camera(2,2,2);m.detection({'state':'ready','stamp':{'sec':0,'nanosec':0},'detections':[]},2,2)
    assert m.step(e,2,True)==[0,0,0] and m.hold_since is not None
    observe(m,6,['valve']);m.step(e,6,True)
    assert m.active and m.state=='travel' and m.index==2 and not m.visits and m.hold_since is None
    assert m.phase_started==5 and not m.observations

def test_camera_and_inference_health_are_independent_and_replayed_status_is_stale():
    m,e=fixture();m.camera(4,4,4)
    assert 'Inference' in m.health_reason(4)
    observe(m,5,['pipe']);m.camera_seen=0
    assert 'camera' in m.health_reason(5)
    m.camera(6,6,6);m.detection({'state':'ready','stamp':{'sec':5,'nanosec':0},'detections':[]},9,9)
    assert m.capture_seen==5

def test_navigation_and_operator_stop_override_perception_hold():
    m,e=fixture();m.step(e,4,True)
    assert m.hold_since is not None
    assert m.step(e,5,False)==[0,0,0] and not m.active
    m,e=fixture();m.step(e,4,True);m.cancel('Operator stop')
    assert m.step(e,5,True)==[0,0,0] and not m.active and m.hold_since is None

def test_shallow_lateral_passes_stay_inside_safe_pipe_clearance():
    for direction in (-1,1):
        start=np.array([1.4,-.85,1.5]);goal=start+np.array([0,direction,0])
        points=lateral_transit(start,goal,35);assert len(points)==2
        first=np.array(points[0])-start;second=goal-np.array(points[0])
        assert np.isclose(abs(np.degrees(np.arctan2(first[1],first[0]))),35)
        assert np.isclose(abs(np.degrees(np.arctan2(-second[1],-second[0]))),35)
        assert max(p[0] for p in points)<3.1 and points[-1]==goal.tolist()

def test_view_route_has_fewer_observation_stops_and_more_standoff():
    route=inspection_route(np.array(RIG['spawn']['xyz']),SETTINGS)
    assert len(route)==5 and SETTINGS['cruise_speed_m_s']>.2
    assert all(p['position'][0]<2 for p in route)

def test_reverse_leg_overshoot_drives_back_towards_endpoint():
    m,e=fixture();m.state='travel';m.index=1;m.transit=[[2.1,-1.35,1.5],[1.4,-.85,1.5]];m.transit_index=1
    e.position=np.array([1.,-.85,1.5]);cmd,_,_=m.motion(e,m.transit[1])
    assert (cmd[0]+cmd[1])/2>0
    e.position[0]=1.8;cmd,_,_=m.motion(e,m.transit[1])
    assert (cmd[0]+cmd[1])/2<0

def test_shallow_transfer_aligns_before_surge_to_avoid_cross_track_error():
    m,e=fixture();m.index=1;m.transit=[[2.1,-1.35,1.5],[1.4,-.85,1.5]];m.transit_index=0
    e.position=np.array([1.4,-1.85,1.5]);e.attitude[2]=0
    cmd,_,_=m.motion(e,m.transit[0])
    assert abs(cmd[0]+cmd[1])<1e-8 and cmd[0]!=0

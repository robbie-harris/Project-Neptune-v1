"""Presentation rendering, profile defaults and host argument forwarding."""

import json
import os
from pathlib import Path
import subprocess

import cv2
import numpy as np
import pytest
from sensor_msgs.msg import Image

from neptune_bringup.demo_gui import (
    WINDOW_FLAGS, image_fit, mission_progress, render,
)
from neptune_bringup.presentation import window_profile


def snapshot(phase='TRANSIT'):
    message = Image()
    message.header.stamp.sec = 100
    return dict(image=message, image_receipt=9.95, state_receipt=9.95,
                mission_receipt=9.95, receipts=[9.8, 9.9, 10.0],
                mission={'state': phase, 'mission_elapsed_s': 84, 'complete': False},
                health={'ready': True},
                telemetry={'depth': 3.03, 'x': -10.4, 'y': .2, 'heading': 1.2})


@pytest.mark.parametrize('phase,index', [
    ('INITIALIZING', 0), ('WAIT_FOR_STATE', 0), ('DIVE', 1), ('TRANSIT', 2),
    ('INSPECT', 3), ('RETURN', 4), ('ASCEND', 5), ('COMPLETE', 6),
])
def test_mission_progress(phase, index):
    assert mission_progress(phase) == index


@pytest.mark.parametrize('size', [(720, 540), (800, 600), (1000, 800), (1400, 1000)])
def test_resize_preserves_camera_aspect_and_health(size):
    frame = np.full((240, 320, 3), (30, 85, 120), np.uint8)
    canvas, health = render(snapshot(), frame, 10.0, 100.1, size=size)
    assert canvas.shape == (size[1], size[0], 3)
    x, y, width, height = health['camera_rect']
    assert width*3 == height*4
    assert x >= 0 and y >= 0 and x+width <= size[0] and y+height <= size[1]-74
    assert np.array_equal(canvas[y:y+height, x:x+width],
                          np.broadcast_to(frame[0, 0], (height, width, 3)))
    assert health['camera_live'] and health['state_live'] and health['mission_status_live']
    assert health['autonomy_status'] == 'ACTIVE' and health['progress_index'] == 2


def test_integer_camera_upscale_and_centering():
    assert image_fit((320, 240), (0, 0, 680, 520)) == (20, 20, 640, 480)


def test_waiting_stale_and_timeout_are_not_reported_as_active():
    state = snapshot('WAIT_FOR_STATE')
    canvas, health = render(state, None, 10.0, 100.1, size=(1000, 800))
    assert canvas.shape == (800, 1000, 3)
    assert health['autonomy_status'] == 'STANDBY'
    state['mission']['state'] = 'TRANSIT'
    _, health = render(state, None, 11.0, 101.1)
    assert not health['state_live'] and not health['camera_live']
    assert not health['mission_status_live'] and health['autonomy_status'] == 'PAUSED'
    state['mission']['outcome'] = 'TIMEOUT'
    _, health = render(state, None, 11.0, 101.1)
    assert health['autonomy_status'] == 'TIMEOUT'


def test_plain_resizable_window_and_minimum_size():
    assert WINDOW_FLAGS & cv2.WINDOW_GUI_NORMAL
    assert WINDOW_FLAGS & cv2.WINDOW_FREERATIO
    assert not WINDOW_FLAGS & cv2.WINDOW_AUTOSIZE
    canvas, _ = render(snapshot(), None, 10.0, 100.1, size=(300, 200))
    assert canvas.shape == (540, 720, 3)


def test_engineering_defaults_and_presentation_only_window_sizes():
    assert window_profile() == {'stonefish': (1280, 720), 'gui': (1280, 880)}
    assert window_profile(True, (2560, 1600)) == {
        'stonefish': (1280, 720), 'gui': (1000, 800)}
    assert window_profile(True, (1920, 1080)) == {
        'stonefish': (1280, 720), 'gui': (928, 800)}


@pytest.mark.parametrize('presentation', [False, True])
def test_runner_forwards_presentation_option_without_changing_other_arguments(tmp_path, presentation):
    stub = tmp_path/'docker'
    stub.write_text('''#!/usr/bin/python3
import os,sys,json
args=sys.argv[1:]
if args[0]=='compose': print('existing-dev')
elif args[0]=='inspect': print('true')
elif args[0]=='exec':
 with open(os.environ['CAPTURE'],'w') as f: json.dump(args,f)
''')
    stub.chmod(0o755)
    capture = tmp_path/'args.json'
    runner = Path(__file__).resolve().parents[3]/'scripts/run_demo_v0.sh'
    args = ['bash', str(runner)] + (['--presentation'] if presentation else []) + ['auto_start:=false', 'gui:=true', '--show-args']
    env = dict(os.environ, PATH=str(tmp_path)+':'+os.environ['PATH'], CAPTURE=str(capture))
    subprocess.run(args, env=env, check=True, capture_output=True)
    received = json.loads(capture.read_text())
    assert ('presentation:=true' in received) == presentation
    assert received[-3:] == ['auto_start:=false', 'gui:=true', '--show-args']


def test_host_work_area_dimensions_apply_only_to_presentation(monkeypatch):
    monkeypatch.setenv('NEPTUNE_PRESENTATION_WIDTH', '1246')
    monkeypatch.setenv('NEPTUNE_PRESENTATION_HEIGHT', '1476')
    assert window_profile(True) == {'stonefish': (1280, 720), 'gui': (1246, 1476)}
    assert window_profile() == {'stonefish': (1280, 720), 'gui': (1280, 880)}


def test_presentation_removes_only_legacy_omni(tmp_path):
    import importlib.util
    import xml.etree.ElementTree as ET
    from neptune_sim.perception_profile import write_performance_scenario
    launch = Path(__file__).resolve().parents[1]/'launch/perception_demo.launch.py'
    spec = importlib.util.spec_from_file_location('presentation_launch', launch)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    scenario = write_performance_scenario(launch.parents[2]/'neptune_sim', tmp_path)
    demo._orient_demo_inspection(scenario)
    vehicle_path = ET.parse(scenario).find('include').get('file')
    expected = ET.parse(vehicle_path)
    robot = expected.find('robot')
    assert robot.find("light[@name='Omni']") is not None
    robot.remove(robot.find("light[@name='Omni']"))
    demo._remove_presentation_omni(scenario)
    assert ET.tostring(ET.parse(vehicle_path).getroot()) == ET.tostring(expected.getroot())
    assert len(robot.findall('light')) == 2


def test_presentation_keeps_native_manual_stonefish_view():
    launch = Path(__file__).resolve().parents[1]/'launch/perception_demo.launch.py'
    source = launch.read_text()
    assert 'presentation_view' not in source
    assert 'ExecuteProcess' not in source
    assert not (launch.parents[1]/'neptune_bringup/presentation_view.py').exists()


@pytest.mark.parametrize('desktop', [(1280, 720), (1920, 1080), (2560, 1600), (3840, 2160)])
def test_presentation_never_scales_renderer_to_desktop(desktop, monkeypatch):
    monkeypatch.setenv('NEPTUNE_PRESENTATION_WIDTH', '3200')
    monkeypatch.setenv('NEPTUNE_PRESENTATION_HEIGHT', '2000')
    assert window_profile(True, desktop)['stonefish'] == (1280, 720)
    assert window_profile(True)['stonefish'] == (1280, 720)


def test_windows_stonefish_placement_is_move_only():
    helper = Path(__file__).resolve().parents[3]/'scripts/demo_presentation_windows.ps1'
    source = helper.read_text()
    stonefish = source.split("if($name -eq 'Stonefish Simulator') {")[1].split('} else {')[0]
    assert '$placement.StonefishX,$placement.StonefishY,0,0,0x15' in stonefish
    assert 'ShowWindow(' not in stonefish
    assert 'SetForegroundWindow(' not in stonefish
    assert source.index("@('Stonefish Simulator','Project Neptune - Demo V0')") > 0


@pytest.mark.parametrize('presentation', [False, True])
def test_launch_constructs_baseline_stonefish_arguments_without_running(tmp_path, monkeypatch, presentation):
    import importlib.util
    from types import SimpleNamespace
    from launch import LaunchContext

    launch = Path(__file__).resolve().parents[1]/'launch/perception_demo.launch.py'
    spec = importlib.util.spec_from_file_location('safe_presentation_launch', launch)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    monkeypatch.setenv('NEPTUNE_PRESENTATION_WIDTH', '1246')
    monkeypatch.setenv('NEPTUNE_PRESENTATION_HEIGHT', '1476')
    monkeypatch.setattr(demo.subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout='D3D12 (NVIDIA) Accelerated: yes'))
    monkeypatch.setattr(demo, 'get_package_share_directory',
                        lambda _name: str(launch.parents[2]/'neptune_sim'))
    calls = []
    actual_node = demo.Node

    def record_node(**kwargs):
        calls.append(kwargs)
        return actual_node(**kwargs)  # Construct launch actions only; never execute.

    monkeypatch.setattr(demo, 'Node', record_node)
    context = LaunchContext()
    context.launch_configurations.update(simulation_data=str(tmp_path),
        presentation=str(presentation).lower(), auto_start='true', gui='true', evidence_directory='')
    actions = demo._start(context)
    simulator = next(call for call in calls if call['executable'] == 'stonefish_simulator')
    assert simulator['arguments'][2:] == ['100', '1280', '720', 'low']
    assert actions

"""Demo-only physical mounts and ROS optical axes must agree without changing optics."""

import ast
import importlib.util
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from neptune_sim.perception_profile import write_performance_scenario


LAUNCH = Path(__file__).resolve().parents[1] / 'launch/perception_demo.launch.py'
SPEC = importlib.util.spec_from_file_location('demo_orientation_launch', LAUNCH)
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


def rotate(rpy, vector):
    r, p, y = rpy
    x, v, z = vector
    v, z = math.cos(r)*v-math.sin(r)*z, math.sin(r)*v+math.cos(r)*z
    x, z = math.cos(p)*x+math.sin(p)*z, -math.sin(p)*x+math.cos(p)*z
    return math.cos(y)*x-math.sin(y)*v, math.sin(y)*x+math.cos(y)*v, z


def test_only_demo_camera_and_light_mounts_change(tmp_path):
    share = LAUNCH.parents[2] / 'neptune_sim'
    source = share / 'scenarios/neptune_girona_perception.scn'
    source_bytes = source.read_bytes()
    scenario = write_performance_scenario(share, tmp_path)
    vehicle_path = ET.parse(scenario).find('include').get('file')
    before = ET.parse(vehicle_path)
    DEMO._orient_demo_inspection(scenario)
    after = ET.parse(vehicle_path)
    for selector, expected_xyz in (
        ("sensor[@name='inspection_camera_optical_frame']", (-0.97, 0, 0.20)),
        ("light[@name='InspectionLightPort']", (-0.91, -0.24, 0.22)),
        ("light[@name='InspectionLightStarboard']", (-0.91, 0.24, 0.22)),
    ):
        old = before.find(f'robot/{selector}/origin')
        new = after.find(f'robot/{selector}/origin')
        rpy = tuple(map(float, new.get('rpy').split()))
        assert rotate(rpy, (0, 0, 1)) == pytest.approx((-1, 0, 0))
        assert rotate(rpy, (1, 0, 0)) == pytest.approx((0, -1, 0))
        assert rotate(rpy, (0, 1, 0)) == pytest.approx((0, 0, 1))
        xyz = tuple(map(float, new.get('xyz').split()))
        assert xyz == expected_xyz
        if selector.startswith('light'):
            specs = after.find(f'robot/{selector}/specs')
            old_specs = before.find(f'robot/{selector}/specs')
            assert specs.get('illuminance') == '1000.0'
            specs.set('illuminance', old_specs.get('illuminance'))
        new.set('rpy', old.get('rpy'))
        new.set('xyz', old.get('xyz'))
    assert ET.tostring(after.getroot()) == ET.tostring(before.getroot())
    assert source.read_bytes() == source_bytes


def test_demo_tf_composes_to_the_physical_optical_frame():
    arguments = {}
    for call in ast.walk(ast.parse(LAUNCH.read_text())):
        if not isinstance(call, ast.Call):
            continue
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        name = keywords.get('name')
        if isinstance(name, ast.Constant) and name.value in (
            'inspection_camera_mount_tf', 'inspection_camera_optical_tf',
        ):
            arguments[name.value] = ast.literal_eval(keywords['arguments'])
    def options(name):
        args = arguments[name]
        return dict(zip(args[::2], args[1::2]))
    mount = options('inspection_camera_mount_tf')
    optical = options('inspection_camera_optical_tf')
    assert tuple(float(mount[f'--{a}']) for a in ('x', 'y', 'z')) == (-0.97, 0, 0.20)
    assert mount['--frame-id'] == 'base_link'
    assert optical['--frame-id'] == mount['--child-frame-id'] == 'inspection_camera_link'
    assert optical['--child-frame-id'] == 'GIRONA500/inspection_camera_optical_frame'
    angles = lambda args: tuple(float(args.get('--'+a, 0)) for a in ('roll', 'pitch', 'yaw'))
    for local, expected in [((0, 0, 1), (-1, 0, 0)),
                            ((1, 0, 0), (0, -1, 0)),
                            ((0, 1, 0), (0, 0, 1))]:
        assert rotate(angles(mount), rotate(angles(optical), local)) == pytest.approx(expected)

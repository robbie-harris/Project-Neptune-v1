"""Performance optics change must preserve the demo and vehicle physics."""
from pathlib import Path
import xml.etree.ElementTree as ET

from neptune_sim.perception_profile import VISION_TYPES, write_performance_scenario


def test_alignment_optics_and_preservation(tmp_path):
    share = Path(__file__).resolve().parents[1]
    original = share/'scenarios/neptune_girona_perception.scn'
    original_bytes = original.read_bytes()
    source = ET.parse(original).find('robot')
    scene = ET.parse(write_performance_scenario(share, tmp_path))
    robot = ET.parse(scene.find('include').get('file')).find('robot')
    camera = robot.find("sensor[@name='inspection_camera_optical_frame']")
    assert camera.get('rate') == '10.0'
    assert camera.find('specs').attrib == {
        'resolution_x': '320', 'resolution_y': '240', 'horizontal_fov': '80.0'}
    assert ET.tostring(camera.find('ros_publisher')) == ET.tostring(
        source.find("sensor[@name='inspection_camera_optical_frame']/ros_publisher"))
    assert [s.get('name') for s in robot.findall('sensor') if s.get('type') in VISION_TYPES] == [
        'inspection_camera_optical_frame']
    assert [ET.tostring(a) for a in robot.findall('actuator')] == [
        ET.tostring(a) for a in source.findall('actuator')]
    assert ET.tostring(robot.find('base_link')) == ET.tostring(source.find('base_link'))
    assert robot.find('world_transform').attrib == source.find('world_transform').attrib
    assert original.read_bytes() == original_bytes
    assert source.find("sensor[@name='inspection_camera_optical_frame']/specs").get(
        'horizontal_fov') == '145.0'

"""Generate the optional P3 performance scene without duplicating demo assets."""

from pathlib import Path
import xml.etree.ElementTree as ET


VISION_TYPES = {
    'camera', 'depthcamera', 'thermalcamera', 'opticalflowcamera',
    'segmentationcamera', 'eventbasedcamera', 'multibeam2', 'fls', 'sss', 'msis',
}


def write_performance_scenario(package_share, output_directory):
    """Write a 320x240 inspection-only scene; retain original physics and spawn."""
    share = Path(package_share)
    output = Path(output_directory)
    scene = ET.parse(share / 'scenarios/benchmarks/03_port_pipe_perception.scn')
    vehicle = ET.parse(share / 'scenarios/neptune_girona_perception.scn')
    robot = vehicle.find('robot')
    camera = robot.find("sensor[@name='inspection_camera_optical_frame']")
    if camera is None or camera.get('type') != 'camera' or camera.get('rate') != '10.0':
        raise ValueError('Performance profile requires the existing 10 Hz inspection camera')
    specs = camera.find('specs')
    specs.set('resolution_x', '320')
    specs.set('resolution_y', '240')
    for sensor in list(robot.findall('sensor')):
        if sensor is not camera and sensor.get('type') in VISION_TYPES:
            robot.remove(sensor)
            continue
        # Match the validated reduced runtime: retained sensors start enabled.
        # No startup service call can be starved by the graphics executor.
        service = sensor.find('ros_service')
        if service is not None:
            sensor.remove(service)
    include = scene.find(
        "include[@file='$(find neptune_sim)/scenarios/neptune_girona_perception.scn']"
    )
    if include is None:
        raise ValueError('Performance profile requires the optional perception vehicle include')
    output.mkdir(parents=True, exist_ok=True)
    vehicle_path = output.resolve() / 'neptune_girona_performance.scn'
    scene_path = output.resolve() / '03_port_pipe_performance.scn'
    include.set('file', str(vehicle_path))
    vehicle.write(vehicle_path, encoding='utf-8', xml_declaration=True)
    scene.write(scene_path, encoding='utf-8', xml_declaration=True)
    return scene_path

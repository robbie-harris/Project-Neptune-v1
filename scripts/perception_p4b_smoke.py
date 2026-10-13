"""Bounded A1-only robust pipe smoke. No physical orientation or motion outputs."""

from collections import Counter
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
from urllib.request import build_opener, ProxyHandler
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory, get_package_prefix
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from neptune_sim.perception_profile import write_performance_scenario
from neptune_perception.core import A1_MODEL_ID, MODEL_ID
from perception_p4a_smoke import header_key, stop


def main():
    root = Path(tempfile.mkdtemp(prefix='neptune-p4b-smoke-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    scene = ET.parse(scenario)
    robot_path = Path(scene.find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'true')
    body.find('world_transform').set('xyz', '-18.5 0 3.0')
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    result = dict(model_id=A1_MODEL_ID, outcome='FAIL', resolution=[320, 240],
                  hfov_deg=145, orientation_valid=False, input='full frame',
                  scene='temporary fixed inspection pose')
    rclpy.init()
    node = rclpy.create_node('p4b_smoke_observer')
    camera_headers, detection_headers, annotated_headers = set(), set(), set()
    latest = None
    cold_latency = None
    measured = False
    cameras, outputs, latencies, ages = [], [], [], []
    observed, states = Counter(), Counter()
    errors = []
    last_result_header = None
    max_pending = max_in_flight = 0

    def camera(message):
        camera_headers.add(header_key(message.header))
        if measured:
            cameras.append(time.monotonic())
        if (message.width, message.height) != (320, 240):
            errors.append('camera dimensions')

    def detections(message):
        key = header_key(message.header)
        if key in detection_headers:
            errors.append('duplicate source detection array')
        detection_headers.add(key)
        if measured:
            outputs.append(time.monotonic())
        for detection in message.detections:
            if detection.header != message.header:
                errors.append('per detection header')
            for hypothesis in detection.results:
                observed[hypothesis.hypothesis.class_id] += 1

    def annotated(message):
        annotated_headers.add(header_key(message.header))
        if (message.width, message.height) != (320, 240):
            errors.append('annotated dimensions')

    def status(message):
        nonlocal latest, cold_latency, last_result_header, max_pending, max_in_flight
        latest = json.loads(message.data)
        states[latest['state']] += 1
        max_pending = max(max_pending, latest['pending_frames'])
        max_in_flight = max(max_in_flight, latest['in_flight'])
        if latest['model_id'] != A1_MODEL_ID or latest['orientation_valid'] is not False:
            errors.append('model or orientation contract')
        for observation in latest['observations']:
            if (observation['class_name'] != 'pipe'
                    or observation['orientation_valid'] is not False
                    or observation['orientation_rad'] is not None):
                errors.append('pipe or orientation contract')
        header = latest['source_header']
        key = None if header is None else (
            header['stamp']['sec'], header['stamp']['nanosec'], header['frame_id'])
        if latest['runtime'] is not None and cold_latency is None:
            cold_latency = latest['processing_latency_s']
            result['cold_start_state'] = latest['state']
        if (measured and key != last_result_header and latest['runtime'] is not None
                and latest['observation_valid']):
            latencies.append(latest['processing_latency_s'])
            ages.append(latest['observation_age_s'])
        last_result_header = key

    node.create_subscription(Image, '/neptune/camera/inspection/image_color', camera,
                             qos_profile_sensor_data)
    node.create_subscription(Detection2DArray, '/neptune/perception/orientation_a_detections', detections, 10)
    node.create_subscription(Image, '/neptune/perception/orientation_a_annotated', annotated, 10)
    node.create_subscription(String, '/neptune/perception/orientation_a_status', status, 10)
    simulator = detector = None
    simulator_log = (root/'simulator.log').open('w')
    detector_log = (root/'detector.log').open('w')

    def spin(duration):
        end = time.monotonic()+duration
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.02)
            if simulator is not None and simulator.poll() is not None:
                raise RuntimeError('Simulator exited')
            if detector is not None and detector.poll() is not None:
                raise RuntimeError('A1 observer exited')

    try:
        environment = dict(os.environ, GALLIUM_DRIVER='llvmpipe',
                           LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='8')
        simulator = subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low',
        ], env=environment, stdout=simulator_log, stderr=subprocess.STDOUT)
        executable = Path(get_package_prefix('neptune_perception'))/'lib/neptune_perception/orientation_a'
        detector = subprocess.Popen([str(executable)], stdout=detector_log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+125
        while not detection_headers or not annotated_headers or latest is None or latest['runtime'] is None:
            spin(0.1)
            if time.monotonic() >= deadline:
                raise RuntimeError('A1 camera/model/output deadline exceeded')
        result['runtime'] = latest['runtime']
        assert result['runtime']['cuda_node_events'] > 0
        assert 'CUDAExecutionProvider' in result['runtime']['providers']
        assert '4080' in result['runtime']['gpu_name']
        measured = True
        start = time.monotonic()
        spin(20)
        elapsed = time.monotonic()-start
        measured = False
        spin(0.2)
        assert not errors, errors
        assert detection_headers <= camera_headers and annotated_headers <= camera_headers
        assert detection_headers == annotated_headers, 'Unpaired source headers'
        assert set(observed) <= {'pipe'}
        assert latencies and outputs, 'No warm valid observations'
        assert max_pending <= 1 and max_in_flight <= 1
        forbidden_topics = ('/neptune/cmd_body', '/sim/thruster_setpoints',
                            '/neptune/perception/object_detections',
                            '/neptune/perception/annotated', '/neptune/perception/status')
        publishers = {topic: node.count_publishers(topic) for topic in forbidden_topics}
        assert all(count == 0 for count in publishers.values()), publishers
        ordered = sorted(latencies)
        result.update(
            outcome='PASS' if observed else 'RUNTIME_PASS_NO_DETECTIONS',
            cold_start_latency_s=cold_latency, measured_window_s=elapsed,
            camera_frames=len(cameras), camera_fps=len(cameras)/elapsed,
            processed_frames=len(outputs), processed_fps=len(outputs)/elapsed,
            latency_s=dict(count=len(latencies), mean=statistics.mean(latencies),
                           median=statistics.median(latencies),
                           p95=ordered[int(0.95*(len(ordered)-1))], maximum=max(latencies)),
            observation_age_s=dict(mean=statistics.mean(ages), maximum=max(ages)),
            observed_class_counts=dict(observed), source_headers_preserved=True,
            paired_headers=len(detection_headers), max_pending_frames=max_pending,
            max_in_flight_requests=max_in_flight, last_warm_status=latest,
            forbidden_publisher_counts=publishers)
        stop(simulator)
        simulator = None
        spin(0.8)
        assert latest['state'] == 'CAMERA_STALE' and not latest['observation_valid']
        result['camera_loss_status'] = latest['state']
        result['status_states'] = dict(states)
        opener = build_opener(ProxyHandler({}))
        with opener.open('http://127.0.0.1:9001/health/orientation_a', timeout=2) as reply:
            result['a1_server_health'] = json.load(reply)
        with opener.open('http://127.0.0.1:9001/health', timeout=2) as reply:
            p4a = json.load(reply)
            assert p4a['model_id'] == MODEL_ID
            assert p4a['runtime'] is None, 'P4a was unexpectedly exercised'
            result['p4a_session_not_exercised'] = True
    except Exception as error:
        result.update(outcome='FAIL', reason=str(error), last_status=latest)
    finally:
        stop(detector)
        stop(simulator)
        simulator_log.close()
        detector_log.close()
        node.destroy_node()
        rclpy.shutdown()
        (root/'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(dict(evidence_directory=str(root), **result), indent=2), flush=True)
    return 0 if result['outcome'] in ('PASS', 'RUNTIME_PASS_NO_DETECTIONS') else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""One bounded, fixed-pose observation smoke; no mission or actuator publisher.

Run inside the ROS dev container with installed P3/P4a overlays. The host runner
owns the inference container. Evidence contains only public model/runtime data.
"""

from collections import Counter
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory, get_package_prefix
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from neptune_sim.perception_profile import write_performance_scenario
from neptune_perception.core import MODEL_ID


def header_key(header):
    return header.stamp.sec, header.stamp.nanosec, header.frame_id


def stop(process):
    if process is None or process.poll() is not None:
        return
    for sig, wait in [(signal.SIGINT, 3), (signal.SIGTERM, 2), (signal.SIGKILL, 2)]:
        process.send_signal(sig)
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            pass
    raise RuntimeError('Owned process cleanup failed')


def main():
    root = Path(tempfile.mkdtemp(prefix='neptune-p4a-smoke-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    scene = ET.parse(scenario)
    robot_path = Path(scene.find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'true')
    body.find('world_transform').set('xyz', '-18.5 0 3.0')
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    result = dict(model_id=MODEL_ID, outcome='FAIL', scene='temporary fixed inspection pose',
                  resolution=[320, 240], hfov_deg=145, measurement_window_s=20)
    rclpy.init()
    node = rclpy.create_node('p4a_smoke_observer')
    camera_headers, detection_headers, annotated_headers = set(), set(), set()
    latest_status = None
    camera_samples, result_samples, latencies, ages = [], [], [], []
    observed = Counter()
    states = Counter()
    max_pending = max_in_flight = 0
    measurement = False
    matched_result_count = 0
    malformed = []

    def camera(message):
        camera_headers.add(header_key(message.header))
        if measurement:
            camera_samples.append(time.monotonic())
        if (message.width, message.height) != (320, 240):
            malformed.append('camera resolution')

    def detections(message):
        detection_headers.add(header_key(message.header))
        if measurement:
            result_samples.append(time.monotonic())
        for detection in message.detections:
            if detection.header != message.header:
                malformed.append('per detection header')
            for hypothesis in detection.results:
                observed[hypothesis.hypothesis.class_id] += 1

    def annotated(message):
        annotated_headers.add(header_key(message.header))
        if (message.width, message.height) != (320, 240):
            malformed.append('annotated resolution')

    status_result_stamp = None

    def status(message):
        nonlocal latest_status, status_result_stamp, max_pending, max_in_flight
        latest_status = json.loads(message.data)
        max_pending = max(max_pending, latest_status['pending_frames'])
        max_in_flight = max(max_in_flight, latest_status['in_flight'])
        states[latest_status['state']] += 1
        header = latest_status['source_header']
        stamp = None if header is None else (header['stamp']['sec'], header['stamp']['nanosec'])
        if measurement and stamp != status_result_stamp and latest_status['runtime'] is not None:
            if latest_status['processing_latency_s'] is not None:
                latencies.append(latest_status['processing_latency_s'])
                ages.append(latest_status['observation_age_s'])
        status_result_stamp = stamp

    node.create_subscription(Image, '/neptune/camera/inspection/image_color', camera,
                             qos_profile_sensor_data)
    node.create_subscription(Detection2DArray, '/neptune/perception/object_detections', detections, 10)
    node.create_subscription(Image, '/neptune/perception/annotated', annotated, 10)
    node.create_subscription(String, '/neptune/perception/status', status, 10)
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
                raise RuntimeError('Detector exited')

    try:
        environment = dict(os.environ, GALLIUM_DRIVER='llvmpipe',
                           LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='8')
        simulator = subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low',
        ], env=environment, stdout=simulator_log, stderr=subprocess.STDOUT)
        executable = Path(get_package_prefix('neptune_perception'))/'lib/neptune_perception/inspection_objects'
        detector = subprocess.Popen([str(executable)], stdout=detector_log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+125
        while not detection_headers or latest_status is None or latest_status['runtime'] is None:
            spin(0.1)
            if time.monotonic() >= deadline:
                result['last_status'] = latest_status
                raise RuntimeError('Model/runtime or camera-to-detections deadline exceeded')
        result['cold_start_latency_s'] = latest_status['processing_latency_s']
        result['runtime'] = latest_status['runtime']
        assert latest_status['model_id'] == MODEL_ID
        assert result['runtime']['cuda_node_events'] > 0
        assert 'CUDAExecutionProvider' in result['runtime']['providers']
        assert '4080' in result['runtime']['gpu_name']
        camera_samples.clear()
        result_samples.clear()
        measurement = True
        start = time.monotonic()
        spin(20)
        elapsed = time.monotonic()-start
        measurement = False
        # Drain output to allow paired annotated messages to arrive.
        spin(0.2)
        matched = detection_headers & annotated_headers
        assert detection_headers <= camera_headers, 'Detection source header mismatch'
        assert annotated_headers <= camera_headers, 'Annotated source header mismatch'
        assert matched, 'No paired outputs'
        assert not malformed, malformed
        assert set(observed) <= {'pipe', 'valve', 'flange'}
        assert max_pending <= 1 and max_in_flight <= 1
        command_publishers = node.count_publishers('/neptune/cmd_body')
        motor_publishers = node.count_publishers('/sim/thruster_setpoints')
        assert command_publishers == motor_publishers == 0
        sorted_latencies = sorted(latencies)
        result.update(
            outcome='PASS' if observed else 'RUNTIME_PASS_NO_DETECTIONS',
            measured_window_s=elapsed, camera_frames=len(camera_samples),
            camera_fps=len(camera_samples)/elapsed,
            processed_frames=len(result_samples), processed_fps=len(result_samples)/elapsed,
            latency_s=dict(count=len(latencies), mean=statistics.mean(latencies),
                           median=statistics.median(latencies),
                           p95=sorted_latencies[int(0.95*(len(sorted_latencies)-1))],
                           maximum=max(latencies)),
            observation_age_s=dict(mean=statistics.mean(ages), maximum=max(ages)),
            observed_class_counts=dict(observed), status_states=dict(states),
            paired_headers=len(matched), source_headers_preserved=True,
            max_pending_frames=max_pending, max_in_flight_requests=max_in_flight,
            last_status=latest_status,
            command_publishers=command_publishers, thruster_publishers=motor_publishers,
        )
        # Stop only this owned simulator, then observe the live silence watchdog.
        stop(simulator)
        simulator = None
        spin(0.8)
        assert latest_status['state'] == 'CAMERA_STALE', latest_status['state']
        assert not latest_status['observation_valid']
        result['camera_loss_status'] = latest_status['state']
    except Exception as error:
        result['outcome'] = 'FAIL'
        result['reason'] = str(error)  # this process has no credential or upstream response
        result['last_status'] = latest_status
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

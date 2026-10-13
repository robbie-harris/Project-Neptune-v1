"""One 20-second dual-model warm GPU window, no commands or mission."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from urllib.request import build_opener, ProxyHandler

from ament_index_python.packages import get_package_share_directory, get_package_prefix
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
from neptune_sim.perception_profile import write_performance_scenario
from neptune_perception.fusion import MODELS
from perception_p4a_smoke import stop, header_key


def stats(values):
    if not values:
        return dict(count=0, mean=None, median=None, p95=None, minimum=None, maximum=None)
    ordered = sorted(values)
    return dict(count=len(values), mean=statistics.mean(values), median=statistics.median(values),
                p95=ordered[int(0.95*(len(ordered)-1))], minimum=min(values), maximum=max(values))


def key(status):
    h = status['source_header']
    return None if h is None else (h['stamp']['sec'], h['stamp']['nanosec'], h['frame_id'])


def main():
    root = Path(tempfile.mkdtemp(prefix='neptune-p4c-smoke-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    scene = ET.parse(scenario)
    robot_path = Path(scene.find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'true')
    body.find('world_transform').set('xyz', '-18.5 0 3.0')
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    result = dict(outcome='FAIL', scheduling=dict(inspection=1, orientation_a=1),
                  model_ids=MODELS, resolution=[320, 240], hfov_deg=145)
    rclpy.init()
    node = rclpy.create_node('p4c_smoke_observer')
    measured = False
    camera_headers, warm_camera = set(), set()
    headers = {m: set() for m in MODELS}
    warm_headers = {m: set() for m in MODELS}
    latest, baseline = {}, {}
    seen = {m: set() for m in MODELS}
    latencies = {m: [] for m in MODELS}
    stale = Counter()
    max_pending, max_flight = Counter(), Counter()
    fused, selected, ious, ages = [], [], [], []
    states, semantic_counts = Counter(), Counter()
    sequences = set()
    latest_fusion = None
    errors = []
    processes, logs = [], []
    simulator = None

    def camera(message):
        camera_headers.add(header_key(message.header))
        if measured:
            warm_camera.add(header_key(message.header))
        if (message.width, message.height) != (320, 240):
            errors.append('camera dimensions')

    def detections(model, message):
        h = header_key(message.header)
        if h in headers[model]:
            errors.append('duplicate model source')
        headers[model].add(h)
        if measured:
            warm_headers[model].add(h)
        if any(d.header != message.header for d in message.detections):
            errors.append('detection header')

    def status(model, message):
        s = json.loads(message.data)
        latest[model] = s
        max_pending[model] = max(max_pending[model], s['pending_frames'])
        max_flight[model] = max(max_flight[model], s['in_flight'])
        if s['model_id'] != MODELS[model] or s['orientation_valid'] is not False:
            errors.append('model/orientation')
        h = key(s)
        if h is not None and h not in seen[model] and s['processing_latency_s'] is not None:
            seen[model].add(h)
            if measured:
                latencies[model].append(s['processing_latency_s'])
                if not s['observation_valid']:
                    stale[model] += 1

    def fusion(message):
        nonlocal latest_fusion
        s = json.loads(message.data)
        latest_fusion = s
        if s['orientation_valid'] is not False:
            errors.append('fused orientation')
        if s['pending_frames'] > s['cache_capacity']:
            errors.append('cache bound')
        if s['sequence'] in sequences or not s['sequence']:
            return
        sequences.add(s['sequence'])
        if not measured:
            return
        fused.append(s)
        states[s['state']] += 1
        if s['valid']:
            selected.append(s)
            ages.append(s['observation_age_s'])
            if not 0 <= s['observation_age_s'] <= 0.5:
                errors.append('stale valid selection')
        for p in s['pipes']:
            if p['iou'] is not None:
                ious.append(p['iou'])
            if p['orientation_valid'] is not False:
                errors.append('pipe orientation')
        for o in s['semantic_detections']:
            semantic_counts[o['class_name']] += 1
            if o['model_id'] != MODELS['inspection']:
                errors.append('semantic provenance')

    node.create_subscription(Image, '/neptune/camera/inspection/image_color', camera, qos_profile_sensor_data)
    for model, topic in [('inspection', '/neptune/perception/status'),
                         ('orientation_a', '/neptune/perception/orientation_a_status')]:
        node.create_subscription(String, topic, lambda m, model=model: status(model, m), 10)
    for model, topic in [('inspection', '/neptune/perception/object_detections'),
                         ('orientation_a', '/neptune/perception/orientation_a_detections')]:
        node.create_subscription(Detection2DArray, topic, lambda m, model=model: detections(model, m), 10)
    node.create_subscription(String, '/neptune/perception/fused_status', fusion, 10)

    def spin(duration):
        deadline = time.monotonic()+duration
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.01)
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Owned observer exited')
            if simulator is not None and simulator.poll() is not None:
                raise RuntimeError('Simulator exited')

    try:
        log = (root/'simulator.log').open('w')
        logs.append(log)
        simulator = subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low'],
            env=dict(os.environ, GALLIUM_DRIVER='llvmpipe', LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='8'),
            stdout=log, stderr=subprocess.STDOUT)
        prefix = Path(get_package_prefix('neptune_perception'))/'lib/neptune_perception'
        for executable in ['inspection_objects', 'orientation_a', 'pipe_fusion']:
            log = (root/f'{executable}.log').open('w')
            logs.append(log)
            processes.append(subprocess.Popen([str(prefix/executable)], stdout=log, stderr=subprocess.STDOUT))
        deadline = time.monotonic()+125
        while not (len(latest) == 2 and all(s['observation_valid'] and s['runtime'] is not None
                                          for s in latest.values())
                   and latest_fusion is not None and latest_fusion.get('source_matched')):
            spin(0.1)
            if time.monotonic() >= deadline:
                raise RuntimeError('Dual model warmup deadline')
        baseline = deepcopy(latest)
        measured = True
        start = time.monotonic()
        spin(20)
        elapsed = time.monotonic()-start
        measured = False
        warm_end = deepcopy(latest)
        spin(0.2)
        assert not errors, errors
        assert all(headers[m] <= camera_headers for m in MODELS)
        assert all(key(s) in camera_headers for s in fused)
        for s in fused:
            if s['source_matched']:
                assert all(key(s) in headers[m] for m in MODELS), 'Cross-frame fusion'
        assert all(max_pending[m] <= 1 and max_flight[m] <= 1 for m in MODELS)
        assert node.count_publishers('/neptune/cmd_body') == node.count_publishers('/sim/thruster_setpoints') == 0
        result.update(measured_window_s=elapsed, camera_frames=len(warm_camera), camera_fps=len(warm_camera)/elapsed)
        for model in MODELS:
            runtime = latest[model]['runtime']
            assert 'CUDAExecutionProvider' in runtime['providers'] and runtime['cuda_node_events'] > 0
            result[model] = dict(processed_frames=len(warm_headers[model]),
                processed_fps=len(warm_headers[model])/elapsed, latency_s=stats(latencies[model]),
                warm_replacements=warm_end[model]['replaced_frames']-baseline[model]['replaced_frames'],
                total_replacements=warm_end[model]['replaced_frames'], warm_stale_completions=stale[model],
                rejected_stale_results=warm_end[model].get('rejected_stale_results'),
                max_pending=max_pending[model], max_in_flight=max_flight[model], runtime=runtime,
                pending_at_start=baseline[model]['pending_frames'], pending_at_end=warm_end[model]['pending_frames'])
        matched = sum(s['source_matched'] for s in fused)
        result['fusion'] = dict(output_frames=len(fused), output_fps=len(fused)/elapsed,
            selected_target_frames=len(selected), selected_target_fps=len(selected)/elapsed,
            state_counts={state: states[state] for state in ['CONSENSUS', 'INSPECTION_ONLY',
                'ORIENTATION_A_ONLY', 'AMBIGUOUS', 'NO_PIPE', 'STALE', 'MODEL_UNAVAILABLE']},
            source_matched_frames=matched, source_match_rate=matched/len(fused) if fused else 0,
            source_match_camera_rate=matched/len(warm_camera) if warm_camera else 0,
            iou=stats(ious), age_s=stats(ages), semantic_counts=dict(semantic_counts), last_status=latest_fusion)
        opener = build_opener(ProxyHandler({}))
        for model, route in [('inspection', '/health'), ('orientation_a', '/health/orientation_a')]:
            with opener.open('http://127.0.0.1:9001'+route, timeout=2) as response:
                result[model]['server_health'] = json.load(response)
        stop(simulator)
        simulator = None
        spin(0.8)
        assert latest_fusion['valid'] is False, 'Selection remained valid after camera loss'
        result['camera_loss_fused_state'] = latest_fusion['state']
        result['outcome'] = 'PASS' if len(selected)/elapsed >= 4 else 'RATE_FAIL'
        result['orientation_valid'] = False
        result['command_publishers'] = result['thruster_publishers'] = 0
    except Exception as error:
        result.update(outcome='FAIL', reason=str(error), latest=latest, latest_fusion=latest_fusion)
    finally:
        for process in reversed(processes):
            stop(process)
        stop(simulator)
        result['owned_processes_exited'] = all(p.poll() is not None for p in processes)
        for log in logs:
            log.close()
        node.destroy_node()
        rclpy.shutdown()
        (root/'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(dict(evidence_directory=str(root), **result), indent=2), flush=True)
    return 0 if result['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Bounded 80-degree P4 regression, median sign calibration or P5a centering."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import statistics
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_prefix, get_package_share_directory
import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
import rclpy
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
import yaml

from neptune_evaluation.lateral_motion import LateralMotionEvaluation
from neptune_sim.perception_profile import write_performance_scenario
from perception_p4a_smoke import header_key, stop


def medians(samples):
    return {'error': statistics.median(s['selected_target']['horizontal_error'] for s in samples),
            'center_x': statistics.median(s['selected_target']['center'][0] for s in samples),
            'source_stamps': [s['source_header']['stamp'] for s in samples]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['regression', 'diagnostic', 'sign', 'closed'])
    parser.add_argument('--pose', nargs=3, type=float, default=[-16.0, 0.8, 3.0])
    args = parser.parse_args()
    config = Path(get_package_share_directory('neptune_controls'))/'config/pipe_centering.yaml'
    parameters = yaml.safe_load(config.read_text())['pipe_centering']['ros__parameters']
    if args.mode == 'closed' and parameters['sway_sign'] not in (-1, 1):
        raise RuntimeError('Closed loop requires an experimentally established sway_sign')
    root = Path(tempfile.mkdtemp(prefix='neptune-p5a-80-'+args.mode+'-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    robot_path = Path(ET.parse(scenario).find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'true')
    body.find('world_transform').set('xyz', ' '.join(map(str, args.pose)))
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal.default_int_handler)
    node = rclpy.create_node('p5a_smoke_observer')
    evaluation = LateralMotionEvaluation(node)
    processes, logs = [], []
    latest, images = {}, {}
    camera_headers = set()
    model_headers = {'inspection': set(), 'orientation_a': set()}
    detector_status = {}
    camera_times, model_events, fused_status_samples = [], [], []
    all_observations, measured_observations, commands, statuses, transitions = [], [], [], [], []
    fresh_streak, last_sequence, invalid_generation = 0, None, 0
    last_invalid_time = float('-inf')
    active, start = False, None
    result = {'mode': args.mode, 'outcome': 'FAIL', 'pose': args.pose,
              'resolution': [320, 240], 'hfov_deg': 80, 'truth_evaluation_only': True,
              'controller_parameters': parameters}
    pub = controller = None

    def fresh(s):
        h = s.get('source_header')
        if not h or not s.get('valid') or s.get('state') not in (
                'CONSENSUS', 'INSPECTION_ONLY', 'ORIENTATION_A_ONLY'):
            return False
        source_age = node.get_clock().now().nanoseconds/1e9-(h['stamp']['sec']+h['stamp']['nanosec']/1e9)
        return 0 <= source_age < 0.3 and 0 <= s['observation_age_s'] < 0.3 and s['receipt_age_s'] < 0.3

    def fused(message):
        nonlocal fresh_streak, last_sequence, invalid_generation, last_invalid_time
        s = json.loads(message.data)
        latest['fused'] = s
        if active:
            fused_status_samples.append((time.monotonic()-start, s))
        if not s.get('valid'):
            fresh_streak = 0
            invalid_generation += 1
            last_invalid_time = time.monotonic()
        if s['sequence'] != last_sequence:
            last_sequence = s['sequence']
            all_observations.append((time.monotonic(), s))
            fresh_streak = fresh_streak+1 if fresh(s) else 0
            if active:
                measured_observations.append((time.monotonic()-start, s))
        if active and (not transitions or s['state'] != transitions[-1][1]):
            transitions.append((time.monotonic()-start, s['state']))

    def cmd(message):
        if active:
            commands.append((time.monotonic()-start, [message.linear.x, message.linear.y,
                message.linear.z, message.angular.x, message.angular.y, message.angular.z]))

    def alignment(message):
        s = json.loads(message.data)
        latest['alignment'] = s
        if active:
            statuses.append((time.monotonic()-start, s))

    def image(message):
        images[header_key(message.header)[:2]] = message
        while len(images) > 100:
            del images[next(iter(images))]

    def camera(message):
        camera_headers.add(header_key(message.header))
        if active:
            camera_times.append(time.monotonic()-start)

    def camera_info(message):
        latest['camera_info'] = {'width': message.width, 'height': message.height,
            'frame_id': message.header.frame_id, 'k': list(message.k), 'p': list(message.p),
            'd': list(message.d), 'distortion_model': message.distortion_model}

    node.create_subscription(String, '/neptune/perception/fused_status', fused, 10)
    node.create_subscription(Twist, '/neptune/cmd_body', cmd, 10)
    node.create_subscription(String, '/neptune/control/alignment_status', alignment, 10)
    node.create_subscription(Image, '/neptune/perception/annotated', image, 10)
    node.create_subscription(Image, '/neptune/camera/inspection/image_color', camera, 10)
    node.create_subscription(CameraInfo, '/neptune/camera/inspection/camera_info', camera_info, 10)
    for model, topic in [('inspection', '/neptune/perception/object_detections'),
                         ('orientation_a', '/neptune/perception/orientation_a_detections')]:
        node.create_subscription(Detection2DArray, topic,
            lambda m, model=model: model_headers[model].add(header_key(m.header)), 10)
    def detector_status_received(model, message):
        s = json.loads(message.data)
        detector_status[model] = s
        if active:
            model_events.append((time.monotonic()-start, model, s))

    for model, topic in [('inspection', '/neptune/perception/status'),
                         ('orientation_a', '/neptune/perception/orientation_a_status')]:
        node.create_subscription(String, topic,
            lambda m, model=model: detector_status_received(model, m), 10)

    def launch(package, executable, extra=()):
        log = (root/(executable+'.log')).open('w')
        logs.append(log)
        path = Path(get_package_prefix(package))/'lib'/package/executable
        p = subprocess.Popen([str(path), *extra], stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        return p

    def spin(duration):
        end = time.monotonic()+duration
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=min(0.01, max(0, end-time.monotonic())))
            if active and node.count_publishers('/neptune/cmd_body') > 1:
                raise RuntimeError('Competing body command publisher')
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Owned process exited')

    def wait(predicate, seconds, label):
        end = time.monotonic()+seconds
        while not predicate():
            spin(0.02)
            if time.monotonic() >= end:
                raise RuntimeError('Deadline: '+label)

    def collect(count=5, seconds=15):
        mark = len(all_observations)
        samples = []
        last_time = None
        generation = invalid_generation
        deadline = time.monotonic()+seconds
        while len(samples) < count:
            spin(0.02)
            new = all_observations[mark:]
            mark = len(all_observations)
            if invalid_generation != generation:
                samples.clear()
                last_time = None
                generation = invalid_generation
            for receipt, s in new:
                if receipt <= last_invalid_time:
                    continue
                if last_time is not None and receipt-last_time > 0.5:
                    samples.clear()
                last_time = receipt
                if fresh(s):
                    samples.append(s)
                else:
                    samples.clear()
            if time.monotonic() >= deadline:
                raise RuntimeError('Five fresh observation deadline')
        return samples[-count:]

    def save_frame(label, s):
        h = s['source_header']['stamp']
        m = images.get((h['sec'], h['nanosec']))
        if m is None:
            return
        frame = CvBridge().imgmsg_to_cv2(m, desired_encoding='bgr8')
        u, v = s['selected_target']['center']
        cv2.line(frame, (160, 0), (160, 239), (255, 255, 255), 1)
        cv2.circle(frame, (round(u), round(v)), 4, (0, 0, 255), 2)
        cv2.imwrite(str(root/(label+'.png')), frame)

    def start_simulator(label):
        log = (root/(label+'.log')).open('w')
        logs.append(log)
        p = subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low'],
            env=dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='8'),
            stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        return p

    try:
        assert node.count_publishers('/neptune/cmd_body') == 0
        simulator = start_simulator('fixed_simulator')
        for executable in ['inspection_objects', 'orientation_a', 'pipe_fusion']:
            launch('neptune_perception', executable)
        if args.mode == 'diagnostic':
            launch('neptune_vehicle', 'stonefish_adapter', ['--ros-args', '-p', 'motor_count:=7'])
            controller = launch('neptune_controls', 'pipe_centering', [
                '--ros-args', '--params-file', str(config), '-p', 'sway_sign:=0.0', '-r',
                '/neptune/control/alignment_cmd_body:=/neptune/cmd_body'])
        print('Fixed 80-degree perception warmup', flush=True)
        wait(lambda: fresh_streak >= 3, 125, 'three fresh observations')
        warm_start = time.monotonic()
        warm_mark = len(all_observations)
        spin(3)
        warm = [s for _, s in all_observations[warm_mark:]]
        valid = [s for s in warm if s['valid']]
        assert len(valid) >= 5, 'Insufficient short warm regression outputs'
        assert all(s['source_matched'] for s in valid), 'Exact association missing'
        spin(0.1)
        assert all((s['source_header']['stamp']['sec'], s['source_header']['stamp']['nanosec'],
            s['source_header']['frame_id']) in camera_headers & model_headers['inspection'] &
            model_headers['orientation_a'] for s in valid), 'Cross-frame association'
        assert all(s['pending_frames'] <= 1 and s['in_flight'] <= 1
                   and s['runtime']['cuda_node_events'] > 0 for s in detector_status.values())
        assert set(detector_status) == {'inspection', 'orientation_a'}
        result['camera_info'] = latest['camera_info']
        assert result['camera_info']['width'] == 320 and result['camera_info']['height'] == 240
        assert 190 < result['camera_info']['k'][0] < 192, 'Actual focal length inconsistent with 80 degrees'
        result['regression'] = {'valid_selected': len(valid), 'window_s': time.monotonic()-warm_start,
            'states': dict(Counter(s['state'] for s in warm)), 'source_matching': True,
            'medians': medians(valid), 'max_pending': max(s['pending_frames'] for s in detector_status.values()),
            'semantic_counts': dict(Counter(o['class_name'] for s in valid for o in s['semantic_detections']))}
        print('Perception regression: '+json.dumps(result['regression']), flush=True)
        if args.mode == 'diagnostic':
            def cpu_snapshot():
                snapshot = {}
                for process in processes:
                    stat = Path(f'/proc/{process.pid}/stat').read_text().split(') ')[1].split()
                    snapshot[str(process.pid)] = (int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK')
                return snapshot

            cpu_before = cpu_snapshot()
            counters_before = json.loads(json.dumps(detector_status))
            start = time.monotonic()
            active = True
            print('DIAGNOSTIC_WINDOW_STARTED', flush=True)
            spin(12)
            duration = time.monotonic()-start
            cpu_after = cpu_snapshot()
            active = False
            fresh_outputs = [(t, s) for t, s in measured_observations if s['valid']]
            times = [t for t, _ in fresh_outputs]
            gaps = [b-a for a, b in zip(times, times[1:])]
            gaps += [times[0], duration-times[-1]] if times else [duration]
            max_age = max((s['observation_age_s'] for _, s in fused_status_samples if s['valid']), default=None)
            metrics = {'duration_s': duration, 'camera_fps': len(camera_times)/duration,
                'camera_max_gap_s': max((b-a for a, b in zip(camera_times, camera_times[1:])), default=None),
                'fused_valid_fps': len(fresh_outputs)/duration, 'fused_valid_max_gap_s': max(gaps),
                'max_selected_target_age_s': max_age,
                'max_new_selected_target_age_s': max((s['observation_age_s'] for _, s in fresh_outputs), default=None),
                'controller_callback_hz': len(statuses)/duration,
                'cpu_percent_one_core': {pid: 100*(cpu_after[pid]-value)/duration
                    for pid, value in cpu_before.items()},
                'processes': {str(p.pid): p.args[0] for p in processes},
                'rss_kib': {str(p.pid): int(next(line.split()[1] for line in
                    Path(f'/proc/{p.pid}/status').read_text().splitlines() if line.startswith('VmRSS:')))
                    for p in processes}}
            for model in ('inspection', 'orientation_a'):
                events = [s for _, m, s in model_events if m == model]
                unique = {}
                for s in events:
                    if s.get('source_header') and s.get('processing_latency_s') is not None:
                        h = s['source_header']['stamp']
                        unique.setdefault((h['sec'], h['nanosec']), s)
                latency = [s['processing_latency_s'] for s in unique.values()]
                end_status = detector_status[model]
                baseline = counters_before[model]
                metrics[model] = {
                    'processed_fps': (end_status['processed_frames']-baseline['processed_frames'])/duration,
                    'latency_mean_s': statistics.mean(latency) if latency else None,
                    'latency_max_s': max(latency) if latency else None,
                    'max_pending': max(s['pending_frames'] for s in events),
                    'max_in_flight': max(s['in_flight'] for s in events),
                    'replacements': end_status['replaced_frames']-baseline['replaced_frames'],
                    'stale_completions': sum(not s['observation_valid'] for s in unique.values()),
                    'rejected_stale_delta': end_status.get('rejected_stale_results', 0)-baseline.get('rejected_stale_results', 0),
                    'last_status': end_status}
            metrics['stable'] = (metrics['fused_valid_fps'] >= 4 and metrics['fused_valid_max_gap_s'] < 0.5
                                and max_age is not None and max_age < 0.5)
            metrics['commands_all_zero'] = bool(commands) and all(c == [0]*6 for _, c in commands)
            metrics['fixed_vehicle'] = True
            result['diagnostic'] = metrics
            result['diagnostic_raw'] = {'camera_receipts': camera_times, 'model_events': model_events,
                                       'fusion_status': fused_status_samples}
            result['outcome'] = 'PASS' if metrics['stable'] and metrics['commands_all_zero'] else 'FAIL'
            if not metrics['stable']:
                result['reason'] = 'Integrated no-motion freshness gates failed'
        elif args.mode == 'regression':
            save_frame('regression', valid[-1])
            result['outcome'] = 'PASS'
        else:
            stop(simulator)
            processes.remove(simulator)
            body.set('fixed', 'false')
            robot.write(robot_path)
            fresh_streak = 0
            launch('neptune_vehicle', 'stonefish_adapter', ['--ros-args', '-p', 'motor_count:=7'])
            start_simulator('dynamic_simulator')
            print('Dynamic-pose fresh warmup', flush=True)
            wait(lambda: fresh_streak >= 3, 45, 'dynamic three fresh observations')
            if args.mode == 'sign':
                pub = node.create_publisher(Twist, '/neptune/cmd_body', 1)
                wait(lambda: pub.get_subscription_count() >= 2, 5, 'adapter discovery')
            before_samples = collect()
            before = medians(before_samples)
            result['before'] = before
            assert 0.15 <= abs(before['error']) <= 0.30, 'Initial error outside requested range'
            save_frame('before', before_samples[-1])
            start = time.monotonic()
            active = True
            evaluation.begin()
            if args.mode == 'sign':
                pulse_start = time.monotonic()
                while time.monotonic()-pulse_start < 4.0:
                    target_status = latest['fused']
                    h = target_status['source_header']['stamp']
                    age = node.get_clock().now().nanoseconds/1e9-(h['sec']+h['nanosec']/1e9)
                    if not target_status['valid'] or not 0 <= age <= 0.5:
                        pub.publish(Twist())
                        result.update(pulse_magnitude=0.25,
                                      pulse_duration_s=time.monotonic()-pulse_start)
                        raise RuntimeError('Fused target stale/lost during calibration pulse')
                    m = Twist()
                    m.linear.y = 0.25
                    pub.publish(m)
                    spin(min(0.05, max(0, 4.0-(time.monotonic()-pulse_start))))
                pub.publish(Twist())
                result.update(pulse_magnitude=0.25, pulse_duration_s=time.monotonic()-pulse_start)
                spin(0.5)
                after_samples = collect()
                after = medians(after_samples)
                result['after'] = after
                result['error_change'] = after['error']-before['error']
                save_frame('after', after_samples[-1])
                assert abs(result['error_change']) >= 0.01, 'Median sign response too small'
                result['derived_controller_sign'] = -1 if result['error_change'] > 0 else 1
            else:
                controller = launch('neptune_controls', 'pipe_centering', [
                    '--ros-args', '--params-file', str(config), '-r',
                    '/neptune/control/alignment_cmd_body:=/neptune/cmd_body'])
                wait(lambda: latest.get('alignment', {}).get('state') == 'ALIGNED', 30, 'alignment')
                result['time_to_alignment_s'] = time.monotonic()-start
                # Confirm live hold over three further distinct fresh source frames.
                after_samples = collect(count=3)
                assert all(abs(s['selected_target']['horizontal_error']) <= 0.05 for s in after_samples)
                assert latest['alignment']['state'] == 'ALIGNED'
                assert latest['alignment']['sway_command'] == 0
                result['after'] = medians(after_samples)
                result['aligned_fresh_observations'] = len(after_samples)
                save_frame('after', after_samples[-1])
                result['final_alignment_state'] = latest['alignment']['state']
                stop(controller)
                processes.remove(controller)
                controller = None
                spin(0.1)
                assert commands and commands[-1][1] == [0]*6, 'Final command not zero'
            # Truth is read for the report only AFTER sign/alignment decisions.
            result['evaluation'] = evaluation.summary()
            result['outcome'] = 'PASS'
    except Exception as error:
        result.update(reason=str(error), latest=latest)
    finally:
        if active:
            result.setdefault('evaluation', evaluation.summary())
        result['association_counts'] = dict(Counter(s['state'] for _, s in measured_observations))
        result['control_state_counts'] = dict(Counter(s['state'] for _, s in statuses))
        errors = [s['selected_target']['horizontal_error'] for _, s in measured_observations if s['valid']]
        result['sign_crossings'] = sum(a*b < 0 for a, b in zip(errors, errors[1:]))
        result['overshoot_error'] = (max(0.0, -min(errors))
            if errors and result.get('before', {}).get('error', 0) > 0 else
            max(0.0, max(errors)) if errors else None)
        result['event_counts'] = {state: sum(s == state for _, s in transitions)
            for state in ('STALE', 'MODEL_UNAVAILABLE', 'NO_PIPE', 'AMBIGUOUS')}
        if errors:
            result['last_fresh_error'] = errors[-1]
        if commands:
            result['max_sway'] = max(abs(c[1]) for _, c in commands)
            result['only_sway'] = all(c[0] == 0 and c[2:] == [0]*4 for _, c in commands)
            if not result['only_sway']:
                result.update(outcome='FAIL', reason='Unowned axes commanded')
        if args.mode == 'closed':
            result.setdefault('final_alignment_state', latest.get('alignment', {}).get('state'))
            result['unsafe_motion_ticks'] = sum(s['sway_command'] != 0 for _, s in statuses
                if s['state'] not in ('ALIGNING', 'ALIGNED'))
            if result['unsafe_motion_ticks']:
                result.update(outcome='FAIL', reason='Unsafe motion tick')
        if pub is not None:
            pub.publish(Twist())
            # Drain the local observer before teardown so the explicit stop is recorded.
            until = time.monotonic()+0.1
            while time.monotonic() < until:
                rclpy.spin_once(node, timeout_sec=0.01)
        for p in reversed(processes):
            stop(p)
        result['owned_processes_exited'] = all(p.poll() is not None for p in processes)
        result['exit_codes'] = [p.returncode for p in processes]
        for log in logs:
            log.close()
        result.update(fusion_state_transitions=transitions, observations=measured_observations,
                      commands=commands, alignment_statuses=statuses)
        (root/'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(dict(evidence_directory=str(root), **{k: v for k, v in result.items()
            if k not in ('observations', 'commands', 'alignment_statuses', 'latest', 'diagnostic_raw')}), indent=2), flush=True)
        node.destroy_node()
        rclpy.shutdown()
    return 0 if result['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

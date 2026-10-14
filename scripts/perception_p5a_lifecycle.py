"""Two bounded zero-command experiments isolating dynamic body and restart."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from geometry_msgs.msg import Twist
import rclpy
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, FluidPressure, Image, Imu
from std_msgs.msg import String
from stonefish_ros2.msg import DVL

from neptune_evaluation.lateral_motion import LateralMotionEvaluation
from neptune_sim.perception_profile import write_performance_scenario
from perception_p4a_smoke import stop


CAMERA = '/neptune/camera/inspection/image_color'


def max_gap(times, start, end):
    """Include empty tails so a stopped stream cannot report a small gap."""
    times = [t for t in times if start <= t <= end]
    edges = [start, *times, end]
    return max(b-a for a, b in zip(edges, edges[1:]))


def advancing(timestamps, count=6):
    """Qualify a current consecutive window rather than all historical stamps."""
    recent = timestamps[-count:]
    return len(recent) == count and all(b > a for a, b in zip(recent, recent[1:]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('experiment', choices=['A', 'B'])
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='neptune-p5a-lifecycle-'+args.experiment+'-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    robot_path = Path(ET.parse(scenario).find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'false' if args.experiment == 'A' else 'true')
    body.find('world_transform').set('xyz', '-16.0 0.8 3.0')
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal.default_int_handler)
    node = rclpy.create_node('p5a_lifecycle_observer')
    evaluation = LateralMotionEvaluation(node)
    streams = {k: [] for k in ['image', 'info', 'imu', 'dvl', 'pressure', 'clock']}
    model_status, fused, commands, lifecycle = {}, [], [], []
    processes, logs = [], []
    baseline_time = time.monotonic()
    result = {'experiment': args.experiment, 'outcome': 'FAIL', 'body_fixed': args.experiment == 'B',
              'domain': os.environ.get('ROS_DOMAIN_ID'), 'service_calls': [], 'lifecycle': lifecycle,
              'inspection_enable_service_required': False, 'freshness_s': 0.5}
    latest = {}
    stage = None
    last_graph_check = 0

    def record(name, message):
        now = time.monotonic()
        streams[name].append(now)
        if name == 'image' and stage is not None:
            h = message.header.stamp
            stamp = h.sec+h.nanosec/1e9
            if stamp >= stage['start_wall_s'] and now >= stage['start_monotonic_s']:
                stage.setdefault('first_new_image_s', now-baseline_time)
                stage.setdefault('new_image_receipts', []).append(now-baseline_time)
                stage.setdefault('new_image_stamps', []).append(stamp)

    for name, topic, msg in [('image', CAMERA, Image),
        ('info', '/neptune/camera/inspection/camera_info', CameraInfo),
        ('imu', '/sim/imu', Imu), ('dvl', '/sim/dvl', DVL),
        ('pressure', '/sim/pressure', FluidPressure), ('clock', '/clock', Clock)]:
        node.create_subscription(msg, topic, lambda m, name=name: record(name, m), 10)

    def model_receive(model, message):
        model_status[model] = json.loads(message.data)

    for model, topic in [('inspection', '/neptune/perception/status'),
                         ('orientation_a', '/neptune/perception/orientation_a_status')]:
        node.create_subscription(String, topic, lambda m, model=model: model_receive(model, m), 10)

    def fusion_receive(message):
        s = json.loads(message.data)
        latest['fused'] = s
        fused.append((time.monotonic(), s))

    def command_receive(message):
        axes = [message.linear.x, message.linear.y, message.linear.z,
                message.angular.x, message.angular.y, message.angular.z]
        commands.append((time.monotonic(), axes))
        if axes != [0]*6:
            raise RuntimeError('Nonzero command in zero-only diagnostic')

    node.create_subscription(String, '/neptune/perception/fused_status', fusion_receive, 10)
    node.create_subscription(Twist, '/neptune/cmd_body', command_receive, 10)

    def graph():
        return [bytes(e.endpoint_gid).hex() for e in node.get_publishers_info_by_topic(CAMERA)]

    def spin(seconds):
        nonlocal last_graph_check
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=min(0.01, max(0, end-time.monotonic())))
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Owned process exited')
            if stage is not None and time.monotonic()-last_graph_check >= 0.2:
                last_graph_check = time.monotonic()
                gids = graph()
                new = sorted(set(gids)-set(stage.get('old_gids', [])))
                if new and 'first_new_publisher_s' not in stage:
                    stage.update(first_new_publisher_s=time.monotonic()-baseline_time, new_gids=new)

    def wait(predicate, deadline_s):
        deadline = time.monotonic()+deadline_s
        while not predicate() and time.monotonic() < deadline:
            spin(0.02)
        return bool(predicate())

    def launch(package, executable, extra=()):
        log = (root/(executable+'.log')).open('w')
        logs.append(log)
        p = subprocess.Popen([str(Path(get_package_prefix(package))/'lib'/package/executable), *extra],
                             stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        return p

    def simulator(label, old_gids=()):
        nonlocal stage
        stage = {'label': label, 'start_monotonic_s': time.monotonic(), 'start_wall_s': time.time(),
                 'start_s': time.monotonic()-baseline_time, 'old_gids': list(old_gids)}
        lifecycle.append(stage)
        evaluation.arm()
        log = (root/(label+'.log')).open('w')
        logs.append(log)
        p = subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low'],
            env=dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='8'),
            stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        stage.update(pid=p.pid, proc_start_ticks=Path(f'/proc/{p.pid}/stat').read_text().split(') ')[1].split()[19])
        return p

    def new_frames():
        return (stage is not None and 'first_new_publisher_s' in stage
                and advancing(stage.get('new_image_stamps', [])))

    def warm():
        return (new_frames() and len(model_status) == 2
                and all(s.get('runtime') is not None for s in model_status.values()))

    try:
        assert not graph(), 'Existing camera publisher in isolated domain'
        sim = simulator('direct_dynamic' if args.experiment == 'A' else 'fixed_initial')
        for exe in ['inspection_objects', 'orientation_a', 'pipe_fusion']:
            launch('neptune_perception', exe)
        launch('neptune_vehicle', 'stonefish_adapter', ['--ros-args', '-p', 'motor_count:=7'])
        launch('neptune_controls', 'pipe_centering', ['--ros-args', '-p', 'sway_sign:=0.0',
            '-r', '/neptune/control/alignment_cmd_body:=/neptune/cmd_body'])
        print('Experiment '+args.experiment+' startup', flush=True)
        warmed = wait(warm, 100)
        result['initial_warmup_complete'] = warmed
        if args.experiment == 'B':
            # Same stop/relaunch path as the calibration harness; no service calls.
            def stable_initial():
                entries = [(t, s) for t, s in fused if t >= time.monotonic()-2.0]
                unique = {s['sequence']: s for t, s in entries if s['valid']}
                return len(unique) >= 5
            result['initial_fixed_stable'] = wait(stable_initial, 20)
            old_gids = graph()
            stage['gids_before_stop'] = old_gids
            stop(sim)
            processes.remove(sim)
            stage.update(exit_code=sim.returncode, old_process_exited=sim.poll() is not None,
                         stop_complete_s=time.monotonic()-baseline_time)
            result['graph_immediately_after_stop'] = graph()
            sim = simulator('fixed_restarted', old_gids)
            result['restart_advancing_new_frames'] = wait(new_frames, 45)
            # Wait for current-source detector completions, not old READY/runtime metadata.
            result['restart_current_model_results'] = wait(lambda: warm() and all(
                s.get('source_header') and s['source_header']['stamp']['sec']+
                s['source_header']['stamp']['nanosec']/1e9 >= stage['start_wall_s']
                for s in model_status.values()), 15)
        # Record a full bounded window even if an upstream failure prevents warm qualification.
        start = time.monotonic()
        baseline_models = deepcopy(model_status)
        print('MEASUREMENT_WINDOW_STARTED', flush=True)
        spin(12)
        end = time.monotonic()
        duration = end-start
        measured = [(t, s) for t, s in fused if start <= t <= end]
        unique = {}
        for t, s in measured:
            if s['valid']:
                unique.setdefault(s['sequence'], (t, s))
        selected = list(unique.values())
        times = [t for t, s in selected]
        ages = [s['observation_age_s'] for t, s in measured if s['valid']]
        transitions = []
        for t, s in measured:
            if not transitions or transitions[-1][1] != s['state']:
                transitions.append((t-start, s['state']))
        streams['odometry'] = evaluation.receipts
        metrics = {'duration_s': duration, 'camera_fps': sum(start <= t <= end for t in streams['image'])/duration,
            'camera_max_gap_s': max_gap(streams['image'], start, end), 'fused_fresh_fps': len(selected)/duration,
            'fused_max_gap_s': max_gap(times, start, end), 'max_selected_target_age_s': max(ages) if ages else None,
            'state_transitions': transitions, 'stale_events': sum(s == 'STALE' for t, s in transitions),
            'streams': {name: {'count': sum(start <= t <= end for t in data),
                'fps': sum(start <= t <= end for t in data)/duration, 'max_gap_s': max_gap(data, start, end),
                'first_receipt_s': data[0]-baseline_time if data else None,
                'last_receipt_s': data[-1]-baseline_time if data else None} for name, data in streams.items()},
            'commands_all_zero': bool(commands) and all(c == [0]*6 for t, c in commands),
            'evaluation_only_drift': evaluation.summary(),
            'inspection_fps': (model_status.get('inspection', {}).get('processed_frames', 0)-
                baseline_models.get('inspection', {}).get('processed_frames', 0))/duration,
            'a1_fps': (model_status.get('orientation_a', {}).get('processed_frames', 0)-
                baseline_models.get('orientation_a', {}).get('processed_frames', 0))/duration,
            'last_fused': latest.get('fused'), 'last_models': model_status,
            'current_graph_gids': graph()}
        metrics['stable'] = (metrics['camera_fps'] >= 4 and metrics['fused_fresh_fps'] >= 4
            and metrics['camera_max_gap_s'] < 0.5 and metrics['fused_max_gap_s'] < 0.5
            and metrics['max_selected_target_age_s'] is not None and metrics['max_selected_target_age_s'] < 0.5)
        for entry in lifecycle:
            receipts = entry.get('new_image_receipts', [])
            entry['first_five_image_intervals_s'] = [b-a for a, b in zip(receipts, receipts[1:])][:5]
            entry['last_new_image_s'] = receipts[-1] if receipts else None
            entry['source_stamp_regressions'] = sum(b <= a for a, b in zip(
                entry.get('new_image_stamps', []), entry.get('new_image_stamps', [])[1:]))
        result.update(metrics=metrics, outcome='PASS' if metrics['stable'] and metrics['commands_all_zero'] else 'FAIL')
    except Exception as error:
        result['reason'] = str(error)
    finally:
        for p in reversed(processes):
            stop(p)
        result['owned_processes_exited'] = all(p.poll() is not None for p in processes)
        for log in logs:
            log.close()
        (root/'result.json').write_text(json.dumps(result, indent=2))
        compact = deepcopy(result)
        for entry in compact['lifecycle']:
            entry.pop('new_image_receipts', None)
            entry.pop('new_image_stamps', None)
        if 'metrics' in compact:
            compact['metrics'].pop('last_models', None)
            compact['metrics'].pop('last_fused', None)
        print(json.dumps({'evidence_directory': str(root), **compact}, indent=2), flush=True)
        node.destroy_node()
        rclpy.shutdown()
    return 0 if result['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

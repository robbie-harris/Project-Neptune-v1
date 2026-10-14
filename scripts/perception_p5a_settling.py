"""One dynamic runtime: distinguish startup transients from settled perception."""
from collections import Counter
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from geometry_msgs.msg import Twist
import rclpy
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import CameraInfo, FluidPressure, Image, Imu
from std_msgs.msg import String
from stonefish_ros2.msg import DVL

from neptune_evaluation.lateral_motion import LateralMotionEvaluation
from neptune_sim.perception_profile import write_performance_scenario
from perception_p4a_smoke import stop
from perception_p5a_lifecycle import max_gap


def span(values):
    return [min(values), max(values)] if values else None


def physical_window(pressure, imu, start, end):
    """Use onboard pressure-rate and IMU gyro; no truth input."""
    p = [s for s in pressure if start <= s['receipt'] <= end]
    i = [s for s in imu if start <= s['receipt'] <= end]
    rates = [s['depth_rate'] for s in p]
    yaw_rates = [s['yaw_rate'] for s in i]
    good = (end-start >= 5 and len(p) >= 2 and len(i) >= 2
            and max_gap([s['receipt'] for s in p], start, end) < 0.5
            and max_gap([s['receipt'] for s in i], start, end) < 0.5
            and all(v is not None and math.isfinite(v) and abs(v) < 0.05 for v in rates)
            and all(math.isfinite(v) and abs(v) < 0.03 for v in yaw_rates))
    return {'physical_settled': good, 'depth_range_m': span([s['depth'] for s in p]),
            'depth_rate_range_m_s': span([v for v in rates if v is not None]),
            'yaw_rate_range_rad_s': span(yaw_rates)}


def stream_metrics(camera, fused, start, end):
    """Count distinct fresh selected sources, not watchdog duplicates."""
    c = [t for t in camera if start <= t <= end]
    f = [(t, s) for t, s in fused if start <= t <= end]
    selected = {}
    for t, s in f:
        if s.get('valid'):
            selected.setdefault(s['sequence'], (t, s))
    duration = end-start
    age = [s['observation_age_s'] for t, s in f if s.get('valid')]
    states = []
    for _, s in f:
        if not states or states[-1] != s['state']:
            states.append(s['state'])
    return {'duration_s': duration, 'camera_fps': len(c)/duration,
        'camera_max_gap_s': max_gap(c, start, end), 'fusion_fps': len(selected)/duration,
        'fusion_max_gap_s': max_gap([t for t, s in selected.values()], start, end),
        'max_selected_age_s': max(age) if age else None,
        'state_events': dict(Counter(states)), 'states': states}


def perception_window(camera, fused, models, start, end):
    """Require fresh targets throughout the same full physical window."""
    metrics = stream_metrics(camera, fused, start, end)
    current = [(t, s) for t, s in fused if start <= t <= end]
    unique = {}
    for t, s in current:
        unique.setdefault(s['sequence'], (t, s))
    models_current = [s for t, model, s in models if start <= t <= end]
    good = (metrics['camera_fps'] >= 4 and metrics['fusion_fps'] >= 4
            and metrics['camera_max_gap_s'] < 0.5 and metrics['fusion_max_gap_s'] < 0.5
            and metrics['max_selected_age_s'] is not None and metrics['max_selected_age_s'] < 0.5
            and len(unique) >= 5 and bool(current)
            and all(s.get('valid') and 0 <= s['observation_age_s'] < 0.5
                    and s['receipt_age_s'] < 0.5 for t, s in current)
            and {model for t, model, s in models if start <= t <= end} == {'inspection', 'orientation_a'}
            and bool(models_current) and all(s['state'] != 'CAMERA_STALE' for s in models_current))
    return good, metrics


def median_target(samples):
    return {'error': statistics.median(s['selected_target']['horizontal_error'] for s in samples),
            'center_x': statistics.median(s['selected_target']['center'][0] for s in samples)}


def main():
    root = Path(tempfile.mkdtemp(prefix='neptune-p5a-settling-'))
    scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), root)
    robot_path = Path(ET.parse(scenario).find('include').get('file'))
    robot = ET.parse(robot_path)
    body = robot.find('robot')
    body.set('fixed', 'false')
    body.find('world_transform').set('xyz', '-16.0 0.8 3.0')
    body.find('world_transform').set('rpy', '0 0 3.141592653589793')
    robot.write(robot_path)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal.default_int_handler)
    node = rclpy.create_node('p5a_settling_observer')
    evaluation = LateralMotionEvaluation(node)
    evaluation.arm()
    pressure, imu, fused, model_events, camera, info, dvl, commands, alignment = [], [], [], [], [], [], [], [], []
    latest, model_latest = {}, {}
    camera_source, dvl_velocity = [], []
    processes, logs = [], []
    start = None
    result = {'outcome': 'BLOCKED', 'minimum_settling_s': 20, 'settle_deadline_s': 40,
              'window_s': 5, 'depth_rate_limit_m_s': 0.05, 'yaw_rate_limit_rad_s': 0.03,
              'freshness_s': 0.5, 'restarts': 0, 'truth_used_for_gate': False}
    pub = node.create_publisher(Twist, '/neptune/cmd_body', 1)
    last_zero = 0
    phase = 'settling'

    def stamp(message):
        return message.header.stamp.sec+message.header.stamp.nanosec/1e9

    def pressure_receive(message):
        depth = message.fluid_pressure/(997.0*9.81)+0.40
        rate = None
        if pressure:
            dt = stamp(message)-pressure[-1]['stamp']
            if 0 < dt < 1:
                rate = (depth-pressure[-1]['depth'])/dt
        pressure.append({'receipt': time.monotonic(), 'stamp': stamp(message),
                         'depth': depth, 'depth_rate': rate})

    def imu_receive(message):
        q = message.orientation
        imu.append({'receipt': time.monotonic(), 'stamp': stamp(message),
            'yaw': math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)),
            'yaw_rate': message.angular_velocity.z,
            'angular_velocity': [message.angular_velocity.x, message.angular_velocity.y, message.angular_velocity.z]})

    def fusion_receive(message):
        s = json.loads(message.data)
        latest['fused'] = s
        fused.append((time.monotonic(), s))

    def model_receive(model, message):
        s = json.loads(message.data)
        model_latest[model] = s
        model_events.append((time.monotonic(), model, s))

    def command_receive(message):
        values = [message.linear.x, message.linear.y, message.linear.z,
                  message.angular.x, message.angular.y, message.angular.z]
        commands.append((time.monotonic(), phase, values))
        if phase == 'settling' and values != [0]*6:
            raise RuntimeError('Nonzero settling command')

    def camera_receive(message):
        now = time.monotonic()
        camera.append(now)
        camera_source.append((now, stamp(message)))

    def info_receive(message):
        info.append((time.monotonic(), stamp(message)))
        latest['camera_info'] = {'width': message.width, 'height': message.height, 'k': list(message.k)}

    def dvl_receive(message):
        now = time.monotonic()
        dvl.append((now, stamp(message)))
        dvl_velocity.append((now, [message.velocity.x, message.velocity.y, message.velocity.z]))

    node.create_subscription(FluidPressure, '/sim/pressure', pressure_receive, 10)
    node.create_subscription(Imu, '/sim/imu', imu_receive, 10)
    node.create_subscription(Image, '/neptune/camera/inspection/image_color',
        camera_receive, 10)
    node.create_subscription(CameraInfo, '/neptune/camera/inspection/camera_info',
        info_receive, 10)
    node.create_subscription(DVL, '/sim/dvl', dvl_receive, 10)
    node.create_subscription(String, '/neptune/perception/fused_status', fusion_receive, 10)
    node.create_subscription(Twist, '/neptune/cmd_body', command_receive, 10)
    node.create_subscription(String, '/neptune/control/alignment_status',
        lambda m: alignment.append((time.monotonic(), json.loads(m.data))), 10)
    for model, topic in [('inspection', '/neptune/perception/status'),
                         ('orientation_a', '/neptune/perception/orientation_a_status')]:
        node.create_subscription(String, topic, lambda m, model=model: model_receive(model, m), 10)

    def spin(seconds):
        nonlocal last_zero
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            if phase == 'settling' and time.monotonic()-last_zero >= 0.05:
                pub.publish(Twist())
                last_zero = time.monotonic()
            rclpy.spin_once(node, timeout_sec=min(0.01, max(0, until-time.monotonic())))
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Owned process exited')

    def launch(package, executable, extra=()):
        log = (root/(executable+'.log')).open('w')
        logs.append(log)
        p = subprocess.Popen([str(Path(get_package_prefix(package))/'lib'/package/executable), *extra],
                             stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        return p

    def fresh(s):
        if not s or not s.get('valid') or s['state'] not in ('CONSENSUS', 'INSPECTION_ONLY', 'ORIENTATION_A_ONLY'):
            return False
        h = s['source_header']['stamp']
        age = node.get_clock().now().nanoseconds/1e9-(h['sec']+h['nanosec']/1e9)
        return (0 <= age < 0.5 and s['observation_age_s'] < 0.5 and s['receipt_age_s'] < 0.5
                and all(s.get('state') != 'CAMERA_STALE' for s in model_latest.values()))

    def collect():
        mark = len(fused)
        seen = set()
        samples = []
        last_time = None
        end = time.monotonic()+10
        while len(samples) < 5 and time.monotonic() < end:
            spin(0.02)
            for receipt, s in fused[mark:]:
                if not fresh(s):
                    seen.clear()
                    samples.clear()
                    last_time = None
                    continue
                if s['sequence'] not in seen:
                    if last_time is not None and receipt-last_time >= 0.5:
                        samples.clear()
                    seen.add(s['sequence'])
                    samples.append(s)
                    last_time = receipt
            mark = len(fused)
        if len(samples) < 5:
            raise RuntimeError('Five consecutive fresh observation deadline')
        return samples[-5:]

    try:
        assert node.count_publishers('/neptune/camera/inspection/image_color') == 0
        start = time.monotonic()
        log = (root/'simulator.log').open('w')
        logs.append(log)
        processes.append(subprocess.Popen([
            '/opt/stonefish_ws/install/stonefish_ros2/lib/stonefish_ros2/stonefish_simulator',
            '/workspace/external/stonefish/Tests/Data', str(scenario), '100', '160', '120', 'low'],
            env=dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='8'),
            stdout=log, stderr=subprocess.STDOUT))
        for exe in ['inspection_objects', 'orientation_a', 'pipe_fusion']:
            launch('neptune_perception', exe)
        launch('neptune_vehicle', 'stonefish_adapter', ['--ros-args', '-p', 'motor_count:=7'])
        print('Single dynamic startup; 20 s minimum, 40 s absolute settling deadline', flush=True)
        physical_first = combined_first = None
        while time.monotonic()-start < 40:
            spin(min(0.05, max(0, 40-(time.monotonic()-start))))
            now = time.monotonic()
            if now-start < 25:
                continue
            physical = physical_window(pressure, imu, now-5, now)
            perception_good, metrics = perception_window(camera, fused, model_events, now-5, now)
            if physical['physical_settled'] and physical_first is None:
                physical_first = now
                result['first_physical_settled_time_s'] = now-start
                result['first_physical_window'] = {**physical, **metrics}
                print('Physical five-second settling window passed at '+str(now-start), flush=True)
            models_warm = (set(model_latest) == {'inspection', 'orientation_a'}
                           and all(s.get('runtime') is not None for s in model_latest.values()))
            if physical['physical_settled'] and perception_good and models_warm:
                combined_first = now
                result['settled_gate_time_s'] = now-start
                result['settled_window'] = {**physical, **metrics}
                break
        now = time.monotonic()
        result['settling_duration_s'] = now-start
        result['physical_settled'] = physical_first is not None
        result['combined_settled_gate'] = combined_first is not None
        boundary = (physical_first-5) if physical_first is not None else now
        result['startup_unsettled'] = {**stream_metrics(camera, fused, start, boundary),
                                      **physical_window(pressure, imu, start, boundary)}
        if physical_first is not None:
            result['after_physical_settling'] = {**stream_metrics(camera, fused, boundary, now),
                                               **physical_window(pressure, imu, boundary, now)}
        result['last_five_seconds'] = {**stream_metrics(camera, fused, now-5, now),
                                      **physical_window(pressure, imu, now-5, now)}
        if combined_first is None:
            result['blocker'] = 'No combined physical/perception settling window by 40 s'
        else:
            phase = 'sign'
            before = median_target(collect())
            result['sign_before'] = before
            if not 0.15 <= abs(before['error']) <= 0.30:
                raise RuntimeError('Selected target is outside the requested initial-error range')
            pulse_start = time.monotonic()
            while time.monotonic()-pulse_start < 4:
                if not fresh(latest.get('fused')):
                    pub.publish(Twist())
                    raise RuntimeError('Stale/invalid/ambiguous target during sign pulse')
                message = Twist()
                message.linear.y = 0.25
                pub.publish(message)
                spin(min(0.05, max(0, 4-(time.monotonic()-pulse_start))))
            pub.publish(Twist())
            result['pulse_duration_s'] = time.monotonic()-pulse_start
            spin(0.5)
            after = median_target(collect())
            result['sign_after'] = after
            delta = after['error']-before['error']
            result['sign_change'] = delta
            if abs(delta) < 0.01:
                raise RuntimeError('Median sign response below 0.01')
            sign = -1.0 if delta > 0 else 1.0
            result['experimental_sign'] = sign
            phase = 'closed'
            closed_before = median_target(collect())
            result['closed_before'] = closed_before
            if not 0.15 <= abs(closed_before['error']) <= 0.30:
                raise RuntimeError('Closed-loop initial error outside requested range')
            pub.publish(Twist())
            spin(0.1)
            node.destroy_publisher(pub)
            pub = None
            config = Path(get_package_share_directory('neptune_controls'))/'config/pipe_centering.yaml'
            controller = launch('neptune_controls', 'pipe_centering', ['--ros-args',
                '--params-file', str(config), '-p', 'sway_sign:='+str(sign), '-r',
                '/neptune/control/alignment_cmd_body:=/neptune/cmd_body'])
            closed_start = time.monotonic()
            while time.monotonic()-closed_start < 25 and not (
                    alignment and alignment[-1][1]['state'] == 'ALIGNED'):
                spin(0.02)
            if not alignment or alignment[-1][1]['state'] != 'ALIGNED':
                raise RuntimeError('Closed-loop alignment deadline')
            result['time_to_alignment_s'] = time.monotonic()-closed_start
            samples = collect()
            if not all(abs(s['selected_target']['horizontal_error']) <= 0.05 for s in samples):
                raise RuntimeError('Deadband was not maintained over fresh observations')
            result['closed_after'] = median_target(samples)
            result['final_controller_state'] = alignment[-1][1]['state']
            if alignment[-1][1]['sway_command'] != 0:
                raise RuntimeError('Aligned sway not zero')
            result['outcome'] = 'PASS'
    except Exception as error:
        result['blocker'] = str(error)
    finally:
        if pub is not None:
            pub.publish(Twist())
            for _ in range(10):
                rclpy.spin_once(node, timeout_sec=0.01)
        result['commands_all_zero_before_gate'] = all(c == [0]*6 for t, p, c in commands if p == 'settling')
        result['only_sway_commanded'] = all(c[0] == 0 and c[2:] == [0]*4 for t, p, c in commands)
        result['initial_depth_m'] = pressure[0]['depth'] if pressure else None
        result['final_depth_m'] = pressure[-1]['depth'] if pressure else None
        result['evaluation_only'] = evaluation.summary()
        result['camera_info'] = latest.get('camera_info')
        result['last_models'] = model_latest
        result['last_fused'] = latest.get('fused')
        result['raw'] = {'pressure': pressure, 'imu': imu, 'camera_receipts': camera,
            'camera_source': camera_source, 'camera_info': info, 'dvl': dvl,
            'dvl_sensor_velocity': dvl_velocity, 'fused': fused, 'model_status': model_events,
            'commands': commands, 'alignment': alignment, 'truth_evaluation': evaluation.history}
        for p in reversed(processes):
            stop(p)
        result['owned_processes_exited'] = all(p.poll() is not None for p in processes)
        for log in logs:
            log.close()
        (root/'result.json').write_text(json.dumps(result, indent=2))
        compact = {k: v for k, v in result.items() if k not in ('raw', 'last_models', 'last_fused')}
        print(json.dumps({'evidence_directory': str(root), **compact}, indent=2), flush=True)
        node.destroy_node()
        rclpy.shutdown()
    return 0 if result['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

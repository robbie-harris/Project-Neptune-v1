#!/usr/bin/env python3
"""Passive ROS/Stonefish freeze recorder; never launches or controls a demo.

Run on the host or in a sourced ROS environment. Host mode uses only the existing
running Compose dev container and copies its output to host /tmp on exit.
All times/ordering used for liveness are monotonic receipt times. Simulator truth
is evaluation-only and is never returned to any production node.
"""

import argparse
from collections import deque
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


TOPICS = {
    'pressure': ('/sim/pressure', 'sensor_msgs/msg/FluidPressure'),
    'imu': ('/sim/imu', 'sensor_msgs/msg/Imu'),
    'dvl': ('/sim/dvl', 'stonefish_ros2/msg/DVL'),
    'sim_odometry': ('/sim/odometry', 'nav_msgs/msg/Odometry'),
    'state': ('/state/odometry', 'nav_msgs/msg/Odometry'),
    'camera': ('/neptune/camera/inspection/image_color', 'sensor_msgs/msg/Image'),
    'thrusters': ('/sim/thruster_setpoints', 'std_msgs/msg/Float64MultiArray'),
    'cmd_body': ('/neptune/cmd_body', 'geometry_msgs/msg/Twist'),
    'mission': ('/neptune/mission/status', 'std_msgs/msg/String'),
}
RAW = ('pressure', 'imu', 'dvl', 'sim_odometry')


def finite(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


class Stream:
    """Bounded metadata only; images are neither retained nor decoded."""

    def __init__(self):
        self.count = 0
        self.last = self.stamp = self.delta = None
        self.recent = deque(maxlen=4096)
        self.data = None
        self.source_regressions = 0
        self.last_source_regression = None

    def receive(self, at, stamp=None, data=None):
        self.count += 1
        self.last = at
        self.delta = stamp - self.stamp if stamp is not None and self.stamp is not None else None
        if self.delta is not None and self.delta < 0:
            self.source_regressions += 1
            self.last_source_regression = dict(monotonic=at, source_stamp=stamp,
                                               previous_stamp=self.stamp, delta=self.delta)
        self.stamp = stamp
        self.data = data
        self.recent.append(at)

    def snapshot(self, now, window=5.0):
        while self.recent and self.recent[0] <= now - window:
            self.recent.popleft()
        return dict(count=self.count, recent_hz=len(self.recent)/window,
                    rate_window_s=window, receipt_monotonic=self.last,
                    age_s=None if self.last is None else max(0.0, now-self.last),
                    source_stamp=self.stamp, source_stamp_delta=self.delta, data=self.data,
                    source_regressions=self.source_regressions,
                    last_source_regression=self.last_source_regression)


class GapDetector:
    """Receipt-only episodes; startup silence before a first message is unknown."""

    def __init__(self, threshold=0.5, sustained=5.0):
        self.threshold, self.sustained = threshold, sustained
        self.individual = {}
        self.global_start = None
        self.camera_start = None
        self.sustained_reported = False
        self.global_gaps = []

    def update(self, now, streams, mission=None):
        events = []
        stale = {k: v['age_s'] is not None and v['age_s'] >= self.threshold
                 for k, v in streams.items()}

        def emit(kind, start, **extra):
            events.append(dict(type=kind, detected_monotonic=now,
                               start_monotonic=start, duration_s=max(0, now-start), **extra))

        for key, item in streams.items():
            if stale[key] and key not in self.individual:
                self.individual[key] = item['receipt_monotonic']
            elif not stale[key] and key in self.individual:
                start = self.individual.pop(key)
                # Recovery duration ends at the actual new receipt, not sample time.
                duration = max(0, item['receipt_monotonic']-start)
                if key in RAW:
                    emit('TRANSIENT_GAP', start, scope=key, recovered=True,
                         gap_duration_s=duration)
                emit('RECOVERY', start, scope=key, recovered=True, gap_duration_s=duration)
        global_gap = all(stale.get(k, False) for k in RAW)
        if global_gap and self.global_start is None:
            self.global_start = max(streams[k]['receipt_monotonic'] for k in RAW)
            self.sustained_reported = False
            self.global_gaps.append(dict(start_monotonic=self.global_start,
                                         mission=mission, recovered=False, duration_s=None))
            emit('GLOBAL_GAP', self.global_start, scope='global')
        if global_gap:
            self.global_gaps[-1]['duration_s'] = now-self.global_start
            if not self.sustained_reported and now-self.global_start >= self.sustained:
                self.sustained_reported = True
                self.global_gaps[-1]['sustained_at'] = now
                emit('SUSTAINED_FREEZE', self.global_start, scope='global')
        elif self.global_start is not None:
            # First resumed raw stream ends a simultaneous global outage.
            recovered_at = min(streams[k]['receipt_monotonic'] for k in RAW
                               if not stale.get(k, False))
            duration = max(0, recovered_at-self.global_start)
            self.global_gaps[-1].update(duration_s=duration, recovered=True,
                                        recovered_monotonic=recovered_at)
            emit('RECOVERY', self.global_start, scope='global', recovered=True,
                 gap_duration_s=duration)
            self.global_start = None
        scalar_live = all(streams.get(k, {}).get('count', 0) and not stale.get(k) for k in RAW)
        camera_only = stale.get('camera', False) and scalar_live
        if camera_only and self.camera_start is None:
            self.camera_start = streams['camera']['receipt_monotonic']
            emit('CAMERA_ONLY_GAP', self.camera_start, scope='camera')
        elif not camera_only and self.camera_start is not None:
            emit('CAMERA_ONLY_GAP_END', self.camera_start, scope='camera',
                 recovered=not stale.get('camera', False))
            self.camera_start = None
        return events

    def status(self, now):
        if self.global_start is not None:
            name = 'SUSTAINED FREEZE' if self.sustained_reported else 'GLOBAL GAP'
            return f'{name} {now-self.global_start:.2f}s'
        if self.camera_start is not None:
            return f'CAMERA ONLY GAP {now-self.camera_start:.2f}s'
        return 'STREAM GAP' if self.individual else 'HEALTHY'


class ProcMonitor:
    """Read only /proc, with exact executable/domain matching and PID birth identity."""

    def __init__(self, domain, root='/proc'):
        self.root, self.domain = Path(root), str(domain)
        self.pid = self.birth = None
        self.previous = None
        self.candidates = []
        self.ticks = os.sysconf('SC_CLK_TCK')

    def stat(self, path):
        parts = (path/'stat').read_text().rsplit(') ', 1)[1].split()
        return dict(state=parts[0], cpu_time_s=(int(parts[11])+int(parts[12]))/self.ticks,
                    start_ticks=int(parts[19]), threads=int(parts[17]),
                    rss_bytes=int(parts[21])*os.sysconf('SC_PAGE_SIZE'))

    def discover(self):
        self.candidates = []
        for path in self.root.iterdir():
            if not path.name.isdigit():
                continue
            try:
                argv = (path/'cmdline').read_bytes().split(b'\0')
                if not argv or Path(os.fsdecode(argv[0])).name != 'stonefish_simulator':
                    continue
                env = (path/'environ').read_bytes().split(b'\0')
                if f'ROS_DOMAIN_ID={self.domain}'.encode() not in env:
                    # Unset domain means ROS default 0, not the demo's default 92.
                    if self.domain != '0' or any(x.startswith(b'ROS_DOMAIN_ID=') for x in env):
                        continue
                stat = self.stat(path)
                self.candidates.append((int(path.name), stat['start_ticks']))
            except (OSError, ValueError, IndexError):
                continue
        if len(self.candidates) == 1:
            self.pid, self.birth = self.candidates[0]

    def sample(self, now, threads=False):
        if self.pid is None:
            try:
                self.discover()
            except OSError:
                pass
        result = dict(pid=self.pid, alive=None, candidates=self.candidates,
                      cpu_percent=None, rss_bytes=None, thread_count=None,
                      fd_count=None, state=None, wchan=None)
        if self.pid is None:
            return result
        path = self.root/str(self.pid)
        try:
            values = self.stat(path)
            if values['start_ticks'] != self.birth or values['state'] in ('Z', 'X'):
                result['alive'] = False
                return result
            result.update(alive=True, state=values['state'], rss_bytes=values['rss_bytes'],
                          thread_count=values['threads'], cpu_time_s=values['cpu_time_s'])
            if self.previous and now > self.previous[0]:
                result['cpu_percent'] = 100*(values['cpu_time_s']-self.previous[1])/(now-self.previous[0])
            self.previous = (now, values['cpu_time_s'])
        except (OSError, ValueError, IndexError) as exc:
            result.update(alive=False if not path.exists() else None, error=str(exc))
            return result
        for key, reader in [('wchan', lambda: (path/'wchan').read_text().strip()),
                            ('fd_count', lambda: sum(1 for _ in (path/'fd').iterdir()))]:
            try:
                result[key] = reader()
            except OSError as exc:
                result[key+'_error'] = str(exc)
        if threads:
            result['thread_evidence'] = []
            try:
                paths = list((path/'task').iterdir())
            except OSError as exc:
                result['thread_error'] = str(exc)
                paths = []
            for task in paths:
                row = {'tid': int(task.name)}
                try:
                    row.update(self.stat(task))
                    row['wchan'] = (task/'wchan').read_text().strip()
                except (OSError, ValueError, IndexError) as exc:
                    row['error'] = str(exc)
                result['thread_evidence'].append(row)
        return result


class GpuMonitor:
    """GPU commands run in an independent daemon, never in a ROS callback."""

    def __init__(self):
        self.value = {'available': False, 'reason': 'nvidia-smi unavailable'}
        self.stop = threading.Event()
        self.pid = None
        self.thread = None
        if shutil.which('nvidia-smi'):
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def query(self, query):
        done = subprocess.run(['nvidia-smi', query, '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=1)
        if done.returncode:
            raise RuntimeError(done.stderr.strip()[:200])
        return list(csv.reader(done.stdout.splitlines()))

    def run(self):
        while not self.stop.is_set():
            try:
                rows = self.query('--query-gpu=index,utilization.gpu,memory.used,memory.total')
                devices = []
                for row in rows:
                    def number(index):
                        try:
                            return finite(float(row[index].strip()))
                        except (ValueError, IndexError):
                            return None
                    devices.append(dict(index=row[0].strip(), utilization_percent=number(1),
                                        memory_used_mib=number(2), memory_total_mib=number(3)))
                value = dict(available=True, sampled_monotonic=time.monotonic(), devices=devices,
                             process_memory_mib=None)
                if self.pid:
                    try:
                        apps = self.query('--query-compute-apps=pid,used_gpu_memory')
                        values = [float(row[1]) for row in apps if row[0].strip() == str(self.pid)]
                        value['process_memory_mib'] = finite(sum(values)) if values else None
                        value['process_memory_note'] = 'Compute-app accounting; graphics/WSL attribution may be unavailable'
                    except (ValueError, IndexError, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                        value['process_memory_error'] = str(exc)[:200]
                self.value = value
            except (ValueError, IndexError, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                self.value = dict(available=False, error=str(exc)[:200], sampled_monotonic=time.monotonic())
            self.stop.wait(1)

    def snapshot(self, now):
        value = dict(self.value)
        value['query_age_s'] = (now-value['sampled_monotonic']
                                if 'sampled_monotonic' in value else None)
        return value


def message_data(key, msg):
    if key in ('state', 'sim_odometry'):
        p, q, v = msg.pose.pose.position, msg.pose.pose.orientation, msg.twist.twist.linear
        return dict(xyz=[finite(p.x), finite(p.y), finite(p.z)],
                    yaw_deg=finite(math.degrees(math.atan2(2*(q.w*q.z+q.x*q.y),
                                                        1-2*(q.y*q.y+q.z*q.z)))),
                    speed_m_s=finite(math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)),
                    horizontal_body_speed_m_s=finite(math.hypot(v.x, v.y)))
    if key == 'cmd_body':
        return {name: [finite(getattr(vector, axis)) for axis in ('x', 'y', 'z')]
                for name, vector in [('linear', msg.linear), ('angular', msg.angular)]}
    if key == 'thrusters':
        return [finite(v) for v in msg.data]
    if key == 'mission':
        try:
            return json.loads(msg.data, parse_constant=lambda _value: None)
        except (ValueError, TypeError):
            return {'state': 'INVALID_STATUS'}
    return None


def camera_order(topics, tolerance):
    camera = topics['camera']['receipt_monotonic']
    raw = [topics[k]['receipt_monotonic'] for k in RAW]
    if camera is None or any(v is None for v in raw):
        return 'unknown'
    if topics['camera']['age_s'] < 0.5 and all(topics[k]['age_s'] >= 0.5 for k in RAW):
        return 'camera receipt still fresh during scalar gap'
    delta = camera-max(raw)
    if abs(delta) <= tolerance:
        return f'same sampling interval (+/-{tolerance:.2f}s)'
    return 'before scalar sensors' if delta < 0 else 'after scalar sensors'


def dashboard(sample, status):
    topics, sf = sample['topics'], sample['stonefish']
    mission = topics['mission']['data'] or {}
    def fmt(value, digits=1):
        return '?' if value is None else f'{value:.{digits}f}'
    state, cmd = topics['state']['data'] or {}, topics['cmd_body']['data'] or {}
    gpu = sample['gpu'].get('devices', [{}])[0] if sample['gpu'].get('devices') else {}
    line = (f"[{mission.get('state', 'WAITING'):10} {fmt(mission.get('mission_elapsed_s'))}s] "
            + ' '.join(f'{k} {topics[k]["recent_hz"]:.1f}Hz' for k in TOPICS if k not in ('mission', 'cmd_body', 'thrusters'))
            + f" | SF {sf['pid']} {sf['state']} CPU {fmt(sf['cpu_percent'])}% "
            + f"RSS {fmt(sf['rss_bytes']/2**30 if sf['rss_bytes'] is not None else None, 2)}GiB "
            + f"threads {sf['thread_count']} GPU {fmt(gpu.get('utilization_percent'))}%\n"
            + f"speed {fmt(state.get('horizontal_body_speed_m_s'), 3)}m/s yaw {fmt(state.get('yaw_deg'))} "
            + f"cmd {cmd} | STATUS: {status}")
    if 'GAP' in status or 'FREEZE' in status:
        line += '\n' + ' '.join(f'{k} age={fmt(topics[k]["age_s"], 2)}s' for k in RAW)
        line += f" | wchan={sf['wchan']} GPU={sample['gpu']}"
    print(('\033[2J\033[H' if sys.stdout.isatty() else '')+line, flush=True)


def gap_resources(output, gap):
    """Summarize saved samples, retaining no per-sample objects in memory."""
    result = {'metrics': {}, 'wchan_counts': {}, 'process_states': {}}
    start, end = gap['start_monotonic'], gap.get('recovered_monotonic', math.inf)

    def add(name, value):
        if finite(value) is None:
            return
        row = result['metrics'].setdefault(name, dict(count=0, min=value, max=value,
                                                      first=value, last=value, sum=0))
        row.update(count=row['count']+1, min=min(row['min'], value),
                   max=max(row['max'], value), last=value, sum=row['sum']+value)

    try:
        with (output/'samples.jsonl').open() as records:
            for line in records:
                sample = json.loads(line)
                if not start <= sample['monotonic'] <= end:
                    continue
                sf = sample['stonefish']
                for key in ('cpu_percent', 'rss_bytes', 'thread_count', 'fd_count'):
                    add(key, sf.get(key))
                for field, destination in [('wchan', 'wchan_counts'), ('state', 'process_states')]:
                    value = str(sf.get(field))
                    result[destination][value] = result[destination].get(value, 0)+1
                gpu = sample['gpu']
                if gpu.get('available') and (gpu.get('query_age_s') or 0) <= 3:
                    for device in gpu.get('devices', []):
                        prefix = 'gpu_'+str(device['index'])+'_'
                        for key in ('utilization_percent', 'memory_used_mib', 'memory_total_mib'):
                            add(prefix+key, device.get(key))
    except (OSError, ValueError, KeyError) as exc:
        result['error'] = str(exc)
    for row in result['metrics'].values():
        row['mean'] = row.pop('sum')/row['count']
        row['change'] = row['last']-row['first']
    return result


def write_summary(output, detector, events, reason, interval):
    gaps = detector.global_gaps
    transient = [g for g in gaps if g['recovered'] and 'sustained_at' not in g]
    sustained = [e for e in events if e['type'] == 'SUSTAINED_FREEZE']
    camera_only = [e for e in events if e['type'] == 'CAMERA_ONLY_GAP']
    lines = [f'Exit: {reason}', f'Transient recovered global gaps (<5 s): {len(transient)}',
             f'Global gaps total: {len(gaps)}',
             f'Recovered global gaps (any duration): {sum(g["recovered"] for g in gaps)}',
             f'First sustained freeze monotonic: {sustained[0]["detected_monotonic"] if sustained else "none"}',
             'Durations start at last receipt, not the 0.5 s detection threshold.',
             f'Ordering tolerance: {interval}s; receipt ordering is not capture/physics timing.']
    for index, gap in enumerate(gaps, 1):
        lines.append(f'Global gap {index}: {json.dumps(gap, sort_keys=True)}')
        lines.append('  CPU/RSS/thread/FD/GPU behavior during gap: '+
                     json.dumps(gap_resources(output, gap), sort_keys=True))
    for event in events:
        if event['type'] not in ('GLOBAL_GAP', 'SUSTAINED_FREEZE', 'RECOVERY', 'CAMERA_ONLY_GAP'):
            continue
        if event['type'] == 'RECOVERY' and event.get('scope') != 'global':
            continue
        snap = event['snapshot']
        lines.append(f"{event['type']} at {event['detected_monotonic']:.6f}, "
                     f"mission={snap['topics']['mission']['data']}; camera={event['camera_order']}; "
                     f"sim odometry age={snap['topics']['sim_odometry']['age_s']}; "
                     f"sim odometry stale={snap['topics']['sim_odometry']['age_s'] is not None and snap['topics']['sim_odometry']['age_s'] >= 0.5}")
        lines.append('  Process/thread evidence: '+json.dumps(snap['stonefish'], sort_keys=True))
        lines.append('  GPU evidence: '+json.dumps(snap['gpu'], sort_keys=True))
    choice = 'D) camera-only delivery issue' if camera_only and not gaps else 'F) insufficient evidence'
    lines += [f'Most supported: {choice}',
              'Global ROS silence alone cannot distinguish A) simulation/stepping,',
              'B) graphics/readback/shared-lock, or C) ROS publication/executor stalls.',
              'Futex/low CPU alone does not prove a deadlock or a GL call.',
              'E) resource exhaustion requires pressure/budget evidence; growth alone is not proof.',
              'GPU memory is device-wide unless explicit process attribution is available.',
              'See samples.jsonl for CPU/RSS/FD/GPU trends throughout every gap.',
              'No independent physics clock, render FPS or native stack trace was available.']
    (output/'summary.txt').write_text('\n'.join(lines)+'\n')
    (output/'events.json').write_text(json.dumps(events, indent=2, allow_nan=False)+'\n')


def observe(args, output):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from rosidl_runtime_py.utilities import get_message

    output.mkdir(parents=True, exist_ok=True)
    (output/'observer.pid').write_text(str(os.getpid()))
    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    from rclpy.node import Node

    class SuppressedParameterEvents:
        def publish(self, _message):
            # Jazzy's constructor emits parameter events even with services off.
            # Discard them locally: no DDS publisher is ever constructed.
            pass

    class PassiveNode(Node):
        def create_publisher(self, _kind, topic, *_args, **_kwargs):
            if topic == '/parameter_events':
                return SuppressedParameterEvents()
            raise RuntimeError('Passive observer cannot create publishers')

    node = PassiveNode('neptune_freeze_diagnostic', enable_rosout=False,
                       start_parameter_services=False)
    assert not list(node.publishers), 'Observer must have no ROS publishers'
    streams = {key: Stream() for key in TOPICS}
    lock = threading.Lock()
    detector = GapDetector()
    pending_events = deque(maxlen=256)
    dropped_events = [0]

    def detect(now, topics):
        for event in detector.update(now, topics, topics['mission']['data']):
            event['topic_snapshot'] = topics
            if len(pending_events) == pending_events.maxlen:
                dropped_events[0] += 1
            pending_events.append(event)

    def callback(key):
        def receive(msg):
            at = time.monotonic()
            stamp = (finite(msg.header.stamp.sec+msg.header.stamp.nanosec/1e9)
                     if hasattr(msg, 'header') else None)
            data = message_data(key, msg)
            with lock:
                at = time.monotonic()
                # Evaluate just before reception as well as on the sample timer.
                # This retains >=0.5 s gaps that recover between dashboard ticks.
                detect(at, {k: v.snapshot(at) for k, v in streams.items()})
                streams[key].receive(at, stamp, data)
                detect(at, {k: v.snapshot(at) for k, v in streams.items()})
        return receive
    for key, (topic, kind) in TOPICS.items():
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        if key == 'mission':
            qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.BEST_EFFORT)
        node.create_subscription(get_message(kind), topic, callback(key), qos)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    stopped = threading.Event()
    spin_errors = []
    def spin():
        try:
            while not stopped.is_set():
                executor.spin_once(timeout_sec=0.05)
        except Exception as exc:
            spin_errors.append(str(exc))
            stopped.set()
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    process, gpu = ProcMonitor(args.domain), GpuMonitor()
    events = []
    reason = 'Ctrl-C'
    print(f'Output: {output}\nWaiting for stonefish_simulator in ROS domain {args.domain}.', flush=True)
    last = time.monotonic()
    try:
        with (output/'samples.jsonl').open('w', buffering=1) as sample_log, \
                (output/'events.jsonl').open('w', buffering=1) as event_log:
            while not stopped.is_set():
                now = time.monotonic()
                with lock:
                    now = time.monotonic()
                    topics = {key: value.snapshot(now) for key, value in streams.items()}
                    detect(now, topics)
                    new_events = list(pending_events)
                    pending_events.clear()
                    status = detector.status(now)
                sf = process.sample(now)
                gpu.pid = process.pid
                sample = dict(monotonic=now, wall_time=time.time(),
                              wall_iso=datetime.now(timezone.utc).isoformat(),
                              ros_time=node.get_clock().now().nanoseconds/1e9,
                              sample_interval_s=now-last, observer_lag_s=max(0, now-last-args.interval),
                              topics=topics, stonefish=sf, gpu=gpu.snapshot(now),
                              dropped_event_snapshots=dropped_events[0])
                last = now
                if new_events:
                    sample['stonefish'] = process.sample(now, threads=True)
                    # Preserve this sample's interval CPU, not a zero-interval recomputation.
                    sample['stonefish']['cpu_percent'] = sf['cpu_percent']
                    for event in new_events:
                        event_topics = event.pop('topic_snapshot')
                        event_sample = dict(sample, topics=event_topics)
                        event.update(snapshot=event_sample,
                                     resources_sampled_monotonic=now,
                                     resource_capture_delay_s=max(0, now-event['detected_monotonic']),
                                     camera_order=camera_order(event_topics, args.interval))
                        events.append(event)
                        event_log.write(json.dumps(event, allow_nan=False)+'\n')
                sample_log.write(json.dumps(sample, allow_nan=False)+'\n')
                if process.pid is None:
                    status = 'WAITING FOR SIMULATOR' if len(process.candidates) < 2 else 'MULTIPLE SIMULATORS; NOT ATTACHED'
                elif not all(topics[k]['count'] for k in RAW):
                    status = 'WAITING FOR RAW STREAMS'
                dashboard(sample, status)
                if process.pid is not None and sf['alive'] is False:
                    reason = 'Stonefish exited'
                    break
                stopped.wait(max(0, args.interval-(time.monotonic()-now)))
            if spin_errors:
                reason = 'Observer error: '+spin_errors[-1]
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        thread.join(timeout=2)
        gpu.stop.set()
        if gpu.thread:
            gpu.thread.join(timeout=3)
        write_summary(output, detector, events, reason, args.interval)
        executor.shutdown(timeout_sec=1)
        node.destroy_node()
        rclpy.shutdown()
        print(f'Finished: {reason}. Summary: {output}/summary.txt', flush=True)
    return 0 if not spin_errors else 1


def host_bridge(args, output):
    """Use an already running dev container; signals target only our observer PID."""
    compose = Path(__file__).resolve().parents[1]/'docker/compose.yaml'
    try:
        found = subprocess.run(['docker', 'compose', '-f', str(compose), 'ps', '-q',
                                '--status', 'running', 'dev'], capture_output=True,
                               text=True, check=True, timeout=5).stdout.split()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'ROS unavailable; cannot access existing dev container: {exc}', file=sys.stderr)
        return 1
    if len(found) != 1:
        print('Start the existing dev container first; observer will not start it.', file=sys.stderr)
        return 1
    container = found[0]
    command = ['docker', 'exec', '-e', f'ROS_DOMAIN_ID={args.domain}', container, 'bash', '-c',
               'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; '
               'exec python3 /workspace/scripts/diagnose_demo_freeze.py "$@"', 'bash',
               '--native', '--domain', str(args.domain), '--interval', str(args.interval),
               '--output-dir', str(output)]
    print(f'Using running dev container; logs at container:{output}; copied to host on exit.', flush=True)
    child = subprocess.Popen(command, start_new_session=True)
    try:
        code = child.wait()
    except KeyboardInterrupt:
        # Never signal a demo PID/process group. Validate the observer's own command.
        stop_code = ('import os,signal,sys; from pathlib import Path; '
                     'p=Path(sys.argv[1]); pid=int(p.read_text()); '
                     'a=Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\\0"); '
                     'assert b"/workspace/scripts/diagnose_demo_freeze.py" in a; '
                     'os.kill(pid,signal.SIGINT)')
        try:
            subprocess.run(['docker', 'exec', container, 'python3', '-c', stop_code,
                            str(output/'observer.pid')], timeout=5, check=True)
            code = child.wait(timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f'Could not confirm observer shutdown: {exc}; demo was not signalled.', file=sys.stderr)
            code = 1
    try:
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run(['docker', 'cp', f'{container}:{output}/.', str(output)],
                       check=True, timeout=15, capture_output=True)
        print(f'Host output: {output}', flush=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'Logs remain at container:{output}; copy failed: {exc}', file=sys.stderr)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', type=int, default=int(os.environ.get('ROS_DOMAIN_ID', '92')),
                        help='ROS domain, matching the demo (default: ROS_DOMAIN_ID or 92)')
    parser.add_argument('--interval', type=float, default=0.5, help='Sample period, 0.25–0.5 s')
    parser.add_argument('--output-dir', type=Path, help='Override timestamped /tmp output directory')
    parser.add_argument('--native', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0.25 <= args.interval <= 0.5:
        parser.error('--interval must be between 0.25 and 0.5 seconds')
    output = args.output_dir or Path('/tmp')/('neptune-freeze-diagnostic-'+
              datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    if not args.native and not Path('/.dockerenv').exists():
        return host_bridge(args, output)
    os.environ['ROS_DOMAIN_ID'] = str(args.domain)
    return observe(args, output)


if __name__ == '__main__':
    sys.exit(main())

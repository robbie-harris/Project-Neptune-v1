"""Read-only camera-first Demo V0 display, with separate ROS and UI loops.

The donor lumyn/Perception GUI inspired the dark/cyan palette and camera/sidebar
layout. No donor TCP bridge, manual controls, truth display or thruster path is
used. Only the newest camera message is retained; conversion runs in the UI.
"""

from collections import deque
import json
import math
from pathlib import Path
import signal
import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from nav_msgs.msg import Odometry
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String


STAGES = ('INITIALIZING', 'WAIT_FOR_STATE', 'DIVE', 'TRANSIT', 'INSPECT',
          'RETURN', 'ASCEND', 'COMPLETE')
WINDOW = 'Project Neptune - Demo V0'
# BGR equivalents of the donor's charcoal, pale text and cyan palette.
BG, PANEL, FG, MUTED = (27, 22, 17), (43, 35, 28), (238, 234, 224), (151, 137, 116)
CYAN, GREEN, AMBER, RED = (217, 179, 79), (156, 215, 105), (89, 194, 245), (95, 105, 240)


def image_bgr(message):
    """Decode supported native image rows while honoring stride/padding."""
    if message.width <= 0 or message.height <= 0:
        raise ValueError('Empty camera image')
    channels = 1 if message.encoding == 'mono8' else 3
    if message.encoding not in ('rgb8', 'bgr8', 'mono8'):
        raise ValueError('Unsupported camera encoding')
    if message.step < message.width * channels:
        raise ValueError('Invalid camera stride')
    data = np.frombuffer(message.data, dtype=np.uint8)
    if data.size != message.height * message.step:
        raise ValueError('Invalid camera payload length')
    rows = data.reshape(message.height, message.step)[:, :message.width * channels]
    pixels = rows.reshape(message.height, message.width, channels)
    if message.encoding == 'rgb8':
        return cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
    if message.encoding == 'mono8':
        return cv2.cvtColor(pixels[:, :, 0], cv2.COLOR_GRAY2BGR)
    return pixels.copy()


class DemoGui(Node):
    """Application-topic subscriptions only; this node publishes no commands/data."""

    def __init__(self, **options):
        super().__init__('demo_gui', **options)
        self.evidence_directory = self.declare_parameter('evidence_directory', '').value
        self.lock = threading.Lock()
        self.latest_image = None
        self.image_sequence = 0
        self.image_receipt = None
        self.camera_receipts = deque(maxlen=60)
        self.camera_info = None
        self.telemetry = None
        self.state_receipt = None
        self.mission = {'state': 'INITIALIZING', 'mission_elapsed_s': 0.0,
                        'complete': False, 'outcome': 'RUNNING'}
        self.health = {'ready': False, 'reason': 'Waiting for sensor-derived state'}
        self.mission_receipt = None
        self.health_receipt = None
        self.displayed_frames = 0
        self.last_display = None
        self.maximum_display_gap = 0.0
        camera_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        status_qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(Image, '/neptune/camera/inspection/image_color',
                                 self.camera, camera_qos)
        self.create_subscription(CameraInfo, '/neptune/camera/inspection/camera_info',
                                 self.info, camera_qos)
        self.create_subscription(Odometry, '/state/odometry', self.state, 10)
        self.create_subscription(String, '/neptune/mission/status', self.mission_status, status_qos)
        self.create_subscription(String, '/neptune/demo/health', self.demo_health, status_qos)

    def camera(self, message):
        with self.lock:
            self.latest_image = message
            self.image_sequence += 1
            self.image_receipt = time.monotonic()
            self.camera_receipts.append(self.image_receipt)

    def info(self, message):
        with self.lock:
            self.camera_info = (message.width, message.height, message.header.frame_id)

    def state(self, message):
        p, q = message.pose.pose.position, message.pose.pose.orientation
        yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))
        with self.lock:
            self.telemetry = dict(x=p.x, y=p.y, depth=p.z, heading=math.degrees(yaw))
            self.state_receipt = time.monotonic()

    def mission_status(self, message):
        try:
            data = json.loads(message.data)
            if data.get('state') not in STAGES:
                return
            with self.lock:
                self.mission = data
                self.mission_receipt = time.monotonic()
        except (ValueError, TypeError):
            self.get_logger().warning('Invalid mission status received')

    def demo_health(self, message):
        try:
            data = json.loads(message.data)
            with self.lock:
                self.health = data
                self.health_receipt = time.monotonic()
        except (ValueError, TypeError):
            self.get_logger().warning('Invalid demo health received')

    def snapshot(self):
        with self.lock:
            return dict(image=self.latest_image, sequence=self.image_sequence,
                        image_receipt=self.image_receipt, receipts=list(self.camera_receipts),
                        info=self.camera_info, telemetry=self.telemetry,
                        state_receipt=self.state_receipt, mission=dict(self.mission),
                        health=dict(self.health), mission_receipt=self.mission_receipt,
                        health_receipt=self.health_receipt)


def text(canvas, value, x, y, size=0.6, color=FG, weight=1):
    """Draw consistent readable UI typography."""
    cv2.putText(canvas, str(value), (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                size, color, weight, cv2.LINE_AA)


def render(snapshot, image, now, ros_now, camera_error=''):
    """Compose a camera-first observational display without generated detections."""
    canvas = np.full((880, 1280, 3), BG, dtype=np.uint8)
    cv2.rectangle(canvas, (0, 0), (1279, 82), PANEL, -1)
    text(canvas, 'PROJECT NEPTUNE', 24, 43, 1.05, CYAN, 2)
    text(canvas, 'MARINE INSPECTION  /  DEMO V0', 26, 66, 0.43, MUTED)
    text(canvas, 'ONBOARD AUTONOMY', 991, 35, 0.49, GREEN)
    text(canvas, 'PERCEPTION: DISABLED', 984, 60, 0.46, MUTED)
    text(canvas, 'INSPECTION CAMERA', 24, 110, 0.48, MUTED)
    camera_at = snapshot['image_receipt']
    camera_live = camera_at is not None and now - camera_at < 0.5 and not camera_error
    msg = snapshot['image']
    if msg is not None:
        age = ros_now - msg.header.stamp.sec - msg.header.stamp.nanosec / 1e9
        camera_live = camera_live and -0.05 <= age < 0.5
    if image is not None:
        h, w = image.shape[:2]
        scale = min(920 / w, 690 / h)
        dw, dh = round(w*scale), round(h*scale)
        pixels = cv2.resize(image, (dw, dh), interpolation=cv2.INTER_LINEAR)
        left, top = 24 + (920-dw)//2, 122 + (690-dh)//2
        canvas[top:top+dh, left:left+dw] = pixels
    else:
        cv2.rectangle(canvas, (24, 122), (943, 811), PANEL, -1)
        text(canvas, 'WAITING FOR LIVE CAMERA', 238, 467, 0.9, MUTED)
    cv2.rectangle(canvas, (24, 122), (943, 811), CYAN if camera_live else MUTED, 1)
    badge = 'LIVE' if camera_live else 'WAITING' if camera_at is None else 'STALE'
    text(canvas, badge, 830, 110, 0.48, GREEN if camera_live else AMBER, 2)
    cv2.rectangle(canvas, (963, 94), (1255, 811), PANEL, -1)
    mission = snapshot['mission']
    mission_fresh = (snapshot['mission_receipt'] is not None
                     and now - snapshot['mission_receipt'] < 0.75)
    phase = mission.get('state', 'INITIALIZING')
    text(canvas, 'MISSION', 984, 126, 0.5, MUTED)
    label = 'WAIT FOR STATE' if phase == 'WAIT_FOR_STATE' else phase
    text(canvas, label, 984, 160, 0.72 if len(label) < 13 else 0.58,
         CYAN if mission_fresh else AMBER, 2)
    t = snapshot['telemetry']
    state_live = snapshot['state_receipt'] is not None and now - snapshot['state_receipt'] < 0.5
    text(canvas, 'DEPTH', 984, 210, 0.5, MUTED)
    text(canvas, '--' if t is None else f"{t['depth']:.2f}", 980, 272, 1.9, FG, 2)
    text(canvas, 'm', 1190, 272, 0.7, MUTED)
    text(canvas, 'ONBOARD STATE', 984, 326, 0.46, MUTED)
    text(canvas, 'LIVE' if state_live else 'WAITING / STALE', 984, 351,
         0.6, GREEN if state_live else AMBER, 2)
    text(canvas, 'Pressure + IMU + DVL', 984, 376, 0.43, MUTED)
    receipts = snapshot['receipts']
    fps = (len(receipts)-1)/(receipts[-1]-receipts[0]) if len(receipts)>1 and camera_live else 0.0
    text(canvas, 'CAMERA', 984, 425, 0.46, MUTED)
    text(canvas, f'{fps:.1f} Hz  /  320 x 240', 984, 452, 0.57, FG)
    text(canvas, '80 deg HFOV  /  RGB', 984, 478, 0.43, MUTED)
    text(canvas, 'ESTIMATED POSITION', 984, 527, 0.46, MUTED)
    text(canvas, '--' if t is None else f"X {t['x']:+.2f}   Y {t['y']:+.2f} m", 984, 554, 0.53)
    text(canvas, '--' if t is None else f"Heading {t['heading']:+.1f} deg", 984, 580, 0.48, MUTED)
    elapsed = mission.get('mission_elapsed_s', 0.0)
    text(canvas, 'MISSION TIME', 984, 628, 0.46, MUTED)
    text(canvas, f'{int(elapsed)//60:02d}:{int(elapsed)%60:02d}', 984, 666, 1.0, FG)
    if mission.get('complete'):
        note, color = 'MISSION COMPLETE', GREEN
    elif mission.get('outcome') == 'TIMEOUT':
        note, color = 'MISSION TIMEOUT', RED
    elif not mission_fresh:
        note, color = 'Awaiting mission status', AMBER
    elif phase == 'INITIALIZING':
        note = 'Ready - awaiting start' if snapshot['health'].get('ready') else 'Qualifying startup'
        color = AMBER
    else:
        note, color = 'Autonomy active' if snapshot['health'].get('ready') else 'Paused: sensor health', GREEN
    text(canvas, note, 984, 727, 0.53, color, 1)
    text(canvas, 'READ-ONLY DISPLAY', 984, 786, 0.42, MUTED)
    current = STAGES.index(phase)
    for index, stage in enumerate(STAGES):
        left = 24 + index*155
        selected = index == current
        color = CYAN if selected else GREEN if index < current else MUTED
        cv2.rectangle(canvas, (left, 834), (left+143, 863), color, 1)
        text(canvas, 'WAIT FOR STATE' if stage == 'WAIT_FOR_STATE' else stage,
             left+6, 853, 0.35, color, 1)
    return canvas, {'camera_live': bool(camera_live), 'camera_fps_recent': fps,
                    'state_live': bool(state_live), 'mission_state': phase,
                    'mission_status_live': bool(mission_fresh)}


def main(args=None):
    """Use OpenCV's existing native UI and a separate, bounded ROS spin thread."""
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    old_handlers = {sig: signal.signal(sig, signal.default_int_handler)
                    for sig in (signal.SIGINT, signal.SIGTERM)}
    node = DemoGui()
    stop = threading.Event()
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    def spin():
        while not stop.is_set() and rclpy.ok():
            executor.spin_once(timeout_sec=0.05)

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    evidence = Path(node.evidence_directory) if node.evidence_directory else None
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
    saved = set()
    last_sequence, image, camera_error = -1, None, ''
    reported = last_evidence = 0.0
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        while rclpy.ok():
            snapshot = node.snapshot()
            now = time.monotonic()
            if snapshot['image'] is not None and snapshot['sequence'] != last_sequence:
                last_sequence = snapshot['sequence']
                try:
                    image = image_bgr(snapshot['image'])
                    camera_error = ''
                    if node.last_display is not None:
                        node.maximum_display_gap = max(node.maximum_display_gap, now-node.last_display)
                    node.last_display = now
                    node.displayed_frames += 1
                except ValueError as error:
                    camera_error = str(error)
            canvas, health = render(snapshot, image, now, node.get_clock().now().nanoseconds/1e9,
                                    camera_error)
            cv2.imshow(WINDOW, canvas)
            if cv2.waitKey(25) & 0xff in (27, ord('q')):
                break
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if now-reported >= 5:
                node.get_logger().info(
                    f"GUI {health['mission_state']}: camera {health['camera_fps_recent']:.1f} Hz, "
                    f"displayed={node.displayed_frames}, state_live={health['state_live']}")
                reported = now
            if evidence:
                phase = health['mission_state']
                name = phase + ('-live' if phase == 'INITIALIZING' and image is not None else '')
                if name not in saved:
                    cv2.imwrite(str(evidence/(name+'.png')), canvas)
                    saved.add(name)
                if now-last_evidence >= 1:
                    (evidence/'gui-health.json').write_text(json.dumps({
                        **health, 'receipt_monotonic': now, 'received_frames': snapshot['sequence'],
                        'displayed_frames': node.displayed_frames,
                        'max_display_gap': node.maximum_display_gap,
                        'camera_error': camera_error, 'screenshots': sorted(saved),
                    }, indent=2))
                    last_evidence = now
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        thread.join(timeout=2)
        executor.remove_node(node)
        executor.shutdown(timeout_sec=1)
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)

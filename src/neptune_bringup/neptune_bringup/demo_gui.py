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
        self.window_width = self.declare_parameter('window_width', 1280).value
        self.window_height = self.declare_parameter('window_height', 880).value
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


PROGRESS_STAGES = ('INIT', 'DIVE', 'TRANSIT', 'INSPECT', 'RETURN', 'ASCEND', 'COMPLETE')
MINIMUM_SIZE = (720, 540)
WINDOW_FLAGS = cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_FREERATIO


def mission_progress(phase):
    """Merge startup/waiting into one non-interactive presentation stage."""
    return 0 if phase in ('INITIALIZING', 'WAIT_FOR_STATE') else PROGRESS_STAGES.index(phase)


def image_fit(source, bounds):
    """Center an undistorted image; prefer integer upscaling when it wastes <15%."""
    sw, sh = source
    x, y, width, height = bounds
    scale = min(width/sw, height/sh)
    integer = math.floor(scale)
    if integer >= 1 and integer/scale >= 0.85:
        scale = integer
    divisor = math.gcd(sw, sh)
    unit = max(1, math.floor(scale*divisor))
    dw, dh = sw//divisor*unit, sh//divisor*unit
    return x+(width-dw)//2, y+(height-dh)//2, dw, dh


def text(canvas, value, x, y, size=0.6, color=FG, weight=1, max_width=None):
    """Draw quiet, consistently sized typography, fitting long mission labels."""
    value = str(value)
    if max_width:
        width = cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, size, weight)[0][0]
        if width > max_width:
            size *= max_width/width
    cv2.putText(canvas, value, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX,
                size, color, weight, cv2.LINE_AA)


def status(canvas, label, value, x, y, live, width):
    """Compact health indicator, never a control."""
    text(canvas, label, x, y, 0.45, MUTED)
    cv2.circle(canvas, (x+76, y-4), 3, GREEN if live else AMBER, -1, cv2.LINE_AA)
    text(canvas, value, x+88, y, 0.47, GREEN if live else AMBER,
         max_width=width-88)


def render(snapshot, image, now, ros_now, camera_error='', size=(1280, 880)):
    """Responsive camera-first presentation; ROS inputs and freshness rules unchanged."""
    width, height = max(MINIMUM_SIZE[0], size[0]), max(MINIMUM_SIZE[1], size[1])
    canvas = np.full((height, width, 3), BG, dtype=np.uint8)
    margin = max(20, min(32, round(width*0.024)))
    gap = 24
    header = min(96, round(height*0.15))
    sidebar = max(198, min(300, round((width-2*margin)*0.25)))
    sx = width-margin-sidebar
    bottom = height-74
    top = header+38
    span = bottom-top
    camera_at = snapshot['image_receipt']
    camera_live = camera_at is not None and now-camera_at < 0.5 and not camera_error
    msg = snapshot['image']
    if msg is not None:
        age = ros_now-msg.header.stamp.sec-msg.header.stamp.nanosec/1e9
        camera_live = camera_live and -0.05 <= age < 0.5
    state_live = snapshot['state_receipt'] is not None and now-snapshot['state_receipt'] < 0.5
    mission = snapshot['mission']
    mission_fresh = snapshot['mission_receipt'] is not None and now-snapshot['mission_receipt'] < 0.75
    phase = mission.get('state', 'INITIALIZING')
    current = mission_progress(phase)
    ready = snapshot['health'].get('ready', False)
    active = current > 0 and phase != 'COMPLETE' and ready and state_live and mission_fresh
    autonomy = ('COMPLETE' if mission.get('complete') else 'TIMEOUT'
                if mission.get('outcome') == 'TIMEOUT' else 'ACTIVE' if active else
                'STANDBY' if current == 0 else 'PAUSED')
    receipts = snapshot['receipts']
    fps = (len(receipts)-1)/(receipts[-1]-receipts[0]) if len(receipts)>1 and camera_live else 0.0

    # One quiet header; no engineering toolbar or application controls.
    cv2.rectangle(canvas, (0, 0), (width-1, header-1), PANEL, -1)
    brand = 0.82 if width >= 900 else 0.65
    text(canvas, 'PROJECT NEPTUNE', margin, 39, brand, FG, 2)
    text(canvas, 'Autonomous Subsea Inspection', margin+1, 63, 0.43, MUTED)
    tag_x = width-margin-174
    text(canvas, 'AUTONOMY', tag_x, 27, 0.36, MUTED)
    cv2.circle(canvas, (tag_x+3, 45), 3, GREEN if active or autonomy == 'COMPLETE' else MUTED, -1)
    text(canvas, autonomy, tag_x+15, 50, 0.48, GREEN if active or autonomy == 'COMPLETE' else FG)
    text(canvas, 'PERCEPTION  DISABLED', tag_x, 72, 0.36, MUTED)

    camera_bounds = (margin, top, sx-gap-margin, span)
    text(canvas, 'INSPECTION CAMERA', margin, top-14, 0.42, MUTED)
    badge = 'LIVE' if camera_live else 'WAITING' if camera_at is None else 'STALE'
    badge_x = sx-gap-74
    cv2.circle(canvas, (badge_x, top-19), 3, GREEN if camera_live else AMBER, -1)
    text(canvas, badge, badge_x+11, top-14, 0.41, GREEN if camera_live else AMBER)
    bx, by, bw, bh = camera_bounds
    cv2.rectangle(canvas, (bx, by), (bx+bw-1, by+bh-1), (18, 13, 9), -1)
    image_rect = None
    if image is not None:
        ih, iw = image.shape[:2]
        left, y, dw, dh = image_fit((iw, ih), camera_bounds)
        integral = dw % iw == 0 and dh % ih == 0
        pixels = cv2.resize(image, (dw, dh), interpolation=(
            cv2.INTER_NEAREST if integral else cv2.INTER_CUBIC))
        canvas[y:y+dh, left:left+dw] = pixels
        image_rect = [left, y, dw, dh]
    else:
        label = 'Awaiting camera'
        tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .55, 1)[0][0]
        text(canvas, label, bx+(bw-tw)//2, by+bh//2, .55, MUTED)

    # Readable status column with no boxed tabs, sensor internals or fake detections.
    cv2.line(canvas, (sx-12, top), (sx-12, bottom), PANEL, 1)
    text(canvas, 'MISSION', sx+8, top+8, .45, MUTED)
    label = 'INITIALIZING' if current == 0 else phase
    text(canvas, label, sx+6, top+48, 1.0, CYAN if mission_fresh else MUTED, 2,
         max_width=sidebar-18)
    dy = top+round(span*.25)
    text(canvas, 'DEPTH', sx+8, dy, .45, MUTED)
    telemetry = snapshot['telemetry']
    depth = '--' if telemetry is None else f"{telemetry['depth']:.2f}"
    text(canvas, depth, sx+5, dy+48, 1.65 if height >= 650 else 1.35, FG, 2,
         max_width=sidebar-44)
    text(canvas, 'm', sx+sidebar-23, dy+48, .52, MUTED)
    health_y = top+round(span*.52)
    status(canvas, 'STATE', 'HEALTHY' if state_live else 'WAITING', sx+8,
           health_y, state_live, sidebar-16)
    status(canvas, 'CAMERA', badge, sx+8, health_y+31, camera_live, sidebar-16)
    if height >= 650:
        position_y = top+round(span*.70)
        text(canvas, 'POSITION', sx+8, position_y, .40, MUTED)
        text(canvas, '--' if telemetry is None else
             f"{telemetry['x']:+.1f}, {telemetry['y']:+.1f} m", sx+8,
             position_y+25, .50, FG, max_width=sidebar-16)
        text(canvas, '--' if telemetry is None else
             f"Heading {telemetry['heading']:+.1f} deg", sx+8,
             position_y+49, .41, MUTED, max_width=sidebar-16)
    elapsed = max(0, int(mission.get('mission_elapsed_s', 0.0)))
    text(canvas, 'MISSION TIME', sx+8, bottom-40, .40, MUTED)
    text(canvas, f'{elapsed//60:02d}:{elapsed%60:02d}', sx+8, bottom-10, .70, FG)

    # A continuous rail, visibly status rather than seven clickable rectangles.
    rail_y = height-43
    centers = [margin+26+i*(width-2*margin-52)//6 for i in range(7)]
    cv2.line(canvas, (centers[0], rail_y), (centers[-1], rail_y), PANEL, 2)
    if current:
        cv2.line(canvas, (centers[0], rail_y), (centers[current], rail_y), MUTED, 2)
    for index, (stage, x) in enumerate(zip(PROGRESS_STAGES, centers)):
        color = CYAN if index == current else MUTED if index < current else (78, 63, 49)
        cv2.circle(canvas, (x, rail_y), 5 if index == current else 3, color, -1, cv2.LINE_AA)
        font = .40 if width >= 900 else .31
        tw = cv2.getTextSize(stage, cv2.FONT_HERSHEY_SIMPLEX, font, 1)[0][0]
        text(canvas, stage, x-tw//2, rail_y+23, font, color)
    return canvas, {'camera_live': bool(camera_live), 'camera_fps_recent': fps,
                    'state_live': bool(state_live), 'mission_state': phase,
                    'mission_status_live': bool(mission_fresh), 'autonomy_status': autonomy,
                    'progress_index': current, 'window_size': [width, height],
                    'camera_rect': image_rect}


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
        cv2.namedWindow(WINDOW, WINDOW_FLAGS)
        window_size = (max(MINIMUM_SIZE[0], node.window_width),
                       max(MINIMUM_SIZE[1], node.window_height))
        cv2.resizeWindow(WINDOW, *window_size)
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
                                    camera_error, size=window_size)
            cv2.imshow(WINDOW, canvas)
            if cv2.waitKey(25) & 0xff in (27, ord('q')):
                break
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            _, _, client_width, client_height = cv2.getWindowImageRect(WINDOW)
            if client_width > 0 and client_height > 0:
                window_size = (max(MINIMUM_SIZE[0], client_width),
                               max(MINIMUM_SIZE[1], client_height))
                if window_size != (client_width, client_height):
                    cv2.resizeWindow(WINDOW, *window_size)
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
                    cv2.imwrite(str(evidence/'latest.png'), canvas)
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

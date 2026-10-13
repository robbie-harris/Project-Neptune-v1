"""Latest-frame Inspection Objects observer; no command interfaces."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import time

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose

from .backends import LocalInference
from .core import Freshness, LatestFrame, MODEL_ID, SchemaError, parse_response

# Adapted from lumyn/Perception backends.py at 608a3b985b8c5dbfc56f5398b8679c8038861bbe.
COLORS = {'pipe': (0, 255, 0), 'valve': (255, 180, 0), 'flange': (220, 80, 255)}


def stamp_seconds(header):
    return header.stamp.sec + header.stamp.nanosec/1e9


def header_dict(header):
    return dict(stamp=dict(sec=header.stamp.sec, nanosec=header.stamp.nanosec),
                frame_id=header.frame_id)


def detection_message(header, observations):
    result = Detection2DArray()
    result.header = deepcopy(header)
    for observation in observations:
        detection = Detection2D()
        detection.header = deepcopy(header)
        detection.bbox.center.position.x, detection.bbox.center.position.y = observation.center
        detection.bbox.size_x = observation.xyxy[2]-observation.xyxy[0]
        detection.bbox.size_y = observation.xyxy[3]-observation.xyxy[1]
        hypothesis = ObjectHypothesisWithPose()
        hypothesis.hypothesis.class_id = observation.class_name
        hypothesis.hypothesis.score = observation.confidence
        detection.results = [hypothesis]
        result.detections.append(detection)
    return result


def annotate(bgr, observations):
    output = bgr.copy()
    for observation in observations:
        x1, y1, x2, y2 = observation.xyxy
        color = COLORS[observation.class_name]
        cv2.rectangle(output, (int(x1), int(y1)),
                      (min(output.shape[1]-1, int(x2)), min(output.shape[0]-1, int(y2))),
                      color, 1)
        cv2.putText(output, f'{observation.class_name} {observation.confidence:.2f}',
                    (int(x1), max(10, int(y1)-3)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, color, 1)
    return output


class InspectionObjects(Node):
    def __init__(self):
        super().__init__('inspection_objects')
        url = self.declare_parameter('inference_url', 'http://127.0.0.1:9001').value
        freshness = self.declare_parameter('freshness_s', 0.5).value
        timeout = self.declare_parameter('request_timeout_s', 120.0).value
        self.backend = LocalInference(url, timeout)
        self.bridge = CvBridge()
        self.slot = LatestFrame()
        self.freshness = Freshness(time.monotonic(), freshness)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.frame = None
        self.observation_context = dict(source_header=None, image_width=None, image_height=None,
                            observations=[], runtime=None)
        self.processed = 0
        self.discarded_stale = 0
        self.started = time.monotonic()
        self.detections = self.create_publisher(
            Detection2DArray, '/neptune/perception/object_detections', 1)
        self.annotated = self.create_publisher(Image, '/neptune/perception/annotated', 1)
        self.status = self.create_publisher(String, '/neptune/perception/status', 1)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE)
        self.subscription = self.create_subscription(
            Image, '/neptune/camera/inspection/image_color', self.receive, qos)
        self.wall_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.timer = self.create_timer(0.05, self.tick, clock=self.wall_clock)

    def receive(self, message):
        now = time.monotonic()
        self.freshness.camera(now)
        self.slot.put((message, now))

    def infer(self, image):
        start = time.monotonic()
        try:
            bgr = self.bridge.imgmsg_to_cv2(image, desired_encoding='bgr8')
            ok, encoded = cv2.imencode('.png', bgr)
            if not ok:
                raise SchemaError('Image encoding failed')
            response = self.backend.infer(encoded.tobytes())
            observations = parse_response(response, image.width, image.height)
            return start, time.monotonic(), bgr, observations, response['runtime'], None
        except Exception as error:
            state = 'SCHEMA_ERROR' if isinstance(error, (SchemaError, ValueError)) else 'MODEL_UNAVAILABLE'
            return start, time.monotonic(), None, [], None, state

    def tick(self):
        now = time.monotonic()
        ros_now = self.get_clock().now().nanoseconds/1e9
        if self.future is not None and self.future.done():
            start, end, bgr, observations, runtime, error = self.future.result()
            image = self.frame
            self.observation_context = dict(source_header=header_dict(image.header),
                                image_width=image.width, image_height=image.height,
                                observations=[o.as_dict() for o in observations], runtime=runtime)
            if error:
                self.freshness.fail(error, end)
            else:
                self.freshness.finish(stamp_seconds(image.header), start, end, ros_now, observations)
                self.detections.publish(detection_message(image.header, observations))
                annotated = self.bridge.cv2_to_imgmsg(annotate(bgr, observations), encoding='bgr8')
                annotated.header = deepcopy(image.header)
                self.annotated.publish(annotated)
                self.processed += 1
            self.future = self.frame = None
        if self.future is None:
            pending = self.slot.take()
            if pending is not None:
                image, received = pending
                age = ros_now-stamp_seconds(image.header)
                if age < 0 or age > self.freshness.threshold or now-received > self.freshness.threshold:
                    self.discarded_stale += 1
                else:
                    self.frame = image
                    self.freshness.begin(stamp_seconds(image.header), now)
                    self.future = self.pool.submit(self.infer, image)
        contract = dict(model_id=MODEL_ID, orientation_valid=False,
                        **self.observation_context, **self.freshness.snapshot(now, ros_now),
                        **self.slot.counts(), in_flight=int(self.future is not None),
                        processed_frames=self.processed, discarded_stale_frames=self.discarded_stale,
                        processed_fps=self.processed/(now-self.started))
        self.status.publish(String(data=json.dumps(contract, allow_nan=False)))

    def close(self):
        self.timer.cancel()
        self.pool.shutdown(wait=True, cancel_futures=True)


def main(args=None):
    rclpy.init(args=args)
    node = InspectionObjects()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

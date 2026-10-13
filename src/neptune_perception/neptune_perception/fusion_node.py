"""Reuse detector status observations with exact-source association and watchdog."""

from copy import deepcopy
import json
import time

from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.node import Node
from std_msgs.msg import String, Header
from vision_msgs.msg import Detection2DArray

from .core import Observation
from .detector import detection_message, run
from .fusion import MatchingCache, MODELS


def arrays(output):
    header = Header()
    h = output['source_header']
    header.stamp.sec, header.stamp.nanosec = h['stamp']['sec'], h['stamp']['nanosec']
    header.frame_id = h['frame_id']
    observations, provenance = [], []
    for pipe in output['pipes']:
        for model in MODELS:
            if pipe[model] is not None:
                observations.append(pipe[model])
                provenance.append(MODELS[model])
    pipe_array = detection_message(header, [Observation(
        o['class_name'], float(o['confidence']), [float(x) for x in o['xyxy']],
        [float(x) for x in o['center']],
        o['horizontal_error'], o['vertical_error']) for o in observations])
    for detection, model_id in zip(pipe_array.detections, provenance):
        detection.id = model_id
    semantics = output['semantic_detections']
    semantic_array = detection_message(header, [Observation(
        o['class_name'], float(o['confidence']), [float(x) for x in o['xyxy']],
        [float(x) for x in o['center']],
        o['horizontal_error'], o['vertical_error']) for o in semantics])
    for detection, o in zip(semantic_array.detections, semantics):
        detection.id = o['model_id']
    return pipe_array, semantic_array


class PipeFusion(Node):
    def __init__(self):
        super().__init__('pipe_fusion')
        self.cache = MatchingCache(
            threshold=self.declare_parameter('iou_threshold', 0.30).value,
            window=self.declare_parameter('association_window_s', 0.20).value,
            freshness=self.declare_parameter('freshness_s', 0.5).value,
            capacity=self.declare_parameter('cache_capacity', 8).value)
        self.pipes = self.create_publisher(Detection2DArray, '/neptune/perception/fused_pipe_detections', 1)
        self.semantics = self.create_publisher(Detection2DArray, '/neptune/perception/fused_semantic_detections', 1)
        self.status = self.create_publisher(String, '/neptune/perception/fused_status', 1)
        self.subscriptions_owned = [self.create_subscription(String, topic,
            lambda message, model=model: self.receive(model, message), 10)
            for model, topic in [('inspection', '/neptune/perception/status'),
                                 ('orientation_a', '/neptune/perception/orientation_a_status')]]
        self.last = None
        self.last_received = None
        self.sequence = self.schema_errors = 0
        self.clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.timer = self.create_timer(0.05, self.tick, clock=self.clock)

    def receive(self, model, message):
        now = time.monotonic()
        try:
            outputs = self.cache.add(model, json.loads(message.data), now,
                                     self.get_clock().now().nanoseconds/1e9)
            for output in outputs:
                self.publish_observation(output, now)
        except (ValueError, KeyError, TypeError, IndexError):
            self.schema_errors += 1
            self.cache.model_states[model] = 'SCHEMA_ERROR'

    def publish_observation(self, output, now):
        self.sequence += 1
        output['sequence'] = self.sequence
        self.last, self.last_received = output, now
        # STALE emits no diagnostic geometry downstream.
        if output['state'] != 'STALE':
            pipes, semantics = arrays(output)
            self.pipes.publish(pipes)
            self.semantics.publish(semantics)
        self.publish_status(now)

    def publish_status(self, now):
        ros_now = self.get_clock().now().nanoseconds/1e9
        output = deepcopy(self.last) if self.last is not None else dict(
            sequence=0, state='MODEL_UNAVAILABLE', valid=False, selected_target=None,
            source_header=None, image_width=None, image_height=None, pipes=[],
            semantic_detections=[], orientation_valid=False, orientation_rad=None)
        if self.last is not None:
            stamp = output['source_header']['stamp']
            age = ros_now-(stamp['sec']+stamp['nanosec']/1e9)
            output['observation_age_s'] = age
            output['receipt_age_s'] += now-self.last_received
            if (age < 0 or age > self.cache.freshness
                    or output['receipt_age_s'] > self.cache.freshness):
                unavailable = all(self.cache.model_states[k] in ('MODEL_UNAVAILABLE', 'SCHEMA_ERROR')
                                  or self.cache.model_receipts[k] is None
                                  or now-self.cache.model_receipts[k] > self.cache.freshness
                                  for k in MODELS)
                output.update(state='MODEL_UNAVAILABLE' if unavailable else 'STALE', valid=False)
                if output['selected_target'] is not None:
                    output['selected_target']['valid'] = False
                    output['selected_target']['state'] = output['state']
        output.update(model_states=dict(self.cache.model_states), pending_frames=len(self.cache.pending),
                      cache_capacity=self.cache.capacity, rejected_inputs=self.cache.rejected,
                      evicted_entries=self.cache.evicted, mismatched_frames=self.cache.mismatched,
                      schema_errors=self.schema_errors, freshness_threshold_s=self.cache.freshness)
        self.status.publish(String(data=json.dumps(output, allow_nan=False)))

    def tick(self):
        now = time.monotonic()
        for output in self.cache.flush(now, self.get_clock().now().nanoseconds/1e9):
            self.publish_observation(output, now)
        self.publish_status(now)

    def close(self):
        self.timer.cancel()


def main(args=None):
    run(PipeFusion, args)

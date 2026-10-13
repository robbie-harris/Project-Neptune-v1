"""Strict response contract and freshness bookkeeping, independent of ROS."""

from dataclasses import dataclass
import math
from threading import Lock

MODEL_ID = 'projects-zwfft/neptune-inspection-objects-2-yolo11n-t1'
CLASSES = frozenset(('pipe', 'valve', 'flange'))
A1_MODEL_ID = 'projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1'
A1_CLASSES = frozenset(('pipe',))


class SchemaError(ValueError):
    """The model or response does not match the selected detector contract."""


class ModelUnavailable(RuntimeError):
    """Local runtime or model is unavailable; message never includes remote data."""


def validate_classes(classes, expected_classes=CLASSES):
    if (not isinstance(classes, list) or len(classes) != len(expected_classes)
            or any(not isinstance(c, str) for c in classes)
            or set(classes) != expected_classes):
        raise SchemaError('Unexpected Inspection Objects class schema'
                          if expected_classes == CLASSES else 'Unexpected A1 pipe class schema')


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError('Invalid numeric prediction')
    if not math.isfinite(value):
        raise SchemaError('Nonfinite prediction')
    return float(value)


@dataclass(frozen=True)
class Observation:
    class_name: str
    confidence: float
    xyxy: tuple
    center: tuple
    horizontal_error: float
    vertical_error: float

    def as_dict(self):
        return dict(class_name=self.class_name, confidence=self.confidence,
                    xyxy=self.xyxy, center=self.center,
                    horizontal_error=self.horizontal_error,
                    vertical_error=self.vertical_error,
                    orientation_valid=False, orientation_rad=None)


def parse_response(response, width, height, model_id=MODEL_ID, expected_classes=CLASSES):
    # Adapt donor decode_predictions' finite-value, class and xywh -> xyxy
    # checks, with mandatory model schema/dimensions and stricter invalid boxes.
    if width <= 0 or height <= 0 or not isinstance(response, dict):
        raise SchemaError('Invalid response or image dimensions')
    if response.get('model_id') != model_id:
        raise SchemaError('Unexpected model ID')
    validate_classes(response.get('classes'), expected_classes)
    runtime = response.get('runtime')
    if (not isinstance(runtime, dict)
            or not isinstance(runtime.get('providers'), list)
            or 'CUDAExecutionProvider' not in runtime.get('providers', [])
            or number(runtime.get('cuda_node_events')) <= 0):
        raise ModelUnavailable('GPU execution is not verified')
    image = response.get('image')
    if not isinstance(image, dict) or image != {'width': width, 'height': height}:
        raise SchemaError('Response image dimensions mismatch')
    predictions = response.get('predictions')
    if not isinstance(predictions, list) or len(predictions) > 300:
        raise SchemaError('Invalid prediction list')
    observations = []
    for prediction in predictions:
        if (not isinstance(prediction, dict)
                or not isinstance(prediction.get('class'), str)
                or prediction.get('class') not in expected_classes):
            raise SchemaError('Unexpected prediction class')
        c = number(prediction.get('confidence'))
        if 'class_id' in prediction:
            class_id = prediction['class_id']
            if (isinstance(class_id, bool) or not isinstance(class_id, int)
                    or not 0 <= class_id < len(expected_classes)
                    or response['classes'][class_id] != prediction['class']):
                raise SchemaError('Prediction class ID/name mismatch')
        x, y, w, h = (number(prediction.get(k)) for k in ('x', 'y', 'width', 'height'))
        if not 0 <= c <= 1 or w <= 0 or h <= 0:
            raise SchemaError('Invalid prediction confidence or extent')
        x1, x2 = max(0., min(width, x-w/2)), max(0., min(width, x+w/2))
        y1, y2 = max(0., min(height, y-h/2)), max(0., min(height, y+h/2))
        if x2 <= x1 or y2 <= y1:
            raise SchemaError('Prediction lies outside image')
        u, v = (x1+x2)/2, (y1+y2)/2
        observations.append(Observation(
            prediction['class'], c, (x1, y1, x2, y2), (u, v),
            (u-width/2)/(width/2), (v-height/2)/(height/2)))
    return observations


class LatestFrame:
    """One replaceable slot; the single worker owns the in-flight request."""

    def __init__(self):
        self.lock = Lock()
        self.pending = None
        self.received = 0
        self.replaced = 0

    def put(self, frame):
        with self.lock:
            self.received += 1
            self.replaced += self.pending is not None
            self.pending = frame

    def take(self):
        with self.lock:
            frame, self.pending = self.pending, None
            return frame

    def counts(self):
        with self.lock:
            return dict(received_frames=self.received, replaced_frames=self.replaced,
                        pending_frames=int(self.pending is not None))


class Freshness:
    """Monotonic loss watchdog plus ROS-clock source observation age."""

    def __init__(self, now, threshold=0.5):
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('Freshness threshold must be positive')
        self.created = now
        self.threshold = threshold
        self.camera_received = None
        self.result_received = None
        self.last_valid_observation = None
        self.source_stamp = None
        self.start = None
        self.end = None
        self.state = 'MODEL_UNAVAILABLE'
        self.error = None
        self.in_flight_stamp = None
        self.in_flight_start = None

    def camera(self, now):
        self.camera_received = now

    def begin(self, stamp, now):
        self.in_flight_stamp = stamp
        self.in_flight_start = now

    def finish(self, stamp, start, end, ros_now, observations):
        self.source_stamp, self.start, self.end = stamp, start, end
        self.result_received = end
        self.in_flight_stamp = self.in_flight_start = None
        self.error = None
        age = ros_now-stamp
        if age < 0 or age > self.threshold or end-start > self.threshold:
            self.state = 'STALE'
        else:
            self.state = 'READY' if observations else 'NO_DETECTION'
            self.last_valid_observation = stamp

    def fail(self, state, now):
        self.state = self.error = state
        self.source_stamp = self.in_flight_stamp
        self.start = self.in_flight_start
        self.end = now
        self.in_flight_stamp = self.in_flight_start = None

    def snapshot(self, now, ros_now):
        silence = now-(self.camera_received if self.camera_received is not None else self.created)
        age = None if self.source_stamp is None else ros_now-self.source_stamp
        receipt_age = None if self.result_received is None else now-self.result_received
        state = self.state
        if silence > self.threshold:
            state = 'CAMERA_STALE'
        elif state in ('READY', 'NO_DETECTION') and (
                age is None or age < 0 or age > self.threshold
                or receipt_age is None or receipt_age > self.threshold):
            state = 'STALE'
        return dict(state=state, model_state=self.error or self.state,
                    observation_valid=state in ('READY', 'NO_DETECTION'),
                    source_stamp_s=self.source_stamp, inference_start_monotonic_s=self.start,
                    inference_end_monotonic_s=self.end,
                    processing_latency_s=None if self.end is None or self.start is None
                    else self.end-self.start, observation_age_s=age,
                    result_receipt_age_s=receipt_age,
                    last_valid_observation_stamp_s=self.last_valid_observation,
                    in_flight_source_stamp_s=self.in_flight_stamp,
                    in_flight_start_monotonic_s=self.in_flight_start,
                    camera_silence_s=silence, freshness_threshold_s=self.threshold)

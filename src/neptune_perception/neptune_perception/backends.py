"""Pixel-only detector backends; no ROS or simulator geometry dependencies."""
import base64
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import cv2


def decode_predictions(response, width, height):
    if isinstance(response, list):
        if len(response) != 1:
            raise ValueError('Expected one image result')
        response = response[0]
    if not isinstance(response, dict) or not isinstance(response.get('predictions'), list):
        raise ValueError('Missing detection predictions')
    image = response.get('image', {})
    if image.get('width', width) != width or image.get('height', height) != height:
        raise ValueError('Prediction coordinates do not match input resolution')
    result = []
    for p in response['predictions']:
        if p.get('class') != 'pipe':
            raise ValueError('Unexpected model class; expected pipe only')
        x, y, w, h, score = [float(p[k]) for k in ('x', 'y', 'width', 'height', 'confidence')]
        if not all(math.isfinite(v) for v in (x,y,w,h,score)) or w <= 0 or h <= 0 or not 0 <= score <= 1:
            raise ValueError('Invalid detection coordinates/confidence')
        box = [max(0., x-w/2), max(0., y-h/2), min(float(width), x+w/2), min(float(height), y+h/2)]
        if box[2] > box[0] and box[3] > box[1]:
            result.append({'class': 'pipe', 'confidence': score, 'bbox': box})
    return result


def annotate(frame, detections):
    output = frame.copy()
    for d in detections:
        x1,y1,x2,y2 = map(round, d['bbox'])
        cv2.rectangle(output, (x1,y1), (x2,y2), (0,255,0), 2)
        cv2.putText(output, f"pipe {d['confidence']:.2f}", (x1,max(15,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0,255,0), 1)
    return output


class RoboflowBackend:
    """Official Inference REST contract, isolated from SDK NumPy 2 dependencies.

    PNG preserves camera pixels. Authentication stays in headers. No cloud
    image fallback or active-learning upload is enabled.
    """
    def __init__(self, api_url, model_id, key_file='', timeout=10., load_timeout=180.):
        url = urlsplit(api_url)
        if url.scheme != 'http' or url.hostname not in {'localhost','127.0.0.1','host.docker.internal','neptune-inference'} or url.username or url.password or url.query:
            raise ValueError('Use a local Roboflow Inference server URL')
        self.api_url = api_url.rstrip('/')
        self.model_id = model_id
        self.timeout, self.load_timeout = float(timeout), float(load_timeout)
        key = Path(key_file).read_text().strip() if key_file else os.environ.get('ROBOFLOW_API_KEY', '').strip()
        if not key:
            raise ValueError('Configure a local Roboflow API key file or environment variable')
        self._headers = {'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}

    def request(self, route, payload, timeout):
        request = Request(self.api_url+route, data=json.dumps(payload).encode(), headers=self._headers, method='POST')
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f'Local Inference HTTP {exc.code}; check server/model access') from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError('Local Inference unavailable or timed out') from None

    def load(self):
        return self.request('/model/add', {'model_id': self.model_id}, self.load_timeout)

    def infer(self, frame, confidence):
        ok, encoded = cv2.imencode('.png', frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not ok:
            raise ValueError('Cannot encode camera image')
        response = self.request('/infer/object_detection', {
            'model_id': self.model_id,
            'image': {'type': 'base64', 'value': base64.b64encode(encoded).decode()},
            'confidence': float(confidence), 'iou_threshold': .7,
            'class_agnostic_nms': False, 'max_detections': 300,
            'disable_active_learning': True,
            'disable_model_monitoring': True,
        }, self.timeout)
        return decode_predictions(response, frame.shape[1], frame.shape[0])

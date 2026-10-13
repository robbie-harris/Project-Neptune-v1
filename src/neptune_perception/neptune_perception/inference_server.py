"""Constrained Roboflow GPU adapter, run only in the pinned inference container.

Credentials are read from a read-only secret file into process memory. Third-party
output is discarded at the file-descriptor boundary, including native libraries;
only fixed errors and explicit, credential-free runtime evidence cross HTTP.
"""

from collections import Counter
import json
import os
from pathlib import Path
import signal
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

from .core import MODEL_ID, SchemaError, validate_classes

SECRET_PATH = '/run/secrets/roboflow_api_key'


def read_secret(path=SECRET_PATH):
    try:
        key = Path(path).read_text().strip()
    except (OSError, UnicodeError):
        raise RuntimeError('Roboflow secret unavailable') from None
    if not key or len(key) > 4096 or any(c.isspace() for c in key):
        raise RuntimeError('Roboflow secret invalid')
    return key


def silence_dependency_output():
    # Called before importing inference or reading the secret. No third-party
    # exception, URL, native diagnostic or request body can reach Docker logs.
    fd = os.open(os.devnull, os.O_WRONLY)
    for target in (1, 2):
        os.dup2(fd, target)
    os.close(fd)


class GPUModel:
    def __init__(self):
        self.model = None
        self.evidence = None
        self.profile_pending = False
        self.error = 'MODEL_UNAVAILABLE'

    def load(self):
        import onnxruntime as ort
        from inference import get_model

        key = read_secret()
        model = get_model(model_id=MODEL_ID, api_key=key,
                          onnxruntime_execution_providers=['CUDAExecutionProvider'])
        validate_classes(model.class_names)
        if 'CUDAExecutionProvider' not in model.onnx_session.get_providers():
            raise RuntimeError('CUDA session unavailable')
        # Profile the actual model session rather than equating an available
        # provider list or nvidia-smi visibility with GPU computation.
        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.enable_profiling = True
        options.profile_file_prefix = '/tmp/neptune-onnx-profile'
        model.onnx_session = ort.InferenceSession(
            model.cache_file(model.weights_file), sess_options=options,
            providers=['CUDAExecutionProvider'])
        # A later CUDA execution failure must become MODEL_UNAVAILABLE rather
        # than transparently rerunning the observation on the CPU.
        model.onnx_session.disable_fallback()
        providers = model.onnx_session.get_providers()
        if 'CUDAExecutionProvider' not in providers:
            raise RuntimeError('CUDA session unavailable')
        gpu_name = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            timeout=5, text=True).strip()
        self.evidence = dict(providers=providers, gpu_name=gpu_name,
                             cuda_node_events=0, node_events_by_provider={})
        self.model = model
        self.profile_pending = True

    def infer(self, png):
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise SchemaError('Invalid image')
        if self.model is None:
            self.load()
        responses = self.model.infer(image, confidence=0.05, iou_threshold=0.7,
                                     max_detections=300)
        if not isinstance(responses, list) or len(responses) != 1:
            raise SchemaError('Unexpected inference batch')
        response = responses[0].model_dump(by_alias=True, exclude_none=True)
        if self.profile_pending:
            profile_path = Path(self.model.onnx_session.end_profiling())
            try:
                events = json.loads(profile_path.read_text())
                counts = Counter(event.get('args', {}).get('provider') for event in events
                                 if event.get('cat') == 'Node' and
                                 event.get('args', {}).get('provider'))
            finally:
                profile_path.unlink(missing_ok=True)
            self.evidence['node_events_by_provider'] = dict(counts)
            self.evidence['cuda_node_events'] = counts['CUDAExecutionProvider']
            self.profile_pending = False
        if self.evidence['cuda_node_events'] <= 0:
            self.model = None
            raise RuntimeError('CUDA execution not proven')
        # Dimensions describe the full received image, not a locally cropped or
        # resized input. Roboflow retains its configured managed preprocessing.
        expected_image = {'width': image.shape[1], 'height': image.shape[0]}
        if response.get('image') != expected_image:
            raise SchemaError('Unexpected inference dimensions')
        self.error = None
        return dict(model_id=MODEL_ID, classes=list(self.model.class_names),
                    runtime=self.evidence, image=expected_image,
                    predictions=response.get('predictions'))


def serve(bind='0.0.0.0', port=9001):
    silence_dependency_output()
    runtime = GPUModel()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, code, body):
            data = json.dumps(body, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != '/health':
                self.reply(404, {'state': 'MODEL_UNAVAILABLE'})
                return
            self.reply(200, dict(model_id=MODEL_ID, state=runtime.error or 'READY',
                                 runtime=runtime.evidence))

        def do_POST(self):
            if self.path != '/infer':
                self.reply(404, {'state': 'MODEL_UNAVAILABLE'})
                return
            self.connection.settimeout(10)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 10_000_000 or self.headers.get('Content-Type') != 'image/png':
                    raise SchemaError('Invalid image request')
                png = self.rfile.read(size)
                if len(png) != size:
                    raise SchemaError('Truncated image')
                response = runtime.infer(png)
            except SchemaError:
                runtime.error = 'SCHEMA_ERROR'
                self.reply(422, {'state': 'SCHEMA_ERROR'})
                return
            except Exception:
                runtime.error = 'MODEL_UNAVAILABLE'
                self.reply(503, {'state': 'MODEL_UNAVAILABLE'})
                return
            self.reply(200, response)

    # Deliberately serial: no inference queue or parallel GPU requests.
    server = HTTPServer((bind, port), Handler)

    def stop(_signal, _frame):
        raise KeyboardInterrupt

    # Python as container PID 1 must explicitly handle Docker's SIGTERM.
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()

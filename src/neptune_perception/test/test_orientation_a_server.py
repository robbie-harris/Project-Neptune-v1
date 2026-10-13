"""One local server routes independent detector sessions without mixing schemas."""

import json
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from neptune_perception.backends import LocalInference
from neptune_perception.core import A1_MODEL_ID, MODEL_ID
from test_backend_secret import free_port


def test_same_server_independent_routes_and_health():
    port = free_port()
    code = f'''
from neptune_perception import inference_server as server
def fake_infer(self, png):
    self.calls = getattr(self, 'calls', 0) + 1
    self.error = None
    return dict(model_id=self.model_id, classes=sorted(self.expected_classes),
                predictions=[], image=dict(width=320, height=240),
                runtime=dict(providers=['CUDAExecutionProvider'], cuda_node_events=2),
                calls=self.calls)
server.GPUModel.infer = fake_infer
server.serve('127.0.0.1', {port})
'''
    process = subprocess.Popen([sys.executable, '-c', code],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic()+5
        while True:
            try:
                with urlopen(url+'/health', timeout=0.2) as reply:
                    assert json.load(reply)['model_id'] == MODEL_ID
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        a1 = LocalInference(url, 1, '/infer/orientation_a')
        p4a = LocalInference(url, 1)
        assert a1.infer(b'png')['classes'] == ['pipe']
        assert a1.infer(b'png')['calls'] == 2
        p4a_result = p4a.infer(b'png')
        assert p4a_result['calls'] == 1
        assert p4a_result['model_id'] == MODEL_ID
        assert set(p4a_result['classes']) == {'pipe', 'valve', 'flange'}
        assert a1.infer(b'png')['calls'] == 3
        with urlopen(url+'/health/orientation_a', timeout=1) as reply:
            assert json.load(reply) == dict(model_id=A1_MODEL_ID, state='READY', runtime=None)
        with urlopen(url+'/health', timeout=1) as reply:
            assert json.load(reply)['model_id'] == MODEL_ID
        with pytest.raises(HTTPError) as error:
            urlopen(url+'/health/arbitrary_model', timeout=1)
        assert error.value.code == 404
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=3)
    assert process.returncode == 0
    assert stdout == stderr == b''

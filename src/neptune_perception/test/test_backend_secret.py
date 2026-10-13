"""Local transport errors and credential boundaries."""

from contextlib import closing
import json
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

from neptune_perception.backends import LocalInference
from neptune_perception.core import ModelUnavailable, SchemaError
from neptune_perception.inference_server import read_secret


def test_secret_missing(tmp_path, capsys):
    with pytest.raises(RuntimeError, match='secret unavailable'):
        read_secret(tmp_path/'missing')
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('value', ['', 'contains whitespace', '\n'])
def test_invalid_secret_not_echoed(tmp_path, capsys, value):
    path = tmp_path/'secret'
    path.write_text(value)
    with pytest.raises(RuntimeError, match='secret invalid') as error:
        read_secret(path)
    assert 'contains whitespace' not in str(error.value)
    assert capsys.readouterr() == ('', '')


def test_read_secret_only_from_file(tmp_path, capsys):
    path = tmp_path/'secret'
    path.write_text('synthetic-test-credential\n')
    assert read_secret(path) == 'synthetic-test-credential'
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('url', ['https://127.0.0.1:9001', 'http://example.com',
                              'http://user:password@localhost', 'http://localhost?key=x'])
def test_remote_or_credential_urls_rejected(url):
    with pytest.raises(ValueError):
        LocalInference(url, 1)


def free_port():
    with closing(socket.socket()) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize('error_type,expected', [('RuntimeError', ModelUnavailable),
                                               ('SchemaError', SchemaError)])
def test_server_exception_and_native_output_never_logged(error_type, expected):
    port = free_port()
    synthetic = 'synthetic-sensitive-value-for-log-test'
    code = f'''
import os
from neptune_perception import inference_server as server
def fail(self, png):
    os.write(1, b'{synthetic}')
    os.write(2, b'{synthetic}')
    raise server.{error_type}('{synthetic}')
server.GPUModel.infer = fail
server.serve('127.0.0.1', {port})
'''.replace('server.RuntimeError', 'RuntimeError')
    process = subprocess.Popen([sys.executable, '-c', code],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic()+5
        while True:
            try:
                with urlopen(url+'/health', timeout=0.2) as reply:
                    assert json.load(reply)['model_id']
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        with pytest.raises(expected) as error:
            LocalInference(url, 1).infer(b'not-an-image')
        assert synthetic not in str(error.value)
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=3)
    assert stdout == stderr == b''
    assert process.returncode == 0


def test_model_unavailable_transport():
    port = free_port()
    with pytest.raises(ModelUnavailable):
        LocalInference(f'http://127.0.0.1:{port}', 0.1).infer(b'image')


@pytest.mark.parametrize('body', [b'{broken', b'[]', b'null'])
def test_transport_malformed_json(body):
    from io import BytesIO
    backend = LocalInference('http://127.0.0.1:9001', 1)
    backend.opener.open = lambda *args, **kwargs: BytesIO(body)
    if body == b'{broken':
        with pytest.raises(SchemaError):
            backend.infer(b'full-frame-png')
    else:
        from neptune_perception.core import parse_response
        with pytest.raises(SchemaError):
            parse_response(backend.infer(b'full-frame-png'), 320, 240)

"""Validate GPU adapter wiring without external model access or credentials."""

import json
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from neptune_perception import inference_server
from neptune_perception.core import MODEL_ID, SchemaError


def fake_runtime(monkeypatch, tmp_path, classes=None, providers=None, cuda_events=2):
    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if providers is None else providers
    profile = tmp_path/'profile.json'
    profile.write_text(json.dumps([
        dict(cat='Node', args=dict(provider='CUDAExecutionProvider'))
        for _ in range(cuda_events)]))
    sessions, calls = [], []

    class Session:
        def __init__(self, *args, **kwargs):
            self.fallback_disabled = False
            sessions.append(self)

        def get_providers(self):
            return providers

        def disable_fallback(self):
            self.fallback_disabled = True

        def end_profiling(self):
            return str(profile)

    model = SimpleNamespace(
        class_names=['pipe', 'valve', 'flange'] if classes is None else classes,
        onnx_session=Session(), weights_file='weights.onnx', cache_file=lambda name: name)

    def infer(image, **kwargs):
        calls.append((image.copy(), kwargs))
        return [SimpleNamespace(model_dump=lambda **kwargs: dict(
            image=dict(width=320, height=240), predictions=[]))]

    model.infer = infer

    def get_model(**kwargs):
        assert kwargs == dict(model_id=MODEL_ID, api_key='synthetic-test-key',
                              onnxruntime_execution_providers=['CUDAExecutionProvider'])
        return model

    monkeypatch.setitem(sys.modules, 'onnxruntime', SimpleNamespace(
        SessionOptions=lambda: SimpleNamespace(), InferenceSession=Session))
    monkeypatch.setitem(sys.modules, 'inference', SimpleNamespace(get_model=get_model))
    monkeypatch.setattr(inference_server, 'read_secret', lambda: 'synthetic-test-key')
    monkeypatch.setattr(inference_server.subprocess, 'check_output',
                        lambda *args, **kwargs: 'NVIDIA GeForce RTX 4080 Laptop GPU\n')
    return model, sessions, calls, profile


def test_adapter_full_received_frame_fixed_settings_and_actual_cuda_profile(monkeypatch, tmp_path):
    model, sessions, calls, profile = fake_runtime(monkeypatch, tmp_path)
    image = np.full((240, 320, 3), 123, dtype=np.uint8)
    ok, png = cv2.imencode('.png', image)
    assert ok
    adapter = inference_server.GPUModel()
    result = adapter.infer(png.tobytes())
    assert np.array_equal(calls[0][0], image)
    assert calls[0][1] == dict(confidence=0.05, iou_threshold=0.7, max_detections=300)
    assert sessions[-1].fallback_disabled
    assert result['model_id'] == MODEL_ID
    assert result['runtime']['cuda_node_events'] == 2
    assert result['predictions'] == []
    assert not profile.exists()


def test_adapter_rejects_actual_loaded_model_class_schema(monkeypatch, tmp_path):
    fake_runtime(monkeypatch, tmp_path, classes=['pipe'])
    with pytest.raises(SchemaError):
        inference_server.GPUModel().load()


def test_adapter_rejects_cpu_only_session(monkeypatch, tmp_path):
    fake_runtime(monkeypatch, tmp_path, providers=['CPUExecutionProvider'])
    with pytest.raises(RuntimeError, match='CUDA session unavailable'):
        inference_server.GPUModel().load()


def test_adapter_rejects_provider_available_without_cuda_execution(monkeypatch, tmp_path):
    fake_runtime(monkeypatch, tmp_path, cuda_events=0)
    ok, png = cv2.imencode('.png', np.zeros((240, 320, 3), dtype=np.uint8))
    assert ok
    adapter = inference_server.GPUModel()
    with pytest.raises(RuntimeError, match='CUDA execution not proven'):
        adapter.infer(png.tobytes())
    assert adapter.model is None

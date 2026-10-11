import base64
import json
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/neptune_perception'))
from neptune_perception.backends import RoboflowBackend, decode_predictions


def test_box_conversion_and_invalid_response():
    p={'class':'pipe','x':20,'y':10,'width':60,'height':10,'confidence':.7}
    assert decode_predictions({'predictions':[p]},40,30)[0]['bbox']==[0,5,40.,15]
    with pytest.raises(ValueError): decode_predictions({},40,30)
    with pytest.raises(ValueError): decode_predictions({'predictions':[dict(p,confidence=float('nan'))]},40,30)
    with pytest.raises(ValueError): decode_predictions({'predictions':[dict(p,**{'class':'person'})]},40,30)
    with pytest.raises(ValueError): decode_predictions({'predictions':[],'image':{'width':640,'height':480}},40,30)


def test_lossless_payload_header_only_and_local_guard(tmp_path,monkeypatch):
    key=tmp_path/'key'; key.write_text('test-secret')
    with pytest.raises(ValueError): RoboflowBackend('https://serverless.roboflow.com','test',str(key))
    model=RoboflowBackend('http://localhost:9001','test',str(key))
    image=np.random.default_rng(42).integers(0,256,(30,40,3),dtype=np.uint8)
    calls=[]
    def request(route,payload,timeout):
        calls.append(payload)
        pixels=cv2.imdecode(np.frombuffer(base64.b64decode(payload['image']['value']),np.uint8),cv2.IMREAD_COLOR)
        assert np.array_equal(image,pixels)
        assert 'api_key' not in json.dumps(payload)
        assert payload['disable_active_learning'] is True
        return {'predictions':[]}
    monkeypatch.setattr(model,'request',request)
    assert model.infer(image,.25)==[]
    assert calls[0]['model_id']=='test'
    assert model._headers['Authorization']=='Bearer test-secret'

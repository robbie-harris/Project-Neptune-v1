import sys
from pathlib import Path
import numpy as np
import pytest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/neptune_sim'),str(ROOT/'src/neptune_perception'),str(ROOT/'src/tools')]
from neptune_sim.optics import validate_profile,native_request,applied_profile,DEFAULTS
from neptune_perception.backends import decode_predictions,annotate

def test_profile_acknowledgement_and_validation():
    p={**DEFAULTS,'natural':False,'water':'turbid','particles':True}
    v=native_request(p,1)
    assert applied_profile(v+[1])==p
    with pytest.raises(ValueError): applied_profile(v+[0])
    with pytest.raises(ValueError): validate_profile({**p,'lamps':'false'})
    with pytest.raises(ValueError): validate_profile({**p,'water':'NTU'})

def test_three_class_pixels_and_boxes():
    predictions=[{'class':c,'x':20,'y':20,'width':10,'height':12,'confidence':.8} for c in ('pipe','valve','flange')]
    detections=decode_predictions({'predictions':predictions},40,40)
    assert [d['class'] for d in detections]==['pipe','valve','flange']
    image=np.zeros((40,40,3),np.uint8)
    assert annotate(image,detections).any()
    assert not image.any()

def test_fixture_and_capture_scene_contract():
    scene=ET.parse(ROOT/'Simulation/scenarios/inspection_tank.scn').getroot()
    assert len(scene.findall('static'))==11
    names={obj.get('name'):obj for obj in scene.findall('static')}
    for name in ('InspectionValve','InspectionFlange'):
        assert names[name].find('physical/mesh') is not None
        assert names[name].find('visual/mesh') is not None
    for name in ('valve','flange'):
        assert '\nvn ' in (ROOT/'Simulation/assets'/f'{name}.obj').read_text()
    left=scene.find("robot/sensor[@name='CameraLeft']")
    mask=scene.find("robot/sensor[@name='CaptureInstances']")
    assert left.find('origin').attrib==mask.find('origin').attrib
    assert left.find('specs').attrib==mask.find('specs').attrib
    assert [float(l.find('specs').get('illuminance')) for l in scene.findall('robot/light')]==[800,800]

from inspection_dataset import boxes_from_mask,labels

def test_occluded_visible_masks_and_class_mapping():
    mask=np.zeros((40,60),dtype=np.uint16)
    mask[5:25,5:25]=21;mask[10:30,30:50]=22;mask[2:4,52:54]=23
    boxes=boxes_from_mask(mask,{'21':'Pipeline','22':'InspectionValve','23':'InspectionFlange'})
    assert boxes[0]['bbox']==[5,5,25,25] and boxes[0]['visible_pixels']==400
    assert boxes[1]['class']=='valve' and boxes[1]['eligible']
    assert boxes[2]['class']=='flange' and not boxes[2]['eligible']
    assert labels(boxes,60,40).splitlines()[1].startswith('1 ')
    with pytest.raises(ValueError): boxes_from_mask(mask,{'21':'Pipeline'})

from neptune_perception.backends import validate_model_names

def test_class_names_allow_provider_id_remapping_only():
    assert validate_model_names({0:'flange',1:'pipe',2:'valve'})
    assert validate_model_names({0:'pipe'})
    with pytest.raises(ValueError): validate_model_names({0:'pipe',1:'person'})
    with pytest.raises(ValueError): validate_model_names({0:'pipe',1:'pipe',2:'flange'})

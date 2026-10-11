import json
from xml.etree.ElementTree import fromstring
import pytest
from roboflow_annotations import prepare,voc
from roboflow_transfer import pack


def sample():
    return {'id':'view','image':'images/val/view.png','source':'stonefish','width':640,'height':480,'bbox':[10.5,20,300,250],'split':'val'}


def test_annotation_preserves_pixels_and_explicit_empty_negative():
    record=sample(); image={'filename':'view.png','id':'server-id','split':'valid'}
    request=prepare([record],[image],'workspace/neptune')[0][0]
    assert request['annotation_name']=='view.txt' and request['labelmap']=={'0':'pipe'}
    _,cx,cy,w,h=map(float,request['annotation_content'].split())
    assert (cx-w/2)*640==pytest.approx(10.5,abs=1e-4)
    assert (cy-h/2)*480==pytest.approx(20,abs=1e-4)
    with pytest.raises(ValueError,match='normalized YOLO'): voc(record)
    record['bbox']=None
    assert fromstring(voc(record)).findtext('size/width')=='640'
    assert not fromstring(voc(record)).findall('object')


def test_staging_refuses_split_changes_and_unauthorized_sources():
    record=sample(); image={'filename':'view.png','id':'server-id','split':'valid'}
    requests,report=prepare([record],[image],'workspace/neptune')
    assert len(requests)==1 and requests[0]['add_to_dataset']
    image['in_dataset']=True
    assert prepare([record],[image],'workspace/neptune')[1]['already_in_dataset']==1
    refreshed,_=prepare([record],[image],'workspace/neptune',refresh_all=True)
    assert len(refreshed)==1 and refreshed[0]['overwrite']
    image['split']='train'
    with pytest.raises(ValueError,match='split'): prepare([record],[image],'workspace/neptune')
    record['source']='cou'
    with pytest.raises(ValueError,match='authorized'): prepare([record],[image],'workspace/neptune')


def test_zip_never_stages_cou(tmp_path):
    record=sample(); record['source']='cou'
    (tmp_path/'manifest.jsonl').write_text(json.dumps(record)+'\n')
    with pytest.raises(ValueError,match='authorized'): pack(tmp_path,tmp_path/'upload.zip')
    assert not (tmp_path/'upload.zip').exists()

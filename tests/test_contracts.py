import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pytest
from geometry import rotation_rpy, camera_matrix, pipe_surface, projected_box, yolo_label, iou
from neptune_sim.protocol import command, active_command
ROOT=Path(__file__).resolve().parents[1]


def test_safety_invalid_and_stale_commands():
    assert command({'cmd':[2,-2,0.5]})==[1,-1,0.5]
    for cmd in [[float('nan'),0,0],[float('inf'),0,0],[0,0],None]:
        with pytest.raises((ValueError,TypeError)): command({'cmd':cmd})
    assert active_command([1,1,1],10,10.9)==[1,1,1]
    assert active_command([1,1,1],10,11)==[0,0,0]
    assert active_command([1,1,1],10,9)==[0,0,0]


def test_scene_sensor_and_boundary_contract():
    root=ET.parse(ROOT/'Simulation/scenarios/pipe_tank.scn').getroot()
    assert len(root.findall('static'))==7 # Six boundaries and one pipe.
    robot=root.find('robot'); assert robot.get('name')=='Neptune'
    assert robot.find('ros_base_link_transform').get('publish')=='true'
    sensors=robot.findall('sensor'); rates={s.get('name'):float(s.get('rate')) for s in sensors}
    assert rates=={'CameraLeft':10,'CameraRight':10,'CameraDown':10,'IMU':100,'Pressure':20,'DVL':10,'Sonar':10,'GroundTruth':100}
    for sensor in sensors:
        if sensor.get('type') not in ['camera']:
            assert sensor.find('noise') is not None
            for v in sensor.find('noise').attrib.values(): assert all(float(x)==0 for x in v.split())
    left=next(s for s in sensors if s.get('name')=='CameraLeft'); right=next(s for s in sensors if s.get('name')=='CameraRight')
    assert np.linalg.norm(np.fromstring(left.find('origin').get('xyz'),sep=' ')-np.fromstring(right.find('origin').get('xyz'),sep=' '))==pytest.approx(.12)
    for mesh in root.findall('.//mesh'):
        assert (ROOT/'Simulation/scenarios'/mesh.get('filename')).resolve().exists()


def test_geometry_visible_and_negative_views():
    rig=json.loads((ROOT/'Simulation/config/rig.json').read_text()); cam=rig['cameras']['left']
    T=np.eye(4); T[:3,:3]=rotation_rpy(cam['rpy']); T[:3,3]=np.array(rig['spawn']['xyz'])+cam['xyz']
    points=pipe_surface(rig['pipe']); box=projected_box(points,T,camera_matrix())
    assert box is not None and box[0]<320<box[2] and box[1]<240<box[3]
    _,cx,cy,w,h=map(float,yolo_label(box).split())
    assert 0<=cx<=1 and 0<=cy<=1 and 0<w<=1 and 0<h<=1
    assert T[:3,2]==pytest.approx([1,0,0]) # Camera looks forward, optical y is down.
    assert T[:3,1]==pytest.approx([0,0,1])
    backwards=np.eye(4); backwards[:3,:3]=rotation_rpy([0,0,np.pi])@T[:3,:3]; backwards[:3,3]=T[:3,3]
    assert projected_box(points,backwards,camera_matrix()) is None
    assert iou([0,0,10,10],[0,0,10,10])==1
    assert iou([0,0,10,10],[20,20,30,30])==0


def test_dataset_validation_rejects_missing_labels_and_split_leakage(tmp_path):
    from validate_dataset import validate
    records=[]
    for group,split in enumerate(['train','val','test']):
        for variant in range(2):
            key=f'g{group:03d}_v{variant:02d}'
            image=tmp_path/'images'/split/(key+'.png'); image.parent.mkdir(parents=True,exist_ok=True); image.write_bytes(key.encode())
            label=tmp_path/'labels'/split/(key+'.txt'); label.parent.mkdir(parents=True,exist_ok=True)
            label.write_text('0 0.5 0.5 0.2 0.2\n' if variant else '')
            records.append({'id':key,'group':group,'split':split,'bbox':[1,1,2,2] if variant else None,'image':str(image.relative_to(tmp_path))})
    manifest=tmp_path/'manifest.jsonl'
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    assert validate(tmp_path,expected=6)['images']==6
    records[2]['group']=0
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    with pytest.raises(ValueError,match='leaks'): validate(tmp_path,expected=6)
    records[2]['group']=1
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    train_image=tmp_path/records[0]['image']; val_image=tmp_path/records[2]['image']
    original=val_image.read_bytes(); val_image.write_bytes(train_image.read_bytes())
    with pytest.raises(ValueError,match='Duplicate image leaks'): validate(tmp_path,expected=6)
    val_image.write_bytes(original)
    records[2]['sha256']='wrong'
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    with pytest.raises(ValueError,match='hash mismatch'): validate(tmp_path,expected=6)
    del records[2]['sha256']
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    positive=tmp_path/'labels/train/g000_v01.txt'
    positive.write_text('0 0.99 0.5 0.2 0.2\n')
    with pytest.raises(ValueError,match='exceeds image'): validate(tmp_path,expected=6)
    positive.write_text('0 0.5 0.5 0.2 0.2\n0 0.25 0.25 0.1 0.1\n')
    assert validate(tmp_path,expected=6)['images']==6
    (tmp_path/'labels/test/g002_v01.txt').unlink()
    with pytest.raises(ValueError,match='Missing'): validate(tmp_path,expected=6)


def test_projection_clips_silhouette_before_bounding_rectangle():
    # Triangle's top point lies off-screen: clipping removes that y extreme.
    points=np.array([[-10.,0.,1.],[10.,10.,1.],[10.,20.,1.]])
    box=projected_box(points,np.eye(4),np.eye(3),width=20,height=30)
    assert box==pytest.approx([0,5,10,20])

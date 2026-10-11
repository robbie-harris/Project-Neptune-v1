import json
from collections import Counter
import numpy as np
import pytest
from geometry import projected_geometry,AmbiguousProjection
from orientation_views import orientation_views,replacement_view
from import_cou import clipped_box,sequence
from test_contracts import ROOT


def test_near_plane_clips_edges_and_never_silently_makes_negative():
    points=np.array([[0.,0.,-1.],[2.,0.,1.],[0.,2.,1.]])
    with pytest.raises(AmbiguousProjection): projected_geometry(points,np.eye(4),np.eye(3))
    result=projected_geometry(points,np.eye(4),np.eye(3),100,100,np.array([[0,1],[1,2],[2,0]]),near=.1)
    assert result['bbox']==pytest.approx([0,0,11,11])
    assert result['partial'] and result['visible_area']>0
    assert projected_geometry(points+[0,0,-3],np.eye(4),np.eye(3))['bbox'] is None


def test_sampling_group_quota_orientation_and_replacements():
    rig=json.loads((ROOT/'Simulation/config/rig.json').read_text()); views=list(orientation_views(rig,40))
    assert Counter(v['split'] for v in views)=={'train':280,'val':60,'test':60}
    assert Counter(v['split'] for v in views if not v['positive'])=={'train':70,'val':15,'test':15}
    assert set(v['angle_bin'] for v in views if v['positive'])==set(range(6))
    assert max(v['rpy'][0] for v in views)>2.8 and min(v['rpy'][0] for v in views)<-2.8
    for group in {v['group'] for v in views}: assert len({v['split'] for v in views if v['group']==group})==1
    positive=next(v for v in views if v['positive']); replacement=replacement_view(positive,rig,1)
    assert {k:replacement[k] for k in ['id','group','split','angle_bin']}=={k:positive[k] for k in ['id','group','split','angle_bin']}
    assert list(orientation_views(rig,40))==views


def test_coco_clipping_and_sequence_grouping():
    assert clipped_box({'bbox':[-5,10,20,30]},100,100)==[0,10,15,40]
    with pytest.raises(ValueError): clipped_box({'bbox':[110,0,5,5]},100,100)
    assert sequence('G18_0003.jpg')==sequence('G18_0031.jpg')=='G18'
    assert sequence('pooltrial_1_4773.jpg')=='pooltrial_1'

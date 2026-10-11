import json
from pathlib import Path
import numpy as np
import pytest
from neptune_sim.navigation import DeadReckoning, ReturnGuidance, agreement, quat, rpy, rotation, sensors_fresh
from neptune_sim.error_model import ErrorModel

ROOT=Path(__file__).parents[1]
SETTINGS=json.loads((ROOT/'Simulation/config/errors.json').read_text())
SPAWN={'xyz':[-3.8,0,1.5],'rpy':[0,0,0]}


def test_quaternion_rotation_agreement_and_dead_reckoning():
    angles=np.array([.1,.2,3.12]); assert rpy(quat(angles))==pytest.approx(angles)
    assert rotation([0,0,np.pi/2])@[1,0,0]==pytest.approx([0,1,0])
    dr=DeadReckoning(SPAWN); dr.dvl([1,0,0],0); dr.dvl([1,0,0],.1)
    assert dr.position==pytest.approx([-3.7,0,1.5])
    dr.gyro=np.array([0,1,0]); dr.dvl([.18,0,0],.2)
    assert dr.velocity==pytest.approx([0,0,0]) # lever arm correction
    result=agreement([.5,0,0],[0,0,0],[0,0,0],[0,0,0],SETTINGS['agreement'])
    assert result['pose_accuracy_percent']==50
    assert agreement([0,0,0],[0,0,np.pi],[0,0,0],[0,0,-np.pi],SETTINGS['agreement'])['pose_accuracy_percent']==pytest.approx(100)


def test_return_orientation_precedes_translation_and_safety():
    dr=DeadReckoning(SPAWN); dr.position[0]=-2.8; dr.attitude[2]=.5
    g=ReturnGuidance(SPAWN,SETTINGS['return']); g.start(0)
    cmd=g.step(dr,.1); assert g.state=='orient_initial' and cmd[0]==-cmd[1] and cmd[0]<0
    dr.attitude[2]=0; g.step(dr,.2); assert g.state=='translate'
    cmd=g.step(dr,.3); assert cmd[0]<0 and cmd[1]<0 # reverse home without 180-degree turn
    dr.position[2]=2; assert g.step(dr,.4)[2]>0 # go up, not down
    assert g.step(dr,.5,fresh=False)==[0,0,0] and g.state=='cancelled'
    g.start(0); assert g.step(dr,181)==[0,0,0] and 'timed out' in g.reason


def test_return_completion_requires_low_velocity_and_heading():
    dr=DeadReckoning(SPAWN); g=ReturnGuidance(SPAWN,SETTINGS['return']); g.start(0)
    g.step(dr,.1); g.step(dr,.2); dr.velocity[0]=.1
    g.step(dr,.3); assert g.state!='complete'
    dr.velocity[:]=0; dr.attitude[0]=.2
    g.step(dr,.4); assert g.state!='complete'
    dr.attitude[0]=0; assert g.step(dr,.5)==[0,0,0] and g.state=='complete'


def test_seeded_pixel_noise_and_camera_pair_timing():
    image=np.full((48,64,3),100,np.uint8)
    a,b=ErrorModel(SETTINGS),ErrorModel(SETTINGS)
    assert np.array_equal(a.camera(image,10,'left'),b.camera(image,10,'left'))
    assert not np.array_equal(a.camera(image,10,'left'),image)
    assert a.stamp_offset('left',10)==b.stamp_offset('left',10)
    assert a.stamp_offset('left',10)!=a.stamp_offset('right',10)


def test_lock_loss_hold_does_not_disable_stream_watchdog():
    settings=SETTINGS['return']; seen={'imu':10.,'pressure':10.,'dvl_stream':10.}
    assert sensors_fresh(10.1,seen,5.4,5.,settings)
    assert not sensors_fresh(10.1,seen,5.7,5.,settings)
    assert not sensors_fresh(10.8,seen,5.1,5.,settings)

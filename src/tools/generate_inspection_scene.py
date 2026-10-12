#!/usr/bin/env python3
"""Reproducible maintenance fixtures; Trimesh primitives, dimensions in metres."""
from pathlib import Path
import math
import copy
import xml.etree.ElementTree as ET
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]

def shifted(mesh, xyz):
    mesh.apply_translation(xyz)
    return mesh

def generate():
    if trimesh.__version__ != '4.6.8':
        raise RuntimeError('Install trimesh==4.6.8')
    assets = ROOT/'Simulation/assets'
    # Pipe axis is world Y. Fixtures are single joined meshes (one instance ID each).
    body = trimesh.creation.icosphere(subdivisions=3, radius=.31)
    body.apply_scale([.85, 1.15, 1.])
    stem = shifted(trimesh.creation.cylinder(radius=.055, height=.42, sections=32), [0,0,-.38])
    wheel = shifted(trimesh.creation.torus(major_radius=.24, minor_radius=.025), [0,0,-.62])
    hub = shifted(trimesh.creation.cylinder(radius=.06,height=.06),[0,0,-.62])
    parts = [body,stem,wheel,hub]
    for angle in (0, math.pi/2):
        spoke=trimesh.creation.box(extents=[.46,.025,.025])
        spoke.apply_transform(trimesh.transformations.rotation_matrix(angle,[0,0,1]))
        parts.append(shifted(spoke,[0,0,-.62]))
    trimesh.util.concatenate(parts).export(assets/'valve.obj',include_normals=True)
    parts=[]
    rot=trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0])
    for y in (-.045,.045):
        plate=trimesh.creation.annulus(r_min=.205,r_max=.33,height=.065,sections=64)
        plate.apply_transform(rot); parts.append(shifted(plate,[0,y,0]))
    for a in np.linspace(0,2*math.pi,8,endpoint=False):
        x,z=.275*math.cos(a),.275*math.sin(a)
        bolt=trimesh.creation.cylinder(radius=.018,height=.2,sections=16)
        bolt.apply_transform(rot);parts.append(shifted(bolt,[x,0,z]))
        for y in (-.105,.105):
            nut=trimesh.creation.cylinder(radius=.03,height=.035,sections=6)
            nut.apply_transform(rot);parts.append(shifted(nut,[x,y,z]))
    trimesh.util.concatenate(parts).export(assets/'flange.obj',include_normals=True)
    tree=ET.parse(ROOT/'Simulation/scenarios/pipe_tank.scn'); scene=tree.getroot()
    looks=scene.find('looks')
    for name,rgb in [('valve','0.18 0.48 0.65'),('flange','0.65 0.67 0.7')]:
        ET.SubElement(looks,'look',name=name,rgb=rgb,roughness='0.45')
    for name,mesh,xyz,look in [('InspectionValve','valve','4.4 -0.85 1.5','valve'),('InspectionFlange','flange','4.4 0.85 1.5','flange')]:
        obj=ET.SubElement(scene,'static',name=name,type='model')
        physical=ET.SubElement(obj,'physical'); ET.SubElement(physical,'mesh',filename=f'../assets/{mesh}.obj',scale='1',convex='false')
        ET.SubElement(physical,'origin',xyz='0 0 0',rpy='0 0 0')
        visual=ET.SubElement(obj,'visual'); ET.SubElement(visual,'mesh',filename=f'../assets/{mesh}.obj',scale='1')
        ET.SubElement(visual,'origin',xyz='0 0 0',rpy='0 0 0')
        ET.SubElement(obj,'material',name='Concrete');ET.SubElement(obj,'look',name=look)
        ET.SubElement(obj,'world_transform',xyz=xyz,rpy='0 0 0')
    for light in scene.findall('robot/light'):
        ET.SubElement(light,'ros_service',topic='/neptune/optics/'+light.get('name')+'/set_enabled')
    robot=scene.find('robot')
    mask=ET.SubElement(robot,'sensor',name='CaptureInstances',type='segmentation',rate='10')
    ET.SubElement(mask,'link',name='Vehicle')
    ET.SubElement(mask,'origin',xyz='0.62 -0.06 0',rpy='1.5707963267948966 0 1.5707963267948966')
    ET.SubElement(mask,'specs',resolution_x='640',resolution_y='480',horizontal_fov='80')
    ET.SubElement(mask,'rendering',minimum_distance='0.05',maximum_distance='20')
    ET.SubElement(mask,'ros_publisher',topic='/neptune/capture/instances',frame_id='Neptune/CameraLeft')
    ET.SubElement(mask,'ros_service',set_enabled='/neptune/capture/instances/set_enabled')
    # Distractors are structural supports, never targets or mislabeled negatives.
    for name,y in [('SupportLeft',-1.7),('SupportRight',1.7)]:
        obj=ET.SubElement(scene,'static',name=name,type='box')
        ET.SubElement(obj,'dimensions',xyz='0.12 0.12 1.25')
        ET.SubElement(obj,'material',name='Concrete'); ET.SubElement(obj,'look',name='panel')
        ET.SubElement(obj,'world_transform',xyz=f'4.65 {y} 2.35',rpy='0 0 0')
    ET.indent(tree,space='  ');tree.write(ROOT/'Simulation/scenarios/inspection_tank.scn',encoding='UTF-8',xml_declaration=True)
    for variant,scale in enumerate((.9,1.,1.1,1.2)):
        varied=copy.deepcopy(scene)
        for obj in varied.findall('static'):
            if obj.get('name') in ('InspectionValve','InspectionFlange'):
                for mesh in obj.findall('./*/mesh'):mesh.set('scale',str(scale))
        varied.find("looks/look[@name='valve']").set('rgb',('0.18 0.48 0.65','0.38 0.42 0.45','0.65 0.22 0.12','0.2 0.5 0.28')[variant])
        varied.find("looks/look[@name='flange']").set('roughness',str(.35+.15*variant))
        ET.ElementTree(varied).write(ROOT/f'Simulation/scenarios/inspection_variant_{variant}.scn',encoding='UTF-8',xml_declaration=True)

if __name__=='__main__': generate()

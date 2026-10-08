"""Blender integration checks. Synthetic geometry, never a game-asset acceptance test.
blender --background --factory-startup --python-exit-code 1 --python THIS -- --out new-dir
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
import bpy

p=Path(__file__).resolve().parents[1]/'blender_asset_probe.py'
s=importlib.util.spec_from_file_location('probe',p);probe=importlib.util.module_from_spec(s);s.loader.exec_module(probe)
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=.02)
mesh=bpy.context.object;mesh.name='TestMesh'
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='TestRig'
bone=rig.data.bones[0];bone.name='test_bone'
vg=mesh.vertex_groups.new(name=bone.name);vg.add(list(range(8)),1.,'REPLACE')
helper=mesh.vertex_groups.new(name='selection_only');helper.add(list(range(8)),3.,'REPLACE')
modifier=mesh.modifiers.new('Skin','ARMATURE');modifier.object=rig
rig.pose.bones[bone.name].rotation_mode='XYZ'
rig.pose.bones[bone.name].keyframe_insert('rotation_euler',frame=1)
rig.pose.bones[bone.name].rotation_euler[1]=.2
rig.pose.bones[bone.name].keyframe_insert('rotation_euler',frame=10)
action=rig.animation_data.action;action.name='TestRotation'
bpy.ops.object.camera_add(location=(.06,-.06,.04))
cam=bpy.context.object;cam.name='TestCamera'
from mathutils import Vector
cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.04
src=args.out/'test.blend';bpy.ops.wm.save_as_mainfile(filepath=str(src))
spec={'schema':'asset-probe/1','source':str(src),'coordinate':'test X right Y forward Z up','to_cm':[[100,0,0,0],[0,100,0,0],[0,0,100,0],[0,0,0,1]],
    'rigs':[{'id':'body','object':'TestRig'}],
    'meshes':[{'id':'body','object':'TestMesh','rig':'body','sections':[{'id':'slab','center_cm':[0,0,.117],'normal':[0,0,1],'half_thickness_cm':.4}]}],
    'frames':[{'id':'pose','clip':'TestRotation','frame':10,'actions':{'body':'TestRotation'}}],
    'views':[{'camera':'TestCamera','width':320,'height':320}]}
out=args.out/'measured';out.mkdir()
r=probe.run(spec,out);m=r['meshes']['body'];section=m['sections']['slab']
assert m['weights']['unweighted_vertices']==0 and m['weights']['weight_sum_max_error']<1e-6
assert m['weights']['groups_outside_deform_bones']==['selection_only']
assert abs(section['slices'][1]['area_cm2']-4)<1e-4,section
assert abs(section['slab_volume_estimate_cm3']-3.2)<1e-4,section
assert abs(r['frames'][0]['meshes']['body']['edge_stretch_max']-1)<1e-5
assert r['frames'][0]['views'] and (out/r['frames'][0]['views'][0]['file']).is_file()
# An open sheet cannot become a successful volume measurement.
area=probe.slice_area(probe.np.array([[0,0,-1],[1,0,1],[0,1,1]],float),probe.np.array([[0,1,2]]),[0,0,0],[0,0,1],1e-5)
assert area['area_cm2'] is None and not area['closed']
# Local section excludes a distant second body intersected by the same infinite plane.
verts=probe.np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)
tris=probe.np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
both=probe.np.vstack([verts,verts+[20,0,0]]);tt=probe.np.vstack([tris,tris+8])
local=probe.slice_area(both,tt,[0,0,.117],[0,0,1],.0001,3)
assert local['closed'] and abs(local['area_cm2']-4)<1e-5
(args.out/'checks.json').write_text(json.dumps({'checks':8,'passed':8,'scope':'synthetic Blender geometry/skin/action/render integration'}),'utf8')
print('BLENDER_PROBE_TESTS: 8 passed')

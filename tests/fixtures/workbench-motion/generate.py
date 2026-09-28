"""Blender-generated original shapes for browser integration, not game animation quality.
Run Blender --background --factory-startup --python generate.py -- OUTPUT_DIRECTORY.
"""
import bpy
import hashlib
import json
from pathlib import Path
import sys

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
if root.exists() and any(root.iterdir()):raise ValueError('Choose a new or empty fixture folder')
root.mkdir(parents=True,exist_ok=True);game=root/'game';game.mkdir()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='ReviewRig';rig.data.bones[0].name='Root'
bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=(0,0,1));body=bpy.context.object
body.name='OriginalTestBody';body.scale=(.3,.3,1)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
group=body.vertex_groups.new(name='Root');group.add(list(range(len(body.data.vertices))),1,'REPLACE')
body.parent=rig;modifier=body.modifiers.new('Skin','ARMATURE');modifier.object=rig
material=bpy.data.materials.new('TestBlue');material.diffuse_color=(.15,.4,.8,1);body.data.materials.append(material)
bone=rig.pose.bones['Root'];bone.rotation_mode='XYZ'
for frame,angle in [(1,0),(12,.6),(24,0)]:
    bone.rotation_euler=(0,angle,0);bone.keyframe_insert('rotation_euler',frame=frame)
rig.animation_data.action.name='Swing';bpy.context.scene.frame_end=24
bpy.ops.export_scene.fbx(filepath=str(game/'character.fbx'),object_types={'ARMATURE','MESH'},add_leaf_bones=False)
bpy.ops.export_scene.fbx(filepath=str(game/'attack.fbx'),object_types={'ARMATURE','MESH'},add_leaf_bones=False)
bpy.ops.export_scene.gltf(filepath=str(game/'native-preview.glb'),export_format='GLB')
bpy.ops.export_scene.fbx(filepath=str(root/'motion-only.fbx'),object_types={'ARMATURE'},add_leaf_bones=False)
bpy.ops.export_scene.gltf(filepath=str(root/'candidate.gltf'),export_format='GLTF_SEPARATE')
document=json.loads((root/'candidate.gltf').read_text('utf-8'))
document['animations']=[{**document['animations'][0],'name':name} for name in ('Swing','Swing','Recover')]
(root/'candidate.gltf').write_text(json.dumps(document),'utf-8')
# Synthetic opaque resource tests only the mapping protocol; it is explicitly not an Unreal asset.
(game/'mapped-native.uasset').write_bytes(b'OAGD synthetic browser mapping fixture; not a loadable UE asset')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=root/'.asset-browser';meta.mkdir()
mapping={'version':1,'assets':{'game/mapped-native.uasset':{'path':'game/native-preview.glb',
    'source_sha256':digest(game/'mapped-native.uasset'),'sha256':digest(game/'native-preview.glb'),
    'note':'自制关联预览接口测试；不是 Unreal 原生运行验证'}}}
(meta/'previews.json').write_text(json.dumps(mapping),'utf-8')
deps={name:digest(root/name) for name in ('game/character.fbx','game/attack.fbx','game/mapped-native.uasset')}
characters=[{'id':role,'title':title,'role':role,'model':'game/character.fbx',
    'actions':[{'label':'FBX Swing','path':'game/attack.fbx'},{'label':'关联预览 Swing','path':'game/mapped-native.uasset'}],
    'dependencies':deps,'note':'工具包自制测试夹具；用于验证角色上下文，不是游戏成品'}
    for role,title in [('player','测试主角'),('boss','测试 Boss')]]
(meta/'characters.json').write_text(json.dumps({'version':1,'characters':characters},ensure_ascii=False),'utf-8')
print('Generated original workbench fixture:',root)

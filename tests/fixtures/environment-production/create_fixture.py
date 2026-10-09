"""Create a tiny original scene for actual Blender audit/bake/export/capture tests."""
import bpy
import json
from pathlib import Path
import sys

output=Path(sys.argv[sys.argv.index('--')+1]).resolve()
output.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=1)
plane=bpy.context.object;plane.name='Surface';plane.scale=(2,1,1)
image=bpy.data.images.new('ColorGrid',width=256,height=256)
image.generated_type='COLOR_GRID';image.filepath_raw=str(output/'grid.png');image.file_format='PNG';image.save();image.pack()
mat=bpy.data.materials.new('SurfaceMaterial');mat.use_nodes=True
nodes=mat.node_tree.nodes;links=mat.node_tree.links
texture=nodes.new('ShaderNodeTexImage');texture.image=image
mapping=nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(2,2,1)
coords=nodes.new('ShaderNodeTexCoord');links.new(coords.outputs['UV'],mapping.inputs['Vector'])
links.new(mapping.outputs[0],texture.inputs['Vector']);links.new(texture.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
nodes.get('Principled BSDF').inputs['Roughness'].default_value=.4
nodes.get('Principled BSDF').inputs['Metallic'].default_value=.2
plane.data.materials.append(mat)
bpy.ops.object.light_add(type='AREA',location=(0,0,3));bpy.context.object.data.energy=200
bpy.context.scene.world=bpy.data.worlds.new('World');bpy.context.scene.world.use_nodes=True
bpy.context.scene.view_settings.view_transform='Standard'
bpy.ops.wm.save_as_mainfile(filepath=str(output/'source.blend'))
request={'schema':'blender-environment/1','source':str(output/'source.blend'),'coordinate':'+X right,+Y forward,+Z up',
         'meters_per_unit':1,'objects':['Surface']}
for operation in ('audit','export','bake'):
 r={**request,'operation':operation}
 if operation=='bake':r.update(channels=['base_color','roughness','metallic','normal'],resolution=64,samples=1,uv_layout_reviewed=True)
 (output/(operation+'.json')).write_text(json.dumps(r,indent=2),'utf8')
plan={'schema':'environment-views/1','revision':'fixture','engine':'blender','scene':'fixture','coordinate':request['coordinate'],
      'unit':'m','rotation_order':'XYZ','resolution':[160,120],
      'conditions':{'render_engine':'CYCLES','exposure':0,'view_transform':'Standard','frame':1},
      'dependencies':['source.blend'], 'views':[{'id':'surface','position':[0,0,3],'rotation_deg':[0,0,0],'fov_deg':55}]}
(output/'views.json').write_text(json.dumps(plan,indent=2),'utf8')
(output/'capture.json').write_text(json.dumps({**request,'operation':'capture','plan':str(output/'views.json'),'samples':1},indent=2),'utf8')

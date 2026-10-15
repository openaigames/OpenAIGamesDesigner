"""Original engineering portal fixture, authored in an isolated Blender process."""
import bpy,json,sys,hashlib
from pathlib import Path
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=False)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
materials=[]
for name,color,rough,metal in [('Stone',(.32,.45,.58,1),.8,0),('Trim',(.9,.47,.12,1),.3,.6)]:
 m=bpy.data.materials.new(name);m.use_nodes=True;m.use_backface_culling=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=color;n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;materials.append(m)
objects=[]
def block(name,size,pos,mat,bevel=.03):
 # glTF X,Y,Z -> Blender X,-Z,Y.
 bpy.ops.mesh.primitive_cube_add(size=1,location=(pos[0],-pos[2],pos[1]));o=bpy.context.object;o.name=name;o.dimensions=(size[0],size[2],size[1]);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(materials[mat]);mod=o.modifiers.new('Crafted_edges','BEVEL');mod.width=bevel;mod.segments=6;bpy.ops.object.modifier_apply(modifier=mod.name);objects.append(o)
# Same 2.4 x 2.5 metre opening as the generated-scene example; blocks are outside that clearance.
for side in (-1,1):
 for i in range(6):block('Stone', [.3,.5,2], [.1,.25+i*.5,side*2.2],0)
 block('Trim',[.4,2.5,.12],[.1,1.25,side*1.26],1,.012)
for i in range(8):block('Lintel',[.3,.5,.8],[.1,2.75,-2.8+i*.8],0)
block('TopTrim',[.4,.10,6.4],[.1,2.91,0],1,.015)
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();o=bpy.context.object;o.name='Portal'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
o.data.calc_loop_triangles();triangles=len(o.data.loop_triangles)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'portal.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'portal.glb'),export_format='GLB',use_selection=True,export_animations=False,export_yup=True)
(out/'source-report.json').write_text(json.dumps({'blender':bpy.app.version_string,'triangles':triangles,'materials':['Stone','Trim'],'source':'Original engineering calibration portal, not final art','license':'Toolkit LICENSE','glb_sha256':hashlib.sha256((out/'portal.glb').read_bytes()).hexdigest()},indent=2))

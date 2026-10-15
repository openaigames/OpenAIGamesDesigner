"""Blender: derive two planar technical examples from the adopted Cesium revision.
Usage: blender -b --python this.py -- BASE_REVISION NEW_OUTPUT
No runtime actor displacement is authored in code: these are actual keyed bone tracks.
"""
import bpy,sys,math,json,hashlib
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
base,out=map(Path,sys.argv[sys.argv.index('--')+1:]);out.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.open_mainfile(filepath=str(base/'idle.blend'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
names=[b.name for b in rig.data.bones];parents={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
idle={p.name:rig.matrix_world@p.matrix for p in rig.pose.bones}
world_inverse=rig.matrix_world.inverted()
hips='Skeleton_torso_joint_1';root='motion_root'
assert root in names and hips in names,'This author example explicitly targets adopted Cesium; other characters need authored clips'
rest={n:rig.data.bones[n].matrix_local.copy() for n in names}
local={n:idle[parents[n]].inverted()@idle[n] if parents[n] else idle[n].copy() for n in names}
rig.animation_data_clear()
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
scene.render.fps=30;scene.frame_start=1
for name,duration,distance in [('dash',1.0,2.4),('roll',1.2,2.0)]:
 action=bpy.data.actions.new(name);action.use_fake_user=True
 rig.animation_data_create();rig.animation_data.action=action
 count=round(duration*30)+1;scene.frame_end=count
 previous={}
 for i in range(count):
  scene.frame_set(i+1);t=i/(count-1);ease=t*t*(3-2*t);envelope=math.sin(math.pi*t)**2
  poses={}
  for n in names:
   parent=parents[n];m=poses[parent]@local[n] if parent else idle[n].copy()
   delta=0.0
   if name=='dash':
    if n==hips:delta=.20*envelope
    if n=='Skeleton_arm_joint_R':delta=-1.35*envelope
    if n=='Skeleton_arm_joint_R__2_':delta=-.65*envelope
    if n=='leg_joint_L_1':delta=-.5*envelope
    if n=='leg_joint_R_1':delta=.45*envelope
   else:
    if n==hips:delta=2*math.pi*ease
    if n in ('leg_joint_L_1','leg_joint_R_1'):delta=-1.25*envelope
    if n in ('leg_joint_L_2','leg_joint_R_2'):delta=2.25*envelope
    if n in ('Skeleton_arm_joint_R','Skeleton_arm_joint_L__4_'):delta=-1.25*envelope
    if n in ('Skeleton_arm_joint_R__2_','Skeleton_arm_joint_L__3_'):delta=-1.6*envelope
   if delta:
    # Joint rotation about the authored global sagittal axis, carried with hips.
    axis=Vector((1,0,0))
    if n!=hips and name=='roll':axis=poses[hips].to_quaternion()@idle[hips].to_quaternion().inverted()@axis
    rotation=Quaternion(axis,delta).to_matrix().to_4x4();position=m.translation.copy()
    m=rotation@m;m.translation=position
   if n==root:m.translation+=Vector((0,-distance*ease,0))
   if n==hips and name=='roll':m.translation.z-=.24*envelope
   poses[n]=m
   pb=rig.pose.bones[n];pb.rotation_mode='QUATERNION';pb.matrix=world_inverse@m
   if n in previous and previous[n].dot(pb.rotation_quaternion)<0:pb.rotation_quaternion=-pb.rotation_quaternion
   previous[n]=pb.rotation_quaternion.copy()
   for channel in ('location','rotation_quaternion','scale'):pb.keyframe_insert(channel,frame=i+1,group=n)
   bpy.context.view_layer.update()
  # Calibrate source mesh ground contact, without putting vertical displacement
  # on the root track. This is authored hip translation, not runtime foot IK.
  deps=bpy.context.evaluated_depsgraph_get();low=float('inf')
  for obj in bpy.context.scene.objects:
   if obj.type!='MESH':continue
   evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
   low=min(low,min((evaluated.matrix_world@v.co).z for v in mesh.vertices));evaluated.to_mesh_clear()
  if math.isfinite(low):
   pb=rig.pose.bones[hips];m=rig.matrix_world@pb.matrix;m.translation.z+=.002-low;pb.matrix=world_inverse@m
   pb.keyframe_insert('location',frame=i+1,group=hips);bpy.context.view_layer.update()
 for layer in action.layers:
  for strip in layer.strips:
   bag=strip.channelbag(rig.animation_data.action_slot)
   if bag:
    for curve in bag.fcurves:
     for key in curve.keyframe_points:key.interpolation='LINEAR'
rig.animation_data.action=bpy.data.actions['dash'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'root-source.blend'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec={'schema':'oagd.motion/1','source':{'file':'root-source.blend','sha256':digest(out/'root-source.blend'),'armature':rig.name},'target':{'file':str(base/'idle.blend'),'sha256':digest(base/'idle.blend'),'armature':rig.name},'mapping':{n:n for n in names},'alignment_xyzw':[0,0,0,1],'root_motion':{'owner':'animation','translation':'scaled','scale':1,'bone':root,'translation_bones':[n for n in names if n!=root]},'tolerances':{'contact_m':.002},'clips':[{'id':n,'action':n,'start_frame':1,'end_frame':round(d*30)+1,'fps':30,'repairs':{}} for n,d in [('dash',1.),('roll',1.2)]]}
(out/'motion.json').write_text(json.dumps(spec,indent=2))
(out/'provenance.json').write_text(json.dumps({'base':str(base),'idle_sha256':digest(base/'idle.blend'),'author_script_sha256':digest(Path(__file__)),'kind':'new technical sample animation on adopted Cesium mesh, not mocap or finished combat animation'},indent=2))
print('ROOT_AUTHOR_OK',rig.name)

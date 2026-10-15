"""Author hold/carry on the adopted Cesium body. Preserve mesh, weights and lower-body animation.
blender -b --python author_grip_sample.py -- BASE_REVISION NEW_OUTPUT
"""
import bpy,sys,json,hashlib,math
from pathlib import Path
from mathutils import Vector,Quaternion
base,out=map(Path,sys.argv[sys.argv.index('--')+1:]);out.mkdir(parents=True,exist_ok=False)
samples={};durations={}
for action,source in [('hold','idle'),('carry','walk')]:
 bpy.ops.wm.open_mainfile(filepath=str(base/(source+'.blend')))
 rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
 count=scene.frame_end-scene.frame_start+1;durations[action]=(count-1)/scene.render.fps;samples[action]=[]
 for frame in range(scene.frame_start,scene.frame_end+1):
  scene.frame_set(frame);bpy.context.view_layer.update();samples[action].append({p.name:(rig.matrix_world@p.matrix).copy() for p in rig.pose.bones})
bpy.ops.wm.open_mainfile(filepath=str(base/'idle.blend'));rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
names=[b.name for b in rig.data.bones];inverse=rig.matrix_world.inverted();parents={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
rig.animation_data_clear()
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
for name,frames in samples.items():
 action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=action
 scene.render.fps=30;scene.frame_start=1;scene.frame_end=len(frames)
 for f,pose in enumerate(frames,1):
  scene.frame_set(f)
  for side,chain in [('R',['Skeleton_arm_joint_R','Skeleton_arm_joint_R__2_','Skeleton_arm_joint_R__3_']),('L',['Skeleton_arm_joint_L__4_','Skeleton_arm_joint_L__3_','Skeleton_arm_joint_L__2_'])]:
   a,b,c=[pose[n].copy() for n in chain];start=a.translation;end=Vector((-.16 if side=='R' else .16,-.30,1.03))
   # Carry follows the small authored torso translation, while keeping hands in front.
   end.z+=pose['torso_joint_3'].translation.z-1.2764958
   l1=(b.translation-start).length;l2=(c.translation-b.translation).length;d=(end-start).length;aim=(end-start).normalized()
   pole=Vector((-.7 if side=='R' else .7,0,-.7));bend=(pole-aim*pole.dot(aim)).normalized();x=(l1*l1-l2*l2+d*d)/(2*d)
   elbow=start+aim*x+bend*math.sqrt(max(0,l1*l1-x*x))
   qa=(b.translation-start).rotation_difference(elbow-start);qb=(c.translation-b.translation).rotation_difference(end-elbow)
   for m,q,pos in [(a,qa,start),(b,qb,elbow),(c,qb,end)]:
    scale=m.to_scale();m_new=q.to_matrix().to_4x4()@m;m_new.translation=pos
    pose[chain[0] if m is a else chain[1] if m is b else chain[2]]=m_new
  for n in names:
   p=rig.pose.bones[n];p.rotation_mode='QUATERNION';p.matrix=inverse@pose[n];bpy.context.view_layer.update()
   for channel in ('location','rotation_quaternion','scale'):p.keyframe_insert(channel,frame=f,group=n)
rig.animation_data.action=bpy.data.actions['hold'];scene.frame_start=1;scene.frame_end=len(samples['hold']);scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'grip-source.blend'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec={'schema':'oagd.motion/1','source':{'file':'grip-source.blend','sha256':digest(out/'grip-source.blend'),'armature':rig.name},'target':{'file':str(base/'idle.blend'),'sha256':digest(base/'idle.blend'),'armature':rig.name},'mapping':{n:n for n in names},'alignment_xyzw':[0,0,0,1],'root_motion':{'owner':'controller','translation':'in_place','scale':1,'bone':'motion_root','translation_bones':[n for n in names if n!='motion_root']},'tolerances':{'contact_m':.002},'clips':[{'id':n,'action':n,'start_frame':1,'end_frame':len(samples[n]),'fps':30,'repairs':{}} for n in samples]}
(out/'motion.json').write_text(json.dumps(spec,indent=2));(out/'provenance.json').write_text(json.dumps({'base':str(base),'inputs':{n:digest(base/(n+'.blend')) for n in ('idle','walk')},'script':digest(Path(__file__)),'kind':'authored technical hold/carry, same adopted body and weights'},indent=2))

"""Original editable technical mannequin + animation source. Run in Blender.
Simple segmented skin is intentional; these clips test integration, not finished character art.
"""
import bpy, json, math, hashlib, sys
from pathlib import Path
from mathutils import Quaternion, Vector, Matrix

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
names=['root','hips','spine','head']+[n+'_'+s for s in ('L','R') for n in ('thigh','shin','foot','upperarm','forearm','hand')]
def build(target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefix='dst_' if target else 'src_';name='TargetRig' if target else 'SourceRig'
    data=bpy.data.armatures.new(name);rig=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    points=[('root',None,(0,0,0),(0,0,.1)),('hips','root',(0,0,.98),(0,0,1.12)),('spine','hips',(0,0,1.12),(0,0,1.48)),('head','spine',(0,0,1.48),(0,0,1.78))]
    for side,x in [('L',1),('R',-1)]:
        points += [(f'thigh_{side}','hips',(.14*x,0,.98),(.14*x,-.08,.55)),(f'shin_{side}',f'thigh_{side}',(.14*x,-.08,.55),(.14*x,0,.06)),
            (f'foot_{side}',f'shin_{side}',(.14*x,0,.06),(.14*x,-.22,.06)),(f'upperarm_{side}','spine',(.22*x,0,1.45),(.39*x,0,1.16)),
            (f'forearm_{side}',f'upperarm_{side}',(.39*x,0,1.16),(.44*x,-.04,.87)),(f'hand_{side}',f'forearm_{side}',(.44*x,-.04,.87),(.46*x,-.05,.74))]
    for n,parent,head,tail in points:
        b=data.edit_bones.new(prefix+n);b.head=head;b.tail=tail
        if target: b.roll=.13 if n.endswith('L') else -.09
        if parent:b.parent=data.edit_bones[prefix+parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for n,_,_,_ in points:
        if n=='root':continue
        b=data.bones[prefix+n]
        bpy.ops.mesh.primitive_cube_add(size=1,location=(b.head_local+b.tail_local)/2)
        obj=bpy.context.object;obj.name='skin_'+n;obj.rotation_mode='QUATERNION';obj.rotation_quaternion=b.matrix_local.to_quaternion()
        width=.26 if n=='head' else .31 if n in ('hips','spine') else .10
        obj.scale=(width,b.length,.17 if n in ('head','spine','hips') else .10)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        obj.parent=rig;obj.modifiers.new('Skin','ARMATURE').object=rig
        obj.vertex_groups.new(name=prefix+n).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        material=bpy.data.materials.new(n);material.diffuse_color=(.05,.48,.72,1) if not n.endswith('R') else (.95,.44,.10,1)
        material.use_nodes=True;material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=material.diffuse_color;obj.data.materials.append(material)
    bpy.context.scene.render.fps=30
    # Explicit anatomical front is Blender -Y (the same direction as the toes).
    # Facial features and a chest panel make this visible without reading axes.
    for part,bone,center,size,color in [
        ('nose','head',(0,-.145,1.63),(.065,.12,.07),(.96,.89,.65,1)),
        ('eye_L','head',(.065,-.096,1.69),(.035,.025,.035),(.015,.025,.035,1)),
        ('eye_R','head',(-.065,-.096,1.69),(.035,.025,.035),(.015,.025,.035,1)),
        ('chest_front','spine',(0,-.101,1.32),(.14,.035,.16),(.92,.95,.98,1))]:
        bpy.ops.mesh.primitive_cube_add(size=1,location=center);obj=bpy.context.object;obj.name=part;obj.scale=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        obj.parent=rig;obj.modifiers.new('Skin','ARMATURE').object=rig
        obj.vertex_groups.new(name=prefix+bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        material=bpy.data.materials.new(part);material.diffuse_color=color;material.use_nodes=True
        material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color;obj.data.materials.append(material)
    return rig

rig=build(True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'target.blend'))
rig=build(False)
def rotate(name,axis,angle):
    b=rig.pose.bones['src_'+name];local_axis=b.bone.matrix_local.to_quaternion().inverted()@Vector(axis)
    b.rotation_quaternion=Quaternion(local_axis,angle)

def leg(side,y,height=0):
    # Authored gait: exact two-bone positions and a flat foot during stance.
    # No runtime IK or floor proxy masquerades as evaluated skin evidence.
    upper=rig.pose.bones['src_thigh_'+side];lower=rig.pose.bones['src_shin_'+side];foot=rig.pose.bones['src_foot_'+side]
    bpy.context.view_layer.update()
    hip=upper.matrix.translation.copy();knee=lower.matrix.translation.copy();ankle=foot.matrix.translation.copy()
    goal=Vector((.14 if side=='L' else -.14,y,.06+height));a=(knee-hip).length;b=(ankle-knee).length
    direction=goal-hip;distance=direction.length
    if distance>=a+b:raise RuntimeError('Authored stride exceeds leg reach')
    axis=direction.normalized();pole=Vector((0,-1,0));bend=(pole-axis*pole.dot(axis)).normalized()
    along=(a*a-b*b+distance*distance)/(2*distance);desired=hip+axis*along+bend*math.sqrt(max(0,a*a-along*along))
    upper.matrix=Matrix.LocRotScale(hip,(knee-hip).rotation_difference(desired-hip)@upper.matrix.to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update();knee=lower.matrix.translation.copy()
    lower.matrix=Matrix.LocRotScale(knee,(foot.matrix.translation-knee).rotation_difference(goal-knee)@lower.matrix.to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update();foot.matrix=Matrix.LocRotScale(goal,foot.bone.matrix_local.to_quaternion(),Vector((1,1,1)));bpy.context.view_layer.update()

clips=[('idle',2.0,True),('walk',1.0,True),('run',.6,True),('jump',.4,False),('fall',.6,True),('land',.3,False),('action',1.2,False),('action_v2',1.2,False)]
for ident,duration,loop in clips:
    rig.animation_data_create();rig.animation_data.action=None
    count=round(duration*30)
    for frame in range(count+1):
        t=frame/30;p=t/duration
        for pb in rig.pose.bones:pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
        hips=rig.pose.bones['src_hips'];hips.location=hips.bone.matrix_local.to_quaternion().inverted()@Vector((0,0,-.10))
        if ident in ('walk','run'):
            amp=.36 if ident=='walk' else .65
            for side,offset in [('L',0),('R',math.pi)]:
                phase=2*math.pi*p+offset
                # Opposite arm to the forward leg; elbow flexion goes toward -Y.
                rotate('upperarm_'+side,(1,0,0),amp*.65*math.cos(phase))
                rotate('forearm_'+side,(1,0,0),-.24 if ident=='walk' else -.8)
        elif ident=='idle':rotate('spine',(1,0,0),.015*math.sin(2*math.pi*p))
        elif ident in ('jump','fall','land'):
            bend=math.sin(math.pi*p)*.4 if ident!='fall' else .25
            for side in ('L','R'):
                rotate('thigh_'+side,(1,0,0),bend);rotate('shin_'+side,(1,0,0),-bend*1.5)
                rotate('upperarm_'+side,(1,0,0),-.35)
        else:
            envelope=math.sin(math.pi*p)**2
            # Raising a downward arm around -X moves it toward anatomical -Y.
            # Shoulder flexion and elbow flexion share the sagittal plane.
            rotate('upperarm_R',(1,0,0),(-1.0 if ident=='action' else -1.15)*envelope)
            rotate('forearm_R',(1,0,0),(-.55 if ident=='action' else -.40)*envelope)
            rotate('head',(0,0,1),-.25*envelope)
            # A known isolated defect exercises the real motion repair path.
            if frame==18 and ident=='action':rotate('forearm_R',(1,0,0),1.8)
        for side,offset in [('L',0),('R',.5)]:
            y=0;height=0
            if ident in ('walk','run'):
                phase=(p+offset)%1;speed=1 if ident=='walk' else 2.5;half=speed*duration/4
                if phase<=.5:y=-half+4*half*phase
                else:
                    swing=(phase-.5)*2;y=half*math.cos(math.pi*swing);height=(.14 if ident=='walk' else .24)*math.sin(math.pi*swing)
            elif ident in ('jump','fall'):
                height=.12*math.sin(math.pi*p) if ident=='jump' else .12
            leg(side,y,height)
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_quaternion',frame=frame+1);pb.keyframe_insert('location',frame=frame+1)
    rig.animation_data.action.name=ident;rig.animation_data.action.use_fake_user=True
rig.animation_data.action=None
for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'source.blend'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec={'schema':'oagd.motion/1','source':{'file':'source.blend','armature':'SourceRig','sha256':sha(out/'source.blend')},'target':{'file':'target.blend','armature':'TargetRig','sha256':sha(out/'target.blend')},
 'mapping':{'dst_'+n:'src_'+n for n in names},'alignment_xyzw':[0,0,0,1],
 'root_motion':{'bone':'dst_root','owner':'controller','translation':'in_place','scale':1,'translation_bones':['dst_hips']},'tolerances':{'contact_m':.002},'clips':[]}
binding={'schema':'oagd.playback/1','revision':'original-mannequin-r03','root_bone':'dst_root','default_action':'action_v2','character_scene':'character_r03.tscn','unreal_root':'/Game/PlaybackR03','clips':[]}
for ident,duration,loop in clips:
    repairs={'rotation_spikes':{'bones':['dst_forearm_R'],'threshold_deg':50,'neighbor_deg':10}} if ident=='action' else {}
    spec['clips'].append({'id':ident,'action':ident,'start_frame':1,'end_frame':round(duration*30)+1,'fps':30,'repairs':repairs})
    binding['clips'].append({'id':ident,'clip':ident,'loop':loop,'motion_owner':'controller','in_place':True,'duration_s':duration,'markers':[{'name':'pulse','at_s':.65}] if ident.startswith('action') else []})
for name,value in [('motion.json',spec),('bindings.json',binding),('provenance.json',{'source':'Original authored segmented mannequin and parameterized technical animation','license':'MIT; repository LICENSE','scope':'Prototype integration fixture. Flat ground stance: left phase 0..0.5, right phase 0.5..1; exclude 0.12s state transition and turns. Walk 1m/s, run 2.5m/s. No terrain IK or production character quality claim.','source_sha256':sha(out/'source.blend'),'target_sha256':sha(out/'target.blend')})]:
    (out/name).write_text(json.dumps(value,indent=2),encoding='utf-8')

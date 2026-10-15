"""Blender 4.5+ worker: explicit rest-relative retargeting and constrained repairs.

Invoked by tools/motion_workflow.py. All mutations are in a new Blender process.
"""
import bpy
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
import sys
from mathutils import Matrix, Quaternion, Vector

VERSION='0.2.0'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def quat(q):return Quaternion((q[3],q[0],q[1],q[2]))
def xyzw(q):return [q.x,q.y,q.z,q.w]
def angle(a,b):return math.degrees(a.rotation_difference(b).angle if a.dot(b)>=0 else a.rotation_difference(-b).angle)
def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix=Path(path).suffix.lower()
    if suffix=='.blend':bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    elif suffix=='.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path),automatic_bone_orientation=False)
        # FBX has joint transforms, not Blender's connected-bone constraint.
        # The importer can connect a lone child while estimating bone lengths;
        # that suppresses valid child translation keys (e.g. pelvis bob).
        # Preserve hierarchy/rest transforms but allow the file's actual motion.
        for rig in [o for o in bpy.context.scene.objects if o.type=='ARMATURE']:
            bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
            bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
            for bone in rig.data.edit_bones:bone.use_connect=False
            bpy.ops.object.mode_set(mode='OBJECT')
    elif suffix=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:raise ValueError('Unsupported rig file')


def bones_order(rig):
    return sorted(rig.data.bones,key=lambda b:len(b.parent_recursive))


def rig_named(name):
    rig=bpy.data.objects.get(name)
    if rig is None or rig.type!='ARMATURE':raise ValueError('Armature not found: '+name)
    if rig.parent:raise ValueError('Export a standalone armature; parent transforms are not supported')
    s=rig.matrix_world.to_scale()
    if min(s)<=0 or max(s)-min(s)>1e-5 or rig.matrix_world.determinant()<=0:
        raise ValueError('Armature requires positive uniform scale; normalize a source copy first')
    return rig


def actions_for(rig):
    # Keep source action selection explicit, including modern layered action slots.
    return [a for a in bpy.data.actions if a.id_root in ('OBJECT','') or len(a.slots)]


def choose(rig,name):
    action=bpy.data.actions.get(name)
    if not action:raise ValueError('Source Action not found: '+name)
    rig.animation_data_create();rig.animation_data.action=action
    if action.slots:
        slots=[s for s in action.slots if s.target_id_type=='OBJECT']
        named=[s for s in slots if s.name_display==rig.name or s.identifier=='OB'+rig.name]
        if len(named)==1:slot=named[0]
        elif len(slots)==1:slot=slots[0]
        else:raise ValueError('Ambiguous Action slots; export a single-rig Action')
        rig.animation_data.action_slot=slot
    for track in rig.animation_data.nla_tracks:track.mute=True


def rest_data(rig):
    return {b.name:{'parent':b.parent.name if b.parent else None,'m':rig.matrix_world@b.matrix_local,
                    'length':b.length*rig.matrix_world.to_scale().x} for b in bones_order(rig)}


def inventory(path):
    load(path);rigs=[]
    for rig in [o for o in bpy.context.scene.objects if o.type=='ARMATURE']:
        rest=rest_data(rig)
        rigs.append({'name':rig.name,'bones':[{'name':n,'parent':b['parent'],'head_m':list(b['m'].translation),
                      'rest_xyzw':xyzw(b['m'].to_quaternion()),'length_m':b['length']} for n,b in rest.items()],
                     'actions':[{'name':a.name,'frames':list(a.frame_range)} for a in actions_for(rig)],
                     'meshes':[o.name for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]})
    if not rigs:raise ValueError('No armature in asset; automatic rigging is outside this tool')
    return {'ok':True,'schema':'oagd.rig-inventory/1','file':str(path),'sha256':sha(path),'blender':bpy.app.version_string,
            'coordinates':'Blender world metres Z-up; object transforms included','scene_fps':bpy.context.scene.render.fps/bpy.context.scene.render.fps_base,
            'rigs':rigs,'mapping':'explicit_target_to_source_required'}


def fk(rest,local,root,translation,offsets=None):
    result={}
    for n,b in rest.items():
        parent=b['parent'];base=(result[parent]@rest[parent]['m'].inverted()@b['m']) if parent else b['m'].copy()
        if offsets and n in offsets:base=base@Matrix.Translation(offsets[n])
        base=base@local[n].to_matrix().to_4x4()
        if n==root:base.translation+=translation
        result[n]=base
    return result


def set_world_rotation(rest,local,poses,name,rotation):
    parent=rest[name]['parent']
    base=(poses[parent]@rest[parent]['m'].inverted()@rest[name]['m']) if parent else rest[name]['m']
    local[name]=(base.to_quaternion().inverted()@rotation).normalized()


def pose_json(poses):
    return {n:{'p':list(m.translation),'q':xyzw(m.to_quaternion())} for n,m in poses.items()}


def sample_source(spec):
    load(spec['source']['file']);rig=rig_named(spec['source']['armature']);rest=rest_data(rig)
    if abs(bpy.context.scene.unit_settings.scale_length-1)>1e-6:raise ValueError('Source Blender metric scale_length must be 1')
    for name in spec['mapping'].values():
        if name not in rest:raise ValueError('Missing source bone: '+name)
    captures={};origin_matrix=rig.matrix_world.copy()
    for index,clip in enumerate(spec['clips']):
        if index:
            # Sparse Actions leave unkeyed properties untouched in Blender.
            # Reload the authored starting state so clip order cannot leak pose,
            # custom property, constraint or driver state into another Action.
            load(spec['source']['file']);rig=rig_named(spec['source']['armature'])
        choose(rig,clip['action']);bpy.context.scene.render.fps=round(clip['fps']);frames=[]
        action=rig.animation_data.action
        if clip['start_frame'] < action.frame_range[0] or clip['end_frame'] > action.frame_range[1]:
            raise ValueError('Requested clip outside actual source Action range')
        for frame in range(clip['start_frame'],clip['end_frame']+1):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            if any(abs(evaluated.matrix_world[i][j]-origin_matrix[i][j])>1e-5 for i in range(4) for j in range(4)):
                raise ValueError('Animated armature object: bake movement into an explicit root bone first')
            pose={n:evaluated.matrix_world@evaluated.pose.bones[n].matrix.copy() for n in rest}
            for n in spec['mapping'].values():
                rel=rest[n]['m'].inverted()@pose[n]
                if any(abs(v-1)>1e-3 for v in rel.to_scale()):raise ValueError('Animated scale/stretch is unsupported: '+n)
                parent=rest[n]['parent']
                allowed={spec['mapping'][b] for b in spec['root_motion'].get('translation_bones',[])}
                if parent and n not in allowed:
                    delta=(pose[parent].inverted()@pose[n]).translation-(rest[parent]['m'].inverted()@rest[n]['m']).translation
                    if (pose[parent].to_3x3()@delta).length>1e-5:raise ValueError('Non-root translation requires explicit translation_bones policy: '+n)
            frames.append(pose)
        captures[clip['id']]=frames
    return rest,captures


def reference_frames(spec,rest,side):
    profile=spec.get('character_profile')
    if not profile:return {n:b['m'].copy() for n,b in rest.items()}
    overrides=profile['reference_pose'][side]['local_rotations_xyzw']
    if set(overrides)-set(rest):raise ValueError('Reference pose contains missing '+side+' bones: '+str(sorted(set(overrides)-set(rest))))
    local={n:quat(overrides[n]) if n in overrides else Quaternion() for n in rest}
    root=profile['roles']['root'][side]
    return fk(rest,local,root,Vector((0,0,0)))


def profile_diagnostics(spec,source_rest,target_rest):
    p=spec.get('character_profile')
    if not p:return {'mode':'legacy_rest_relative','reference_pose':'original_bind_rest'}
    axes={'+X':(1,0,0),'-X':(-1,0,0),'+Y':(0,1,0),'-Y':(0,-1,0)}
    result={'id':p['id'],'revision':p['revision'],'rigs':{},'scope':'explicit humanoid roles; auxiliary bones inherit rest; no twist redistribution'}
    for side,rest in [('source',source_rest),('target',target_rest)]:
        mapped={pair[side] for pair in p['roles'].values()}
        missing=mapped-set(rest)
        if missing:raise ValueError('Missing '+side+' role bones: '+str(sorted(missing)))
        extras=set(rest)-mapped;declared=set(p['unmapped_bones'][side])
        if extras!=declared:raise ValueError(side+' extra bones need explicit policies; undeclared='+str(sorted(extras-declared))+' absent='+str(sorted(declared-extras)))
        left=Vector((0,0,1)).cross(Vector(axes[p['coordinates'][side]['forward']]))
        for part in ('upperarm','thigh'):
            l=rest[p['roles'][part+'_L'][side]]['m'].translation;r=rest[p['roles'][part+'_R'][side]]['m'].translation
            if (l-r).dot(left)<=1e-5:raise ValueError(side+' left/right or forward declaration contradicts '+part+' positions')
        refs=reference_frames(spec,rest,side)
        result['rigs'][side]={'bones':len(rest),'unmapped':p['unmapped_bones'][side],
            'reference_world':pose_json(refs),'calibration_deg':{n:angle(rest[n]['m'].to_quaternion(),m.to_quaternion()) for n,m in refs.items()}}
    return result


def retarget(spec,source_rest,target_rest,source_frames,clip=None):
    mapping=spec['mapping'];align=quat(spec['alignment_xyzw']);root=spec['root_motion']['bone'];motion=spec['root_motion']
    if target_rest[root]['parent'] is not None:raise ValueError('Root motion bone must be a top-level target bone')
    if source_rest[mapping[root]]['parent'] is not None:raise ValueError('Root mapping must point to a top-level source bone')
    # Reject a swapped limb/ancestor map even when all names exist. Extra target twist bones may remain unmapped.
    for name,src in mapping.items():
        p=target_rest[name]['parent']
        while p and p not in mapping:p=target_rest[p]['parent']
        if p:
            ancestors=[];s=source_rest[src]['parent']
            while s:ancestors.append(s);s=source_rest[s]['parent']
            if mapping[p] not in ancestors:raise ValueError('Mapping hierarchy mismatch at '+name)
    source_reference=reference_frames(spec,source_rest,'source');target_reference=reference_frames(spec,target_rest,'target')
    frames=[]
    for source_pose in source_frames:
        local={n:Quaternion() for n in target_rest};translation=Vector((0,0,0))
        if motion['translation']=='scaled':
            s=mapping[root];translation=align@(source_pose[s].translation-source_rest[s]['m'].translation)*motion['scale']
        # Absolute rest-relative source rotations are converted back through the actual target parent.
        poses={};offsets={}
        for n,b in target_rest.items():
            parent=b['parent'];base=poses[parent]@target_rest[parent]['m'].inverted()@b['m'] if parent else b['m'].copy()
            if n in mapping:
                s=mapping[n];delta=source_pose[s].to_quaternion()@source_reference[s].to_quaternion().inverted()
                desired=align@delta@align.inverted()@target_reference[n].to_quaternion()
                local[n]=(base.to_quaternion().inverted()@desired).normalized()
                if n in motion.get('translation_bones',[]):
                    sp=source_rest[s]['parent']
                    if not sp:raise ValueError('Secondary translated bone needs a source parent')
                    dp=(source_pose[sp].inverted()@source_pose[s]).translation-(source_rest[sp]['m'].inverted()@source_rest[s]['m']).translation
                    calibration=Vector((clip or {}).get('target_translation_offsets_m',{}).get(n,[0,0,0]))
                    offsets[n]=base.to_3x3().inverted()@(align@(source_pose[sp].to_3x3()@dp)*motion['scale']+calibration)
                    base=base@Matrix.Translation(offsets[n])
            poses[n]=base@local[n].to_matrix().to_4x4()
            if n==root:poses[n].translation+=translation
        frames.append({'local':local,'translation':translation,'offsets':offsets})
    return frames


def repair(spec,clip,rest,frames):
    repairs=clip.get('repairs',{});events=[];root=spec['root_motion']['bone'];fps=clip['fps']
    if 'rotation_spikes' in repairs:
        rule=repairs['rotation_spikes'];edits=[]
        for bone in rule['bones']:
            for i in range(1,len(frames)-1):
                a,b,c=[frames[j]['local'][bone] for j in (i-1,i,i+1)]
                if min(angle(a,b),angle(b,c))>rule['threshold_deg'] and angle(a,c)<=rule['neighbor_deg']:
                    edits.append((i,bone,a.slerp(c,.5)))
        # No cascade: decisions use the untouched series, reject adjacent ambiguity.
        selected={(i,b) for i,b,q in edits}
        for i,b,q in edits:
            if (i-1,b) in selected or (i+1,b) in selected:continue
            frames[i]['local'][b]=q;events.append({'repair':'isolated_rotation_spike','bone':b,'time_s':i/fps})
    if 'loop' in repairs:
        rule=repairs['loop'];duration=(len(frames)-1)/fps
        for bone in rule['bones']:
            correction=frames[-1]['local'][bone].inverted()@frames[0]['local'][bone]
            before=angle(frames[-1]['local'][bone],frames[0]['local'][bone])
            for i,frame in enumerate(frames):
                weight=smooth((i/fps-(duration-rule['blend_s']))/rule['blend_s'])
                q=frame['local'][bone];frame['local'][bone]=q.slerp(q@correction,weight)
            events.append({'repair':'loop_rotation','bone':bone,'before_deg':before,
                           'after_deg':angle(frames[-1]['local'][bone],frames[0]['local'][bone])})
    for rule in repairs.get('contacts',[]):
        upper,lower,foot=rule['chain']
        if rest[lower]['parent']!=upper or rest[foot]['parent']!=lower:raise ValueError('Contact chain must have direct parents')
        start=math.ceil(rule['start_s']*fps-1e-6);end=math.floor(rule['end_s']*fps+1e-6)
        anchor_pose=fk(rest,frames[start]['local'],root,frames[start]['translation'],frames[start]['offsets'])[foot]
        anchor=anchor_pose.translation.copy();anchor_q=anchor_pose.to_quaternion();max_delta=0
        velocity=Vector(rule.get('controller_velocity_mps',[0,0,0]));anchor_time=start/fps
        for i,frame in enumerate(frames):
            t=i/fps
            if t<rule['start_s']-rule['blend_s'] or t>rule['end_s']+rule['blend_s']:continue
            weight=min(smooth((t-rule['start_s']+rule['blend_s'])/rule['blend_s']),smooth((rule['end_s']+rule['blend_s']-t)/rule['blend_s']))
            if weight<=1e-8:continue
            poses=fk(rest,frame['local'],root,frame['translation'],frame['offsets']);old=poses[foot].translation
            goal=old.lerp(anchor-velocity*(t-anchor_time),weight)
            original_rotations={n:poses[n].to_quaternion() for n in rule['chain']}
            correction=(goal-old).length;max_delta=max(max_delta,correction)
            if correction>rule['max_correction_m']:raise ValueError('Contact exceeds correction budget: '+foot+' at '+str(t))
            hip=poses[upper].translation;knee=poses[lower].translation;ankle=poses[foot].translation
            a=(knee-hip).length;b=(ankle-knee).length;direction=goal-hip;distance=direction.length
            if distance<1e-6 or distance>a+b-1e-6 or distance<abs(a-b)+1e-6:
                raise ValueError('Contact unreachable without stretching: '+foot+' at '+str(t))
            axis=direction.normalized();pole=Vector(rule['pole']);bend=pole-axis*pole.dot(axis)
            if bend.length<1e-6:raise ValueError('Contact pole is parallel to leg')
            # Blend the bend-plane direction too, so an explicit pole does not
            # abruptly flip the knee while the positional IK weight is still tiny.
            current_bend=knee-hip-axis*(knee-hip).dot(axis)
            if current_bend.length>1e-6:
                current_bend.normalize();bend.normalize()
                signed=math.atan2(axis.dot(current_bend.cross(bend)),current_bend.dot(bend))
                bend=Quaternion(axis,signed*weight)@current_bend
            along=(a*a-b*b+distance*distance)/(2*distance)
            desired_knee=hip+axis*along+bend.normalized()*math.sqrt(max(0,a*a-along*along))
            upper_q=(knee-hip).rotation_difference(desired_knee-hip)@poses[upper].to_quaternion()
            set_world_rotation(rest,frame['local'],poses,upper,upper_q)
            poses=fk(rest,frame['local'],root,frame['translation'],frame['offsets']);knee=poses[lower].translation
            lower_q=(poses[foot].translation-knee).rotation_difference(goal-knee)@poses[lower].to_quaternion()
            set_world_rotation(rest,frame['local'],poses,lower,lower_q)
            poses=fk(rest,frame['local'],root,frame['translation'],frame['offsets'])
            set_world_rotation(rest,frame['local'],poses,foot,poses[foot].to_quaternion().slerp(anchor_q,weight))
            final=fk(rest,frame['local'],root,frame['translation'],frame['offsets'])
            if max(angle(original_rotations[n],final[n].to_quaternion()) for n in rule['chain'])>rule.get('max_joint_rotation_deg',60):
                raise ValueError('Contact exceeds joint rotation budget: '+foot+' at '+str(t))
        events.append({'repair':'contact_lock','bone':foot,'start_s':rule['start_s'],'end_s':rule['end_s'],
                       'anchor_m':list(anchor),'controller_velocity_mps':list(velocity),'max_correction_m':max_delta})
    return events


def repair_scope(spec,clip,rest,baseline,frames,before,after):
    """Audit actual evaluated local transforms; descendants may move by inheritance."""
    failures=[];edits=[];world_descendants=set();max_p=0;max_q=0;edited_frames=set()
    rules=clip.get('repairs',{});duration=before[-1]['t']
    def permitted(n,t):
        if n in rules.get('rotation_spikes',{}).get('bones',[]) and 0<t<duration:return True
        loop=rules.get('loop',{})
        if n in loop.get('bones',[]) and t>=duration-loop['blend_s']-1e-6:return True
        return any(n in r['chain'] and r['start_s']-r['blend_s']-1e-6<=t<=r['end_s']+r['blend_s']+1e-6 for r in rules.get('contacts',[]))
    def matrices(row):
        return {n:Matrix.LocRotScale(Vector(b['p']),quat(b['q']),Vector((1,1,1))) for n,b in row['bones'].items()}
    for i,(a,b) in enumerate(zip(before,after)):
        aa=matrices(a);bb=matrices(b)
        for n in rest:
            parent=rest[n]['parent'];la=aa[parent].inverted()@aa[n] if parent else aa[n];lb=bb[parent].inverted()@bb[n] if parent else bb[n]
            rotation=angle(la.to_quaternion(),lb.to_quaternion());translation=(la.translation-lb.translation).length
            world_p=(aa[n].translation-bb[n].translation).length;world_q=angle(aa[n].to_quaternion(),bb[n].to_quaternion())
            max_p=max(max_p,world_p);max_q=max(max_q,rotation)
            if translation>2e-5:failures.append('Repair modified local translation: '+n+' at '+str(a['t']))
            if rotation>.01:
                edited_frames.add(i);edits.append({'bone':n,'time_s':a['t'],'local_rotation_deg':rotation})
                if not permitted(n,a['t']):failures.append('Repair escaped bone/time scope: '+n+' at '+str(a['t']))
            elif world_p>2e-5 or world_q>.01:world_descendants.add(n)
    fraction=len(edited_frames)/len(frames)
    budget=spec.get('character_profile',{}).get('repair_budget')
    if budget:
        if max_p>budget['max_position_m']+2e-5:failures.append('Profile position repair budget exceeded')
        if max_q>budget['max_rotation_deg']+.01:failures.append('Profile rotation repair budget exceeded')
        if fraction>budget['max_edited_fraction']+1e-8:failures.append('Profile edited-frame budget exceeded')
    return {'ok':not failures,'method':'evaluated Blender before/after local transforms; world changes of descendants are separately recorded',
        'edits':edits,'inherited_world_changes':sorted(world_descendants),'max_world_position_delta_m':max_p,
        'max_local_rotation_delta_deg':max_q,'edited_frame_fraction':fraction,'budget':budget,'failures':sorted(set(failures))}


def bake(rig,rest,frames,root,name,fps):
    rig.animation_data_clear();action=bpy.data.actions.new(name);rig.animation_data_create();rig.animation_data.action=action
    scene=bpy.context.scene;scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps;scene.frame_start=1;scene.frame_end=len(frames)
    previous={};world_inverse=rig.matrix_world.inverted()
    for i,frame in enumerate(frames,1):
        scene.frame_set(i);poses=fk(rest,frame['local'],root,frame['translation'],frame['offsets'])
        for n in rest:
            pb=rig.pose.bones[n];pb.rotation_mode='QUATERNION';pb.matrix=world_inverse@poses[n]
            if n in previous and previous[n].dot(pb.rotation_quaternion)<0:pb.rotation_quaternion=-pb.rotation_quaternion
            previous[n]=pb.rotation_quaternion.copy()
            for channel in ('location','rotation_quaternion','scale'):pb.keyframe_insert(channel,frame=i,group=n)
            bpy.context.view_layer.update()
    # All samples are baked at the declared rate; use linear interpolation between them.
    for layer in action.layers:
        for strip in layer.strips:
            bag=strip.channelbag(rig.animation_data.action_slot)
            if bag:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    return action


def evaluated_capture(rig,rest,clip):
    frames=[]
    for i in range(clip['end_frame']-clip['start_frame']+1):
        bpy.context.scene.frame_set(i+1);bpy.context.view_layer.update()
        evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        frames.append({'t':i/clip['fps'],'bones':pose_json({n:evaluated.matrix_world@evaluated.pose.bones[n].matrix for n in rest})})
    return frames


def measures(capture,clip,root):
    contacts=[]
    for rule in clip.get('repairs',{}).get('contacts',[]):
        rows=[f for f in capture if rule['start_s']-1e-6<=f['t']<=rule['end_s']+1e-6];bone=rule['chain'][-1]
        anchor=Vector(rows[0]['bones'][bone]['p']);velocity=Vector(rule.get('controller_velocity_mps',[0,0,0]))
        contacts.append({'bone':bone,'samples':len(rows),'space':'declared constant controller velocity + evaluated ankle; no terrain IK',
            'controller_velocity_mps':list(velocity),'max_drift_m':max((Vector(r['bones'][bone]['p'])+velocity*(r['t']-rows[0]['t'])-anchor).length for r in rows)})
    return {'contacts':contacts,'root_displacement_m':list(Vector(capture[-1]['bones'][root]['p'])-Vector(capture[0]['bones'][root]['p'])),
            'loop_error_deg':{b:angle(quat(capture[-1]['bones'][b]['q']),quat(capture[0]['bones'][b]['q'])) for b in clip.get('repairs',{}).get('loop',{}).get('bones',[])}}


def export_fbx(rig,meshes,path):
    """Use an isolated centimetre export copy: no hidden parent scale in UE animation.

    UE's FBX animation importer computes transforms relative to the discarded
    Blender wrapper, cancelling its unit scale. Scaling the component afterwards
    would break skin bind matrices. Scale rest data, vertices and translation
    keys together in a disposable copy with unit_scale=.01 instead.
    """
    scene=bpy.context.scene;old_name=rig.name;old_units=scene.unit_settings.scale_length;copies=[]
    if rig.name=='Armature':rig.name='_MotionSourceArmature'
    copy_rig=rig.copy();copy_rig.data=rig.data.copy();scene.collection.objects.link(copy_rig);copies.append(copy_rig)
    copy_rig.name='Armature';copy_rig.data.transform(Matrix.Scale(100,4)@rig.matrix_world)
    copy_rig.matrix_world=Matrix.Identity(4)
    translation_scale=100*rig.matrix_world.to_scale().x
    action=rig.animation_data.action.copy();copy_rig.animation_data.action=action
    if action.slots:copy_rig.animation_data.action_slot=action.slots[0]
    try:
        for layer in action.layers:
            for strip in layer.strips:
                bag=strip.channelbag(copy_rig.animation_data.action_slot)
                if bag:
                    for curve in bag.fcurves:
                        if curve.data_path.endswith('location'):
                            for key in curve.keyframe_points:
                                key.co.y*=translation_scale;key.handle_left.y*=translation_scale;key.handle_right.y*=translation_scale
        for mesh in meshes:
            obj=mesh.copy();obj.data=mesh.data.copy();scene.collection.objects.link(obj);copies.append(obj)
            obj.data.transform(Matrix.Scale(100,4)@mesh.matrix_world,shape_keys=True)
            if obj.parent==rig:obj.parent=copy_rig
            elif obj.parent:raise ValueError('Export meshes must be unparented or directly parented to the target armature')
            obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4)
            for mod in obj.modifiers:
                if mod.type=='ARMATURE' and mod.object==rig:mod.object=copy_rig
        scene.unit_settings.scale_length=.01
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies:obj.select_set(True)
        bpy.context.view_layer.objects.active=copy_rig;bpy.context.view_layer.update()
        bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE','MESH'},
            add_leaf_bones=False,use_armature_deform_only=False,bake_anim=True,bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False,bake_anim_simplify_factor=0,axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',
            apply_scale_options='FBX_SCALE_UNITS',path_mode='COPY',embed_textures=True)
    finally:
        scene.unit_settings.scale_length=old_units
        for obj in reversed(copies):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.actions.remove(action);rig.name=old_name
        bpy.context.view_layer.objects.active=rig


def export_glb(path,fps):
    # Export baked frames with an integer scene rate. Blender 4.5's glTF
    # exporter multiplies fps_base where Blender itself divides it. Retiming
    # only sampler inputs makes fractional rates explicit and version agnostic.
    scene=bpy.context.scene;old_base=scene.render.fps_base;integer_fps=scene.render.fps
    try:
        scene.render.fps_base=1
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
            export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_force_sampling=True,
            export_frame_range=True,export_anim_slide_to_zero=True,export_yup=True,export_skins=True,export_def_bones=False)
    finally:scene.render.fps_base=old_base
    if abs(integer_fps-fps)<1e-8:return
    data=path.read_bytes();magic,version,length=struct.unpack_from('<III',data)
    if magic!=0x46546c67 or version!=2 or length!=len(data):raise ValueError('Invalid exported GLB')
    chunks=[];offset=12
    while offset<len(data):
        size,kind=struct.unpack_from('<II',data,offset);offset+=8
        chunks.append([kind,bytearray(data[offset:offset+size])]);offset+=size
    document=json.loads(next(c[1] for c in chunks if c[0]==0x4e4f534a))
    binary=next(c[1] for c in chunks if c[0]==0x004e4942)
    inputs={s['input'] for a in document.get('animations',[]) for s in a['samplers']}
    if not inputs:raise ValueError('No exported animation timeline')
    for index in inputs:
        accessor=document['accessors'][index];view=document['bufferViews'][accessor['bufferView']]
        if accessor['componentType']!=5126 or accessor['type']!='SCALAR' or 'sparse' in accessor or view.get('buffer',0)!=0:
            raise ValueError('Unsupported exported animation timeline layout')
        start=view.get('byteOffset',0)+accessor.get('byteOffset',0);stride=view.get('byteStride',4);times=[]
        for i in range(accessor['count']):
            where=start+i*stride;value=struct.unpack_from('<f',binary,where)[0]*integer_fps/fps
            if not math.isfinite(value):raise ValueError('Invalid animation timestamp')
            struct.pack_into('<f',binary,where,value);times.append(value)
        accessor['min']=[min(times)];accessor['max']=[max(times)]
    encoded=json.dumps(document,separators=(',',':'),allow_nan=False).encode('utf-8');encoded+=b' '*((-len(encoded))%4)
    for chunk in chunks:
        if chunk[0]==0x4e4f534a:chunk[1]=encoded
    payload=b''.join(struct.pack('<II',len(content),kind)+content for kind,content in chunks)
    path.write_bytes(struct.pack('<III',magic,version,len(payload)+12)+payload)


def process(spec,out):
    source_rest,source_frames=sample_source(spec)
    load(spec['target']['file']);rig=rig_named(spec['target']['armature']);rest=rest_data(rig)
    diagnostics=profile_diagnostics(spec,source_rest,rest)
    write(out/'profile-diagnostics.json',diagnostics)
    for n in spec['mapping']:
        if n not in rest:raise ValueError('Missing target bone: '+n)
    if any(pb.constraints for pb in rig.pose.bones) or rig.constraints or (rig.animation_data and rig.animation_data.drivers):
        raise ValueError('Target must be an export/deform rig without constraints/drivers; original control rig remains untouched')
    if any(not b.use_inherit_rotation or b.inherit_scale!='FULL' for b in rig.data.bones):
        raise ValueError('Target needs standard rotation/scale inheritance; bake an export rig first')
    if abs(bpy.context.scene.unit_settings.scale_length-1)>1e-6:
        raise ValueError('Use Blender metric scale_length=1; normalize an export copy first')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
    if not meshes:raise ValueError('Target needs a real skinned mesh for engine roundtrip')
    for mesh in meshes:
        if mesh.animation_data and (mesh.animation_data.action or mesh.animation_data.drivers or mesh.animation_data.nla_tracks):
            raise ValueError('Target mesh animation must be baked into the export rig first: '+mesh.name)
        if any(m.type=='ARMATURE' and m.use_deform_preserve_volume for m in mesh.modifiers):
            raise ValueError('Target preserve volume (dual quaternion) skinning is not supported by the linear-skin export: '+mesh.name)
    # Export only this target and its skinned meshes. Clear unrelated animation from the working copy.
    for o in bpy.context.scene.objects:
        if o!=rig and o not in meshes:bpy.data.objects.remove(o,do_unlink=True)
    for o in meshes:o.animation_data_clear()
    for action in list(bpy.data.actions):bpy.data.actions.remove(action)
    root=spec['root_motion']['bone'];reports=[];artifacts={}
    write(out/'target-rig.json',{'coordinates':'RH_Z_UP_METRES','armature':rig.name,'bones':[{'name':n,'parent':b['parent'],
          'rest':pose_json({n:b['m']})[n],'length_m':b['length']} for n,b in rest.items()]})
    for clip in spec['clips']:
        frames=retarget(spec,source_rest,rest,source_frames[clip['id']],clip)
        bake(rig,rest,frames,root,clip['id']+'_baseline',clip['fps']);before=evaluated_capture(rig,rest,clip)
        baseline=copy.deepcopy(frames)
        events=repair(spec,clip,rest,frames)
        bake(rig,rest,frames,root,clip['id'],clip['fps']);after=evaluated_capture(rig,rest,clip)
        scope=repair_scope(spec,clip,rest,baseline,frames,before,after)
        write(out/(clip['id']+'-repair-scope.json'),scope)
        write(out/(clip['id']+'-capture.json'),{'schema':'oagd.motion-capture/1','method':'Blender evaluated dependency graph after baked Action',
              'coordinates':'RH_Z_UP_METRES','before':before,'after':after,
              'source':[{'t':i/clip['fps'],'bones':pose_json(f)} for i,f in enumerate(source_frames[clip['id']])]})
        before_metrics=measures(before,clip,root);after_metrics=measures(after,clip,root)
        failures=scope['failures']+[c['bone']+': contact residual' for c in after_metrics['contacts'] if c['max_drift_m']>spec['tolerances']['contact_m']]
        # Independent readback of the baked pose must agree with the solver, not just the requested transforms.
        residual=max((Vector(actual['bones'][n]['p'])-fk(rest,frame['local'],root,frame['translation'],frame['offsets'])[n].translation).length
                     for actual,frame in zip(after,frames) for n in rest)
        if residual>1e-4:failures.append('Baked pose diverges from solver')
        bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
        for o in meshes:o.select_set(True)
        # Save one editable source per clip. Exporters see only the selected active Action.
        bpy.context.scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/(clip['id']+'.blend')))
        export_glb(out/(clip['id']+'.glb'),clip['fps'])
        export_fbx(rig,meshes,out/(clip['id']+'.fbx'))
        reports.append({'id':clip['id'],'fps':clip['fps'],'duration_s':(len(frames)-1)/clip['fps'],'frames':len(frames),
                        'repairs':events,'reference_translation_offsets_m':clip.get('target_translation_offsets_m',{}),'repair_scope':scope,'before':before_metrics,'after':after_metrics,'bake_residual_m':residual,'failures':failures})
    for p in out.iterdir():
        if p.suffix in ('.blend','.glb','.fbx') or p.name.endswith(('-capture.json','-repair-scope.json')) or p.name in ('target-rig.json','profile-diagnostics.json'):artifacts[p.name]=sha(p)
    return {'schema':'oagd.motion-result/1','tool_version':VERSION,'blender':bpy.app.version_string,
            'ok':not any(r['failures'] for r in reports),'clips':reports,'artifacts':artifacts,
            'unmapped_target_bones':[n for n in rest if n not in spec['mapping']],
            'root_motion':spec['root_motion'],'profile':spec.get('profile_dependency'),'fbx_armature_wrapper':'Armature (UE removes wrapper; bone names unchanged)',
            'quality':'requires_visual_review','engine_validation':'not_run',
            'dependencies':{spec[r]['file']:sha(spec[r]['file']) for r in ('source','target')}}


def main():
    job_path=Path(sys.argv[sys.argv.index('--')+1]).resolve();job=json.loads(job_path.read_text(encoding='utf-8'));out=job_path.parent
    try:
        if job['mode']=='inspect':
            if sha(job['file'])!=job['sha256']:raise ValueError('Source changed before inspection')
            result=inventory(job['file'])
        else:
            spec=job['spec']
            for r in ('source','target'):
                if sha(spec[r]['file'])!=spec[r]['sha256']:raise ValueError('Source changed before processing')
            result=process(spec,out)
            if sha(job['spec_file'])!=job['spec_sha256']:raise ValueError('Spec changed during processing')
            result['dependencies'][job['spec_file']]=job['spec_sha256']
            if 'profile_dependency' in spec:
                dep=spec['profile_dependency']
                if sha(dep['file'])!=dep['sha256']:raise ValueError('Character profile changed during processing')
                result['dependencies'][dep['file']]=dep['sha256']
            for r in ('source','target'):
                if sha(spec[r]['file'])!=spec[r]['sha256']:raise ValueError('Source changed during processing')
        write(out/'report.json',result)
    except Exception as e:
        write(out/'report.json',{'ok':False,'error':str(e),'quality':'not_evaluated'})
        raise


if __name__=='__main__':main()

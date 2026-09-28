"""Blender 4.5 adapter. Run with -- --workspace PATH --mode prepare|export|ui|render."""
import bpy, sys, json, argparse, math, hashlib
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',required=True)
parser.add_argument('--mode',choices=['prepare','export','sample','ui','render'],required=True)
parser.add_argument('--clip',default='sword_heavy')
parser.add_argument('--view',choices=['front','side','game'],default='side')
parser.add_argument('--speed',type=float,default=1)
parser.add_argument('--out')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
root=Path(args.workspace).resolve()
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
baseline=json.loads((root/manifest['baseline_capture']).read_text(encoding='utf-8'))
clips={c['id']:c for c in baseline['clips']}
specs={c['id']:c for c in manifest['clips']}

def tr(t):
    q=t['q'];return Matrix.LocRotScale(Vector(t['p']),Quaternion((q[3],q[0],q[1],q[2])),Vector(t['s']))

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def get_rig():
    found=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(found)!=1:raise RuntimeError('Expected exactly one target armature')
    return found[0]

def choose(clip_id):
    rig=get_rig();rig.animation_data_create();rig.animation_data.action=bpy.data.actions[clip_id]
    # Blender 4.5 layered actions require the compatible slot to be assigned.
    if rig.animation_data.action.slots:rig.animation_data.action_slot=rig.animation_data.action.slots[0]
    scene=bpy.context.scene;scene['animlab_clip']=clip_id
    if specs[clip_id]['fps']!=60:raise RuntimeError('This adapter is validated at 60 Hz; adapt all samplers before changing fps')
    scene.frame_start=1;scene.frame_end=round(specs[clip_id]['duration_s']*60)+1
    scene.timeline_markers.clear()
    for name,t in specs[clip_id]['timing'].items():scene.timeline_markers.new(name,frame=round(t*60)+1)
    scene.frame_set(1);show_weapon(scene)

def show_weapon(scene,*unused):
    cid=scene.get('animlab_clip',next(iter(specs)))
    if cid not in specs:return
    spec=specs[cid];weapon=spec['weapon'];t=(scene.frame_current-1)/60
    for e in spec.get('weapon_events',[]):
        if e['t']<=t+1e-6:weapon=e['weapon']
    for wid in manifest['weapons']:
        for o in bpy.data.objects:
            if o.get('animlab_weapon')==wid:o.hide_render=wid!=weapon;o.hide_set(wid!=weapon)

def prepare():
    output=root/'source/AnimationLab.blend'
    if output.exists():raise RuntimeError('Blend source exists. Preserve artist changes; choose another revision.')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(root/manifest['rig']['reference_fbx']),automatic_bone_orientation=False,use_prepost_rot=True)
    rig=get_rig();imported_rig_name=rig.name;rig.animation_data_clear()
    scene=bpy.context.scene;scene.render.fps=60;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    refs={b['name']:tr(b['rest']) for b in baseline['bones']}
    restored_root=False
    # UE's exported root is represented as the FBX armature object by this importer.
    # Restore it explicitly only for this verified topology; do not invent other bones.
    if 'root' not in rig.data.bones and imported_rig_name=='root' and baseline['bones'][0]['name']=='root' and baseline['bones'][0]['parent']==-1:
        bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        parents=[b for b in rig.data.edit_bones if b.parent is None]
        bone=rig.data.edit_bones.new('root');bone.head=(0,0,0);bone.tail=(0,10,0)
        for b in parents:b.parent=bone
        bpy.ops.object.mode_set(mode='OBJECT');restored_root=True
    rig.name='Armature'
    missing=set(refs)-set(rig.data.bones.keys())
    if missing:raise RuntimeError('FBX reference missing bones: '+str(sorted(missing)))
    rest={n:rig.matrix_world@rig.data.bones[n].matrix_local for n in refs}
    landmarks=[n for n in ['root','pelvis','spine_03','head','hand_r','hand_l','foot_r','foot_l'] if n in refs]
    x=np.array([refs[n].translation[:] for n in landmarks]);y=np.array([rest[n].translation[:] for n in landmarks])
    xc=x-x.mean(0);yc=y-y.mean(0);u,s,vt=np.linalg.svd(xc.T@yc);rotation=u@vt;scale=s.sum()/(xc*xc).sum()
    linear=scale*rotation.T;offset=y.mean(0)-linear@x.mean(0)
    affine=np.eye(4);affine[:3,:3]=linear;affine[:3,3]=offset;C=Matrix(affine.tolist());inverse=C.inverted()
    errors=[((C@refs[n]).translation-rest[n].translation).length/scale for n in refs]
    if max(errors)>1.0:raise RuntimeError('Reference coordinate calibration failed: %.3f cm'%max(errors))
    scene['animlab_workspace']=str(root);scene['animlab_coordinate_matrix']=json.dumps(affine.tolist())
    basis={n:refs[n].inverted()@inverse@rest[n] for n in refs}
    rig_inverse=rig.matrix_world.inverted()
    for clip in baseline['clips']:
        action=bpy.data.actions.new(clip['id']);action.use_fake_user=True
        rig.animation_data_create();rig.animation_data.action=action
        for i,f in enumerate(clip['frames']):
            frame=i+1;scene.frame_set(frame)
            desired={bone['name']:rig_inverse@C@tr(t)@basis[bone['name']] for bone,t in zip(baseline['bones'],f['pose'])}
            for bone,t in zip(baseline['bones'],f['pose']):
                name=bone['name'];pb=rig.pose.bones[name];pb.rotation_mode='QUATERNION'
                # Resolve against this sample's parent, not a stale evaluated parent pose.
                if pb.parent:
                    pb.matrix_basis=pb.bone.convert_local_to_pose(desired[name],pb.bone.matrix_local,parent_matrix=desired[pb.parent.name],parent_matrix_local=pb.parent.bone.matrix_local,invert=True)
                else:pb.matrix_basis=pb.bone.convert_local_to_pose(desired[name],pb.bone.matrix_local,invert=True)
                pb.keyframe_insert(data_path='location',frame=frame,group=name)
                pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=name)
                pb.keyframe_insert(data_path='scale',frame=frame,group=name)
        # Dense samples are intentional. Simplification is deferred until measured roundtrip.
        if hasattr(action,'fcurves'):
            for fc in action.fcurves:
                for key in fc.keyframe_points:key.interpolation='LINEAR'
        print('ANIMLAB_ACTION',clip['id'],len(clip['frames']))
    materials=[]
    for name,color in [('Metal',(.25,.31,.38,1)),('Grip',(.035,.03,.025,1)),('Accent',(.12,.55,.7,1))]:
        mat=bpy.data.materials.new(name);mat.diffuse_color=color;materials.append(mat)
    for wid,w in manifest['weapons'].items():
        verts=[];faces=[];material_ids=[]
        for si,sec in enumerate(w['sections']):
            start=len(verts);verts.extend(sec['vertices']);indices=sec['triangles']
            for j in range(0,len(indices),3):
                face=tuple(start+v for v in indices[j:j+3])
                if len(set(face))==3:faces.append(face);material_ids.append(si)
        mesh=bpy.data.meshes.new(wid+'_geometry');mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new('Weapon_'+wid,mesh);scene.collection.objects.link(obj);obj['animlab_weapon']=wid
        for mat in materials:mesh.materials.append(mat)
        for poly,mid in zip(mesh.polygons,material_ids):poly.material_index=mid
        bone=w['bone'];obj.parent=rig;obj.parent_type='BONE';obj.parent_bone=bone;obj.matrix_parent_inverse=Matrix.Identity(4)
        obj.matrix_basis=Matrix.Translation((0,-rig.data.bones[bone].length,0))@rest[bone].inverted()@C@refs[bone]@tr(w['binding'])
        for key,pos in w['grips'].items():
            marker=bpy.data.objects.new(wid+'_'+key+'_contact',None);scene.collection.objects.link(marker);marker.parent=obj;marker.location=pos;marker.empty_display_type='SPHERE';marker.empty_display_size=3;marker['animlab_weapon']=wid
    # Neutral external review context; all figures use the actual skinned mesh.
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.01));floor=bpy.context.object;floor.name='Inspection_floor';floor.scale=(.1,.1,.1)
    floor_mat=bpy.data.materials.new('Neutral_floor');floor_mat.diffuse_color=(.2,.23,.27,1);floor.data.materials.append(floor_mat)
    center=sum((rest[n].translation for n in ['pelvis','head']),Vector())*.5
    for view,relative in [('front',(-4,0,.3)),('side',(0,-4,.3)),('game',(-3,-3,1.0))]:
        # Directions use the fitted canonical basis, not assumed FBX orientation.
        direction=C.to_3x3()@Vector(relative)/scale
        cam_data=bpy.data.cameras.new('Camera_'+view);cam=bpy.data.objects.new('Camera_'+view,cam_data);scene.collection.objects.link(cam);cam.location=center+direction
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam_data.type='ORTHO';cam_data.ortho_scale=2.9;cam_data.lens=55
    scene.world=bpy.data.worlds.new('Inspection_world')
    scene.camera=bpy.data.objects['Camera_side'];scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH';scene.display.shading.background_type='WORLD';scene.world.color=(.06,.075,.09)
    scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=3;area.spaces.active.region_3d.view_location=center
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;rig.show_in_front=True
    choose('sword_light_1');bpy.ops.wm.save_as_mainfile(filepath=str(output))
    write(root/'reports/blender-prepare.json',{'blender':bpy.app.version_string,'actions':len(clips),'restored_root_from_fbx_armature':restored_root,'reference_fit_max_cm':max(errors),'coordinate_matrix':affine.tolist(),'source':str(output),'status':'baseline_baked_not_repaired'})

def export():
    rig=get_rig();bpy.ops.object.mode_set(mode='OBJECT') if rig.mode!='OBJECT' else None
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
    results=[]
    # Fail before writing any files if a revision already exists.
    for spec in specs.values():
        if (root/spec['fbx']).exists():raise RuntimeError('FBX exists; use a new revision: '+spec['fbx'])
    sample_source()
    for cid,spec in specs.items():
        path=root/spec['fbx']
        if path.exists():raise RuntimeError('FBX exists; export a new revision to preserve evidence: '+str(path))
        choose(cid);bpy.context.scene.render.fps=60
        path.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,use_armature_deform_only=False,
            bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_use_all_bones=True,bake_anim_force_startend_keying=True,bake_anim_step=1,bake_anim_simplify_factor=0,
            axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE')
        results.append({'id':cid,'file':spec['fbx'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frames':bpy.context.scene.frame_end})
    write(root/'reports/blender-export.json',{'blender':bpy.app.version_string,'clips':results,'status':'exported_pending_unreal_roundtrip'})

def check_bake():
    rig=get_rig();C=Matrix(json.loads(bpy.context.scene['animlab_coordinate_matrix']));inverse=C.inverted();scale=abs(C.determinant())**(1/3)
    refs={b['name']:tr(b['rest']) for b in baseline['bones']};rest={n:rig.matrix_world@rig.data.bones[n].matrix_local for n in refs};basis={n:refs[n].inverted()@inverse@rest[n] for n in refs}
    rows=[]
    for cid,clip in clips.items():
        if cid not in specs or specs[cid].get('role')!='baseline':continue
        choose(cid);max_position=max_rotation=0
        for i in sorted({0,len(clip['frames'])//2,len(clip['frames'])-1}):
            bpy.context.scene.frame_set(i+1);bpy.context.view_layer.update()
            for b,t in zip(baseline['bones'],clip['frames'][i]['pose']):
                expected=C@tr(t)@basis[b['name']];actual=rig.matrix_world@rig.pose.bones[b['name']].matrix
                max_position=max(max_position,(expected.translation-actual.translation).length/scale)
                angle=math.degrees(expected.to_quaternion().rotation_difference(actual.to_quaternion()).angle)
                max_rotation=max(max_rotation,min(angle,360-angle))
        rows.append({'id':cid,'sampled_frames':3,'max_position_cm':max_position,'max_rotation_deg':max_rotation})
    write(root/'reports/blender-bake-check.json',{'stage':'actual_blender_evaluation','clips':rows})
    if rows and (max(r['max_position_cm'] for r in rows)>1 or max(r['max_rotation_deg'] for r in rows)>2):raise RuntimeError('Baked baseline differs from runtime source; mark intentional edits as a new candidate revision')

def sample_source():
    """Evaluate editable actions, including constraints, for candidate-vs-import comparison."""
    rig=get_rig();C=Matrix(json.loads(bpy.context.scene['animlab_coordinate_matrix']));inverse=C.inverted()
    refs={b['name']:tr(b['rest']) for b in baseline['bones']}
    inverse_basis={n:(refs[n].inverted()@inverse@rig.matrix_world@rig.data.bones[n].matrix_local).inverted() for n in refs}
    def transform(matrix):
        p,q,s=matrix.decompose();q.normalize()
        return {'p':list(p),'q':[q.x,q.y,q.z,q.w],'s':list(s)}
    rows=[]
    for cid,spec in specs.items():
        choose(cid);frames=[]
        for i in range(bpy.context.scene.frame_end):
            bpy.context.scene.frame_set(i+1);bpy.context.view_layer.update();time=i/60;wid=spec['weapon']
            for event in spec.get('weapon_events',[]):
                if event['t']<=time+1e-6:wid=event['weapon']
            evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            pose=[transform(inverse@evaluated.matrix_world@evaluated.pose.bones[b['name']].matrix@inverse_basis[b['name']]) for b in baseline['bones']]
            weapon=bpy.data.objects['Weapon_'+wid].evaluated_get(bpy.context.evaluated_depsgraph_get())
            frames.append({'t':time,'pose':pose,'weapon':transform(inverse@weapon.matrix_world),'weapon_id':wid})
        rows.append(dict(spec,frames=frames))
    write(root/'capture/blender-source.json',{'schema':'animlab.capture/1','stage':'blender_source','space':manifest['space'],'bones':baseline['bones'],'clips':rows,'source_blend':bpy.data.filepath,'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()})
    print('ANIMLAB_SOURCE_SAMPLED',len(rows))

def configure_cameras():
    scene=bpy.context.scene;C=Matrix(json.loads(scene['animlab_coordinate_matrix']));scale=abs(C.determinant())**(1/3)
    center=C@Vector((0,0,100))
    for view,relative in [('front',(4,0,.3)),('side',(0,-4,.3)),('game',(-3,-3,1))]:
        cam=bpy.data.objects['Camera_'+view];cam.location=center+C.to_3x3()@Vector(relative)/scale
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=3.8

def render():
    choose(args.clip);configure_cameras();scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera_'+args.view]
    scene.render.fps=round(60*args.speed)
    if scene.render.fps<1:raise RuntimeError('Render speed too low')
    out=Path(args.out or root/'reports'/(args.clip+'-'+args.view+'.mp4')).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(out)
    if out.suffix.lower()=='.png':
        scene.frame_set(round(specs[args.clip]['timing']['contact_s']*60)+1);show_weapon(scene);scene.render.image_settings.file_format='PNG';bpy.ops.render.render(write_still=True)
    else:
        scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM';bpy.ops.render.render(animation=True)

class ANIMLAB_OT_select(bpy.types.Operator):
    bl_idname='animlab.select';bl_label='Load action'
    def execute(self,context):choose(context.scene.animlab_clip_choice);return {'FINISHED'}
class ANIMLAB_PT_panel(bpy.types.Panel):
    bl_label='Animation Lab';bl_idname='ANIMLAB_PT_panel';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Animation Lab'
    def draw(self,context):
        layout=self.layout;layout.label(text='Baseline / Review required',icon='ERROR');layout.prop(context.scene,'animlab_clip_choice',text='Action');layout.operator('animlab.select')
        layout.operator('screen.animation_play',text='Play / Pause');layout.label(text='Arrow keys: frame; Timeline: scrub');layout.label(text='Edit FK bones in Pose Mode');layout.label(text='Weapon contact markers follow bone binding');layout.label(text='Save as a new candidate revision')

def ui():
    configure_cameras()
    for cls in [ANIMLAB_OT_select,ANIMLAB_PT_panel]:bpy.utils.register_class(cls)
    bpy.types.Scene.animlab_clip_choice=bpy.props.EnumProperty(name='Action',items=[(cid,cid,'') for cid in specs])
    bpy.context.scene.animlab_clip_choice=next(iter(specs))
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.show_region_ui=True

if show_weapon not in bpy.app.handlers.frame_change_post:bpy.app.handlers.frame_change_post.append(show_weapon)
if args.mode=='prepare':prepare()
elif args.mode=='export':check_bake();export()
elif args.mode=='sample':sample_source()
elif args.mode=='render':render()
else:ui()

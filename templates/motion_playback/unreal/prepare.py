"""Import all clips against one native skeleton and build an editable AnimBP. UE5.8."""
import unreal as u,json,hashlib
from pathlib import Path
root=Path(u.Paths.project_dir()).resolve();binding_path=root/('bindings.pending.json' if (root/'bindings.pending.json').is_file() else 'bindings.json')
definitions=json.loads(binding_path.read_text());destination=definitions.get('unreal_root','/Game/Playback')
if not u.SystemLibrary.get_engine_version().startswith('5.8.'):raise RuntimeError('UE5.8 required')
if not destination.startswith('/Game/Playback') or '..' in destination or u.EditorAssetLibrary.does_directory_exist(destination):raise RuntimeError('Use a new /Game/Playback revision, preserving previous assets')
tools=u.AssetToolsHelpers.get_asset_tools();skeleton=None;sequences={};meshes=[]
for row in definitions['clips']:
    name=row['id'];task=u.AssetImportTask();task.filename=str(root/definitions.get('source_directory','SourceMotion')/(row['clip']+'.fbx'));task.destination_path=destination+'/'+name;task.destination_name=name
    task.automated=True;task.save=True;task.replace_existing=False;task.factory=u.FbxFactory()
    options=u.FbxImportUI();options.automated_import_should_detect_type=False;options.mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH if skeleton is None else u.FBXImportType.FBXIT_ANIMATION
    options.import_mesh=skeleton is None;options.import_as_skeletal=True;options.import_animations=True;options.import_materials=skeleton is None;options.import_textures=skeleton is None;options.create_physics_asset=False
    if skeleton:options.skeleton=skeleton
    animation=options.get_editor_property('anim_sequence_import_data');animation.set_editor_property('use_default_sample_rate',False);animation.set_editor_property('custom_sample_rate',60 if name.startswith('turn_') and definitions.get('turning') else 30)
    for settings in [animation,options.get_editor_property('skeletal_mesh_import_data')]:
        settings.set_editor_property('convert_scene',True);settings.set_editor_property('convert_scene_unit',True);settings.set_editor_property('force_front_x_axis',False)
    task.options=options;tools.import_asset_tasks([task])
    assets=[u.load_asset(p) for p in u.EditorAssetLibrary.list_assets(task.destination_path,True,False)]
    for a in assets:
        if isinstance(a,u.SkeletalMesh):skeleton=a.get_editor_property('skeleton');meshes.append(a)
    clips=[a for a in assets if isinstance(a,u.AnimSequence)]
    if len(clips)!=1:raise RuntimeError('Expected one clip: '+name)
    clip=clips[0]
    if clip.get_editor_property('skeleton')!=skeleton:raise RuntimeError('Mismatched skeleton')
    clip.set_editor_property('bone_compression_settings',u.load_asset('/Engine/Animation/DefaultRecorderBoneCompression'))
    clip.set_editor_property('enable_root_motion',row['motion_owner']=='animation')
    if row['motion_owner']=='animation':clip.set_editor_property('root_motion_root_lock',u.RootMotionRootLock.ANIM_FIRST_FRAME)
    if abs(clip.get_play_length()-row['duration_s'])>.001:raise RuntimeError('Wrong animation length')
    sequences[name]=clip
    if not u.EditorAssetLibrary.save_loaded_assets(assets,False):raise RuntimeError('Save failed')
factory=u.DataAssetFactory();factory.set_editor_property('data_asset_class',u.OAGDPlaybackSet)
bindings=tools.create_asset('Bindings',destination,u.OAGDPlaybackSet,factory);bindings.set_editor_property('revision',definitions['revision']);bindings.set_editor_property('default_action',definitions.get('default_action','action'))
native=[]
for row in definitions['clips']:
    b=u.OAGDClipBinding();b.set_editor_property('id',row['id']);b.set_editor_property('sequence',sequences[row['id']]);b.set_editor_property('loop',row['loop']);b.set_editor_property('motion_owner',row['motion_owner']);b.set_editor_property('controller_owned',row['in_place'])
    b.set_editor_property('layer_only',row.get('layer_only',False))
    events=[]
    for value in row.get('markers',[]):m=u.OAGDMarker();m.set_editor_property('name',value['name']);m.set_editor_property('at_seconds',value['at_s']);events.append(m)
    b.set_editor_property('markers',events);native.append(b)
locomotion=definitions.get('locomotion')
if locomotion:
    b=u.OAGDClipBinding();b.set_editor_property('id','locomotion');b.set_editor_property('sequence',sequences['idle']);b.set_editor_property('loop',True);native.append(b)
    bindings.set_editor_property('locomotion_enabled',True)
    bindings.set_editor_property('walk_speed_mps',definitions['movement_speeds_mps']['walk']);bindings.set_editor_property('run_speed_mps',definitions['movement_speeds_mps']['run'])
bindings.set_editor_property('clips',native)
bindings.set_editor_property('root_motion_enabled',bool(definitions.get('root_motion')))
bindings.set_editor_property('constraints_json',json.dumps(definitions['constraints']) if definitions.get('constraints') else '')
layers=definitions.get('layers')
if layers:
    bindings.set_editor_property('layers_enabled',True);bindings.set_editor_property('upper_root',layers['upper_root']);bindings.set_editor_property('layer_clips',layers['clips'])
    for field,key in [('layer_fade_in','fade_in_s'),('layer_fade_out','fade_out_s'),('layer_replace','replace_s')]:bindings.set_editor_property(field,layers[key])
    observed=definitions['observation_bones']
    bindings.set_editor_property('upper_required_bones',[observed[k] for k in ('dst_head','dst_upperarm_L','dst_forearm_L','dst_hand_L','dst_upperarm_R','dst_forearm_R','dst_hand_R')])
    bindings.set_editor_property('lower_excluded_bones',[definitions['root_bone'],observed['dst_foot_L'],observed['dst_foot_R'],*definitions.get('turn_observation_bones',{}).values()])
factory=u.AnimBlueprintFactory();factory.set_editor_property('parent_class',u.OAGDPlaybackAnimInstance);factory.set_editor_property('target_skeleton',skeleton)
bp=tools.create_asset('ABP_Player',destination,u.AnimBlueprint,factory)
if not u.OAGDPlaybackBuilder.build_graph(bp,bindings,0.0 if definitions.get('root_motion') else locomotion['transition_s'] if locomotion else .12):raise RuntimeError('AnimGraph creation/compilation failed')
u.EditorAssetLibrary.save_loaded_assets([bindings,bp],False)
level=u.get_editor_subsystem(u.LevelEditorSubsystem);level.new_level(destination+'/Example')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world();world.get_world_settings().set_editor_property('default_game_mode',u.load_class(None,'/Script/MotionPlay.ConstraintsGame' if definitions.get('constraints') else '/Script/MotionPlay.RootGame' if definitions.get('root_motion') else '/Script/MotionPlay.MotionGame'))
u.get_editor_subsystem(u.EditorActorSubsystem).spawn_actor_from_class(u.PlayerStart,u.Vector(0,0,100))
level.save_current_level()
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'Content'/destination.removeprefix('/Game/')).rglob('*') if p.is_file()}
(root/(destination.rsplit('/',1)[-1]+'-import-report.json')).write_text(json.dumps({'ok':True,'revision':definitions['revision'],'binding_sha256':hashlib.sha256(binding_path.read_bytes()).hexdigest(),'engine':u.SystemLibrary.get_engine_version(),'clips':{n:a.get_path_name() for n,a in sequences.items()},'mesh':meshes[0].get_path_name(),'blueprint':bp.get_path_name(),'native_files':files},indent=2))

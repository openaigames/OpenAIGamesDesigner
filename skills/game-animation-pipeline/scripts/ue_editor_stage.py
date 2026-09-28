"""Session entry for current work; in-editor /1 helpers retained for compatibility."""
import sys
from pathlib import Path

if __name__=='__main__' and '--session' in sys.argv:
    import argparse
    parser=argparse.ArgumentParser(description='Use the shared engine session; no separate process manager')
    parser.add_argument('--session',action='store_true');parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--request',type=Path,required=True);parser.add_argument('--runtime',type=Path);parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    here=Path(__file__).resolve()
    candidates=[args.runtime] if args.runtime else [here.parents[3],here.parents[2]/'game-preproduction/runtime']
    runtime=next((p for p in candidates if p and (p/'tools/engine_workflow.py').is_file()),None)
    if runtime is None:parser.exit(2,'Provide --runtime pointing to the shared toolkit engine adapter. Legacy editor helpers are not a process-management fallback.\n')
    sys.path.insert(0,str(runtime/'tools'));sys.path.insert(0,str(runtime))
    import engine_workflow
    engine_workflow.execute(args.project.resolve(),args.request.resolve(),args.timeout)
    raise SystemExit(0)

import unreal as u
import os, json
from pathlib import Path

root = Path(os.environ['ANIMLAB_WORKSPACE']).resolve()
stage = os.environ.get('ANIMLAB_STAGE', 'export-reference')

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def export_reference():
    mesh = u.load_asset(os.environ.get('ANIMLAB_MESH', '/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple'))
    if not isinstance(mesh, u.SkeletalMesh):
        raise RuntimeError('Target skeletal mesh is missing')
    path = root / 'source/Manny-reference.fbx'
    if path.exists():raise RuntimeError('Reference exists; preserve it and use a new workspace revision')
    path.parent.mkdir(parents=True, exist_ok=True)
    task = u.AssetExportTask()
    task.object = mesh
    task.filename = str(path)
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    options = u.FbxExportOption()
    options.set_editor_property('ascii', False)
    options.set_editor_property('fbx_export_compatibility', u.FbxExportCompatibility.FBX_2020)
    options.set_editor_property('level_of_detail', False)
    options.set_editor_property('export_morph_targets', False)
    task.options = options
    task.exporter = u.SkeletalMeshExporterFBX()
    if not u.Exporter.run_asset_export_task(task) or not path.is_file():
        raise RuntimeError('Reference FBX export failed')
    skeleton = mesh.get_editor_property('skeleton')
    save_json(root / 'source/rig.json', {'ue_mesh': mesh.get_path_name(), 'ue_skeleton': skeleton.get_path_name(), 'reference_fbx': 'source/Manny-reference.fbx'})
    u.log('ANIMLAB_REFERENCE_EXPORTED ' + str(path))

def import_clips():
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    skeleton = u.load_asset(manifest['rig']['ue_skeleton'])
    tasks = []
    for clip in manifest['clips']:
        source = root / clip['fbx']
        if not source.is_file():
            raise RuntimeError('Missing FBX: ' + str(source))
        task = u.AssetImportTask()
        task.filename = str(source)
        package=clip['ue_asset'].split('.')[0]
        if not package.startswith('/Game/'):raise RuntimeError('Only explicit /Game/ animation destinations are supported')
        task.destination_path,task.destination_name=package.rsplit('/',1)
        task.automated = True
        task.replace_existing = False
        task.save = True
        options = u.FbxImportUI()
        options.set_editor_property('automated_import_should_detect_type', False)
        options.set_editor_property('mesh_type_to_import', u.FBXImportType.FBXIT_ANIMATION)
        options.set_editor_property('import_mesh', False)
        options.set_editor_property('import_animations', True)
        options.set_editor_property('import_materials', False)
        options.set_editor_property('import_textures', False)
        options.set_editor_property('skeleton', skeleton)
        anim_options = options.get_editor_property('anim_sequence_import_data')
        anim_options.set_editor_property('use_default_sample_rate', False)
        anim_options.set_editor_property('custom_sample_rate', 60)
        anim_options.set_editor_property('import_bone_tracks', True)
        task.options = options
        # Force this tested legacy animation importer, independent of Interchange defaults.
        task.factory = u.FbxFactory()
        expected = package
        if u.EditorAssetLibrary.does_asset_exist(expected):
            raise RuntimeError('Destination already exists; use a new revision or explicit reimport: ' + expected)
        tasks.append((clip, task))
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t for _, t in tasks])
    results = []
    for clip, task in tasks:
        asset = u.load_asset(clip['ue_asset'])
        if not isinstance(asset, u.AnimSequence):
            raise RuntimeError('No AnimSequence at ' + clip['ue_asset'] + '; outputs=' + str(task.imported_object_paths))
        if asset.get_editor_property('skeleton') != skeleton:
            raise RuntimeError('Imported skeleton mismatch')
        results.append({'id': clip['id'], 'ue_asset': asset.get_path_name(), 'length_s': asset.get_play_length(), 'skeleton': skeleton.get_path_name()})
    save_json(root / 'reports/unreal-import.json', {'stage': 'actual_editor_import', 'clips': results})
    u.log('ANIMLAB_IMPORT_COMPLETE clips=' + str(len(results)))

def build_stage():
    subsystem = u.get_editor_subsystem(u.LevelEditorSubsystem)
    path = '/Game/AnimationLab/Maps/AnimationLab'
    if u.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError('Lab map already exists; preserve edits and build a new revision')
    if not subsystem.new_level(path):
        raise RuntimeError('Could not create independent lab map')
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    plane = actors.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, 0, -1))
    plane.set_actor_label('Neutral inspection floor')
    plane.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane'))
    plane.set_actor_scale3d(u.Vector(20,20,1))
    for name, yaw, intensity in [('Key',145,4),('Fill',-35,2)]:
        light = actors.spawn_actor_from_class(u.DirectionalLight, u.Vector(0,0,500), u.Rotator(-45,yaw,0))
        light.set_actor_label(name)
        light.light_component.set_editor_property('intensity', intensity)
    actors.spawn_actor_from_class(u.SkyAtmosphere, u.Vector(0,0,0))
    sky = actors.spawn_actor_from_class(u.SkyLight, u.Vector(0,0,500))
    sky.light_component.set_editor_property('intensity', 1.0)
    sky.light_component.set_editor_property('real_time_capture', True)
    start = actors.spawn_actor_from_class(u.PlayerStart, u.Vector(0,0,0))
    start.set_actor_label('Animation lab origin')
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', u.load_class(None, '/Script/'+os.environ.get('ANIMLAB_MODULE','RiftDuel')+'.AnimationLabMode'))
    subsystem.save_current_level()
    u.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    u.log('ANIMLAB_MAP_SAVED ' + path)

def finish_stage():
    """Explicit lighting/material update for the isolated generated lab map."""
    subsystem=u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not subsystem.load_level('/Game/AnimationLab/Maps/AnimationLab'):raise RuntimeError('Lab map missing')
    mat=u.load_asset('/Game/AnimationLab/Materials/M_Inspection')
    if not mat:
        mat=u.AssetToolsHelpers.get_asset_tools().create_asset('M_Inspection','/Game/AnimationLab/Materials',u.Material,u.MaterialFactoryNew())
        library=u.MaterialEditingLibrary
        tint=library.create_material_expression(mat,u.MaterialExpressionVectorParameter,-500,0);tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',u.LinearColor(.5,.55,.6,1))
        rough=library.create_material_expression(mat,u.MaterialExpressionConstant,-300,200);rough.set_editor_property('r',.8)
        ambient=library.create_material_expression(mat,u.MaterialExpressionMultiply,-250,-100);ambient.set_editor_property('const_b',.3)
        library.connect_material_expressions(tint,'',ambient,'A');library.connect_material_property(tint,'',u.MaterialProperty.MP_BASE_COLOR);library.connect_material_property(rough,'',u.MaterialProperty.MP_ROUGHNESS);library.connect_material_property(ambient,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
        library.recompile_material(mat);u.EditorAssetLibrary.save_loaded_asset(mat)
    mat.set_editor_property('used_with_skeletal_mesh',True)
    u.MaterialEditingLibrary.recompile_material(mat);u.EditorAssetLibrary.save_loaded_asset(mat)
    floor=u.load_asset('/Game/AnimationLab/Materials/MI_Floor')
    if not floor:floor=u.AssetToolsHelpers.get_asset_tools().create_asset('MI_Floor','/Game/AnimationLab/Materials',u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
    u.MaterialEditingLibrary.set_material_instance_parent(floor,mat)
    u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(floor,'Tint',u.LinearColor(.045,.055,.07,1))
    u.EditorAssetLibrary.save_loaded_asset(floor)
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if isinstance(actor,u.DirectionalLight):
            component=actor.light_component;component.set_editor_property('mobility',u.ComponentMobility.MOVABLE)
            component.set_editor_property('intensity',3.0 if actor.get_actor_label()=='Key' else 1.5)
            component.set_editor_property('forward_shading_priority',1 if actor.get_actor_label()=='Key' else 0)
        if isinstance(actor,u.StaticMeshActor) and actor.get_actor_label()=='Neutral inspection floor':actor.static_mesh_component.set_material(0,floor)
    subsystem.save_current_level();u.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    u.log('ANIMLAB_INSPECTION_LIGHTING_READY')

if stage == 'export-reference': export_reference()
elif stage == 'import': import_clips()
elif stage == 'build-stage': build_stage();finish_stage()
elif stage == 'finish-stage': finish_stage()
else: raise RuntimeError('Unknown stage ' + stage)

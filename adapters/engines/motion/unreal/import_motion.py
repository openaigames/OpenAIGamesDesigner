"""UE 5.8 editor script; OAGD_MOTION_JOB selects a new revision, never reimports originals."""
import hashlib, json, os
from pathlib import Path
import unreal as u

job=json.loads(Path(os.environ['OAGD_MOTION_JOB']).read_text(encoding='utf-8'))
out=Path(job['report'])
if out.exists():raise ValueError('Import report already exists; choose a new job revision')
try:
    version=u.SystemLibrary.get_engine_version()
    if not version.startswith('5.8.'):raise ValueError('This adapter is pinned to UE 5.8')
    destination=job['destination']
    if not destination.startswith('/Game/') or '..' in destination or u.EditorAssetLibrary.does_directory_exist(destination):
        raise ValueError('Choose a new /Game/ revision directory')
    source=Path(job['fbx'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=job['sha256']:raise ValueError('FBX changed before import')
    task=u.AssetImportTask();task.filename=str(source);task.destination_path=destination;task.destination_name=job['name']
    task.automated=True;task.replace_existing=False;task.save=True;task.factory=u.FbxFactory()
    options=u.FbxImportUI();options.automated_import_should_detect_type=False
    options.mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH;options.import_mesh=True;options.import_as_skeletal=True
    options.import_animations=True;options.import_materials=False;options.import_textures=False;options.create_physics_asset=False
    options.get_editor_property('skeletal_mesh_import_data').set_editor_property('import_morph_targets',True)
    anim_options=options.get_editor_property('anim_sequence_import_data')
    for settings in (options.get_editor_property('skeletal_mesh_import_data'),anim_options):
        settings.set_editor_property('convert_scene',True)
        settings.set_editor_property('convert_scene_unit',True)
        settings.set_editor_property('force_front_x_axis',False)
    anim_options.set_editor_property('use_default_sample_rate',False)
    anim_options.set_editor_property('custom_sample_rate',int(job['fps']))
    anim_options.set_editor_property('import_bone_tracks',True)
    task.options=options;u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    # FbxFactory's task list can contain only the mesh although it created a
    # skeleton and animation too. Read the newly created package directory.
    paths=list(u.EditorAssetLibrary.list_assets(destination,recursive=True,include_folder=False))
    assets=[u.load_asset(p) for p in paths]
    meshes=[a for a in assets if isinstance(a,u.SkeletalMesh)];clips=[a for a in assets if isinstance(a,u.AnimSequence)]
    if len(meshes)!=1 or len(clips)!=1:raise ValueError('Expected one native SkeletalMesh and AnimSequence: '+str(task.imported_object_paths))
    mesh,clip=meshes[0],clips[0]
    skeleton=mesh.get_editor_property('skeleton')
    if skeleton!=clip.get_editor_property('skeleton'):raise ValueError('Imported mesh/animation skeleton mismatch')
    # Use the engine's recording profile for the reference roundtrip. The game's
    # shipping compression is a separate consumer change that needs revalidation.
    compression=u.load_asset('/Engine/Animation/DefaultRecorderBoneCompression')
    if not compression:raise ValueError('Missing UE recording compression profile')
    clip.set_editor_property('bone_compression_settings',compression)
    if not u.EditorAssetLibrary.save_loaded_assets(assets,only_if_is_dirty=False):raise ValueError('Could not save all imported dependencies')
    content=Path(u.Paths.project_content_dir()).resolve();dependencies={}
    for p in paths:
        file=content/(p.split('.')[0][len('/Game/'):]+'.uasset')
        if not file.is_file():raise ValueError('Imported native asset was not saved: '+str(file))
        dependencies[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
    result={'ok':True,'engine_version':version,'mesh':mesh.get_path_name(),'animation':clip.get_path_name(),
            'skeleton':skeleton.get_path_name(),'length_s':clip.get_play_length(),'source_sha256':job['sha256'],
            'method':'UE 5.8 FbxFactory actual native import','runtime_capture':'not_run','assets':paths,'native_dependencies':dependencies,
            'compression':compression.get_path_name(),'compression_codecs':[c.get_class().get_name() for c in compression.get_editor_property('codecs')]}
except Exception as error:
    result={'ok':False,'error':str(error)}
with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
if not result['ok']:raise RuntimeError(result['error'])

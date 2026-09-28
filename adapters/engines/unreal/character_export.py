"""Read actual native character consumers; export derived FBX through existing session."""
from pathlib import Path
import json
import hashlib
import unreal
from observation_worker import actor_detail

def checksum(path):
    if not path:return None
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def native_file(obj,project):
    package=obj.get_path_name().split('.')[0]
    if not package.startswith('/Game/'):
        raise ValueError('Character export requires project /Game assets; external plugin mounts need an explicit project exporter')
    path=Path(project)/'Content'/(package[6:]+'.uasset')
    if not path.is_file():raise ValueError('Native consumer asset file missing: '+str(path))
    return str(path.resolve())

def export_fbx(obj,path,mesh=True):
    if path.exists():raise ValueError('Derived preview already exists; use a new session')
    path.parent.mkdir(parents=True,exist_ok=True)
    task=unreal.AssetExportTask();task.object=obj;task.filename=str(path);task.automated=True;task.prompt=False;task.replace_identical=False
    task.exporter=unreal.SkeletalMeshExporterFBX() if isinstance(obj,unreal.SkeletalMesh) else unreal.AnimSequenceExporterFBX()
    options=unreal.FbxExportOption();options.set_editor_property('ascii',False);options.set_editor_property('level_of_detail',False)
    options.set_editor_property('export_preview_mesh',mesh);task.options=options
    if not unreal.Exporter.run_asset_export_task(task) or not path.is_file() or path.stat().st_size<32:raise ValueError('Native FBX export did not complete')
    with path.open('rb') as stream:
        if not stream.read(23).startswith(b'Kaydara FBX Binary'):raise ValueError('Derived preview is not binary FBX')
    return str(path.resolve())

def collect(request,find_actor):
    rows=[];workspace=Path(request['workspace']);project=Path(request['project'])
    for spec in request.get('character_exports',[]):
        actor=find_actor(spec['target']);components=[c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()==spec['component']]
        if len(components)!=1:raise ValueError('Character component must resolve exactly once')
        component=components[0];mesh=component.get_editor_property('skeletal_mesh_asset')
        if not mesh:raise ValueError('Character consumer has no skeletal mesh')
        skeleton=mesh.get_editor_property('skeleton');actions=[];dependencies=[native_file(mesh,project),native_file(skeleton,project)]
        try:
            single=component.get_editor_property('animation_data').get_editor_property('anim_to_play')
            if single:actions.append({'id':'single-node','label':single.get_name(),'asset':single.get_path_name(),'basis':'static_single_node_reference'})
        except Exception:pass
        anim_class=component.get_editor_property('anim_class')
        if anim_class:
            blueprint=unreal.load_asset(anim_class.get_path_name().split('.')[0])
            if not blueprint:raise ValueError('AnimBP author asset is unresolved')
            dependencies.append(native_file(blueprint,project))
            registry=unreal.AssetRegistryHelpers.get_asset_registry()
            options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
                include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
            queue=[blueprint.get_path_name().split('.')[0]];seen=set()
            while queue:
                package=queue.pop()
                if package in seen:continue
                seen.add(package)
                if len(seen)>1000:raise ValueError('AnimBP dependency traversal limit; provide project availability exporter')
                for target in registry.get_dependencies(package,options):
                    target=str(target)
                    if not target.startswith('/Game/'):continue
                    obj=unreal.load_asset(target)
                    if not obj:raise ValueError('AnimBP reference cannot load: '+target)
                    dependencies.append(native_file(obj,project));queue.append(target)
                    if isinstance(obj,unreal.AnimSequence):actions.append({'id':obj.get_name(),'label':obj.get_name(),'asset':obj.get_path_name(),'basis':'static_animbp_dependency_not_runtime_observation'})
        if spec.get('actions_exporter'):
            raw=actor.call_method(spec['actions_exporter'],())
            if not isinstance(raw,str) or len(raw)>1048576:raise ValueError('Read-only actions exporter must return bounded JSON')
            data=json.loads(raw)
            if not isinstance(data,dict) or not isinstance(data.get('actions'),list) or len(data['actions'])>200:raise ValueError('Invalid project availability export')
            # Explicit source files are required to version a dynamic collection.
            for package in data.get('source_assets',[]):
                obj=unreal.load_asset(package)
                if not obj:raise ValueError('Availability author source missing')
                dependencies.append(native_file(obj,project))
            if not data.get('source_assets'):raise ValueError('Project availability exporter must identify native source_assets')
            for action in data['actions']:
                if not all(isinstance(action.get(k),str) and action[k] for k in ['id','label','asset']):raise ValueError('Availability action requires id,label,asset')
                actions.append({**action,'basis':'project_readonly_available_set_not_observed_playback'})
        unique={a['asset']:a for a in actions};actions=[]
        folder=workspace/'previews/engine'/request['request_id']/spec['id']
        model_preview=export_fbx(mesh,folder/'model.fbx') if spec.get('previews') else None
        for n,action in enumerate(unique.values()):
            animation=unreal.load_asset(action['asset'])
            if not isinstance(animation,unreal.AnimSequence) or animation.get_editor_property('skeleton')!=skeleton:raise ValueError('Available action needs actual compatible AnimSequence')
            file=native_file(animation,project);dependencies.append(file)
            preview=export_fbx(animation,folder/('action-%03d.fbx'%n)) if spec.get('previews') else None
            actions.append({**action,'file':file,'preview':preview,'preview_sha256':checksum(preview)})
        rows.append({'id':spec['id'],'title':spec.get('title',actor.get_actor_label()),'role':spec.get('role','shared'),
            'model':native_file(mesh,project),'preview':model_preview,'preview_sha256':checksum(model_preview),'actions':actions,'dependencies':sorted(set(dependencies)),
            'consumer':actor_detail(actor),'scope':'Actual editor consumer references/explicit availability; no runtime action inferred from absence'})
    return rows

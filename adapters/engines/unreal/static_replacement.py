"""UE 5.8 native static derivation and reversible stable-ID scene replacement.

Caller supplies a verified frozen plan and works in a NEW output package/map.
No existing source, derived asset or map is overwritten by this module.
"""
import json,hashlib,math
from pathlib import Path
import unreal
from static_meshes import configure,inspect_mesh

def prepare(plan,folder,destination):
    payload={k:v for k,v in plan.items() if k!='plan_id'}
    if plan.get('schema')!='oagd.static-plan/1' or hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()!=plan.get('plan_id'):raise ValueError('Frozen plan changed; prepare a new version')
    if hashlib.sha256((Path(folder)/'baseline.json').read_bytes()).hexdigest()!=plan['scene_sha256']:raise ValueError('Frozen scene changed')
    if not destination.startswith('/Game/') or unreal.EditorAssetLibrary.does_directory_exist(destination):raise ValueError('Use a new /Game destination directory')
    sources=[]
    for a in plan['assets']:
        p=(Path(folder)/a['source']).resolve()
        if not p.is_relative_to(Path(folder).resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=a['source_sha256']:raise ValueError('Source changed')
        sources.append(p)
    output={};reports=[];tools=unreal.AssetToolsHelpers.get_asset_tools()
    for a,p in zip(plan['assets'],sources):
        package=destination+'/'+a['id'];task=unreal.AssetImportTask();task.filename=str(p);task.destination_path=package+'/Imported';task.automated=True;task.save=True;task.replace_existing=False
        tools.import_asset_tasks([task])
        meshes=[x for x in task.get_objects() if isinstance(x,unreal.StaticMesh)]
        if not meshes:meshes=[unreal.load_asset(x) for x in task.imported_object_paths if isinstance(unreal.load_asset(x),unreal.StaticMesh)]
        if len(meshes)!=1:raise ValueError('Expected exactly one imported static mesh')
        source=meshes[0];source_before=json.loads(unreal.OAGDStaticAssets.inspect_mesh(source))
        derived_path=package+'/Derived'
        report=configure({'op':'static_mesh_configure','source':source.get_path_name().split('.')[0],'path':derived_path,'strategy':'lod','asset_role':'building','lods':plan['unreal_lods'],'lod_for_collision':0},unreal.load_asset,lambda x:x)
        mesh=unreal.load_asset(derived_path);materials={x['name']:x for x in a['materials']}
        slots=mesh.get_editor_property('static_materials')
        names=[str(x.get_editor_property('imported_material_slot_name')) for x in slots]
        if set(names)!=set(materials):raise ValueError('Imported material slot names differ: '+str(names))
        for i,name in enumerate(names):
            spec=materials[name];m=tools.create_asset(name,package+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
            for param,cls,value,prop in [('BaseColor',unreal.MaterialExpressionVectorParameter,unreal.LinearColor(*spec['base_color']),unreal.MaterialProperty.MP_BASE_COLOR),('Roughness',unreal.MaterialExpressionScalarParameter,spec['roughness'],unreal.MaterialProperty.MP_ROUGHNESS),('Metallic',unreal.MaterialExpressionScalarParameter,spec['metallic'],unreal.MaterialProperty.MP_METALLIC)]:
                expr=unreal.MaterialEditingLibrary.create_material_expression(m,cls,-300,i*150);expr.set_editor_property('parameter_name',param);expr.set_editor_property('default_value',value);unreal.MaterialEditingLibrary.connect_material_property(expr,'',prop)
            unreal.MaterialEditingLibrary.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m);mesh.set_material(i,m)
        mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False)
        if json.loads(unreal.OAGDStaticAssets.inspect_mesh(source))!=source_before:raise ValueError('Imported source was modified')
        output[a['id']]=mesh;reports.append({'asset':a['id'],'source':source_before,'derived':json.loads(unreal.OAGDStaticAssets.inspect_mesh(mesh)),'lod_processing':report})
    return output,reports

def lookup():
    out={}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        for tag in actor.tags:
            key=str(tag)
            if key in out:raise ValueError('Duplicate stable ID/tag: '+key)
            out[key]=actor
    return out

def apply(plan,baseline,assets):
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);objects=lookup();records={r['id']:r for r in baseline['meshes']};used=set()
    # Preflight every mapping and mesh before staging any actor.
    for r in plan['replacements']:
        if r['id'] in objects or r['asset'] not in assets:raise ValueError('Existing replacement or missing derived mesh')
        for key in r['targets']:
            if key in used or key not in records or key not in objects or not unreal.OAGDStaticAssets.geometry_matches(objects[key],json.dumps(records[key])):raise ValueError('Missing, reused or edited target: '+key)
            if hashlib.sha256(json.dumps(records[key],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()!=r['target_fingerprints'][key]:raise ValueError('Target baseline changed: '+key)
            used.add(key)
    receipt={'roots':[],'undo':[]}
    try:
        for r in plan['replacements']:
            # Native GLB local basis is (X,Z,Y); the scene uses (-Z,X,Y).
            # A +90 degree UE yaw converts the imported mesh to the scene basis.
            x,y,z=r['position'];a=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(-z*100,x*100,y*100),unreal.Rotator(pitch=0,yaw=90-r['yaw_degrees'],roll=0))
            receipt['roots'].append(a);a.tags=[r['id']];a.set_actor_label(r['id']);a.set_actor_scale3d(unreal.Vector(r['scale'],r['scale'],r['scale']))
            c=a.static_mesh_component;c.set_mobility(unreal.ComponentMobility.STATIC);c.set_static_mesh(assets[r['asset']]);c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if r['collision']=='source_mesh' else unreal.CollisionEnabled.NO_COLLISION)
            unreal.EditorAssetLibrary.set_metadata_tag(assets[r['asset']],'OAGDSourceSHA256',next(x['source_sha256'] for x in plan['assets'] if x['id']==r['asset']))
        for r in plan['replacements']:
            for key in r['targets']:
                a=objects[key];c=a.get_component_by_class(unreal.ProceduralMeshComponent)
                receipt['undo'].append((a,c,c.get_editor_property('visible'),c.get_collision_enabled()))
                c.set_visibility(False)
                if r['collision']=='source_mesh':c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    except Exception:
        rollback(receipt);raise
    return receipt

def rollback(receipt):
    for a,c,visible,collision in receipt['undo']:c.set_visibility(visible);c.set_collision_enabled(collision)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in receipt['roots']:actors.destroy_actor(a)
    receipt['roots']=[];receipt['undo']=[]

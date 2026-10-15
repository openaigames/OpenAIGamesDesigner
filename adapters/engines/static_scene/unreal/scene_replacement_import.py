"""UE 5.8 editor replacement transactions with persistent conflict checks.

Grayboxes are StaticMeshActors. Save the scene and receipt as a new revision.
Runtime consumers are ordinary native actors, meshes and collision.
"""
import copy
import json
from pathlib import Path
import unreal
import static_scene_import as importer
from static_scene import fingerprint, sha
from scene_replacement import read_plan, state_number


def actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def resource_state(asset, visited=None):
    if not asset:
        return None
    visited = {} if visited is None else visited
    path = asset.get_path_name()
    if path in visited:
        return path
    filename = unreal.SystemLibrary.get_system_path(asset)
    if not filename or not Path(filename).is_file():
        raise ValueError('Save native assets before capturing/replacing: '+path)
    package = path.split('.')[0]
    if package in {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}:
        raise ValueError('Unsaved native asset edits: '+path)
    visited[path] = sha(Path(filename))
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_files_synchronous([filename],force_rescan=True)
    options = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True, include_searchable_names=False, include_soft_management_references=False, include_hard_management_references=False)
    for dep in registry.get_dependencies(package, options) or []:
        dep = str(dep)
        if dep.startswith('/Script/'):
            continue
        obj = unreal.load_asset(dep)
        if obj:
            resource_state(obj, visited)
    return dict(sorted(visited.items()))


def vec(v, canonical_zero=True):
    return [state_number(x,canonical_zero) for x in (v.x,v.y,v.z)]


def enum_values(cls):
    return sorted({getattr(cls, name) for name in dir(cls) if isinstance(getattr(cls, name), cls)}, key=lambda x:x.value)


def snapshot(actor, canonical_zero=True):
    if actor.get_class()!=unreal.StaticMeshActor.static_class() or len(actor.get_components_by_class(unreal.SceneComponent)) != 1:
        raise ValueError('Supported actors have one native StaticMeshComponent; preserve custom actors separately')
    c = actor.static_mesh_component
    t = actor.get_actor_transform()
    q = t.rotation
    parent = actor.get_attach_parent_actor()
    children = sorted(actor.get_attached_actors(), key=lambda a:a.get_actor_label())
    return {'label':actor.get_actor_label(),'class':actor.get_class().get_path_name(),
            'parent':parent.get_actor_label() if parent else None,'tags':sorted(map(str,actor.tags)),
            'transform':[vec(t.translation,canonical_zero),[state_number(x,canonical_zero) for x in (q.x,q.y,q.z,q.w)],vec(t.scale3d,canonical_zero)],
            'actor_collision':actor.get_actor_enable_collision(),'visible':c.get_editor_property('visible'),
            'hidden':c.get_editor_property('hidden_in_game'),'mobility':str(c.get_editor_property('mobility')),
            'collision':str(c.get_collision_enabled()),'profile':str(c.get_collision_profile_name()),
            'responses':{str(i):str(c.get_collision_response_to_channel(i)) for i in enum_values(unreal.CollisionChannel)},
            'mesh':resource_state(c.get_editor_property('static_mesh')),'materials':[resource_state(c.get_material(i)) for i in range(c.get_num_materials())],
            'children':[snapshot(x,canonical_zero) for x in children]}


def lookup():
    out = {}
    for a in actors().get_all_level_actors():
        for t in a.tags:
            if str(t).startswith('OAGD_ID_'):
                key = str(t)[8:]
                if key in out:
                    raise ValueError('Duplicate stable ID: '+key)
                out[key] = a
    return out


def capture(ids):
    objects = lookup()
    rows = {}
    for key in ids:
        if key not in objects:
            raise ValueError('Missing target: '+key)
        if objects[key].get_attach_parent_actor():
            raise ValueError('Graybox targets must be unattached StaticMeshActors')
        state = snapshot(objects[key])
        rows[key] = {'snapshot':state,'fingerprint':fingerprint(state)}
    return {'schema':'oagd.scene-baseline/1','engine':'unreal','fingerprint_format':'canonical-zero/1','objects':rows}


def prepare_resources(folder, destination):
    plan = read_plan(folder)
    if plan['engine'] != 'unreal' or unreal.EditorAssetLibrary.does_directory_exist(destination):
        raise ValueError('UE plan and new native resource destination required')
    prepared = {}
    for aid, item in plan['assets'].items():
        p, meshes, report = importer.prepare(Path(folder)/item['revision'],destination+'/'+aid)
        collision = {}
        selected = {i for r in plan['replacements'] if r['asset']==aid and r['collision']['policy']=='source_mesh' for i in r['collision']['nodes']}
        for n in p['nodes']:
            if n['id'] not in selected:
                continue
            mid = n['mesh']
            if mid in collision:
                continue
            mesh = unreal.EditorAssetLibrary.duplicate_asset(meshes[mid].get_path_name(),destination+'/'+aid+'/Collision_'+str(mid))
            mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False)
            collision[mid] = mesh
        prepared[aid] = {'plan':p,'meshes':meshes,'collision':collision,'readback':report}
    return plan, prepared


def preflight(plan, resources):
    if plan.get('engine') != 'unreal' or plan.get('schema') != 'oagd.scene-replacement/1':
        raise ValueError('Wrong native plan')
    objects = lookup()
    existing = {str(t) for a in actors().get_all_level_actors() for t in a.tags}
    labels = {a.get_actor_label() for a in actors().get_all_level_actors()}
    for r in plan['replacements']:
        if 'Replacement_'+r['id'] in existing or r['id'] in labels:
            raise ValueError('Replacement already exists')
        native = resources.get(r['asset'])
        if not native or native['plan']['plan_id'] != plan['assets'][r['asset']]['plan_id']:
            raise ValueError('Missing or mismatched native revision')
        for key in r['targets']:
            if key not in objects or fingerprint(snapshot(objects[key],plan['baseline'].get('fingerprint_format')=='canonical-zero/1')) != plan['baseline']['objects'][key]['fingerprint']:
                raise ValueError('Graybox changed: '+key)
    return objects


def state(actor):
    c = actor.static_mesh_component
    return {'visible':c.get_editor_property('visible'),'hidden':c.get_editor_property('hidden_in_game'),
            'collision':c.get_collision_enabled().value,'profile':str(c.get_collision_profile_name()),
            'responses':{str(i.value):c.get_collision_response_to_channel(i).value for i in enum_values(unreal.CollisionChannel)}}


def restore(actor, before):
    c = actor.static_mesh_component
    c.set_visibility(before['visible'],False);c.set_hidden_in_game(before['hidden'],False)
    c.set_collision_profile_name(before['profile'])
    c.set_collision_enabled(next(x for x in enum_values(unreal.CollisionEnabled) if x.value==before['collision']))
    for channel in enum_values(unreal.CollisionChannel):
        desired=before['responses'][str(channel.value)]
        if c.get_collision_response_to_channel(channel).value!=desired:
            c.set_collision_response_to_channel(channel,next(x for x in enum_values(unreal.CollisionResponse) if x.value==desired))


def apply(plan, resources):
    objects = preflight(plan, resources)
    receipt = {'schema':'oagd.replacement-receipt/1','fingerprint_format':'canonical-zero/1','plan_id':plan['plan_id'],'targets':{},'roots':{}}
    spawned = []
    try:
        for r in plan['replacements']:
            native = resources[r['asset']]
            root, nodes = importer.assemble(native['plan'],native['meshes'],'Replacement_'+r['id'])
            spawned.append(root)
            root.set_actor_label(r['id'])
            x,y,z = r['position']
            root.set_actor_location(unreal.Vector(-z*100,x*100,y*100),False,True)
            root.set_actor_rotation(unreal.Rotator(pitch=0,yaw=90-r['yaw_degrees'],roll=0),False)
            root.set_actor_scale3d(unreal.Vector(r['scale'],r['scale'],r['scale']))
            policy = r['collision']['policy']
            if policy == 'source_mesh':
                root.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
                for n in native['plan']['nodes']:
                    c = nodes[n['id']].static_mesh_component;c.set_mobility(unreal.ComponentMobility.STATIC)
                    if n['id'] in r['collision']['nodes']:
                        c.set_static_mesh(native['collision'][n['mesh']]);c.set_collision_profile_name('BlockAll')
                        c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            elif policy == 'boxes':
                cube = unreal.load_asset('/Engine/BasicShapes/Cube')
                for i,b in enumerate(r['collision']['boxes']):
                    a = actors().spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
                    a.set_actor_label(r['id']+'_Proxy_'+str(i));a.tags=['OAGD_PROXY','Replacement_'+r['id']]
                    c=a.static_mesh_component;c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_static_mesh(cube)
                    a.attach_to_actor(nodes[b['node']],'',unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
                    x,y,z=b['center'];sx,sy,sz=b['size']
                    a.set_actor_relative_location(unreal.Vector(x*100,z*100,y*100),False,True);a.set_actor_relative_scale3d(unreal.Vector(sx,sz,sy))
                    c.set_visibility(False,False);c.set_hidden_in_game(True,False);c.set_collision_profile_name('BlockAll')
            receipt['roots'][r['id']] = fingerprint(snapshot(root))
        for r in plan['replacements']:
            for key in r['targets']:
                a=objects[key];receipt['targets'][key]={'state':state(a),'before':fingerprint(snapshot(a))}
                c=a.static_mesh_component;c.set_visibility(False,False);c.set_hidden_in_game(True,False)
                if r['collision']['policy']!='retain_graybox':c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                receipt['targets'][key]['after']=fingerprint(snapshot(a))
        return receipt
    except Exception:
        for key,row in receipt['targets'].items():restore(objects[key],row['state'])
        for root in reversed(spawned):destroy_tree(root)
        raise


def destroy_tree(root):
    for child in root.get_attached_actors():destroy_tree(child)
    actors().destroy_actor(root)


def rollback(receipt):
    if receipt.get('schema') != 'oagd.replacement-receipt/1':raise ValueError('Invalid receipt')
    if receipt.get('fingerprint_format') not in (None,'canonical-zero/1'):raise ValueError('Unknown receipt fingerprint format')
    canonical=receipt.get('fingerprint_format')=='canonical-zero/1'
    objects=lookup();labels={}
    for a in actors().get_all_level_actors():labels.setdefault(a.get_actor_label(),[]).append(a)
    for key,row in receipt['targets'].items():
        if key not in objects or fingerprint(snapshot(objects[key],canonical))!=row['after']:raise ValueError('Hidden original changed: '+key)
    for label,expected in receipt['roots'].items():
        if len(labels.get(label,[]))!=1 or fingerprint(snapshot(labels[label][0],canonical))!=expected:raise ValueError('Replacement changed: '+label)
    for key,row in receipt['targets'].items():restore(objects[key],row['state'])
    for label in receipt['roots']:destroy_tree(labels[label][0])
    return {'ok':True,'plan_id':receipt['plan_id']}


# Runtime passage checks use ScenePassage.h in a live game world. Editor
# commandlet worlds do not reliably register a physics scene for capsule traces.

"""UE 5.8 editor adapter: native meshes/materials + editable actor hierarchy.

Call prepare(revision, new_game_folder), then assemble(plan, meshes, prefix).
Save the caller's NEW level with LevelEditorSubsystem. No runtime plugin needed.
"""
import json
import math
from pathlib import Path
import re
import unreal
from static_scene import read_plan


def quaternion(m):
    s = math.sqrt(sum(m[i]*m[i] for i in (0, 1, 2)))
    a = [[m[c*4+r]/s for c in range(3)] for r in range(3)]
    trace = sum(a[i][i] for i in range(3))
    if trace > 0:
        t = math.sqrt(trace+1)*2
        q = [(a[2][1]-a[1][2])/t, (a[0][2]-a[2][0])/t, (a[1][0]-a[0][1])/t, t/4]
    else:
        i = max(range(3), key=lambda j: a[j][j])
        j, k = (i+1)%3, (i+2)%3
        t = math.sqrt(1+a[i][i]-a[j][j]-a[k][k])*2
        q = [0., 0., 0., 0.]
        q[i], q[j], q[k], q[3] = t/4, (a[j][i]+a[i][j])/t, (a[k][i]+a[i][k])/t, (a[k][j]-a[j][k])/t
    return q, s


def inspect_mesh(mesh):
    slots = []
    for slot in mesh.get_editor_property('static_materials'):
        material = slot.get_editor_property('material_interface')
        if not material:
            raise ValueError('Native mesh has an empty material slot')
        textures = []
        bindings = [(str(p.parameter_info.name), p.parameter_value) for p in material.get_editor_property('texture_parameter_values')] if isinstance(material, unreal.MaterialInstanceConstant) else [('', t) for t in unreal.MaterialEditingLibrary.get_used_textures(material)]
        for parameter, texture in bindings:
            if isinstance(texture, unreal.Texture2D):
                textures.append({'parameter': parameter, 'path': texture.get_path_name(), 'srgb': texture.get_editor_property('srgb'),
                                 'compression': str(texture.get_editor_property('compression_settings')),
                                 'flip_green': texture.get_editor_property('flip_green_channel')})
        params = {}
        vectors = {}
        if isinstance(material, unreal.MaterialInstanceConstant):
            for entry in material.get_editor_property('scalar_parameter_values'):
                params[str(entry.parameter_info.name)] = entry.parameter_value
            for entry in material.get_editor_property('vector_parameter_values'):
                value = entry.parameter_value
                vectors[str(entry.parameter_info.name)] = [value.r, value.g, value.b, value.a]
        base = material
        two_sided = None
        while isinstance(base, unreal.MaterialInstanceConstant):
            override = base.get_editor_property('base_property_overrides')
            if two_sided is None and override.get_editor_property('override_two_sided'):
                two_sided = override.get_editor_property('two_sided')
            base = base.get_editor_property('parent')
        if two_sided is None:
            two_sided = base.get_editor_property('two_sided')
        slots.append({'name': str(slot.get_editor_property('imported_material_slot_name')), 'material': material.get_path_name(), 'textures': textures, 'scalars': params, 'vectors': vectors, 'two_sided': two_sided})
    box = mesh.get_bounding_box()
    size = box.max-box.min
    return {'path': mesh.get_path_name(), 'bounds_size_cm': [size.x, size.y, size.z], 'materials': slots}


def prepare(revision, destination):
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise ValueError('This adapter targets UE 5.8')
    plan = read_plan(revision)
    if not re.fullmatch(r'/Game/[A-Za-z0-9_/]+', destination) or unreal.EditorAssetLibrary.does_directory_exist(destination):
        raise ValueError('Use a new /Game destination directory')
    meshes, reports = {}, []
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    # Each file has one identity-transform mesh. Importer cannot accidentally bake
    # node transforms twice or combine a door with its frame.
    for row in plan['meshes']:
        task = unreal.AssetImportTask()
        task.filename = str(Path(revision)/row['file'])
        task.destination_path = destination+'/Mesh_'+str(row['id'])
        task.automated, task.save, task.replace_existing = True, True, False
        asset_tools.import_asset_tasks([task])
        imported = [x for x in task.get_objects() if isinstance(x, unreal.StaticMesh)]
        if not imported:
            imported = [unreal.load_asset(p) for p in task.imported_object_paths if isinstance(unreal.load_asset(p), unreal.StaticMesh)]
        if len(imported) != 1:
            raise ValueError('Expected one native static mesh per frozen mesh file')
        mesh = imported[0]
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, 'OAGDStaticScenePlan', plan['plan_id'])
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        meshes[row['id']] = mesh
        reports.append({'id': row['id'], **inspect_mesh(mesh)})
    return plan, meshes, reports


def assemble(plan, meshes, prefix):
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*', prefix):
        raise ValueError('Use an alphanumeric actor prefix')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if any(str(t) == prefix for a in actors.get_all_level_actors() for t in a.tags):
        raise ValueError('Scene prefix already present')
    nodes, spawned = {}, []
    try:
        root = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
        spawned.append(root)
        root.set_actor_label(prefix)
        root.tags = [prefix]
        root.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        root.static_mesh_component.set_collision_profile_name('NoCollision')
        root.set_actor_rotation(unreal.Rotator(pitch=0, yaw=90, roll=0), False)
        for row in plan['nodes']:
            a = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
            spawned.append(a)
            a.set_actor_label(prefix+'_Node_'+str(row['id']))
            a.tags = [prefix, 'SourceNode_'+str(row['id']), 'SourceName_'+row['name'], 'Plan_'+plan['plan_id']]
            c = a.static_mesh_component
            c.set_mobility(unreal.ComponentMobility.MOVABLE)
            c.set_collision_profile_name('NoCollision')
            if row['mesh'] is not None:
                c.set_static_mesh(meshes[row['mesh']])
            a.attach_to_actor(nodes[row['parent']] if row['parent'] is not None else root, '', unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, False)
            m = row['local_matrix']
            q, scale = quaternion(m)
            a.set_actor_relative_location(unreal.Vector(m[12]*100, m[14]*100, m[13]*100), False, True)
            a.set_actor_relative_rotation(unreal.Quat(-q[0], -q[2], -q[1], q[3]).rotator(), False, True)
            a.set_actor_relative_scale3d(unreal.Vector(scale, scale, scale))
            nodes[row['id']] = a
        return root, nodes
    except Exception:
        for a in reversed(spawned):
            actors.destroy_actor(a)
        raise

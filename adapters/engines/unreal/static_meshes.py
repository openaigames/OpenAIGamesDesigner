"""Actual UE editor mesh queries and new-asset LOD/Nanite processing.

No source replacement, scene rewrite, rendering benchmark, or visual approval.
"""
import json
import math
import unreal
from mesh_contract import validate_operation


def subsystem():
    if not hasattr(unreal, 'StaticMeshEditorSubsystem'):
        unreal.load_module('StaticMeshEditor')
    return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def scalar(value):
    return value if type(value) in (str, int, float, bool) or value is None else str(value)


def optional(record, key, read):
    try:
        record[key] = read()
    except Exception as error:
        record[key] = None
        record.setdefault('unavailable_fields', {})[key] = str(error)


def texture_info(texture):
    row = {'path': texture.get_path_name(), 'class': texture.get_class().get_name()}
    if isinstance(texture, unreal.Texture2D):
        optional(row, 'width', texture.blueprint_get_size_x)
        optional(row, 'height', texture.blueprint_get_size_y)
    for field in ('lod_bias', 'lod_group', 'compression_settings', 'srgb', 'never_stream', 'virtual_texture_streaming'):
        optional(row, field, lambda f=field: scalar(texture.get_editor_property(f)))
    return row


def material_info(material):
    if not material:
        return {'path': None, 'blend_mode': None, 'textures': [], 'unavailable_fields': {'material': 'Empty slot'}}
    if not hasattr(unreal, 'MaterialEditingLibrary'):
        unreal.load_module('MaterialEditor')
    row = {'path': material.get_path_name(), 'class': material.get_class().get_name()}
    base = material.get_base_material()
    row['base_material'] = base.get_path_name()
    # Instance overrides take precedence, nearest instance first.
    mode = base.get_editor_property('blend_mode')
    two_sided = base.get_editor_property('two_sided')
    chain = []
    current = material
    while isinstance(current, unreal.MaterialInstance):
        if current in chain:
            raise ValueError('Cyclic material parent chain')
        chain.append(current)
        current = current.get_editor_property('parent')
    for instance in reversed(chain):
        overrides = instance.get_editor_property('base_property_overrides')
        if overrides.get_editor_property('override_blend_mode'):
            mode = overrides.get_editor_property('blend_mode')
        if overrides.get_editor_property('override_two_sided'):
            two_sided = overrides.get_editor_property('two_sided')
    row.update(blend_mode=str(mode), two_sided=bool(two_sided),
               nanite_blend_supported=mode in (unreal.BlendMode.BLEND_OPAQUE, unreal.BlendMode.BLEND_MASKED))
    optional(row, 'used_with_nanite', lambda: base.get_editor_property('used_with_nanite'))
    # Include parent texture dependencies and instance overrides; not a measurement
    # of compiled permutation residency or runtime streaming allocation.
    textures = {t.get_path_name(): t for t in unreal.MaterialEditingLibrary.get_used_textures(base)}
    for instance in chain:
        for parameter in instance.get_editor_property('texture_parameter_values'):
            texture = parameter.get_editor_property('parameter_value')
            if texture:
                textures[texture.get_path_name()] = texture
    row['textures'] = [texture_info(t) for _, t in sorted(textures.items())]
    row['texture_scope'] = 'Referenced base textures plus instance overrides; may include unused dependencies'
    return row


def inspect_mesh(mesh):
    if not isinstance(mesh, unreal.StaticMesh):
        raise ValueError('Static mesh required: ' + mesh.get_path_name())
    editor = subsystem()
    settings = editor.get_nanite_settings(mesh)
    nanite = {'enabled': settings.get_editor_property('enabled')}
    for field in ('preserve_area', 'keep_percent_triangles', 'trim_relative_error',
                  'fallback_target', 'fallback_percent_triangles', 'fallback_relative_error'):
        optional(nanite, field, lambda f=field: scalar(settings.get_editor_property(f)))
    count = editor.get_lod_count(mesh)
    screens = list(editor.get_lod_screen_sizes(mesh))
    lods = []
    for index in range(count):
        reduction = editor.get_lod_reduction_settings(mesh, index)
        lods.append({'index': index, 'render_triangles': mesh.get_num_triangles(index),
                     'render_vertices': editor.get_number_verts(mesh, index),
                     'sections': mesh.get_num_sections(index),
                     'screen_size': screens[index] if index < len(screens) else None,
                     'reduction_percent': reduction.get_editor_property('percent_triangles')})
    row = {'path': mesh.get_path_name(), 'lod_count': count, 'lods': lods, 'nanite': nanite,
           'triangle_scope': 'Nanite fallback render data' if nanite['enabled'] else 'Conventional LOD render data',
           'nanite_source_triangles': None,
           'source_triangle_note': 'Not exposed by this reader; keep DCC/import source statistics separately',
           'material_slots': len(mesh.get_editor_property('static_materials')),
           'collision': {'simple_shapes': editor.get_simple_collision_count(mesh),
                         'convex_shapes': editor.get_convex_collision_count(mesh),
                         'lod': mesh.get_editor_property('lod_for_collision')},
           'materials': []}
    optional(row, 'lod_group', lambda: str(mesh.get_editor_property('lod_group')))
    optional(row['collision'], 'trace_flag', lambda: str(mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')))
    for index in range(row['material_slots']):
        material = mesh.get_material(index)
        try:
            info = material_info(material)
        except Exception as error:
            info = {'path': material.get_path_name() if material else None, 'unavailable_fields': {'inspection': str(error)}}
        row['materials'].append(info)
    return row


def collect(spec, load):
    meshes = {load(path).get_path_name(): load(path) for path in spec.get('paths', [])}
    consumers = []
    groups = {}
    if spec.get('include_scene'):
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        for actor in actors:
            for component in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = component.get_editor_property('static_mesh')
                if not mesh:
                    continue
                meshes[mesh.get_path_name()] = mesh
                materials = [component.get_material(i) for i in range(component.get_num_materials())]
                row = {'actor': actor.get_actor_label(), 'component': component.get_path_name(),
                       'mesh': mesh.get_path_name(),
                       'instances': component.get_instance_count() if isinstance(component, unreal.InstancedStaticMeshComponent) else 1,
                       'instanced': isinstance(component, unreal.InstancedStaticMeshComponent),
                       'materials': [m.get_path_name() if m else None for m in materials],
                       'mobility': str(component.get_editor_property('mobility')),
                       'cast_shadow': component.get_editor_property('cast_shadow'),
                       'collision_profile': str(component.get_collision_profile_name()),
                       'collision_enabled': str(component.get_collision_enabled())}
                consumers.append(row)
                key = json.dumps([row[k] for k in ('mesh', 'materials', 'mobility', 'cast_shadow', 'collision_profile', 'collision_enabled')])
                groups.setdefault(key, []).append(row['component'])
    assets = [inspect_mesh(mesh) for _, mesh in sorted(meshes.items())]
    limits = spec.get('warning_limits', {})
    warnings = []
    for mesh in assets:
        path = mesh['path']
        if not mesh['nanite']['enabled'] and mesh['lod_count'] == 1:
            warnings.append({'path': path, 'code': 'single_conventional_lod', 'meaning': 'Review use and screen coverage; not automatically a defect'})
        if limits.get('triangles') and mesh['lods'] and mesh['lods'][0]['render_triangles'] > limits['triangles']:
            warnings.append({'path': path, 'code': 'render_triangle_limit', 'scope': mesh['triangle_scope']})
        if limits.get('material_slots') and mesh['material_slots'] > limits['material_slots']:
            warnings.append({'path': path, 'code': 'material_slot_limit'})
        for material in mesh['materials']:
            for texture in material.get('textures', []):
                if limits.get('texture_dimension') and max(texture.get('width') or 0, texture.get('height') or 0) > limits['texture_dimension']:
                    warnings.append({'path': texture['path'], 'mesh': path, 'code': 'texture_dimension_limit'})
    return {'assets': assets, 'consumers': consumers, 'warnings': warnings,
            'instancing_candidates': [{'components': members, 'count': len(members)} for members in groups.values() if len(members) > 1],
            'scope': 'Explicit assets and loaded editor-world components only; unloaded partition cells and runtime spawning excluded',
            'warning_limits': limits, 'performance_validation': 'not_run', 'visual_validation': 'not_run',
            'instancing_note': 'Candidates need interaction, per-instance state and visibility review; no scene objects replaced'}


def configure(op, load, package):
    validate_operation(op)
    destination = package(op['path'])
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        raise ValueError('Derived destination already exists; inspect previous result before choosing a new version')
    source = load(op['source'])
    before = inspect_mesh(source)
    if op['strategy'] == 'nanite':
        if any(m.get('nanite_blend_supported') is not True for m in before['materials']):
            raise ValueError('Nanite requires inspected Opaque/Masked materials; unresolved or unsupported slots remain')
    count = len(op['lods']) if op['strategy'] == 'lod' else before['lod_count']
    collision_lod = op.get('lod_for_collision', before['collision']['lod'])
    if not 0 <= collision_lod < count:
        raise ValueError('Existing collision LOD is outside the new range; specify lod_for_collision')
    # Read optional settings before duplication so unavailable APIs do not leave
    # a saved partial copy. Existing project assets/materials are never edited.
    editor = subsystem()
    settings = editor.get_nanite_settings(source)
    settings.set_editor_property('enabled', op['strategy'] == 'nanite')
    if op['strategy'] == 'nanite':
        values = {'preserve_area': op['asset_role'] == 'foliage', **op.get('nanite', {})}
        for key, value in values.items():
            if key == 'fallback_target':
                value = getattr(unreal.NaniteFallbackTarget, {'auto': 'AUTO', 'percent_triangles': 'PERCENT_TRIANGLES', 'relative_error': 'RELATIVE_ERROR'}[value])
            settings.set_editor_property(key, value)
    mesh = unreal.EditorAssetLibrary.duplicate_asset(op['source'], destination)
    if not mesh:
        raise ValueError('Could not duplicate source mesh')
    editor.set_nanite_settings(mesh, settings, True)
    if op['strategy'] == 'lod':
        options = unreal.StaticMeshReductionOptions()
        options.set_editor_property('auto_compute_lod_screen_size', False)
        reductions = []
        for item in op['lods']:
            reduction = unreal.StaticMeshReductionSettings()
            for key, value in item.items():
                reduction.set_editor_property(key, value)
            reductions.append(reduction)
        options.set_editor_property('reduction_settings', reductions)
        editor.set_lods(mesh, options)
        if editor.get_lod_count(mesh) != count:
            raise ValueError('LOD generation count differs; derived copy requires review')
    mesh.set_editor_property('lod_for_collision', collision_lod)
    after = inspect_mesh(mesh)
    if after['nanite']['enabled'] != (op['strategy'] == 'nanite'):
        raise ValueError('Nanite enabled state did not persist in memory')
    if op['strategy'] == 'lod':
        for actual, wanted in zip(after['lods'], op['lods']):
            if not math.isclose(actual['screen_size'], wanted['screen_size'], abs_tol=1e-5):
                raise ValueError('LOD screen size readback mismatch')
        triangles = [lod['render_triangles'] for lod in after['lods']]
        if any(n <= 0 for n in triangles) or any(b > a for a, b in zip(triangles, triangles[1:])):
            raise ValueError('LOD geometry is empty or increases with distance')
    else:
        for key, wanted in op.get('nanite', {}).items():
            actual = after['nanite'][key]
            if key == 'fallback_target':
                if actual != str(settings.get_editor_property(key)):
                    raise ValueError('Fallback target readback mismatch')
            elif type(wanted) in (float, int):
                if not math.isclose(actual, wanted, abs_tol=1e-5):
                    raise ValueError('Nanite numeric setting readback mismatch: ' + key)
            elif actual != wanted:
                raise ValueError('Nanite setting readback mismatch: ' + key)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
        raise ValueError('Derived mesh save failed')
    warnings = []
    if op['strategy'] == 'nanite':
        for material in after['materials']:
            if material.get('used_with_nanite') is not True:
                warnings.append({'material': material.get('path'),
                                 'code': 'nanite_material_usage_requires_render_check'})
    return {'op': 'static_mesh_configure', 'source': op['source'], 'path': destination,
            'before': before, 'after': after, 'status': 'derived_asset_saved',
            'warnings': warnings,
            'reload_verification': 'requires_separate_inspect_session',
            'scene_replacement': 'not_performed', 'visual_validation': 'not_run',
            'performance_validation': 'not_run'}

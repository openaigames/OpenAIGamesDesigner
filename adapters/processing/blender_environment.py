"""Blender batch recipe for measured surfaces, static export, baking and fixed cameras.

Run in a separate Blender process: --background --factory-startup --python-exit-code 1
--python blender_environment.py -- --request request.json --out NEW_DIRECTORY
"""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from environment.common import digest, number, read, write
from environment.surfaces import triangle_metrics, summarize


def uv_transform(node, mesh):
    """Support default UV, UVMap, Texture Coordinate UV and affine Mapping chains."""
    from mathutils import Matrix, Euler
    socket = node.inputs.get('Vector')
    def follow(sock, seen):
        if not sock or not sock.is_linked:
            return mesh.uv_layers.active, Matrix.Identity(4), None
        link = sock.links[0]
        n = link.from_node
        if n.as_pointer() in seen:
            return None, None, 'cyclic_vector_graph'
        seen = seen | {n.as_pointer()}
        if n.type == 'UVMAP':
            return mesh.uv_layers.get(n.uv_map) if n.uv_map else mesh.uv_layers.active, Matrix.Identity(4), None
        if n.type == 'TEX_COORD' and link.from_socket.name == 'UV':
            return mesh.uv_layers.active, Matrix.Identity(4), None
        if n.type == 'MAPPING' and n.vector_type in ('POINT', 'VECTOR'):
            if any(n.inputs[k].is_linked for k in ('Location','Rotation','Scale')):
                return None, None, 'driven_mapping_transform'
            layer, previous, error = follow(n.inputs['Vector'], seen)
            if error:
                return layer, previous, error
            rotation = Euler(n.inputs['Rotation'].default_value).to_matrix().to_4x4()
            scale = Matrix.Diagonal(tuple(n.inputs['Scale'].default_value)+(1,))
            translation = Matrix.Translation(n.inputs['Location'].default_value) if n.vector_type == 'POINT' else Matrix.Identity(4)
            return layer, translation @ rotation @ scale @ previous, None
        return None, None, 'vector_source_'+n.type+'_'+link.from_socket.name
    return follow(socket, set())


def material_images(material):
    """Only report images reachable from active material outputs; retain socket use."""
    if not material or not material.use_nodes:
        return [], []
    found, unsupported = {}, set()
    def visit(node, use, seen):
        pointer = node.as_pointer()
        if pointer in seen:
            return
        seen = seen | {pointer}
        if node.type == 'TEX_IMAGE' and node.image:
            entry = found.setdefault(pointer, {'node':node, 'uses':set()})
            entry['uses'].add(use)
        if node.type == 'GROUP':
            unsupported.add('node_group_requires_specialized_audit')
        for socket in node.inputs:
            for link in socket.links:
                child_use = socket.name if node.type == 'BSDF_PRINCIPLED' else use
                if node.type == 'BUMP' and socket.name == 'Height':
                    child_use = 'Height'
                visit(link.from_node, child_use, seen)
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            visit(node, 'Surface', set())
    return list(found.values()), sorted(unsupported)


def audit(objects, request, source):
    import bpy
    from mathutils import Vector
    scale = request['meters_per_unit']
    graph = bpy.context.evaluated_depsgraph_get()
    material_cache, image_rows, object_rows, issues = {}, {}, [], []
    color_warnings = set()
    for obj in objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
        try:
            mesh.calc_loop_triangles()
            world = [evaluated.matrix_world @ v.co * scale for v in mesh.vertices]
            if not world:
                continue
            bounds = [[min(v[i] for v in world), max(v[i] for v in world)] for i in range(3)]
            row = {'id':obj.name, 'triangles':len(mesh.loop_triangles), 'bounds_m':bounds,
                   'area_m2':0, 'uv_layers':list(mesh.uv_layers.keys()), 'surfaces':[],
                   'custom_ids':{k:str(obj[k]) for k in request.get('id_properties', []) if k in obj},
                   'negative_transform':evaluated.matrix_world.determinant() < 0}
            row['footprint_m'] = [[bounds[0][0],bounds[1][0]],[bounds[0][1],bounds[1][0]],
                                  [bounds[0][1],bounds[1][1]],[bounds[0][0],bounds[1][1]]]
            for tri in mesh.loop_triangles:
                p = [world[i] for i in tri.vertices]
                row['area_m2'] += (p[1]-p[0]).cross(p[2]-p[0]).length/2
            indices = sorted(set(t.material_index for t in mesh.loop_triangles))
            for index in indices:
                material = mesh.materials[index] if index < len(mesh.materials) else None
                if not material:
                    issues.append({'code':'missing_material', 'object':obj.name, 'slot':index})
                    continue
                if material.name not in material_cache:
                    material_cache[material.name] = material_images(material)
                images, unsupported = material_cache[material.name]
                for reason in unsupported:
                    issues.append({'code':reason, 'object':obj.name, 'material':material.name})
                for entry in images:
                    node, uses = entry['node'], sorted(entry['uses'])
                    image = node.image
                    if image.name not in image_rows:
                        path = Path(bpy.path.abspath(image.filepath)) if image.filepath else None
                        image_rows[image.name] = {'id':image.name, 'size':list(image.size),
                            'color_space':image.colorspace_settings.name, 'packed':bool(image.packed_file),
                            'source':image.source, 'path':str(path) if path else None,
                            'external_exists':bool(path and path.is_file()),
                            'sha256':digest(path) if path and path.is_file() else None}
                    item = {'material':material.name, 'image':image.name, 'uses':uses, 'node':node.name}
                    layer, transform, error = uv_transform(node, mesh)
                    if image.source == 'TILED':
                        error = 'UDIM_density_requires_tile_resolution'
                    if image.size[0] < 1 or image.size[1] < 1:
                        error = 'missing_image_pixels'
                    if not layer and not error:
                        error = 'missing_uv_layer'
                    if error:
                        item.update(status='not_measured', reason=error)
                    else:
                        metrics = []
                        for tri in mesh.loop_triangles:
                            if tri.material_index != index:
                                continue
                            uv = [(transform @ Vector((*layer.data[i].uv, 0, 1)))[:2] for i in tri.loops]
                            metrics.append(triangle_metrics([list(world[i]) for i in tri.vertices], uv, image.size))
                        item.update(status='measured', uv_layer=layer.name,
                                    **summarize(metrics, request.get('surface_limits', {})))
                    if any(x in uses for x in ('Roughness','Metallic','Normal','Height')) and image.colorspace_settings.name not in ('Non-Color','Raw'):
                        key=(material.name,image.name,tuple(uses))
                        if key not in color_warnings:
                            color_warnings.add(key)
                            issues.append({'code':'color_image_reused_for_data' if 'Base Color' in uses else 'data_texture_color_space_review',
                                'severity':'warning', 'material':material.name, 'image':image.name, 'uses':uses,
                                'color_space':image.colorspace_settings.name,
                                'note':'Check intended derivation and channel meaning; do not change a shared base-color image to Non-Color automatically.'})
                    row['surfaces'].append(item)
            object_rows.append(row)
        finally:
            evaluated.to_mesh_clear()
    return {'schema':'environment-surface-report/1', 'source':str(source), 'source_sha256':digest(source),
            'blender':bpy.app.version_string, 'meters_per_unit':scale, 'coordinate':request['coordinate'],
            'objects':object_rows, 'images':list(image_rows.values()), 'issues':issues,
            'limits':request.get('surface_limits', {}), 'visual_approval':'not_assessed',
            'limitations':['Area and UV sampling use evaluated render meshes, not engine LODs or texture residency.',
                'World/procedural/group mappings and UDIM density are explicitly unmeasured.',
                'No UV-overlap verdict: trim sheets, mirrored UVs and tiling may be intentional.',
                'Anisotropy measures directional density; it does not certify that a texture looks natural.']}


def export_static(objects, request, output):
    import bpy
    from mathutils import Matrix
    bpy.ops.object.select_all(action='DESELECT')
    if any(o.type == 'ARMATURE' or o.find_armature() for o in objects):
        raise ValueError('Static map export cannot silently strip a rig')
    if any(o.animation_data and (o.animation_data.action or len(o.animation_data.nla_tracks)) for o in objects):
        raise ValueError('Animated objects require an animation-aware export')
    selected = [o for o in objects if o.type in ('MESH','EMPTY','CURVE','FONT')]
    if not selected:
        raise ValueError('No static exportable objects')
    # glTF export does not apply Blender's display unit setting. Scale root transforms
    # explicitly in this isolated scene, preserving selected parent/child relationships.
    chosen = set(selected)
    roots = [o for o in selected if o.parent not in chosen]
    world = {o:o.matrix_world.copy() for o in roots}
    for obj in roots:
        obj.parent = None
        obj.matrix_world = Matrix.Scale(request['meters_per_unit'], 4) @ world[obj]
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.context.view_layer.update()
    for obj in selected:
        obj.hide_set(False)
        obj.select_set(True)
    before = {o.name:{'type':o.type, 'materials':[m.name for m in o.data.materials if m] if o.type == 'MESH' else []}
              for o in selected}
    source_points = [o.matrix_world @ __import__('mathutils').Vector(v) for o in selected
                     if o.type in ('MESH','CURVE','FONT') for v in o.bound_box]
    expected_bounds = [[min(v[i] for v in source_points),max(v[i] for v in source_points)] for i in range(3)] if source_points else None
    path = output/'scene.glb'
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                              export_apply=True, export_animations=False, export_cameras=False,
                              export_lights=False, export_yup=True, export_extras=True)
    # A new scene readback proves that a file was actually parsed, without resaving the source.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    graph = bpy.context.evaluated_depsgraph_get()
    imported = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            imported.append({'name':obj.name, 'triangles':len(mesh.loop_triangles),
                             'bounds_m':[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)] if points else None})
        finally:
            evaluated.to_mesh_clear()
    measured_bounds = [[min(m['bounds_m'][i][0] for m in imported if m['bounds_m']),
                        max(m['bounds_m'][i][1] for m in imported if m['bounds_m'])] for i in range(3)] if imported else None
    # Source bounding boxes can be conservative after rotated or curved geometry.
    # Save both for review; fixed fixture tests check actual dimensions independently.
    return {'schema':'environment-export-report/1', 'file':str(path), 'sha256':digest(path),
            'source_objects':before, 'reimported_meshes':imported,
            'source_bounds_proxy_m':expected_bounds, 'reimported_bounds_m':measured_bounds,
            'applied_meters_per_unit':request['meters_per_unit'],
            'glTF_coordinate':'meters, +Y up; Blender importer restores +Z up',
            'engine_validation':'not_run', 'visual_approval':'not_assessed',
            'limitations':['Only glTF-exportable materials are transferred. Procedural or engine shaders need baking or reauthoring.',
                           'No collision, navigation, LOD, gameplay, exposure or GI equivalence is implied.']}


def bake(objects, request, output):
    """Bake a selected object's evaluated material to its existing UVs in a copy."""
    import bpy
    if len(objects) != 1 or objects[0].type != 'MESH':
        raise ValueError('Bake one explicit mesh at a time; choose its UV layout before baking')
    obj = objects[0]
    if not obj.data.uv_layers.active:
        raise ValueError('Bake requires an active UV map')
    if request.get('uv_layout_reviewed') is not True:
        raise ValueError('Explicitly review UV overlap and 0-1 coverage before baking')
    channels = request.get('channels', [])
    if not channels or len(set(channels)) != len(channels) or set(channels)-{'base_color','roughness','metallic','normal'}:
        raise ValueError('Choose base_color, roughness, metallic, normal')
    resolution = request.get('resolution', 1024)
    number(resolution, 'bake resolution', 16, 8192)
    if int(resolution) != resolution:
        raise ValueError('Bake resolution must be integer')
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = int(number(request.get('samples', 16), 'bake samples', 1, 4096))
    scene.cycles.device = 'CPU'
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = int(number(request.get('margin', 8), 'bake margin', 0, 128))
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mats = list({m.name:m for m in obj.data.materials if m}.values())
    if not mats:
        raise ValueError('Bake requires materials')
    materials = []
    for mat in mats:
        if not mat.use_nodes:
            raise ValueError('Bake requires node materials')
        nodes = mat.node_tree.nodes
        out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
        if not out or len(out.inputs['Surface'].links) != 1:
            raise ValueError('Bake requires one active material surface')
        original = out.inputs['Surface'].links[0].from_socket
        principled = original.node
        if principled.type != 'BSDF_PRINCIPLED':
            raise ValueError('Supported bake material: direct Principled BSDF output')
        target = nodes.new('ShaderNodeTexImage')
        emission = nodes.new('ShaderNodeEmission')
        materials.append((mat, out, original, principled, target, emission))
    files = []
    for channel in channels:
        image = bpy.data.images.new('Bake_'+channel, width=resolution, height=resolution, alpha=False)
        image.colorspace_settings.name = 'sRGB' if channel == 'base_color' else 'Non-Color'
        for mat, out, original, principled, target, emission in materials:
            target.image = image
            mat.node_tree.nodes.active = target
            for link in list(out.inputs['Surface'].links): mat.node_tree.links.remove(link)
            for link in list(emission.inputs['Color'].links): mat.node_tree.links.remove(link)
            if channel == 'normal':
                mat.node_tree.links.new(original, out.inputs['Surface'])
            else:
                socket = principled.inputs[{'base_color':'Base Color','roughness':'Roughness','metallic':'Metallic'}[channel]]
                if socket.is_linked:
                    mat.node_tree.links.new(socket.links[0].from_socket, emission.inputs['Color'])
                else:
                    v = socket.default_value
                    emission.inputs['Color'].default_value = v if channel == 'base_color' else (v,v,v,1)
                mat.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
        bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', normal_space='TANGENT')
        path = output/(channel+'.png')
        image.filepath_raw = str(path); image.file_format = 'PNG'; image.save()
        files.append({'channel':channel, 'path':str(path), 'sha256':digest(path), 'size':list(image.size),
                      'color_space':image.colorspace_settings.name})
    for mat, out, original, principled, target, emission in materials:
        for link in list(out.inputs['Surface'].links): mat.node_tree.links.remove(link)
        mat.node_tree.links.new(original, out.inputs['Surface'])
    return {'schema':'environment-bake-report/1', 'files':files, 'normal_convention':'tangent OpenGL +Y',
            'visual_approval':'not_assessed', 'note':'Existing evaluated material baked to existing UVs. No new surface detail or high-poly projection is invented.'}


def capture(request, output):
    import bpy
    from mathutils import Euler
    from environment.views import validate_plan
    plan = read(request['plan'])
    views = validate_plan(plan)
    if plan['engine'] != 'blender' or plan['unit'] != 'm' or plan['rotation_order'] != 'XYZ':
        raise ValueError('Blender capture requires engine blender, unit m and XYZ Euler degrees')
    scene = bpy.context.scene
    scene.render.engine = request.get('render_engine', 'CYCLES')
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = request.get('samples', 16)
        scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = plan['resolution']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    camera = bpy.data.objects.new('EnvironmentReviewCamera', bpy.data.cameras.new('EnvironmentReviewCamera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, view in views.items():
        camera.location = [x/request['meters_per_unit'] for x in view['position']]
        camera.rotation_euler = Euler(tuple(math.radians(x) for x in view['rotation_deg']), 'XYZ')
        camera.data.type = 'PERSP' if view.get('projection', 'perspective') == 'perspective' else 'ORTHO'
        camera.data.sensor_fit = 'HORIZONTAL'
        if camera.data.type == 'PERSP': camera.data.angle = math.radians(view['fov_deg'])
        else: camera.data.ortho_scale = view['ortho_size']/request['meters_per_unit']
        scene.render.filepath = str(output/(name+'.png'))
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        receipt = {'schema':'environment-view/1', 'id':name, 'engine':'blender', 'scene':plan['scene'],
                   'unit':'m', 'coordinate':request['coordinate'], 'rotation_order':'XYZ',
                   'position':[x*request['meters_per_unit'] for x in camera.matrix_world.translation],
                   'rotation_deg':[math.degrees(x) for x in camera.matrix_world.to_euler('XYZ')],
                   'projection':view.get('projection','perspective'), 'fov_deg':math.degrees(camera.data.angle),
                   'ortho_size':camera.data.ortho_scale*request['meters_per_unit'], 'resolution':plan['resolution'],
                   'source':'Actual Blender render and camera readback',
                   'conditions':{'render_engine':scene.render.engine, 'exposure':scene.view_settings.exposure,
                                 'view_transform':scene.view_settings.view_transform,
                                 'frame':scene.frame_current}}
        write(output/(name+'.json'), receipt)
    return {'schema':'environment-capture/1', 'views':list(views), 'engine':'blender', 'visual_approval':'not_assessed'}


def main():
    import bpy
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    request = read(args.request)
    if request.get('schema') != 'blender-environment/1':
        raise ValueError('Expected blender-environment/1')
    source = Path(request['source']).resolve()
    if source.suffix.lower() != '.blend' or not source.is_file():
        raise ValueError('Provide an existing editable .blend source')
    number(request.get('meters_per_unit'), 'meters_per_unit', 1e-12)
    if not request.get('coordinate'):
        raise ValueError('Coordinate declaration required')
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original_hash = digest(source)
    write(output/'request.json', request)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    names = request.get('objects')
    objects = list(bpy.context.scene.objects) if names is None else [bpy.data.objects.get(n) for n in names]
    if any(o is None for o in objects) or not objects:
        raise ValueError('Selected objects missing or empty')
    operation = request['operation']
    if operation == 'audit':
        result = audit(objects, request, source)
    elif operation == 'export':
        result = export_static(objects, request, output)
    elif operation == 'bake':
        result = bake(objects, request, output)
    elif operation == 'capture':
        result = capture(request, output)
    else:
        raise ValueError('Unknown operation: '+str(operation))
    if digest(source) != original_hash:
        raise ValueError('Source file changed during processing')
    result.update(source=str(source), source_sha256=original_hash, source_unchanged=True,
                  blender=bpy.app.version_string)
    write(output/'report.json', result)
    print('ENVIRONMENT_REPORT '+str(output/'report.json'))


if __name__ == '__main__':
    main()

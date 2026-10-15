"""Run only inside Blender: static material renders from a self-contained GLB."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    config = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    out = Path(config['output'])
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=config['source'])
    scene = bpy.context.scene
    scene.frame_set(1)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum, maximum = Vector((float('inf'),)*3), Vector((-float('inf'),)*3)
    vertices, triangles, meshes = 0, 0, 0
    for obj in list(scene.objects):
        if obj.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            vertices += len(mesh.vertices)
            triangles += len(mesh.loop_triangles)
            meshes += 1
            for vertex in mesh.vertices:
                point = evaluated.matrix_world @ vertex.co
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], point[axis])
                    maximum[axis] = max(maximum[axis], point[axis])
        finally:
            evaluated.to_mesh_clear()
    if vertices == 0:
        raise ValueError('GLB has no evaluated mesh geometry')
    center, size = (minimum + maximum) / 2, maximum - minimum
    if max(size) <= 0:
        raise ValueError('GLB geometry has no extent')
    span = max(size) * 1.3
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = scene.render.resolution_y = config['resolution']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Evidence world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.8, 0.8, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.4
    for i, direction in enumerate(((1,-1,2),(-1,-1,1),(0,1,2))):
        light = bpy.data.lights.new('Evidence area ' + str(i), 'AREA')
        light.energy, light.shape, light.size = 450 * span * span, 'DISK', span * 2
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(direction) * span
        obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
    front = {'-Y':Vector((0,-1,0)), '+Y':Vector((0,1,0)), '-X':Vector((-1,0,0)), '+X':Vector((1,0,0))}[config['front']]
    right = front.cross(Vector((0,0,1)))
    data = bpy.data.cameras.new('Evidence camera')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type, data.ortho_scale = 'ORTHO', span
    data.clip_start, data.clip_end = max(span/10000, 0.00001), span * 100
    views = []
    for name, direction in (('front',front),('right',right),('back',-front),('left',-right)):
        camera.location = center + direction * span * 3
        camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = str(out / (name + '.png'))
        bpy.ops.render.render(write_still=True)
        views.append({'direction':name, 'camera_position':list(camera.location),
                      'camera_rotation':list(camera.rotation_euler), 'ortho_scale':span})
    result = {'blender_version':bpy.app.version_string, 'frame':1, 'engine':scene.render.engine,
              'view_transform':'AgX', 'front_axis':config['front'], 'up_axis':'+Z',
              'view_convention':'object-relative; right = front cross up',
              'vertices':vertices, 'triangles':triangles, 'meshes':meshes,
              'bounds_min':list(minimum), 'bounds_max':list(maximum), 'dimensions':list(size),
              'units':config['units'], 'resolution':config['resolution'],
              'pixels_per_unit':config['resolution']/span,
              'baseline_y':config['resolution']/2 + (center.z-minimum.z)*config['resolution']/span,
              'views':views, 'animation_verified':False, 'engine_verified':False,
              'limitations':['Static frame only; no deformation, engine material or gameplay acceptance',
                             'Lighting and AgX affect appearance; compare style under matching conditions']}
    (out/'model-metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()

"""Read a Blender/FBX asset, measure it and optionally render fixed review views.
blender --background --factory-startup --python-exit-code 1 --python THIS -- --spec spec.json --out new-dir
Never saves or exports over the source. All coordinates in the report use the explicit to_cm matrix.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector


def points(obj, mesh, transform):
    xyz = np.empty(len(mesh.vertices)*3, dtype=np.float64)
    mesh.vertices.foreach_get('co', xyz)
    a = np.asarray(transform @ obj.matrix_world)
    return xyz.reshape((-1, 3)) @ a[:3, :3].T + a[:3, 3]


def bounds(p):
    if not len(p) or not np.isfinite(p).all():
        raise ValueError('Mesh is empty or contains nonfinite vertices')
    lo, hi = p.min(axis=0), p.max(axis=0)
    return {'min': lo.tolist(), 'max': hi.tolist(), 'size': (hi-lo).tolist()}


def slice_area(vertices, triangles, center, normal, tolerance, radius=None):
    """Oriented triangle-plane intersections. Open/branched contours have no area result."""
    c, n = np.array(center, float), np.array(normal, float)
    n /= np.linalg.norm(n)
    axis = np.eye(3)[np.argmin(abs(n))]
    u = np.cross(n, axis); u /= np.linalg.norm(u)
    v = np.cross(n, u)
    tri = vertices[triangles]
    dist = (tri-c) @ n
    possible = (dist.min(axis=1) <= tolerance) & (dist.max(axis=1) >= -tolerance)
    degree = {}; area = 0.; count = 0; degenerate = 0; collapsed = 0
    for t, d in zip(tri[possible], dist[possible]):
        if radius is not None:
            middle = t.mean(axis=0)
            if np.linalg.norm(middle-c)-np.linalg.norm(t-middle, axis=1).max() > radius:
                continue
        # Plane coincident with a vertex/edge is ambiguous; report it rather than invent closure.
        if (abs(d) < tolerance).any():
            degenerate += 1
            continue
        hit = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if d[i]*d[j] < 0:
                hit.append(t[i]+(t[j]-t[i])*d[i]/(d[i]-d[j]))
        if len(hit) != 2:
            continue
        a, b = hit
        if radius is not None:
            da, db = np.linalg.norm(a-c), np.linalg.norm(b-c)
            if da > radius and db > radius:
                ab = b-a
                f = min(1, max(0, np.dot(c-a, ab)/np.dot(ab, ab)))
                if np.linalg.norm(a+f*ab-c) < radius:
                    degenerate += 1
                continue
            if da > radius or db > radius:
                degenerate += 1
                continue
        direction = np.cross(n, np.cross(t[1]-t[0], t[2]-t[0]))
        if np.dot(b-a, direction) < 0:
            a, b = b, a
        keys = [tuple(np.rint(p/tolerance).astype(np.int64)) for p in (a,b)]
        if keys[0] == keys[1]:
            # A very short segment can collapse during endpoint joining; it is not a branch.
            collapsed += 1
        else:
            for key in keys:
                degree[key] = degree.get(key, 0)+1
        pa = np.array([np.dot(a-c, u), np.dot(a-c, v)])
        pb = np.array([np.dot(b-c, u), np.dot(b-c, v)])
        area += pa[0]*pb[1]-pa[1]*pb[0]
        count += 1
    closed = bool(degree) and not degenerate and all(x == 2 for x in degree.values())
    return {'closed': closed, 'area_cm2': abs(area)/2 if closed else None,
            'segments': count, 'ambiguous_triangles': degenerate,
            'unjoined_endpoints': sum(x != 2 for x in degree.values()), 'collapsed_segments': collapsed}


def sections(p, triangles, definitions):
    result = {}
    for s in definitions:
        n = np.array(s['normal'], float)
        if not np.isfinite(n).all() or np.linalg.norm(n) == 0:
            raise ValueError('Invalid section normal')
        n /= np.linalg.norm(n)
        half = float(s['half_thickness_cm'])
        if not math.isfinite(half) or half <= 0 or s['id'] in result:
            raise ValueError('Invalid section thickness or duplicate id')
        tolerance = float(s.get('join_tolerance_cm', 0.0001))
        radius = s.get('radius_cm')
        if not math.isfinite(tolerance) or tolerance <= 0 or (radius is not None and (not math.isfinite(radius) or radius <= 0)):
            raise ValueError('Invalid section tolerance or radius')
        samples = [slice_area(p, triangles, np.array(s['center_cm'])+n*d, n,
                              tolerance, radius) for d in (-half, 0, half)]
        areas = [x['area_cm2'] for x in samples]
        result[s['id']] = {'definition': s, 'slices': samples,
            'slab_volume_estimate_cm3': (half*(areas[0]+2*areas[1]+areas[2])/2
                                       if all(a is not None for a in areas) else None),
            'method': 'closed oriented contours; three slices and trapezoidal integration; estimate, not exact volume'}
    return result


def skeleton(rig, transform):
    return {b.name: {'parent': b.parent.name if b.parent else None,
        'head_cm': list(transform @ rig.matrix_world @ b.head_local),
        'tail_cm': list(transform @ rig.matrix_world @ b.tail_local),
        'rest_matrix': [list(row) for row in transform @ rig.matrix_world @ b.matrix_local],
        'deform': b.use_deform} for b in rig.data.bones}


def weights(obj, rig):
    bone_names = {b.name for b in rig.data.bones if b.use_deform}
    groups = {g.index: g.name for g in obj.vertex_groups}
    totals, counts = [], []
    for vertex in obj.data.vertices:
        w = [g.weight for g in vertex.groups if groups.get(g.group) in bone_names and g.weight > 0]
        totals.append(sum(w)); counts.append(len(w))
    modifiers = [m.object.name for m in obj.modifiers if m.type == 'ARMATURE' and m.object and m.show_viewport]
    return {'unweighted_vertices': sum(t < 1e-8 for t in totals),
            'weight_sum_max_error': max(abs(t-1) for t in totals),
            'max_influences': max(counts),
            'groups_outside_deform_bones': sorted(set(groups.values())-bone_names),
            'armature_modifiers': modifiers, 'declared_rig_attached': rig.name in modifiers}


def run(spec, out):
    out = Path(out).resolve()
    if spec['schema'] != 'asset-probe/1' or not spec.get('coordinate'):
        raise ValueError('Expected asset-probe/1 with explicit coordinate description')
    source = Path(spec['source']).resolve()
    frame_ids = [f['id'] for f in spec.get('frames', [])]
    if len(set(frame_ids)) != len(frame_ids):
        raise ValueError('Duplicate frame id')
    matrix = np.array(spec['to_cm'], dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]):
        raise ValueError('to_cm must be a finite affine 4x4 matrix')
    gram = matrix[:3, :3].T @ matrix[:3, :3]
    if gram[0, 0] <= 0 or not np.allclose(gram, np.eye(3)*gram[0, 0]):
        raise ValueError('to_cm must have uniform scale and orthogonal axes')
    transform = Matrix(matrix.tolist())
    if source.suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(source))
    elif source.suffix.lower() == '.fbx':
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(source), use_anim=True, ignore_leaf_bones=False)
    else:
        raise ValueError('Only .blend and .fbx supported')
    report = {'schema': 'asset-snapshot/1', 'source': str(source),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'blender': bpy.app.version_string, 'coordinate': spec['coordinate'], 'unit': 'cm',
        'to_cm': spec['to_cm'], 'meshes': {}, 'rigs': {}, 'frames': [], 'visual_review': 'not_performed'}
    rigs = {}
    for row in spec['rigs']:
        ob = bpy.data.objects[row['object']]
        if ob.type != 'ARMATURE' or row['id'] in rigs:
            raise ValueError('Invalid rig selection')
        rigs[row['id']] = ob
        report['rigs'][row['id']] = skeleton(ob, transform)
    selected, rest, edge_indices, topology = {}, {}, {}, {}
    for r in rigs.values():
        r.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    for row in spec['meshes']:
        ob = bpy.data.objects[row['object']]
        if ob.type != 'MESH' or row['id'] in selected:
            raise ValueError('Invalid mesh selection')
        selected[row['id']] = (ob, row)
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = ev.to_mesh(); mesh.calc_loop_triangles()
        p = points(ev, mesh, transform)
        tri = np.array([list(t.vertices) for t in mesh.loop_triangles], dtype=int)
        edges = np.array([list(e.vertices) for e in mesh.edges], dtype=int).reshape((-1, 2))
        rest[row['id']], edge_indices[row['id']] = p.copy(), edges
        topology[row['id']] = hashlib.sha256(edges.tobytes()).hexdigest()
        report['meshes'][row['id']] = {'object': ob.name, 'rig': row['rig'],
            'vertices': len(p), 'triangles': len(tri), 'bounds_cm': bounds(p),
            'weights': weights(ob, rigs[row['rig']]),
            'sections': sections(p, tri, row.get('sections', []))}
        ev.to_mesh_clear()
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    report['fps'] = fps
    for frame in spec.get('frames', []):
        for key, action_name in frame.get('actions', {}).items():
            rig = rigs[key]
            action = bpy.data.actions[action_name]
            rig.animation_data_create()
            for track in rig.animation_data.nla_tracks:
                track.mute = True
            rig.animation_data.action = action
        for rig in rigs.values():
            rig.data.pose_position = 'POSE'
        scene.frame_set(math.floor(frame['frame']), subframe=frame['frame'] % 1)
        bpy.context.view_layer.update()
        record = {'id': frame['id'], 'clip': frame['clip'], 'frame': frame['frame'],
                  'time_s': frame['frame']/fps, 'meshes': {}, 'rigs': {},
                  'actions': {k: (r.animation_data.action.name if r.animation_data and r.animation_data.action else None) for k,r in rigs.items()}}
        for key, rig in rigs.items():
            record['rigs'][key] = {b.name: list(transform @ rig.matrix_world @ b.head) for b in rig.pose.bones}
        for key, (ob, row) in selected.items():
            ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh = ev.to_mesh()
            p = points(ev, mesh, transform); ref = rest[key]; ed = edge_indices[key]
            current_edges = np.array([list(e.vertices) for e in mesh.edges], dtype=int).reshape((-1, 2))
            same_topology = hashlib.sha256(current_edges.tobytes()).hexdigest() == topology[key]
            r = {'bounds_cm': bounds(p), 'same_vertex_count': len(p) == len(ref), 'same_topology': same_topology}
            if len(p) == len(ref) and len(ed) and same_topology:
                a = np.linalg.norm(ref[ed[:, 1]]-ref[ed[:, 0]], axis=1)
                b = np.linalg.norm(p[ed[:, 1]]-p[ed[:, 0]], axis=1)
                ratios = b[a > 1e-6]/a[a > 1e-6]
                r.update(edge_stretch_max=float(ratios.max()), edge_stretch_p99=float(np.quantile(ratios, .99)),
                         edge_compression_min=float(ratios.min()),
                         edge_growth_max_cm=float((b-a).max()), edge_growth_p99_cm=float(np.quantile(b-a,.99)))
                indices=np.flatnonzero(a>1e-6)
                worst=indices[np.argsort(ratios)[-10:][::-1]]
                r['largest_ratios']=[{'vertices':ed[i].tolist(),'rest_length_cm':float(a[i]),
                    'posed_length_cm':float(b[i]),'ratio':float(b[i]/a[i]),'growth_cm':float(b[i]-a[i])} for i in worst]
            record['meshes'][key] = r
            ev.to_mesh_clear()
        for view in spec.get('views', []):
            cam = bpy.data.objects[view['camera']]
            if cam.type != 'CAMERA':
                raise ValueError('Review camera missing')
            scene.camera = cam
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.render.resolution_x = view.get('width', 640)
            scene.render.resolution_y = view.get('height', 640)
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = 'PNG'
            # Fixed source camera and frame: callers must use the same view in compared scenes.
            name = f'frame-{len(report["frames"]):04d}-view-{spec["views"].index(view):02d}.png'
            scene.render.filepath = str(out/name)
            bpy.ops.render.render(write_still=True)
            record.setdefault('views', []).append({'file': name, 'camera': view['camera'],
                'matrix': [list(r) for r in cam.matrix_world], 'lens': cam.data.lens,
                'type': cam.data.type, 'ortho_scale': cam.data.ortho_scale})
        report['frames'].append(record)
    (out/'snapshot.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), 'utf8')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report['source_sha256']
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    spec = json.loads(args.spec.read_text('utf-8-sig'))
    args.out.mkdir(parents=True, exist_ok=False)
    report = run(spec, args.out.resolve())
    print('ASSET_PROBE', json.dumps({'meshes': len(report['meshes']), 'frames': len(report['frames']), 'source_unchanged': True}))


if __name__ == '__main__':
    main()

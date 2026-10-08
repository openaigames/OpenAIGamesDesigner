"""Compare asset snapshots from the same declared coordinate system; never modifies assets."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def ratio(a, b):
    return b/a if abs(a) > 1e-10 else None


def compare(a, b, limits):
    for key in ('joint_cm', 'axis_deg', 'weight_error', 'volume_ratio_min', 'volume_ratio_max', 'stretch_max'):
        if not isinstance(limits[key], (int,float)) or not math.isfinite(limits[key]) or limits[key] < 0:
            raise ValueError('Invalid tolerance: '+key)
    if limits['volume_ratio_min'] > limits['volume_ratio_max']:
        raise ValueError('Inverted volume limits')
    for v in (a, b):
        if v['schema'] != 'asset-snapshot/1' or v['unit'] != 'cm':
            raise ValueError('Unsupported snapshot')
    if a['coordinate'] != b['coordinate']:
        raise ValueError('Coordinate declarations differ; convert before comparing')
    issues, rigs, meshes = [], {}, {}
    for key in sorted(set(a['rigs']) | set(b['rigs'])):
        ra, rb = a['rigs'].get(key, {}), b['rigs'].get(key, {})
        r = {'missing_bones': sorted(set(ra)-set(rb)), 'added_bones': sorted(set(rb)-set(ra)), 'bones': {}}
        if r['missing_bones'] or r['added_bones']:
            issues.append({'kind': 'skeleton_members_changed', 'rig': key})
        for bone in sorted(set(ra) & set(rb)):
            x, y = ra[bone], rb[bone]
            m, n = x['rest_matrix'], y['rest_matrix']
            # Compare each basis direction, catching roll and mirrored bases as well as joint positions.
            angles = []
            for j in range(3):
                u = [m[i][j] for i in range(3)]; v = [n[i][j] for i in range(3)]
                den = distance(u, [0]*3)*distance(v, [0]*3)
                angles.append(math.degrees(math.acos(max(-1, min(1, sum(p*q for p, q in zip(u,v))/den)))) if den else 180)
            q = {'head_delta_cm': distance(x['head_cm'], y['head_cm']),
                 'tail_delta_cm': distance(x['tail_cm'], y['tail_cm']),
                 'axis_angle_max_deg': max(angles), 'parent_changed': x['parent'] != y['parent'],
                 'deform_changed': x['deform'] != y['deform']}
            r['bones'][bone] = q
            if q['parent_changed'] or q['deform_changed'] or max(q['head_delta_cm'], q['tail_delta_cm']) > limits['joint_cm'] or q['axis_angle_max_deg'] > limits['axis_deg']:
                issues.append({'kind': 'rest_pose_changed', 'rig': key, 'bone': bone, **q})
        rigs[key] = r
    for key in sorted(set(a['meshes']) | set(b['meshes'])):
        if key not in a['meshes'] or key not in b['meshes']:
            issues.append({'kind': 'mesh_missing', 'mesh': key}); continue
        x, y = a['meshes'][key], b['meshes'][key]
        r = {'size_ratio': [ratio(v, w) for v, w in zip(x['bounds_cm']['size'], y['bounds_cm']['size'])],
             'triangles_before': x['triangles'], 'triangles_after': y['triangles'], 'sections': {}}
        w = y['weights']
        if w['unweighted_vertices'] or not w['declared_rig_attached'] or w['weight_sum_max_error'] > limits['weight_error']:
            issues.append({'kind': 'skin_weights', 'mesh': key, **w})
        for section in sorted(set(x['sections']) | set(y['sections'])):
            sx, sy = x['sections'].get(section), y['sections'].get(section)
            if not sx or not sy or sx['definition'] != sy['definition']:
                issues.append({'kind': 'section_not_comparable', 'mesh': key, 'section': section}); continue
            va, vb = sx['slab_volume_estimate_cm3'], sy['slab_volume_estimate_cm3']
            areas = [[s['area_cm2'] for s in t['slices']] for t in (sx, sy)]
            r['sections'][section] = {'area_before_cm2': areas[0], 'area_after_cm2': areas[1],
                'volume_estimate_before_cm3': va, 'volume_estimate_after_cm3': vb,
                'volume_ratio': ratio(va, vb) if va is not None and vb is not None else None}
            if va is None or vb is None:
                issues.append({'kind': 'section_open_or_ambiguous', 'mesh': key, 'section': section})
            elif ratio(va, vb) is None or not limits['volume_ratio_min'] <= ratio(va, vb) <= limits['volume_ratio_max']:
                issues.append({'kind': 'section_volume_change', 'mesh': key, 'section': section})
        meshes[key] = r
    fa = {f['id']: f for f in a['frames']}; fb = {f['id']: f for f in b['frames']}
    samples = []
    for key in sorted(set(fa) | set(fb)):
        if key not in fa or key not in fb:
            issues.append({'kind': 'frame_missing', 'frame': key}); continue
        x, y = fa[key], fb[key]
        same = x['clip'] == y['clip'] and x.get('actions') == y.get('actions') and abs(x['time_s']-y['time_s']) < 1e-6
        cameras = [{k:v for k,v in view.items() if k != 'file'} for view in x.get('views', [])] == [{k:v for k,v in view.items() if k != 'file'} for view in y.get('views', [])]
        samples.append({'id': key, 'same_clip_and_time': same,
                        'same_camera': cameras if x.get('views') and y.get('views') else None})
        if not same or not cameras:
            issues.append({'kind': 'preview_not_comparable', 'frame': key})
        for mesh, row in y['meshes'].items():
            if not row['same_vertex_count'] or not row.get('same_topology', True) or row.get('edge_stretch_max', 0) > limits['stretch_max']:
                issues.append({'kind': 'deformation', 'frame': key, 'mesh': mesh, **row})
    return {'schema': 'asset-comparison/1', 'rigs': rigs, 'meshes': meshes, 'samples': samples,
            'limits': limits, 'issues': issues, 'visual_review': 'not_performed',
            'note': 'Section volume is estimated; importer bone tails can differ. Inspect flagged changes before editing a rig.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'limits', 'out'):
        p.add_argument('--'+name, required=True, type=Path)
    args = p.parse_args()
    a, b, limits = [json.loads(f.read_text('utf-8-sig')) for f in (args.before, args.after, args.limits)]
    r = compare(a, b, limits)
    r['inputs'] = {str(f.resolve()): hashlib.sha256(f.read_bytes()).hexdigest() for f in (args.before, args.after, args.limits)}
    with args.out.open('x', encoding='utf8') as f:
        json.dump(r, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'issues': len(r['issues'])}))
    return 2 if r['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

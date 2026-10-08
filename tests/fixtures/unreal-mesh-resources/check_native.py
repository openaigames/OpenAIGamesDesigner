"""Exercise the public runner in an explicitly supplied disposable UE project."""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools'))
from engine_workflow import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True,
                        help='Dedicated empty toolkit-configured project, never a production map')
    parser.add_argument('--attempt', default='1', help='New evidence label after inspecting a failed attempt')
    args = parser.parse_args()
    root = args.project.resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', args.attempt):
        raise ValueError('Safe attempt label required')
    evidence = root/('mesh-native-validation-'+args.attempt)
    evidence.mkdir(exist_ok=False)
    sessions = []

    def run(name, request):
        path = evidence/(name+'.json')
        path.write_text(json.dumps(request, indent=2), encoding='utf-8')
        session = execute(root, path, 240)
        sessions.append(str(session))
        result = json.loads((session/'result.json').read_text('utf-8-sig'))
        if not result.get('success'):
            raise AssertionError(result)
        return result

    report = {'engine': 'unreal', 'sessions': sessions, 'passed': False,
              'visual_validation': 'not_run', 'performance_validation': 'not_run'}
    try:
        baseline = run('baseline', {'engine': 'unreal', 'mode': 'inspect',
            'mesh_audit': {'paths': ['/Engine/BasicShapes/Sphere']}})
        recipe = json.loads((ROOT/'adapters/engines/unreal/examples/mesh-configure.json').read_text('utf-8'))
        recipe['operations'].insert(0, {'op': 'scene', 'path': '/Game/ResourceTest/Map', 'create': True})
        for label, mesh, x in [('LOD_A', 'SM_Sphere_LOD', 0), ('LOD_B', 'SM_Sphere_LOD', 200), ('Nanite_A', 'SM_Sphere_Nanite', 400)]:
            recipe['operations'].append({'op': 'actor', 'target': label, 'create': True,
                'source': '/Game/OptimizationSample/'+mesh, 'position': [x, 0, 0]})
        changed = run('configure', recipe)
        reread = run('reload', {'engine': 'unreal', 'mode': 'inspect', 'scene': '/Game/ResourceTest/Map',
            'mesh_audit': {'include_scene': True, 'paths': ['/Engine/BasicShapes/Sphere']}})
        source = baseline['mesh_audit']['assets'][0]
        assets = {a['path'].split('.')[0]: a for a in reread['mesh_audit']['assets']}
        assert source == assets['/Engine/BasicShapes/Sphere'], 'Source readback changed'
        lod = assets['/Game/OptimizationSample/SM_Sphere_LOD']
        assert lod['lod_count'] == 3 and lod['nanite']['enabled'] is False
        triangles = [row['render_triangles'] for row in lod['lods']]
        assert triangles[0] > triangles[1] > triangles[2] > 0, triangles
        nanite = assets['/Game/OptimizationSample/SM_Sphere_Nanite']
        assert nanite['nanite']['enabled'] is True
        assert nanite['nanite']['preserve_area'] is False
        assert abs(nanite['nanite']['fallback_relative_error'] - 1) < 1e-5
        assert nanite['triangle_scope'] == 'Nanite fallback render data'
        assert nanite['nanite_source_triangles'] is None
        assert len(reread['mesh_audit']['consumers']) == 3
        assert any(c['count'] == 2 for c in reread['mesh_audit']['instancing_candidates'])
        assert not any(m.get('unavailable_fields') for a in assets.values() for m in a['materials']), assets
        report.update(passed=True, version=reread['version'], lod_triangles=triangles,
                      nanite=nanite['nanite'], source_unchanged=True, scene_consumers=3,
                      checks=['public_runner', 'LOD_generation', 'Nanite_configuration',
                              'new_session_reload', 'source_readback_preserved',
                              'scene_consumer_audit', 'instancing_candidates', 'material_inspection'])
    finally:
        (evidence/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

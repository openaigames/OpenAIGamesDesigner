"""Freeze a native-baseline -> multi-node scene replacement transaction."""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
from static_scene import read_plan as read_scene, fingerprint, sha

VERSION = '0.1.1'
SCHEMA = 'oagd.scene-replacement/1'


def state_number(value, canonical_zero=True):
    rounded = round(value, 5)
    return 0.0 if canonical_zero and rounded == 0 else rounded


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}', value):
        raise ValueError('Use 1..64 alphanumeric/underscore IDs starting with a letter')
    return value


def vector(value, positive=False):
    if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or positive and x <= 0 for x in value):
        raise ValueError('Expected a finite three-vector with positive dimensions when applicable')
    return value


def local(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('Use project-relative paths')
    p = (root/relative).resolve()
    if not p.is_relative_to(root) or p == root:
        raise ValueError('Path escapes project')
    return p


def validate(baseline, manifest, assets):
    if baseline.get('schema') != 'oagd.scene-baseline/1' or baseline.get('engine') not in ('godot', 'unreal') or not baseline.get('objects'):
        raise ValueError('Native baseline required')
    if baseline.get('fingerprint_format') not in (None,'canonical-zero/1'):
        raise ValueError('Unsupported native fingerprint format')
    for key, item in baseline['objects'].items():
        identifier(key)
        if not isinstance(item.get('snapshot'), dict) or not re.fullmatch('[0-9a-f]{64}',item.get('fingerprint','')):
            raise ValueError('Each native baseline entry needs a snapshot and SHA256 fingerprint')
    if set(manifest) != {'schema', 'id', 'assets', 'replacements'} or manifest['schema'] != SCHEMA:
        raise ValueError('Unsupported replacement manifest')
    identifier(manifest['id'])
    rows = manifest['replacements']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise ValueError('Use 1..64 replacement groups')
    used, ids = set(), set()
    for r in rows:
        if set(r) != {'id', 'targets', 'asset', 'position', 'yaw_degrees', 'scale', 'collision'}:
            raise ValueError('Replacement fields must be explicit')
        rid = identifier(r['id'])
        if rid in ids or rid in baseline['objects'] or r['asset'] not in assets:
            raise ValueError('Duplicate replacement ID or unknown asset')
        ids.add(rid)
        if not isinstance(r['targets'], list) or not r['targets']:
            raise ValueError('Each replacement needs targets')
        for target in r['targets']:
            identifier(target)
            if target in used or target not in baseline['objects']:
                raise ValueError('Target missing or reused')
            used.add(target)
        vector(r['position'])
        for key, low, high in [('yaw_degrees', -360, 360), ('scale', .001, 1000)]:
            v = r[key]
            if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('Invalid '+key)
        collision = r['collision']
        mesh_nodes = {n['id'] for n in assets[r['asset']]['nodes'] if n['mesh'] is not None}
        nodes = {n['id'] for n in assets[r['asset']]['nodes']}
        policy = collision.get('policy')
        if policy == 'retain_graybox':
            if set(collision) != {'policy'}:
                raise ValueError('retain_graybox has no new collision definition')
        elif policy == 'source_mesh':
            if set(collision) != {'policy', 'nodes'} or not isinstance(collision['nodes'],list) or not collision['nodes'] or any(type(i) is not int or i not in mesh_nodes for i in collision['nodes']) or len(set(collision['nodes'])) != len(collision['nodes']):
                raise ValueError('Select distinct mesh nodes for fixed triangle collision')
        elif policy == 'boxes':
            if set(collision) != {'policy', 'boxes'} or not isinstance(collision['boxes'],list) or not 1 <= len(collision['boxes']) <= 256:
                raise ValueError('Supply 1..256 explicit box proxies')
            for box in collision['boxes']:
                if set(box) != {'node', 'center', 'size'} or type(box['node']) is not int or box['node'] not in nodes:
                    raise ValueError('Box must bind to a source node, not a guessed name')
                vector(box['center']); vector(box['size'], True)
        else:
            raise ValueError('Choose retain_graybox, source_mesh or boxes')
    if set(manifest['assets']) != set(assets) or set(assets) != {r['asset'] for r in rows}:
        raise ValueError('Declare exactly the assets consumed by this transaction')


def prepare(project, baseline_path, manifest_path, output):
    root, out = Path(project).resolve(), Path(output).resolve()
    if out.exists():
        raise ValueError('Use a new transaction directory')
    bp, mp = local(root, baseline_path), local(root, manifest_path)
    baseline = json.loads(bp.read_text(encoding='utf-8-sig'))
    manifest = json.loads(mp.read_text(encoding='utf-8-sig'))
    assets, paths = {}, {}
    for aid, item in manifest.get('assets', {}).items():
        identifier(aid)
        if set(item) != {'revision', 'plan_id'}:
            raise ValueError('Asset needs a revision and its expected plan_id')
        paths[aid] = local(root, item['revision'])
        assets[aid] = read_scene(paths[aid])
        if assets[aid]['plan_id'] != item['plan_id']:
            raise ValueError('Static scene revision changed')
    validate(baseline, manifest, assets)
    plan = {'schema': SCHEMA, 'version': VERSION, 'id': manifest['id'], 'engine': baseline['engine'],
            'baseline': baseline, 'replacements': manifest['replacements'],
            'assets': {k: {'revision': 'assets/'+k, 'plan_id': p['plan_id'], 'nodes': p['nodes']} for k, p in assets.items()}}
    plan['plan_id'] = fingerprint(plan)
    out.mkdir(parents=True)
    for aid, path in paths.items():
        dest = out/'assets'/aid
        dest.mkdir(parents=True)
        for file in ['plan.json', *assets[aid]['files']]:
            target = local(dest, file); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local(path, file), target)
        read_scene(dest)
    (out/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return plan


def read_plan(folder):
    root = Path(folder).resolve()
    p = json.loads((root/'plan.json').read_text(encoding='utf-8'))
    if p.get('schema') != SCHEMA or p.get('engine')!=p.get('baseline',{}).get('engine') or fingerprint({k:v for k,v in p.items() if k != 'plan_id'}) != p.get('plan_id'):
        raise ValueError('Frozen replacement plan changed')
    assets = {k: read_scene(local(root, v['revision'])) for k, v in p['assets'].items()}
    if any(assets[k]['plan_id'] != v['plan_id'] for k, v in p['assets'].items()):
        raise ValueError('Frozen scene revision changed')
    if any(assets[k]['nodes'] != v['nodes'] for k,v in p['assets'].items()):
        raise ValueError('Replacement node table differs from frozen scene')
    validate(p['baseline'], {'schema':SCHEMA,'id':p['id'],'assets':p['assets'],'replacements':p['replacements']}, assets)
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('prepare')
    for name in ('project', 'baseline', 'manifest', 'output'): make.add_argument('--'+name, required=True)
    check = sub.add_parser('check'); check.add_argument('revision')
    a = parser.parse_args()
    try:
        p = prepare(a.project,a.baseline,a.manifest,a.output) if a.command=='prepare' else read_plan(a.revision)
        print(json.dumps({'ok':True,'plan_id':p['plan_id'],'groups':len(p['replacements'])}))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')

#!/usr/bin/env python3
"""Explicit, file-granular migration of project-owned native components.

Core and playback are independently selected packages. This
tool never migrates game scripts, assets, bindings, input profiles or saves.
Conflicts require a project decision; no force/overwrite option is provided.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
LOCK = '.openaigame/component-migration.json'


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def safe(root, relative):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative or any(p in ('', '.', '..') for p in relative.split('/')):
        raise ValueError('Invalid relative component path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Component path escapes project')
    return path


def scope(engine, package):
    if engine not in ('godot', 'unreal') or package not in ('core', 'playback'):
        raise ValueError('Unknown engine/package')
    if engine == 'godot': return 'addons/oagd/' if package == 'core' else 'addons/oagd_playback/'
    return 'Plugins/OAGDCore/' if package == 'core' else 'Plugins/OAGDPlayback/'


def sources(engine, package, toolkit=ROOT):
    prefix = scope(engine, package)
    folder = 'runtime_components' if package == 'core' else 'motion_playback'
    source = Path(toolkit) / 'adapters/engines' / folder / engine
    if engine == 'unreal': source /= 'OAGDCore' if package == 'core' else 'OAGDPlayback'
    result = {prefix + p.relative_to(source).as_posix(): p.read_bytes()
              for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if not result: raise ValueError('Missing package source: ' + str(source))
    return result


def baseline(project, engine, package):
    if (project / LOCK).is_file():
        installed = read(project / LOCK)
        if installed['engine'] != engine: raise ValueError('Engine differs from pin')
        if package in installed['packages']: return installed['packages'][package]['files']
    legacy = project / ('.openaigame/runtime-components.json' if package == 'core' else '.openaigame/motion-playback.json')
    # Playback's historical pin also includes game code; filter it to the plugin.
    if package == 'playback' and not legacy.exists():
        import motion_playback
        legacy = project / motion_playback.LOCK
    if not legacy.is_file(): return {}
    value = read(legacy)
    if value['engine'] != engine: raise ValueError('Engine differs from legacy pin')
    return {p: h for p, h in value['files'].items() if p.startswith(scope(engine, package))}


def plan(project, engine, packages, toolkit=ROOT):
    project = Path(project).resolve()
    if not project.is_dir(): raise ValueError('Project must exist')
    if engine == 'godot' and not (project / 'project.godot').is_file(): raise ValueError('Not a Godot project')
    if engine == 'unreal' and len(list(project.glob('*.uproject'))) != 1: raise ValueError('Expected one Unreal project')
    if engine == 'unreal':
        association=str(read(next(project.glob('*.uproject'))).get('EngineAssociation',''))
        numeric=re.match(r'^(\d+)\.(\d+)(?:\.\d+)?$',association)
        if numeric and tuple(map(int,numeric.group(1,2)))!=(5,8):raise ValueError('This native package targets UE 5.8; convert the project explicitly first')
    if not packages or len(set(packages)) != len(packages): raise ValueError('Choose distinct packages')
    actions = []; pins = {}; expected = {}; conflicts = []; preserved = []
    for package in sorted(packages):
        new = sources(engine, package, toolkit); old = baseline(project, engine, package)
        pins[package] = {'files': {p: sha(b) for p, b in sorted(new.items())}}
        for relative in sorted(set(new) | set(old)):
            path = safe(project, relative)
            current = sha(path.read_bytes()) if path.is_file() else None
            expected[relative] = current
            before = old.get(relative); after = sha(new[relative]) if relative in new else None
            if current == after: continue
            if current == before:
                actions.append({'path': relative, 'before': current, 'after': after})
            elif before == after:
                preserved.append(relative)  # Only the project changed; retain it, including intentional deletion.
            else:
                conflicts.append(relative)  # Both changed, or an unowned file collides.
    for p in (LOCK, '.openaigame/runtime-components.json', '.openaigame/motion-playback.json'):
        path = safe(project, p); expected[p] = sha(path.read_bytes()) if path.is_file() else None
    # Include the actual legacy playback lock name without guessing it.
    import motion_playback
    path = safe(project, motion_playback.LOCK)
    expected[motion_playback.LOCK] = sha(path.read_bytes()) if path.is_file() else None
    return {'schema': 'oagd.component-migration/1', 'project': str(project), 'engine': engine,
            'packages': pins, 'expected': expected, 'actions': actions, 'conflicts': conflicts,
            'preserved': preserved, 'ownership': 'native files only; game rules, config, assets and saves are not migrated'}


def apply(project, specification, receipt, toolkit=ROOT):
    project = Path(project).resolve(); receipt = Path(receipt).resolve()
    if receipt.exists() or receipt.is_relative_to(project): raise ValueError('Receipt must be a new directory outside the project')
    actual = plan(project, specification['engine'], list(specification['packages']), toolkit)
    if actual != specification: raise ValueError('Stale plan: project or toolkit changed; plan again')
    if actual['conflicts']: raise ValueError('Conflicts require explicit project resolution: ' + ', '.join(actual['conflicts']))
    candidates = {}
    for package in actual['packages']: candidates.update(sources(actual['engine'], package, toolkit))
    updates = {a['path']: candidates.get(a['path']) for a in actual['actions']}
    manifest = read(project / LOCK) if (project / LOCK).exists() else {'schema': 1, 'engine': actual['engine'], 'packages': {}}
    manifest['packages'].update(actual['packages'])
    updates[LOCK] = json.dumps(manifest, indent=2).encode('utf-8')
    # Advance only native hashes in existing pins; project/template hashes remain unchanged.
    import runtime_components, motion_playback
    for package, name, versionkey, version in [('core', runtime_components.LOCK, 'component_version', runtime_components.VERSION), ('playback', motion_playback.LOCK, 'version', motion_playback.VERSION)]:
        if package not in actual['packages'] or not (project / name).exists(): continue
        pin = read(project / name); prefix = scope(actual['engine'], package)
        pin['files'] = {p: h for p, h in pin['files'].items() if not p.startswith(prefix)}
        pin['files'].update(actual['packages'][package]['files']); pin[versionkey] = version
        updates[name] = json.dumps(pin, indent=2).encode('utf-8')
    receipt.mkdir(parents=True)
    entries = {}
    for i, (relative, content) in enumerate(updates.items()):
        path = safe(project, relative); before = path.read_bytes() if path.is_file() else None
        backup = str(i) + '.before'
        if before is not None: (receipt / backup).write_bytes(before)
        entries[relative] = {'before': sha(before) if before is not None else None, 'after': sha(content) if content is not None else None, 'backup': backup}
    data = {'schema': 1, 'project': str(project), 'entries': entries, 'state': 'prepared'}
    write(receipt / 'receipt.json', data)
    touched = []
    try:
        for relative, content in updates.items():
            path = safe(project, relative); path.parent.mkdir(parents=True, exist_ok=True); touched.append(relative)
            if content is None: path.unlink()
            else:
                temp = path.with_name(path.name + '.oagd-' + uuid.uuid4().hex)
                try: temp.write_bytes(content); temp.replace(path)
                finally: temp.unlink(missing_ok=True)
        data['state'] = 'applied'; write(receipt / 'receipt.json', data)
    except BaseException:
        for relative in reversed(touched):
            entry = entries[relative]; path = safe(project, relative)
            if entry['before'] is None: path.unlink(missing_ok=True)
            else: shutil.copyfile(receipt / entry['backup'], path)
        data['state'] = 'reverted-on-error'; write(receipt / 'receipt.json', data)
        raise
    return data


def rollback(project, receipt):
    project = Path(project).resolve(); receipt = Path(receipt).resolve(); data = read(receipt / 'receipt.json')
    if data['project'] != str(project) or data['state'] != 'applied': raise ValueError('Receipt is not an applied migration for this project')
    for relative, entry in data['entries'].items():
        path = safe(project, relative)
        current = sha(path.read_bytes()) if path.is_file() else None
        if current != entry['after']: raise ValueError('Project changed after migration: ' + relative)
        if entry['before'] is not None and sha(safe(receipt, entry['backup']).read_bytes()) != entry['before']:
            raise ValueError('Backup integrity failed')
    for relative, entry in data['entries'].items():
        path = safe(project, relative)
        if entry['before'] is None: path.unlink(missing_ok=True)
        else: shutil.copyfile(safe(receipt, entry['backup']), path)
    data['state'] = 'rolled-back'; write(receipt / 'receipt.json', data)
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'apply', 'rollback'])
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--engine', choices=['godot', 'unreal'])
    p.add_argument('--packages', nargs='+', choices=['core', 'playback'])
    p.add_argument('--plan', type=Path)
    p.add_argument('--receipt', type=Path)
    args = p.parse_args()
    try:
        if args.action == 'plan':
            if not args.engine or not args.packages or not args.plan: raise ValueError('plan requires engine, packages and plan path')
            if args.plan.exists(): raise ValueError('Plan output exists')
            result = plan(args.project, args.engine, args.packages); write(args.plan, result)
        elif args.action == 'apply':
            if not args.plan or not args.receipt: raise ValueError('apply requires plan and receipt')
            result = apply(args.project, read(args.plan), args.receipt)
        else:
            if not args.receipt: raise ValueError('rollback requires receipt')
            result = rollback(args.project, args.receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return int(bool(result.get('conflicts')))
    except (OSError, ValueError, KeyError) as e: print(json.dumps({'error': str(e)}, ensure_ascii=False)); return 1


if __name__ == '__main__': sys.exit(main())

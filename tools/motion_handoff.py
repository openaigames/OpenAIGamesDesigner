#!/usr/bin/env python3
"""Snapshot a verified motion revision with local, hash-bound dependencies.

Historical reports/jobs remain byte-exact evidence, not executable recipes. The
received job retains effective playback metadata; rebuild from separately supplied
source specs. This does not certify licensing, visual quality or native playback.
"""
import argparse
import copy
import re
import shutil
from pathlib import Path, PureWindowsPath
import motion_workflow as motion

MANIFEST = 'handoff.json'


def safe(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Expected portable relative path: '+str(relative))
    path = Path(relative)
    if path.is_absolute() or PureWindowsPath(relative).is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe handoff path: '+relative)
    result = (root/path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Handoff path escapes directory: '+relative)
    return result


def pack(revision, output):
    revision, output = Path(revision).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(revision):
        raise ValueError('Choose a new directory outside the source revision')
    checked = motion.verify(revision)
    if not checked['ok']:
        raise ValueError(str(checked['failures']))
    report = motion.read(revision/'report.json')
    job = motion.read(revision/'job.json')
    artifacts = {name: safe(revision, name) for name in report['artifacts']}
    if any(Path(name).parts[0] in {'dependencies','provenance','report.json','job.json',MANIFEST} for name in artifacts):
        raise ValueError('Artifact collides with handoff metadata')
    # Collect the transitive report dependency closure before writing anything.
    # Nested report bytes stay unchanged, so their original hashes remain valid.
    sources = {}
    def collect(path, expected):
        path = path.resolve()
        if not path.is_file() or motion.digest(path) != expected:
            raise ValueError('Dependency changed: '+str(path))
        if str(path) in sources:
            if sources[str(path)] != expected: raise ValueError('Conflicting dependency identity')
            return
        sources[str(path)] = expected
        if path.name == 'report.json':
            nested = motion.read(path)
            for name, sha in nested.get('dependencies', {}).items():
                dep = Path(name)
                collect(dep if dep.is_absolute() else safe(path.parent, name), sha)
    for name, sha in report.get('dependencies', {}).items():
        path = Path(name)
        collect(path if path.is_absolute() else safe(revision, name), sha)
    output.mkdir(parents=True)
    (output/'provenance').mkdir()
    for name in ('job.json','report.json'):
        shutil.copy2(revision/name, output/'provenance'/('original-'+name))
    for name, path in artifacts.items():
        target = safe(output, name); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    mapping = {}
    for name, sha in sources.items():
        # Fixed names avoid basename/path collisions and Windows device names.
        target = 'dependencies/'+sha+'/snapshot'+Path(name).suffix.lower()
        mapping[name] = target
        destination = safe(output, target); destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists(): shutil.copy2(name, destination)
    report = copy.deepcopy(report)
    report['dependencies'] = {mapping[name]: sha for name, sha in sources.items()}
    for name in ('job.json','report.json'):
        path = 'provenance/original-'+name
        report['dependencies'][path] = motion.digest(output/path)
    report['handoff'] = {'schema':'oagd.motion-handoff/1', 'source_report_sha256':motion.digest(revision/'report.json'),
                         'scope':'Dependency relocation only; inherited processing evidence; native and visual acceptance remain separate'}
    motion.write(output/'report.json', report)
    received = {'mode':'received', 'original_mode':job['mode'], 'spec':job['spec'],
                'rebuild':'Use supplied source specs; original job paths are historical provenance, not a replay command'}
    motion.write(output/'job.json', received)
    files = {p.relative_to(output).as_posix():motion.digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    motion.write(output/MANIFEST, {'schema':'oagd.motion-handoff/1', 'files':files,
                                  'source_revision':str(revision), 'dependency_mapping':mapping})
    return check(output)


def check(directory):
    directory = Path(directory).resolve(); manifest = motion.read(directory/MANIFEST)
    if manifest.get('schema') != 'oagd.motion-handoff/1' or not manifest.get('files'):
        raise ValueError('Expected nonempty handoff manifest')
    failures = []
    files = manifest['files']
    if not {'report.json','job.json','provenance/original-job.json','provenance/original-report.json'} <= files.keys():
        raise ValueError('Missing handoff records')
    for name, sha in files.items():
        path = safe(directory, name)
        if not re.fullmatch('[0-9a-f]{64}', sha) or not path.is_file() or motion.digest(path) != sha:
            failures.append('Changed handoff file: '+name)
    report = motion.read(directory/'report.json')
    for name, sha in report.get('dependencies', {}).items():
        safe(directory, name)
        if files.get(name) != sha: failures.append('Unbound dependency: '+name)
    verification = motion.verify(directory)
    failures += verification['failures']
    return {'ok':not failures, 'files_checked':len(files), 'failures':failures,
            'scope':'Relocated processing dependency snapshot; not fresh processing, native playback or independent handoff acceptance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('pack'); create.add_argument('--revision', type=Path, required=True); create.add_argument('--output', type=Path, required=True)
    verify = sub.add_parser('check'); verify.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = pack(args.revision,args.output) if args.command == 'pack' else check(args.directory)
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2)); return int(not result['ok'])
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())

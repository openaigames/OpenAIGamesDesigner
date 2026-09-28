#!/usr/bin/env python3
"""Register actual local outputs and observations; never execute or infer a review."""
import argparse
from pathlib import Path
import json
import sys
from record_io import identifier, local, now, read_json, snapshot_files, changed_files, write_json
from validate_records import contract


def validate_evidence(value):
    errors = contract('evidence', value)
    if errors:
        raise ValueError('; '.join(errors))
    identifier(value['id'])
    if not value['files']:
        raise ValueError('Evidence needs at least one actual output, capture or written observation.')
    for name, digest in {**value['files'], **value['dependencies']}.items():
        if not isinstance(name, str) or not name or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('Evidence file/version is invalid.')
    return value


def register(root, spec):
    allowed = {'id', 'source_type', 'description', 'observer', 'files', 'dependencies',
               'objects', 'task', 'result', 'limitations', 'execution_ref'}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError('Unknown evidence input fields.')
    record_id = identifier(spec.get('id'))
    if not isinstance(spec.get('files'), list) or not spec['files']:
        raise ValueError('Provide actual local source/output files, not a planned command.')
    value = {'schema_version':1, 'id':record_id, 'created_at':now(),
             'source_type':spec.get('source_type'), 'description':spec.get('description'),
             'observer':spec.get('observer'), 'result':spec.get('result'),
             'objects':spec.get('objects', []), 'limitations':spec.get('limitations', []),
             'files':snapshot_files(root, spec['files']),
             'dependencies':snapshot_files(root, spec.get('dependencies', []))}
    for key in ('task', 'execution_ref'):
        if spec.get(key):
            value[key] = spec[key]
            # Reference the existing run/session/command capture; do not synthesize one.
            referenced = snapshot_files(root, [spec[key]])
            if key == 'execution_ref':
                value['dependencies'].update(referenced)
    validate_evidence(value)
    destination = local(root, '.openaigame/evidence/' + record_id + '.json')
    write_json(destination, value, create=True)
    return destination


def assess(root, reference):
    value = validate_evidence(read_json(local(root, reference)))
    changed = changed_files(root, {**value['files'], **value['dependencies']})
    return {'id':value['id'], 'reference':reference, 'status':'stale' if changed else 'current',
            'changed':changed, 'result':value['result'], 'objects':value['objects'],
            'source_type':value['source_type'], 'limitations':value['limitations'],
            'quality_validation':'not_performed_by_tool'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--register', type=Path, help='JSON request referencing existing local evidence')
    action.add_argument('--check', help='Project-relative evidence record')
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve()
        if not root.is_dir():
            raise ValueError('Project directory does not exist.')
        if args.register:
            path = register(root, read_json(args.register))
            result = assess(root, path.relative_to(root).as_posix())
        else:
            result = assess(root, args.check)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['status'] != 'current' else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

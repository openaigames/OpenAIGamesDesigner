#!/usr/bin/env python3
"""Prepare and inspect generation inputs locally, without credentials or model calls."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.assets import input_preparation
from tools.validate_records import contained


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare', help='Compile requirements and an Agent input plan')
    prepare.add_argument('--spec', required=True)
    prepare.add_argument('--plan', required=True)
    prepare.add_argument('--output', required=True, help='New project-relative directory')
    check = sub.add_parser('check', help='Check a frozen request and its current source files')
    check.add_argument('--request', required=True)
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        if not root.is_dir():
            raise ValueError('Project must exist')
        if args.action == 'prepare':
            record = input_preparation.prepare(root, args.spec, args.plan, args.output)
            result = {k: record[k] for k in ('asset_id', 'provider', 'status', 'errors', 'warnings', 'coverage')}
            result.update(request=args.output + '/request.json', preview=args.output + '/preview.md',
                          record=args.output + '/preparation.json', generation_submitted=False)
        else:
            request = json.loads(contained(root, args.request).read_text(encoding='utf-8-sig'))
            link = request.get('preparation', {})
            record = json.loads(contained(root, link.get('path')).read_text(encoding='utf-8'))
            settings = input_preparation.effective_settings(root, record['provider'])
            input_preparation.verify_request(root, record['provider'], request, settings, fresh=True)
            result = {'status': 'ready', 'asset_id': record['asset_id'], 'generation_submitted': False,
                      'quality_verified': False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'ready' else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Turn reviewed output defects into bounded input revisions and compare candidates."""
import argparse
import json
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from adapters.assets import iteration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    draft = sub.add_parser('draft')
    draft.add_argument('--report', required=True)
    draft.add_argument('--previous')
    draft.add_argument('--output', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--plan', required=True)
    prepare.add_argument('--output', required=True)
    compare = sub.add_parser('compare')
    compare.add_argument('--iteration', required=True)
    compare.add_argument('--report', required=True)
    compare.add_argument('--output', required=True)
    check = sub.add_parser('check')
    check.add_argument('--iteration')
    check.add_argument('--comparison')
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve()
        if not root.is_dir():
            raise ValueError('Project must exist')
        if args.action == 'draft':
            result = iteration.draft(root, args.report, args.output, args.previous)
        elif args.action == 'prepare':
            value = iteration.create(root, args.plan, args.output)
            result = {k: value[k] for k in ('status', 'round', 'asset_id', 'generation_submitted')}
            result.update(iteration=args.output + '/iteration.json', preview=args.output + '/preview.md')
            if value['prepared']:
                result['request'] = args.output + '/prepared/request.json'
        elif args.action == 'compare':
            result = iteration.compare(root, args.iteration, args.report, args.output)['result']
        else:
            if bool(args.iteration) == bool(args.comparison):
                raise ValueError('Choose exactly one iteration or comparison')
            if args.iteration:
                value = iteration.inspect(root, args.iteration)
                if value['prepared']:
                    request_path = str(Path(value['prepared']).with_name('request.json')).replace('\\', '/')
                    request = iteration.q.read(root, request_path)
                    iteration.prep.verify_request(root, value['provider'], request, value['settings'])
                result = {'status': value['status'], 'round': value['round'], 'generation_submitted': False}
            else:
                result = iteration.inspect_comparison(root, args.comparison)['result']
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] in ('draft', 'ready', 'accepted', 'stopped', 'complete', 'improved') else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Collect offline asset evidence, review quality and publish the external gate."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters.assets import quality


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    commands = parser.add_subparsers(dest='action', required=True)
    capture = commands.add_parser('capture', help='Render static GLB views with an installed Blender')
    capture.add_argument('--model', required=True)
    capture.add_argument('--blender', required=True)
    capture.add_argument('--front', choices=('-X','+X','-Y','+Y'), default='-Y')
    capture.add_argument('--units', choices=('meters','centimeters','unknown'), default='unknown')
    capture.add_argument('--resolution', type=int, default=512)
    capture.add_argument('--output', required=True)
    collect = commands.add_parser('collect', help='Freeze source, reference and comparison evidence')
    collect.add_argument('--plan', required=True)
    collect.add_argument('--output', required=True)
    assess = commands.add_parser('assess', help='Combine automatic measurements and explicit Agent judgments')
    assess.add_argument('--evidence', required=True)
    assess.add_argument('--review', required=True)
    assess.add_argument('--output', required=True)
    for name in ('check','publish'):
        item = commands.add_parser(name)
        item.add_argument('--report', required=True)
        if name == 'publish':
            item.add_argument('--record', required=True, help='Existing testing record in the asset review registry')
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve()
        if not root.is_dir():
            raise ValueError('Project must exist')
        if args.action == 'capture':
            from adapters.assets.model_evidence import capture
            result = capture(root, args.model, args.output, args.blender, args.front, args.units, args.resolution)
            result = {'status':'collected', 'capture':args.output+'/capture.json', 'views':len(result['views']), 'quality_verified':False}
        elif args.action == 'collect':
            record = quality.collect(root, args.plan, args.output)
            result = {'status':'collected','evidence':args.output+'/evidence.json',
                      'review_template':args.output+'/review-template.json', 'checks':record['checks'],
                      'findings':record['findings'], 'quality_verified':False}
        elif args.action == 'assess':
            result = quality.assess(root,args.evidence,args.review,args.output)['result']
        elif args.action == 'check':
            result = quality.inspect(root,args.report)[0]['result']
        else:
            data = quality.publish(root,args.report,args.record)
            result = {'status':'published','record':data['selectedId'],'gate':'external'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result['status'] in ('fail','needs_review') else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status':'invalid','error':str(exc)},ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

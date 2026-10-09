#!/usr/bin/env python3
"""Environment material plans, placement, fixed-view comparisons and handoff packages."""
import argparse
import json
from pathlib import Path
from environment import materials, placement, views, handoff
from environment.common import read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('materials', 'placement', 'record-views', 'capture', 'handoff'):
        p = sub.add_parser(name)
        p.add_argument('--input', type=Path, required=True)
        p.add_argument('--project', type=Path, default=Path.cwd())
        p.add_argument('--out', type=Path, required=True)
        if name == 'record-views':
            p.add_argument('--captures', type=Path, required=True)
        if name == 'capture':
            p.add_argument('--runner', type=Path, required=True)
        if name == 'placement':
            p.add_argument('--measurements', type=Path, help='Read measured Blender bounds and explicit semantic roles')
        if name == 'handoff':
            p.add_argument('--package', action='store_true', help='Copy the selected files into a new directory')
    p = sub.add_parser('compare-views')
    p.add_argument('--before', type=Path, required=True)
    p.add_argument('--after', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError('Output exists; select a new path')
        if args.command == 'compare-views':
            report = views.compare(read(args.before), read(args.after), args.out)
        elif args.command == 'capture':
            report = views.capture(args.input, args.runner, args.project, args.out)
        else:
            data = read(args.input)
            if args.command == 'materials':
                report = materials.check(data, args.project)
            elif args.command == 'placement':
                if args.measurements:
                    data = placement.measured_input(data, read(args.measurements))
                report = placement.analyze(data)
            elif args.command == 'record-views':
                report = views.record(data, args.captures, args.project)
            else:
                report = handoff.build(data, args.project, args.out if args.package else None)
            if args.command != 'handoff' or not args.package:
                write(args.out, report)
        print(json.dumps({'output':str(args.out), 'checks_ok':report['checks_ok'],
                          'issues':len(report['issues']), 'visual_approval':'not_assessed'}, ensure_ascii=False))
        return 0 if report['checks_ok'] else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error':str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

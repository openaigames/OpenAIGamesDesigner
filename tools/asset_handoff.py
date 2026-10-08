#!/usr/bin/env python3
"""Record production/import facts or check a scoped asset delivery without running an engine."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_io import read_json, local
from workbench import asset_handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    commands = parser.add_subparsers(dest='action', required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('--manifest', required=True, type=Path)
    check = commands.add_parser('check')
    check.add_argument('--scope', required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        if not root.is_dir():
            raise ValueError('Project directory does not exist')
        if args.action == 'apply':
            result = asset_handoff.apply(root, read_json(args.manifest))
        else:
            result = asset_handoff.check(root, read_json(args.scope))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('ok') is False else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

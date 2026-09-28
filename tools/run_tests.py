#!/usr/bin/env python3
"""Run repository tests and every Skill's script tests in separate processes."""
import argparse
from pathlib import Path
import subprocess
import sys
import shutil
import os

ROOT = Path(__file__).resolve().parents[1]


def suites():
    found = {'core': ROOT / 'tests'}
    for folder in sorted((ROOT / 'skills').glob('*/scripts/tests')):
        found[folder.parents[1].name] = folder
    return found


def main():
    groups = suites()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--group', action='append', choices=tuple(groups))
    parser.add_argument('--node', default=os.environ.get('NODE') or shutil.which('node'), help='Node executable for board behavior tests (required for full run)')
    args = parser.parse_args()
    selected = args.group or list(groups)
    if args.list:
        for name in selected: print(name + ': ' + groups[name].relative_to(ROOT).as_posix())
        return 0
    failed = []
    for name in selected:
        print('Testing ' + name, flush=True)
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover',
                                 '-s', str(groups[name]), '-p', 'test_*.py', '-q'], cwd=ROOT)
        if result.returncode: failed.append(name)
    if 'core' in selected:
        if not args.node:
            print('Node is required to validate shared board behavior; supply --node',flush=True)
            failed.append('board-js (runtime unavailable)')
        else:
            for script in sorted((ROOT/'tests').glob('test_*.mjs')):
                if subprocess.run([args.node,str(script)],cwd=ROOT).returncode:failed.append(script.name)
    print('Failed suites: ' + ', '.join(failed) if failed else 'All test suites passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

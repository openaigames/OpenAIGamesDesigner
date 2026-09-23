#!/usr/bin/env python3
"""Run repository tests and every Skill's script tests in separate processes."""
import argparse
from pathlib import Path
import subprocess
import sys

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
    print('Failed suites: ' + ', '.join(failed) if failed else 'All test suites passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

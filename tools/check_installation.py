#!/usr/bin/env python3
"""Read-only comparison of an installed skill bundle with its shipped file manifest."""
import argparse
import hashlib
import json
from pathlib import Path

MANIFEST = 'game-preproduction/runtime/bundle-manifest.json'


def bundle_id(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def check(root):
    root = root.resolve()
    manifest = json.loads((root / MANIFEST).read_text(encoding='utf-8-sig'))
    files = manifest.get('files')
    if manifest.get('version') != 1 or not isinstance(files, dict) or not files or manifest.get('bundle_id') != bundle_id(files):
        raise ValueError('Invalid bundle manifest')
    missing, changed = [], []
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root) or path == root:
            raise ValueError('Manifest path escapes installation: ' + relative)
        if not path.is_file(): missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected: changed.append(relative)
    return {'bundle_id': manifest['bundle_id'], 'files_checked':len(files), 'missing':missing, 'changed':changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.skills_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['missing'] or result['changed'] else 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'error':str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Small file and numeric helpers; reports never approve visual quality."""
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def inside(root, relative, exists=True):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Expected project-relative path: ' + str(relative))
    result = (root / relative).resolve()
    if not result.is_relative_to(root) or result == root:
        raise ValueError('Path escapes project: ' + relative)
    if exists and not result.is_file():
        raise ValueError('Missing file: ' + relative)
    return result


def number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(name + ' is outside its valid range')
    return value


def unique(items):
    result = {}
    for item in items:
        name = item.get('id')
        if not isinstance(name, str) or not name.strip() or name in result:
            raise ValueError('Missing or duplicate ID: ' + str(name))
        result[name] = item
    return result


def identity(root, paths):
    return {name: digest(inside(root, name)) for name in sorted(set(paths))}


def issues_report(kind, issues, **kwargs):
    return {'schema': kind + '/1', 'issues': issues,
            'checks_ok': not any(i.get('severity', 'error') == 'error' for i in issues),
            'visual_approval': 'not_assessed', **kwargs}


def issue(code, severity='error', **details):
    return {'code': code, 'severity': severity, **details}

"""Shared configuration and evidence helpers; engine packages supply report parsers."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def settings(config, engine):
    value = config.get(engine, {})
    if not isinstance(value, dict):
        raise ValueError(f'{engine} settings must be an object')
    return value


def required(options, key):
    value = options.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Configure {key} explicitly for the native engine action')
    return value


def token(value, label, pattern=r'[A-Za-z0-9_./ -]+'):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f'Invalid {label}: {value!r}')
    return value


def file_path(value, label):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f'{label} must be an existing absolute file')
    return path.resolve()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def evidence(path, run):
    return {'path': path.relative_to(run).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def normalize_report(parser, raw, run, label):
    if not raw.is_file():
        raise ValueError(f'Native test report missing: {raw}')
    try:
        result = parser(raw)
    except (ET.ParseError, json.JSONDecodeError, TypeError) as error:
        raise ValueError(f'Malformed {label} test report: {error}') from error
    result['source'] = evidence(raw, run)
    write_json(run / 'test-results.json', result)
    if result['tests'] < 1 or result['failed'] or result['errors']:
        raise ValueError(f'Native tests did not pass: {result}')
    return result

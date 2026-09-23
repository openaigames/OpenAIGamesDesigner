"""Unreal native test report parsing and normalization."""
import json
from ..native_support import normalize_report


def parse_tests(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not isinstance(data.get('tests'), list):
        raise ValueError('Unreal report must contain the actual tests list')
    result = {'tests': 0, 'failed': 0, 'errors': 0, 'skipped': 0}
    for item in data['tests']:
        if not isinstance(item, dict):
            raise ValueError('Malformed Unreal test entry')
        state = str(item.get('state', '')).lower()
        if state in {'success', 'successwithwarnings'}:
            result['tests'] += 1
        elif state == 'fail':
            result['tests'] += 1
            result['failed'] += 1
        else:
            # NotRun, InProcess, Skipped and unknown states cannot certify a complete run.
            result['errors'] += 1
        if item.get('errors', 0) and state != 'fail':
            result['errors'] += 1
    if data.get('failed', 0) and not result['failed']:
        result['errors'] += 1
    if data.get('notRun', 0) or data.get('inProcess', 0):
        result['errors'] += 1
    return result


def normalize_tests(raw, run):
    return normalize_report(parse_tests, raw, run, 'unreal')

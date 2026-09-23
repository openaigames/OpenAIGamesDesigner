"""Unity native test report parsing and normalization."""
import xml.etree.ElementTree as ET
from ..native_support import normalize_report


def parse_tests(path):
    """Count executed leaf cases, rejecting empty, truncated or setup-failed XML."""
    root = ET.parse(path).getroot()
    if root.tag not in {'test-run', 'test-results'}:
        raise ValueError('Expected an NUnit test-run/test-results document')
    counts = {'tests': 0, 'failed': 0, 'errors': 0, 'skipped': 0}
    for case in root.iter('test-case'):
        state = case.get('result', '').lower()
        if state in {'passed', 'success'}:
            counts['tests'] += 1
        elif state in {'failed', 'failure', 'error', 'cancelled'}:
            counts['tests'] += 1
            counts['failed'] += 1
        elif state in {'skipped', 'ignored', 'inconclusive'}:
            counts['skipped'] += 1
        else:
            counts['errors'] += 1
    if root.get('result', '').lower() in {'failed', 'failure', 'error', 'cancelled'} and not counts['failed']:
        counts['errors'] += 1
    if any(s.get('result', '').lower() in {'failed', 'failure'} for s in root.iter('test-suite')) and not counts['failed']:
        counts['errors'] += 1
    return counts


def normalize_tests(raw, run):
    return normalize_report(parse_tests, raw, run, 'unity')

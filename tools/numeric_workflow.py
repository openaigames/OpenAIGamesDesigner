#!/usr/bin/env python3
"""Reviewable numeric table round trips for existing, explicitly bound JSON data.

Python 3.10+, standard library for CSV; optional openpyxl for reading XLSX.
This edits configuration files, not engine assets or live game instances.
"""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid


def digest(data):
    return hashlib.sha256(data).hexdigest()


def local(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes project: {value}")
    return path


def rel(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(data):
    def invalid(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=invalid)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as out:
        out.write(encoded(value))


def atomic_bytes(path, data):
    handle, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def number(value, field, where):
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise ValueError(f"{where}: a number is required; blank is not zero")
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"{where}: invalid number {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"{where}: finite number required")
    if field['type'] == 'integer' and result != result.to_integral_value():
        raise ValueError(f"{where}: integer required")
    for bound, check in [('min', lambda x, y: x < y), ('max', lambda x, y: x > y)]:
        if bound in field and check(result, Decimal(str(field[bound]))):
            raise ValueError(f"{where}: outside {bound}={field[bound]}")
    if field['type'] == 'integer':
        # Excel and common game JSON readers cannot round-trip larger integers exactly.
        if abs(result) > 9007199254740991:
            raise ValueError(f"{where}: integer exceeds exact spreadsheet range")
        return int(result)
    original = result
    result = float(result)
    if not math.isfinite(result) or (original != 0 and result == 0):
        raise ValueError(f"{where}: floating-point overflow")
    return result


def read_binding(root, path):
    raw = path.read_bytes()
    b = decode(raw)
    if not isinstance(b, dict) or b.get('version') != 1:
        raise ValueError('Binding must have version 1')
    if set(b) - {'version', 'target', 'records_key', 'id_field', 'fields'}:
        raise ValueError('Unknown binding keys')
    if not isinstance(b.get('target'), str) or not isinstance(b.get('id_field'), str):
        raise ValueError('Binding requires target and id_field')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', b['id_field']):
        raise ValueError('Unsupported id_field name')
    if b.get('records_key') is not None and not isinstance(b['records_key'], str):
        raise ValueError('records_key must be a string or null')
    target = local(root, b['target'])
    if target.suffix.lower() != '.json' or target == path:
        raise ValueError('Target must be a separate JSON configuration file')
    fields = b.get('fields')
    if not isinstance(fields, dict) or not fields or b['id_field'] in fields:
        raise ValueError('Declare editable numeric fields, excluding id_field')
    for name, field in fields.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError(f'Unsupported field name: {name}')
        if not isinstance(field, dict) or field.get('type') not in ('integer', 'number'):
            raise ValueError(f'{name}: numeric type required')
        if set(field) - {'type', 'unit', 'min', 'max'} or not isinstance(field.get('unit'), str) or not field['unit']:
            raise ValueError(f'{name}: declare unit, type and optional min/max only')
        for k in ('min', 'max'):
            if k in field and (type(field[k]) not in (int, float) or not math.isfinite(field[k])):
                raise ValueError(f'{name}: invalid {k}')
        if 'min' in field and 'max' in field and field['min'] > field['max']:
            raise ValueError(f'{name}: min exceeds max')
    return b, raw, target


def records(document, binding):
    key = binding.get('records_key')
    rows = document if key is None else document.get(key) if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('Target must contain a nonempty record array')
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each record must be an object')
        identity = row.get(binding['id_field'])
        if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}', identity):
            raise ValueError(f'Unsupported stable ID: {identity!r}')
        if identity in result:
            raise ValueError(f'Duplicate ID: {identity}')
        for name, field in binding['fields'].items():
            if type(row.get(name)) not in (int, float):
                raise ValueError(f'{identity}.{name}: source must be a numeric JSON value')
            number(row[name], field, f'{identity}.{name}')
        result[identity] = row
    return result


def export_table(root, binding_path, session):
    b, binding_raw, target = read_binding(root, binding_path)
    source = target.read_bytes()
    rows = records(decode(source), b)
    if session == target or target.is_relative_to(session) or binding_path.is_relative_to(session):
        raise ValueError('Exchange directory cannot contain source or binding')
    session.mkdir(parents=True, exist_ok=False)
    names = [b['id_field'], *b['fields']]
    with (session / 'parameters.csv').open('x', encoding='utf-8-sig', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(names)
        writer.writerows([[row[name] for name in names] for row in rows.values()])
    new_json(session / 'baseline.json', {
        'version': 1, 'binding': rel(root, binding_path), 'binding_sha256': digest(binding_raw),
        'target': rel(root, target), 'target_sha256': digest(source), 'fields': b['fields'],
        'status': 'exported', 'created_at': datetime.now(timezone.utc).isoformat(),
    })
    return {'session': rel(root, session), 'table': rel(root, session / 'parameters.csv'), 'rows': len(rows)}


def table_rows(path, sheet):
    if path.suffix.lower() == '.csv':
        return list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    if path.suffix.lower() != '.xlsx':
        raise ValueError('Use .csv or .xlsx')
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValueError('XLSX reading requires openpyxl; otherwise save the numeric input sheet as CSV') from exc
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        if sheet not in book.sheetnames:
            raise ValueError(f'Missing worksheet: {sheet}')
        result = []
        for row in book[sheet].iter_rows():
            if any(cell.data_type in ('f', 'e') for cell in row):
                raise ValueError('Import sheet contains formula/error cells; recalculate and export reviewed values first')
            result.append([cell.value for cell in row])
        while result and all(x is None for x in result[-1]):
            result.pop()
        return result
    finally:
        book.close()


def candidate(root, session, table, sheet):
    baseline = decode((session / 'baseline.json').read_bytes())
    if baseline.get('version') != 1:
        raise ValueError('Unsupported baseline version')
    bpath = local(root, baseline['binding'])
    b, braw, target = read_binding(root, bpath)
    source = target.read_bytes()
    if digest(braw) != baseline['binding_sha256'] or rel(root, target) != baseline['target']:
        raise ValueError('Binding changed; export a new session and reconcile edits')
    if digest(source) != baseline['target_sha256']:
        raise ValueError('Configuration changed since export; reconcile against a new baseline')
    doc = decode(source)
    indexed = records(doc, b)
    headers = [b['id_field'], *b['fields']]
    lines = table_rows(table, sheet)
    if not lines or lines[0] != headers:
        raise ValueError(f'Header must match exactly: {headers}')
    seen, changes = set(), []
    for line in lines[1:]:
        if len(line) != len(headers):
            raise ValueError('Ragged or extra table columns')
        identity = line[0]
        if identity in seen or identity not in indexed:
            raise ValueError(f'Duplicate or unknown ID: {identity!r}')
        seen.add(identity)
        for name, value in zip(headers[1:], line[1:]):
            value = number(value, b['fields'][name], f'{identity}.{name}')
            previous = indexed[identity][name]
            if value != previous:
                changes.append({'id': identity, 'field': name, 'before': previous,
                                'after': value, 'unit': b['fields'][name]['unit']})
                indexed[identity][name] = value
    if seen != set(indexed):
        raise ValueError('Rows were removed; this tool updates values, not record membership')
    plan = {'version': 1, 'session': rel(root, session), 'table': rel(root, table), 'sheet': sheet,
            'target': rel(root, target), 'binding': rel(root, bpath),
            'baseline_sha256': digest((session / 'baseline.json').read_bytes()),
            'binding_sha256': digest(braw), 'source_sha256': digest(source),
            'table_sha256': digest(table.read_bytes()), 'changes': changes,
            'result_sha256': digest(encoded(doc)), 'engine_validation': 'not_run'}
    return plan, encoded(doc), source


def make_plan(root, session, table, sheet, output):
    plan, _, _ = candidate(root, session, table, sheet)
    new_json(output, plan)
    return plan


def apply_plan(root, path):
    saved = decode(path.read_bytes())
    session = local(root, saved['session'])
    table = local(root, saved['table'])
    plan, after, before = candidate(root, session, table, saved['sheet'])
    if saved != plan:
        raise ValueError('Plan, input table or baseline changed; create and review a new plan')
    if not plan['changes']:
        return {'status': 'no_changes', 'engine_validation': 'not_run'}
    target = local(root, plan['target'])
    operation = local(root, '.openaigame/numeric-imports/' + uuid.uuid4().hex)
    operation.mkdir(parents=True, exist_ok=False)
    (operation / 'before.json').write_bytes(before)
    receipt = copy.deepcopy(plan)
    receipt.update({'status': 'prepared', 'backup': rel(root, operation / 'before.json'),
                    'created_at': datetime.now(timezone.utc).isoformat()})
    receipt_path = operation / 'receipt.json'
    new_json(receipt_path, receipt)
    try:
        # Recheck immediately before writing. Callers must pause competing writers/importers.
        if target.read_bytes() != before:
            raise ValueError('Configuration changed during import')
        atomic_bytes(target, after)
        if digest(target.read_bytes()) != plan['result_sha256']:
            raise ValueError('Configuration differs after replacement; inspect concurrent writers')
    except (OSError, ValueError) as exc:
        receipt.update({'status': 'failed', 'error': str(exc)})
        atomic_bytes(receipt_path, encoded(receipt))
        raise
    receipt['status'] = 'configuration_written'
    atomic_bytes(receipt_path, encoded(receipt))
    return {'status': receipt['status'], 'receipt': rel(root, receipt_path),
            'changes': len(plan['changes']), 'engine_validation': 'not_run'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--binding', required=True)
    export.add_argument('--session', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--session', required=True)
    plan.add_argument('--table', required=True)
    plan.add_argument('--sheet', default='Parameters')
    plan.add_argument('--out', required=True)
    apply = sub.add_parser('apply')
    apply.add_argument('--plan', required=True)
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        if not root.is_dir():
            raise ValueError('Project directory must already exist')
        if args.command == 'export':
            result = export_table(root, local(root, args.binding), local(root, args.session))
        elif args.command == 'plan':
            result = make_plan(root, local(root, args.session), local(root, args.table), args.sheet, local(root, args.out))
        else:
            result = apply_plan(root, local(root, args.plan))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()

"""Numeric exchange checks: no silent coercion, overwrite or false engine success."""
import csv
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import numeric_workflow as numeric
import package_skills


class NumericWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.target = self.root / 'game/data/combat.json'
        self.target.parent.mkdir(parents=True)
        self.target.write_text(json.dumps({'version': 3, 'attacks': [
            {'id': 'LIGHT', 'damage': 30, 'cooldown': 0.5, 'animation': 'KeepMe'},
            {'id': 'HEAVY', 'damage': 55, 'cooldown': 1.2, 'animation': 'KeepMeToo'}]}), encoding='utf-8')
        self.before = self.target.read_bytes()
        self.binding = self.root / 'design/numerics/combat.json'
        self.binding.parent.mkdir(parents=True)
        numeric.new_json(self.binding, {'version': 1, 'target': 'game/data/combat.json',
            'records_key': 'attacks', 'id_field': 'id', 'fields': {
                'damage': {'type': 'integer', 'unit': 'HP/hit', 'min': 0, 'max': 1000},
                'cooldown': {'type': 'number', 'unit': 'seconds', 'min': 0.01, 'max': 10}}})
        self.session = self.root / 'design/numerics/exchange-01'
        numeric.export_table(self.root, self.binding, self.session)
        self.table = self.session / 'parameters.csv'
        self.plan = self.session / 'plan.json'

    def edit(self, value='40', rows=None):
        with self.table.open('w', encoding='utf-8-sig', newline='') as out:
            csv.writer(out).writerows(rows or [['id', 'damage', 'cooldown'], ['LIGHT', value, '0.5'], ['HEAVY', '55', '1.2']])

    def preview(self, table=None):
        return numeric.make_plan(self.root, self.session, table or self.table, 'Parameters', self.plan)

    def test_round_trip_preserves_unbound_fields_and_records_evidence(self):
        self.edit()
        plan = self.preview()
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(plan['changes'], [{'id': 'LIGHT', 'field': 'damage', 'before': 30, 'after': 40, 'unit': 'HP/hit'}])
        result = numeric.apply_plan(self.root, self.plan)
        data = json.loads(self.target.read_text())
        self.assertEqual(data['attacks'][0]['damage'], 40)
        self.assertEqual(data['attacks'][0]['animation'], 'KeepMe')
        self.assertEqual(data['version'], 3)
        receipt = json.loads((self.root / result['receipt']).read_text())
        self.assertEqual((self.root / receipt['backup']).read_bytes(), self.before)
        self.assertEqual(receipt['engine_validation'], 'not_run')
        self.assertEqual(receipt['status'], 'configuration_written')
        with self.assertRaisesRegex(ValueError, 'changed since export'):
            numeric.apply_plan(self.root, self.plan)

    def test_invalid_numbers_leave_source_unchanged(self):
        for value in ['', 'NaN', 'Infinity', '1.5', '-1', '1001', '=10+20', '1,000']:
            with self.subTest(value=value):
                self.edit(value)
                with self.assertRaises(ValueError):
                    self.preview()
                self.assertEqual(self.target.read_bytes(), self.before)
                self.assertFalse(self.plan.exists())

    def test_zero_and_boundary_are_valid_and_reordering_uses_id(self):
        self.edit(rows=[['id', 'damage', 'cooldown'], ['HEAVY', '1000', '10'], ['LIGHT', '0', '0.01']])
        self.preview()
        numeric.apply_plan(self.root, self.plan)
        rows = json.loads(self.target.read_text())['attacks']
        self.assertEqual([(r['id'], r['damage']) for r in rows], [('LIGHT', 0), ('HEAVY', 1000)])

    def test_record_membership_and_headers_must_be_preserved(self):
        cases = [
            [['id', 'damage', 'cooldown'], ['LIGHT', 40, 0.5]],
            [['id', 'damage', 'cooldown'], ['LIGHT', 40, 0.5], ['LIGHT', 55, 1.2]],
            [['id', 'damage', 'cooldown'], ['NEW', 40, 0.5], ['HEAVY', 55, 1.2]],
            [['id', 'damage', 'cooldown_ms'], ['LIGHT', 40, 500], ['HEAVY', 55, 1200]],
        ]
        for rows in cases:
            self.edit(rows=rows)
            with self.assertRaises(ValueError):
                self.preview()
            self.assertEqual(self.target.read_bytes(), self.before)

    def test_target_changed_since_export_is_a_conflict(self):
        self.edit()
        self.preview()
        self.target.write_bytes(self.before + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed since export'):
            numeric.apply_plan(self.root, self.plan)
        self.assertEqual(self.target.read_bytes(), self.before + b'\n')

    def test_edited_table_or_plan_requires_new_review(self):
        self.edit()
        self.preview()
        self.edit('50')
        with self.assertRaisesRegex(ValueError, 'create and review'):
            numeric.apply_plan(self.root, self.plan)
        self.edit()
        saved = json.loads(self.plan.read_text())
        saved['changes'][0]['after'] = 999
        self.plan.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'create and review'):
            numeric.apply_plan(self.root, self.plan)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_binding_change_requires_new_baseline(self):
        self.binding.write_bytes(self.binding.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Binding changed'):
            self.preview()

    def test_paths_and_overwrite_protection(self):
        with self.assertRaises(ValueError):
            numeric.local(self.root, '../outside.json')
        with self.assertRaises(FileExistsError):
            numeric.export_table(self.root, self.binding, self.session)
        self.preview()
        with self.assertRaises(FileExistsError):
            self.preview()

    def test_no_changes_does_not_reformat_target(self):
        self.preview()
        self.assertEqual(numeric.apply_plan(self.root, self.plan)['status'], 'no_changes')
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_failed_replace_retains_original_and_backup(self):
        self.edit()
        self.preview()
        replace = numeric.os.replace
        def fail_target(src, dst):
            if Path(dst) == self.target:
                raise OSError('locked by editor')
            return replace(src, dst)
        with patch.object(numeric.os, 'replace', side_effect=fail_target):
            with self.assertRaises(OSError):
                numeric.apply_plan(self.root, self.plan)
        self.assertEqual(self.target.read_bytes(), self.before)
        receipt = json.loads(next((self.root / '.openaigame/numeric-imports').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual((self.root / receipt['backup']).read_bytes(), self.before)

    def test_json_duplicate_keys_and_nonfinite_rejected(self):
        for data in [b'{"x":1,"x":2}', b'{"x":NaN}']:
            with self.assertRaises(ValueError):
                numeric.decode(data)

    def test_xlsx_values_and_formula_rejection(self):
        # Minimal fixture written as OOXML, not a user-facing authored workbook.
        try:
            import openpyxl  # optional integration reader
        except ImportError:
            self.skipTest('Optional XLSX reader unavailable')
        path = self.session / 'edited.xlsx'
        def fixture(formula=False):
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
                z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Parameters" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
                rows = [['id', 'damage', 'cooldown'], ['LIGHT', 40, 0.5], ['HEAVY', 55, 1.2]]
                xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                for r, row in enumerate(rows, 1):
                    xml += f'<row r="{r}">'
                    for c, value in enumerate(row):
                        ref = f'{chr(65+c)}{r}'
                        if formula and ref == 'B2':
                            xml += f'<c r="{ref}"><f>20+20</f><v>40</v></c>'
                        elif isinstance(value, str):
                            xml += f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
                        else:
                            xml += f'<c r="{ref}" t="n"><v>{value}</v></c>'
                    xml += '</row>'
                z.writestr('xl/worksheets/sheet1.xml', xml + '</sheetData></worksheet>')
        fixture()
        self.assertEqual(self.preview(path)['changes'][0]['after'], 40)
        fixture(formula=True)
        with self.assertRaisesRegex(ValueError, 'formula/error'):
            numeric.candidate(self.root, self.session, path, 'Parameters')

    def test_relocated_bundle_cli_can_plan_and_apply(self):
        bundle = package_skills.package(self.root / 'relocated-bundle')
        tool = bundle / 'game-preproduction/runtime/tools/numeric_workflow.py'
        self.edit('60')
        prefix = [sys.executable, '-B', '-X', 'utf8', str(tool), '--project', str(self.root)]
        plan = subprocess.run(prefix + ['plan', '--session', 'design/numerics/exchange-01',
            '--table', 'design/numerics/exchange-01/parameters.csv', '--out', 'design/numerics/exchange-01/plan.json'],
            capture_output=True, text=True, encoding='utf-8', cwd=self.root, timeout=30)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        applied = subprocess.run(prefix + ['apply', '--plan', 'design/numerics/exchange-01/plan.json'],
            capture_output=True, text=True, encoding='utf-8', cwd=self.root, timeout=30)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(json.loads(self.target.read_text())['attacks'][0]['damage'], 60)


if __name__ == '__main__':
    unittest.main()

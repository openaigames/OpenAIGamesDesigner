"""Offline source routing checks; a website listing must not imply a file download."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_library as library


class SourceTests(unittest.TestCase):
    def test_cli_preserves_unicode_when_parent_uses_legacy_encoding(self):
        query = '魔法火花🎨'
        for encoding in ('cp1252', 'ascii'):
            with self.subTest(encoding=encoding):
                result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/asset_library.py'),
                    'sources', '--kind', 'vfx', '--query', query], cwd=ROOT.parent,
                    env={**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': encoding}, capture_output=True)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                data = json.loads(result.stdout.decode('utf-8'))
                self.assertEqual(data['status'], 'search_plan')
                self.assertTrue(data['sources'])
                self.assertTrue(all(query in row['search_query'] for row in data['sources']))

    def test_direct_requires_anonymous_download_evidence(self):
        rows = [
            {'id': 'legacy', 'domain': 'example.org', 'kinds': ['vfx']},
            {'id': 'claim', 'domain': 'example.org', 'kinds': ['vfx'],
             'download': {'mode': 'direct', 'login': 'none'},
             'verification': {'status': 'download_not_tested', 'files': []}},
            {'id': 'account', 'domain': 'example.org', 'kinds': ['vfx'],
             'download': {'mode': 'direct', 'login': 'required'},
             'verification': {'status': 'sample_download_passed', 'files': [{'url': 'https://example.org/a.zip'}]}},
            {'id': 'verified', 'domain': 'example.org', 'kinds': ['vfx'],
             'download': {'mode': 'direct', 'login': 'none'},
             'verification': {'status': 'sample_download_passed', 'files': [{'url': 'https://example.org/a.zip'}]}}
        ]
        catalog = Mock()
        catalog.read_text.return_value = json.dumps({'sources': rows})
        result = library.sources('vfx', 'spark', catalog, access='direct')
        self.assertEqual([s['id'] for s in result['sources']], ['verified'])
        self.assertEqual(result['sources'][0]['search_query'], 'site:example.org spark vfx')
        self.assertFalse(result['results_are_assets'])
        self.assertEqual(len(library.sources(catalog=catalog)['sources']), 4)
        self.assertEqual([s['id'] for s in library.sources(catalog=catalog, login='unknown')['sources']], ['legacy'])

    def test_browser_step_and_login_are_independent(self):
        result = library.sources(access='user-step', login='conditional')
        ids = {s['id'] for s in result['sources']}
        self.assertIn('fab', ids)
        self.assertIn('itch', ids)
        self.assertNotIn('mixamo', ids)
        self.assertTrue(all(s['download']['login'] == 'conditional' for s in result['sources']))
        self.assertEqual(library.sources(access='direct', login='required')['sources'], [])

    def test_pricing_is_independent_of_login_and_download_evidence(self):
        rows = [
            {'id': 'legacy', 'domain': 'example.org', 'kinds': ['3d']},
            {'id': 'free-account', 'domain': 'example.org', 'kinds': ['3d'],
             'pricing': {'model': 'free'}, 'download': {'mode': 'user-step', 'login': 'required'}},
            {'id': 'mixed-direct', 'domain': 'example.org', 'kinds': ['3d'],
             'pricing': {'model': 'mixed'}, 'download': {'mode': 'direct', 'login': 'none'},
             'verification': {'status': 'sample_download_passed', 'files': [{'url': 'https://example.org/a.zip'}]}},
            {'id': 'paid-account', 'domain': 'example.org', 'kinds': ['3d'],
             'pricing': {'model': 'paid'}, 'download': {'mode': 'user-step', 'login': 'required'}}
        ]
        catalog = Mock()
        catalog.read_text.return_value = json.dumps({'sources': rows})
        cases = [
            ({'pricing': 'unknown'}, ['legacy']),
            ({'pricing': 'free', 'login': 'required'}, ['free-account']),
            ({'pricing': 'mixed', 'access': 'direct'}, ['mixed-direct']),
            ({'pricing': 'paid', 'login': 'required'}, ['paid-account']),
            ({'pricing': 'free', 'access': 'direct'}, []),
            ({}, [row['id'] for row in rows]),
        ]
        for filters, expected in cases:
            with self.subTest(filters=filters):
                self.assertEqual([row['id'] for row in library.sources(catalog=catalog, **filters)['sources']], expected)
        with self.assertRaises(ValueError):
            library.sources(pricing='login-free')

    def test_catalogue_has_auditable_routes(self):
        rows = library.sources()['sources']
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        for row in rows:
            with self.subTest(source=row['id']):
                self.assertTrue(set(row['kinds']) <= set(library.KINDS))
                self.assertTrue(row['evidence_urls'])
                self.assertIn(row['pricing']['model'], library.PRICING)
                self.assertTrue(row['pricing']['summary'])
                self.assertTrue(row['pricing']['evidence_urls'])
                self.assertRegex(row['pricing']['checked_at'], r'^\d{4}-\d{2}-\d{2}$')
                self.assertTrue(row['download']['method'])
                self.assertTrue(row['download']['user_step'])
                self.assertRegex(row['verification']['checked_at'], r'^\d{4}-\d{2}-\d{2}$')
                if row['download']['mode'] == 'direct':
                    self.assertEqual(row['download']['login'], 'none')
                    self.assertEqual(row['verification']['status'], 'sample_download_passed')
                    self.assertTrue(row['verification']['files'])
                    for file in row['verification']['files']:
                        self.assertGreater(file['bytes'], 0)
                        self.assertRegex(file['sha256'], r'^[0-9a-f]{64}$')
                        self.assertTrue(file['url'].startswith('https://'))

    def test_cli_combines_filters_without_claiming_live_search(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = library.main(['sources', '--kind', 'vfx', '--access', 'direct', '--login', 'none', '--pricing', 'free', '--query', 'laser'])
        result = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(result['status'], 'search_plan')
        self.assertFalse(result['results_are_assets'])
        self.assertIn('effekseer', {s['id'] for s in result['sources']})
        for row in result['sources']:
            self.assertIn('vfx', row['kinds'])
            self.assertEqual(row['pricing']['model'], 'free')
            self.assertIn('laser', row['search_query'])
        with self.assertRaises(ValueError):
            library.sources(access='pretend-free')

    def test_requested_sources_are_unique_and_sketchfab_is_not_a_tested_download(self):
        rows = library.sources()['sources']
        ids = [row['id'] for row in rows]
        for source_id in ('kenney', 'quaternius', 'ambientcg', 'mixamo', 'sketchfab', 'polyhaven'):
            self.assertEqual(ids.count(source_id), 1)
        sketchfab = next(row for row in rows if row['id'] == 'sketchfab')
        self.assertEqual(sketchfab['download']['mode'], 'user-step')
        self.assertEqual(sketchfab['download']['login'], 'required')
        self.assertEqual(sketchfab['verification']['files'], [])
        self.assertNotEqual(sketchfab['verification']['status'], 'sample_download_passed')
        self.assertNotIn('sketchfab', {row['id'] for row in library.sources(access='direct')['sources']})


if __name__ == '__main__':
    unittest.main()

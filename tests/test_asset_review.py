"""Review lifecycle must not turn file acquisition or technical checks into quality approval."""
import hashlib
import http.client
import json
import os
import sys
import tempfile
import shutil
import uuid
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from workbench import asset_review as review, art_registry
import project_workbench
from adapters.assets import credential_store


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.root = (ROOT / 'dist' / ('review-test-' + uuid.uuid4().hex)).resolve()
        self.root.mkdir(parents=True)
        def cleanup():
            assert self.root.is_relative_to((ROOT / 'dist').resolve())
            shutil.rmtree(self.root)
        self.addCleanup(cleanup)
        (self.root / 'attack.fbx').write_bytes(b'actual fixture v1')
        (self.root / 'skeleton.fbx').write_bytes(b'fixture dependency')
        (self.root / 'review.md').write_text('Fixture run observation, not a real game approval.', encoding='utf-8')
        (self.root / 'shot.png').write_bytes(b'fixture image')

    def mutate(self, action, **kw):
        return review.mutate(self.root, {'action': action, 'revision': review.load(self.root)[1], **kw})

    def create(self, **kw):
        values = dict(title='attack clip A', kind='animation', role='boss', use='clip A: swipe only', version='v1',
                      files=['attack.fbx', 'skeleton.fbx'], sourceUrl='https://example.com/asset', license='test fixture only',
                      environment='fixture engine / encounter v1', testPlan='Observe preview and gameplay transitions')
        return self.mutate('create', record={**values, **kw})['selectedId']

    def check(self, row_id, gate, **kw):
        return self.mutate('check', id=row_id, gate=gate, status='pass', method='Fixture observation', reviewer='test runner',
                           conclusion='Fixture scope only', evidence=[{'type': 'run_report', 'path': 'review.md'}], **kw)

    def qualified(self):
        row_id = self.create()
        self.mutate('start', id=row_id)
        for gate in review.GATES:
            self.check(row_id, gate)
        self.mutate('qualify', id=row_id)
        return row_id

    def test_source_only_candidate_and_download_do_not_qualify(self):
        row_id = self.create(files=[])
        self.assertEqual(review.snapshot(self.root)['records'][0]['effectiveStage'], 'candidate')
        with self.assertRaises(review.ReviewError):
            self.mutate('start', id=row_id)
        self.mutate('edit', id=row_id, record={'files': ['attack.fbx']})
        self.assertEqual(review.snapshot(self.root)['records'][0]['effectiveStage'], 'candidate')
        with self.assertRaises(review.ReviewError):
            self.mutate('qualify', id=row_id)

    def test_failure_and_missing_gates_block_promotion(self):
        row_id = self.create()
        self.mutate('start', id=row_id)
        self.mutate('check', id=row_id, gate='external', status='fail', method='Inspect wrist', reviewer='tester', conclusion='Clipping')
        self.check(row_id, 'engine')
        with self.assertRaises(review.ReviewError):
            self.mutate('qualify', id=row_id)
        row = review.snapshot(self.root)['records'][0]
        self.assertEqual(row['effectiveStage'], 'testing')
        self.assertEqual(row['checkResults']['external']['status'], 'fail')
        self.check(row_id, 'external')
        row = review.snapshot(self.root)['records'][0]
        self.assertEqual(row['checkHistory'][0]['status'], 'fail')
        self.assertEqual(row['checkResults']['external']['status'], 'pass')

    def test_dynamic_screenshot_cannot_replace_runtime_observation(self):
        row_id = self.create()
        self.mutate('start', id=row_id)
        for evidence in ([], [{'type': 'image', 'path': 'shot.png'}], [{'type': 'video', 'path': 'shot.png'}]):
            with self.assertRaises(review.ReviewError):
                self.mutate('check', id=row_id, gate='game', status='pass', method='Observe', reviewer='tester', conclusion='Okay', evidence=evidence)
        for gate in ('source', 'engine', 'game'):
            with self.assertRaises(review.ReviewError):
                self.mutate('check', id=row_id, gate=gate, status='na', method='Skip', reviewer='tester', conclusion='Skip')

    def test_valid_external_na_still_requires_game_checks(self):
        row_id = self.create()
        self.mutate('start', id=row_id)
        self.mutate('check', id=row_id, gate='external', status='na', method='Native engine asset inspected in engine', reviewer='tester', conclusion='Engine is the source tool')
        for gate in ('source', 'engine', 'game'):
            self.check(row_id, gate)
        self.mutate('qualify', id=row_id)
        self.assertEqual(review.snapshot(self.root)['records'][0]['effectiveStage'], 'qualified')

    def test_dependency_and_evidence_changes_invalidate_qualification(self):
        row_id = self.qualified()
        self.assertEqual(review.snapshot(self.root)['records'][0]['usage']['status'], 'unverified')
        (self.root / 'skeleton.fbx').write_bytes(b'changed rig')
        row = review.snapshot(self.root)['records'][0]
        self.assertEqual(row['effectiveStage'], 'testing')
        self.assertEqual(row['staleFiles'], ['skeleton.fbx'])
        with self.assertRaises(review.ReviewError):
            self.check(row_id, 'external')
        (self.root / 'skeleton.fbx').write_bytes(b'fixture dependency')
        (self.root / 'review.md').write_text('revised report')
        self.assertEqual(review.snapshot(self.root)['records'][0]['checkResults']['game']['status'], 'stale')

    def test_new_version_and_other_clip_have_independent_results(self):
        old = self.qualified()
        new = self.mutate('new_version', id=old, record={'version': 'v2'})['selectedId']
        other = self.create(title='clip B', use='clip B: slam')
        rows = {r['id']: r for r in review.snapshot(self.root)['records']}
        self.assertEqual(rows[old]['effectiveStage'], 'qualified')
        self.assertEqual(rows[new]['effectiveStage'], 'candidate')
        self.assertEqual(rows[other]['checks'], {})
        self.assertEqual(rows[new]['supersedes'], old)
        with self.assertRaises(review.ReviewError):
            self.mutate('edit', id=old, record={'use': 'entire package'})

    def test_conflict_archive_and_failed_save_do_not_overwrite(self):
        revision = review.load(self.root)[1]
        row_id = self.create()
        before = review.registry_path(self.root).read_bytes()
        with self.assertRaises(art_registry.RevisionConflict):
            review.mutate(self.root, {'revision': revision, 'action': 'create', 'record': {}})
        self.assertEqual(review.registry_path(self.root).read_bytes(), before)
        self.mutate('archive', id=row_id, archived=True, reason='Outside current design')
        with self.assertRaises(review.ReviewError):
            self.mutate('start', id=row_id)
        self.mutate('archive', id=row_id, archived=False, reason='Reconsider')
        self.mutate('start', id=row_id)

    def test_path_and_source_guards(self):
        for path in ('../outside.md', '/absolute.md', 'C:/x.md', 'a/../../x', '.openaigame/asset-providers.json', 'a.txt:secret', 'a\\b', 'dir./file'):
            with self.assertRaises(review.ReviewError, msg=path):
                review.safe_path(self.root, path)
        for url in ('javascript:alert(1)', 'file:///secret', 'https://user:password@example.com'):
            with self.assertRaises(review.ReviewError):
                self.create(sourceUrl=url)

    def test_corrupt_registry_does_not_reset_project(self):
        self.create()
        path = review.registry_path(self.root)
        path.write_text('{broken')
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.root)
        self.assertEqual(path.read_text(), '{broken')

    def test_game_usage_independent_and_version_checked(self):
        row_id = self.create()
        self.mutate('start', id=row_id)
        folder = self.root / '.asset-browser'
        folder.mkdir()
        (folder / 'usage.json').write_text(json.dumps({'version': 1, 'dependencies': {'attack.fbx': review.digest(self.root/'attack.fbx')},
                                                     'assets': [{'path': 'attack.fbx', 'roles': ['Boss swipe']}]}))
        row = review.snapshot(self.root)['records'][0]
        self.assertEqual(row['effectiveStage'], 'testing')
        self.assertEqual(row['usage']['status'], 'used')
        (self.root/'attack.fbx').write_bytes(b'new file')
        self.assertEqual(review.snapshot(self.root)['records'][0]['usage']['status'], 'unverified')

    def test_http_auth_cas_and_evidence(self):
        with patch.object(credential_store, 'store_path', return_value=self.root/'profile.json'):
            server = project_workbench.WorkbenchServer(self.root, view='review')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(path, body=None, headers=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                head = {'Content-Type': 'application/json', 'Origin': server.origin, **(headers or {})}
                connection.request('GET' if body is None else 'POST', path, json.dumps(body) if body is not None else None, head)
                response = connection.getresponse()
                result = (response.status, dict(response.getheaders()), response.read())
                connection.close()
                return result
            try:
                self.assertTrue(server.launch_url.endswith('#assets'))
                self.assertEqual(request('/api/asset-review')[0], 401)
                _, headers, _ = request('/session', {}, {'X-Workbench-Connect': '1'})
                auth = {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-CSRF-Token': server.csrf}
                self.assertEqual(request('/api/asset-review', {}, {**auth, 'Origin': 'https://foreign.test'})[0], 403)
                self.assertEqual(request('/api/asset-review?project=other', headers=auth)[0], 404)
                row_id = self.qualified()
                self.assertEqual(request('/api/asset-review', {}, auth)[0], 409)
                status, headers, _ = request(f'/api/asset-review-evidence?id={row_id}&gate=game&index=0', headers=auth)
                self.assertEqual(status, 200)
                self.assertIn('sandbox', headers['Content-Security-Policy'])
                self.assertEqual(request('/api/asset-review-evidence?id=missing&gate=game&index=0', headers=auth)[0], 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()

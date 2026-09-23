"""Cloud contract/recovery and acquisition checks; no paid or live network calls."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_library as library
import asset_workflow as workflow
import package_skills
from adapters.assets import api_common, api_worker, http_io, hunyuan_api, tripo, polyhaven
from adapters.assets import credential_store
from adapters.assets import generation_approval
from adapters.assets.archive_io import extract_zip


class AssetAPITests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        isolated_store = patch.object(credential_store, 'store_path', return_value=self.root / 'profile/credentials.json')
        isolated_store.start(); self.addCleanup(isolated_store.stop)
        # These tests isolate generation I/O. Real consent enforcement is exercised in test_generation_approval.
        for context in (patch.object(generation_approval, 'identity', return_value='f' * 64),
                        patch.object(generation_approval, 'for_job', return_value='f' * 64),
                        patch.object(generation_approval, 'require')):
            context.start(); self.addCleanup(context.stop)

    def test_credentials_never_enter_doctor_or_command(self):
        with patch.dict(os.environ, {'TRIPO_API_KEY': 'private-test-value'}, clear=True):
            report = api_common.doctor('tripo', {'mode': 'api'})
            self.assertTrue(report['ready_to_attempt'])
            command = tripo.command({'mode': 'api'}, 'r', 'o', 's')
            self.assertNotIn('private-test-value', json.dumps([report, command]))
        for settings in ({'mode': 'api', 'api_key': 'bad'}, {'mode': 'api', 'poll_seconds': 0}):
            with self.assertRaises(ValueError):
                workflow.new_job(self.root, 'tripo', {'parameters': {'prompt': 'crate'}}, settings)
        self.assertFalse((self.root / '.openaigame').exists())

    def test_tripo_text_upload_query_and_errors(self):
        with patch.dict(os.environ, {'TRIPO_API_KEY': 'fixture'}):
            client = tripo.Client({})
        with patch.object(http_io, 'json_request', return_value={'code': 0, 'data': {'task_id': 'task-1'}}) as call:
            self.assertEqual(client.submit({'parameters': {'prompt': 'crate'}, 'inputs': []}), 'task-1')
            self.assertEqual(call.call_args.args[1]['type'], 'text_to_model')
            self.assertEqual(call.call_args.args[2]['Authorization'], 'Bearer fixture')
        image = self.root / 'input.png'; image.write_bytes(b'fixture')
        with patch.object(client, 'call', side_effect=[{'image_token': 'upload-token'}, {'task_id': 'task-2'}]) as call:
            client.submit({'parameters': {}, 'inputs': [{'snapshot': str(image)}]})
            self.assertEqual(call.call_args.args[1]['file'], {'type': 'png', 'file_token': 'upload-token'})
        with patch.object(client, 'call', return_value={'task_id': 'task-2', 'status': 'success', 'output': {'model': 'https://example.com/model.glb'}}):
            self.assertTrue(client.query('task-2')['done'])
            with self.assertRaises(ValueError): client.query('wrong-id')
        with patch.object(http_io, 'json_request', return_value={'code': 2000, 'data': {}}):
            with self.assertRaises(ValueError): client.query('task-2')

    def test_hunyuan_auth_body_and_status(self):
        env = {'TENCENTCLOUD_SECRET_ID': 'fixture-id', 'TENCENTCLOUD_SECRET_KEY': 'fixture-secret', 'HUNYUAN3D_API_KEY': 'fixture-key'}
        with patch.dict(os.environ, env):
            tc = hunyuan_api.Client({'region': 'ap-guangzhou'})
            key = hunyuan_api.Client({'auth': 'api_key'})
        with patch.object(http_io, 'json_bytes', return_value={'Response': {'JobId': '123'}}) as call:
            self.assertEqual(tc.submit({'parameters': {'Prompt': '木箱'}, 'inputs': []}), '123')
            self.assertEqual(json.loads(call.call_args.args[1])['Prompt'], '木箱')
            headers = call.call_args.args[2]
            self.assertEqual(headers['X-TC-Action'], 'SubmitHunyuanTo3DProJob')
            self.assertTrue(headers['Authorization'].startswith('TC3-HMAC-SHA256 '))
            self.assertNotIn('fixture-secret', str(headers))
        image = self.root / 'image.png'; image.write_bytes(b'abc')
        with patch.object(http_io, 'json_request', return_value={'JobId': '124'}) as call:
            key.submit({'parameters': {}, 'inputs': [{'snapshot': str(image)}]})
            self.assertEqual(call.call_args.args[2]['Authorization'], 'fixture-key')
            self.assertEqual(call.call_args.args[1]['ImageUrl']['Url'], 'data:image/png;base64,YWJj')
        for status, done, pending in [('WAIT', False, True), ('RUN', False, True), ('FAIL', False, False), ('DONE', True, False)]:
            with patch.object(tc, 'call', return_value={'Status': status, 'ResultFile3Ds': [{'Type': 'GLB', 'Url': 'https://example.com/a.glb'}]}):
                report = tc.query('123')
                self.assertEqual((report['done'], report['pending']), (done, pending))

    def test_worker_checkpoints_before_download_and_resume_never_submits(self):
        output = self.root / 'out'; output.mkdir()
        result = self.root / 'result.json'
        client = Mock()
        client.submit.return_value = 'remote-1'
        client.query.return_value = {'status': 'success', 'done': True, 'pending': False,
                                     'files': [{'label': 'model', 'url': 'https://example.com/a.glb'}], 'credit_consumed': 1}
        request = {'parameters': {'prompt': 'crate'}, 'inputs': [], '_approval': {'project': str(self.root), 'job_id': 'fixture'}}
        with patch.object(tripo, 'Client', return_value=client), patch.object(http_io, 'download', side_effect=ValueError('offline')):
            with self.assertRaises(ValueError): api_worker.run('tripo', {'mode': 'api'}, request, output, result)
        self.assertEqual(json.loads(result.with_name('remote.json').read_text())['provider_job_id'], 'remote-1')
        client.reset_mock()
        def download(url, target, cap): target.write_bytes(b'model fixture')
        with patch.object(tripo, 'Client', return_value=client), patch.object(http_io, 'download', side_effect=download):
            api_worker.run('tripo', {'mode': 'api'}, {**request, 'provider_job_id': 'remote-1'}, output, result)
        client.submit.assert_not_called()
        self.assertEqual(json.loads(result.read_text())['provider_job_id'], 'remote-1')

    def test_subprocess_failure_harvests_id_and_resumes_same_job(self):
        job = workflow.new_job(self.root, 'tripo', {'parameters': {'prompt': 'crate'}}, {'mode': 'api'})
        def command(settings, request, output, result):
            return [sys.executable, '-B', str(ROOT / 'tests/fixtures/cloud_asset_provider.py'), str(request), str(output), str(result)]
        with patch.object(tripo, 'command', side_effect=command):
            failed = workflow.execute_job(self.root, job['job_id'], 10)
            self.assertEqual(failed['status'], 'failed')
            self.assertEqual(failed['provider_job_id'], 'fixture-remote-1')
            with self.assertRaises(ValueError): workflow.execute_job(self.root, job['job_id'], 10, True, 'different-id')
            succeeded = workflow.execute_job(self.root, job['job_id'], 10, True)
            self.assertEqual(succeeded['status'], 'succeeded')
            self.assertEqual(len(succeeded['attempts']), 2)
            with self.assertRaises(ValueError): workflow.execute_job(self.root, job['job_id'], 10, True)
        metadata = self.metadata()
        record = library.acquire(self.root, metadata, succeeded)
        self.assertEqual(record['generation']['provider_job_id'], 'fixture-remote-1')
        self.assertEqual(record['files'][0]['path'], succeeded['artifacts'][0]['path'])
        self.assertEqual(library.check_files(self.root, record), [])

    def metadata(self):
        return {'title': 'Crate', 'kind': '3d', 'source_url': 'https://example.com/crate',
                'author': 'Fixture author', 'license': {'name': 'unknown', 'status': 'unverified'}}

    def test_api_timeout_retains_remote_id_and_retry_requires_new_generation(self):
        job = workflow.new_job(self.root, 'tripo', {'parameters': {'prompt': 'timeout'}}, {'mode': 'api'})
        def command(settings, request, output, result):
            return [sys.executable, '-B', str(ROOT / 'tests/fixtures/cloud_asset_provider.py'), str(request), str(output), str(result)]
        with patch.object(tripo, 'command', side_effect=command):
            failed = workflow.execute_job(self.root, job['job_id'], 1)
        self.assertEqual(failed['attempts'][0]['stop'], 'timeout')
        self.assertEqual(failed['provider_job_id'], 'fixture-remote-1')
        with contextlib.redirect_stdout(io.StringIO()):
            code = workflow.main(['--project', str(self.root), 'retry', '--job', job['job_id']])
        self.assertEqual(code, 2)
        self.assertEqual(len(list(self.root.glob('.openaigame/asset-jobs/*/job.json'))), 1)

    def test_broken_archive_keeps_failed_acquisition_record(self):
        (self.root / 'broken.zip').write_bytes(b'not a zip')
        request = {**self.metadata(), 'files': [{'name': 'broken.zip', 'local': 'broken.zip', 'extract': True}]}
        with self.assertRaises(zipfile.BadZipFile): library.acquire(self.root, request)
        self.assertEqual(library.records(self.root)[0]['status'], 'failed')

    def test_local_acquisition_versions_evidence_and_tampering(self):
        (self.root / 'model.glb').write_bytes(b'first model')
        evidence = self.root / 'license.txt'; evidence.write_text('fixture permission')
        request = {**self.metadata(), 'license': {'name': 'fixture', 'status': 'reviewed', 'evidence_files': ['license.txt']},
                   'files': [{'name': 'models/model.glb', 'local': 'model.glb'}]}
        first = library.acquire(self.root, request)
        self.assertEqual(library.check_files(self.root, first), [])
        self.assertTrue(library.acquire(self.root, request)['reused'])
        evidence.write_text('different terms')
        second = library.acquire(self.root, request)
        self.assertNotEqual(first['asset_id'], second['asset_id'])
        (self.root / first['files'][0]['path']).write_bytes(b'changed')
        self.assertTrue(library.check_files(self.root, first))
        library.index(self.root, 'production/assets.md')
        with self.assertRaises(ValueError): library.index(self.root, 'production/assets.md')

    def test_zip_dependencies_and_reject_traversal_code_collisions(self):
        archive = self.root / 'model.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('model.gltf', '{}'); z.writestr('textures/base.png', b'fixture')
        paths = extract_zip(archive, self.root / 'good')
        self.assertEqual({p.relative_to(self.root / 'good').as_posix() for p in paths}, {'model.gltf', 'textures/base.png'})
        for names in (['../escape.glb'], ['run.py'], ['A.glb', 'a.glb'], ['C:/evil.glb']):
            with zipfile.ZipFile(archive, 'w') as z:
                for name in names: z.writestr(name, b'fixture')
            with self.assertRaises(ValueError): extract_zip(archive, self.root / 'bad')
            self.assertFalse((self.root / 'bad').exists())

    def test_download_boundaries_and_preserves_foreign_partial(self):
        target = self.root / 'model.glb'
        def response(data, headers=None):
            stream = io.BytesIO(data); stream.headers = headers or {}
            return stream
        with patch.object(http_io, 'open_url', return_value=response(b'model')):
            actual = http_io.download('https://example.com/a', target, 10)
            self.assertEqual(actual['sha256'], hashlib.sha256(b'model').hexdigest())
        target.unlink()
        for data, headers, cap, expected in [(b'html', {'Content-Type': 'text/html'}, 10, None), (b'long', {}, 2, None), (b'a', {}, 10, 'bad')]:
            with patch.object(http_io, 'open_url', return_value=response(data, headers)):
                with self.assertRaises(ValueError): http_io.download('https://example.com/a', target, cap, expected)
            self.assertFalse(target.exists())
        partial = target.with_name(target.name + '.part'); partial.write_bytes(b'prior')
        with patch.object(http_io, 'open_url', return_value=response(b'new')):
            with self.assertRaises(FileExistsError): http_io.download('https://example.com/a', target)
        self.assertEqual(partial.read_bytes(), b'prior')
        with patch.object(http_io.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError): http_io.public_url('https://example.com/model')

    def test_download_registration_and_failed_state(self):
        request = {**self.metadata(), 'files': [{'name': 'crate.glb', 'url': 'https://example.com/model.glb?signature=private'}]}
        def download(url, target, *args): target.write_bytes(b'fixture')
        with patch.object(http_io, 'download', side_effect=download):
            record = library.acquire(self.root, request)
        self.assertNotIn('signature=private', json.dumps(record))
        self.assertEqual(record['origins'][0]['url_without_query'], 'https://example.com/model.glb')
        request['title'] = 'another'
        with patch.object(http_io, 'download', side_effect=ValueError('offline')):
            with self.assertRaises(ValueError): library.acquire(self.root, request)
        self.assertIn('failed', [r['status'] for r in library.records(self.root)])

    def test_catalogue_is_plan_and_polyhaven_is_actual_search(self):
        self.assertFalse(library.sources('animation')['results_are_assets'])
        data = {'wood_box': {'name': 'Wood Box', 'type': 2, 'tags': ['wood', 'crate']}, 'wood_floor': {'name': 'Wood Floor', 'type': 1}}
        with patch.object(http_io, 'json_request', return_value=data):
            found = polyhaven.search('wood', '3d')
            self.assertEqual(found['total_matches'], 1)
            self.assertEqual(found['assets'][0]['source'], 'Poly Haven')
        with self.assertRaises(ValueError): polyhaven.files('../escape')

    def test_packaged_entrypoints_run_outside_repository(self):
        bundle = package_skills.package(self.root / 'bundle')
        runtime = bundle / 'game-preproduction/runtime'
        for script, args in [('tools/asset_library.py', ['sources', '--kind', 'vfx']),
                             ('adapters/assets/api_worker.py', ['--help']),
                             ('tools/asset_workflow.py', ['--help'])]:
            result = subprocess.run([sys.executable, '-B', str(runtime / script), *args], cwd=self.root,
                env={**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252'}, capture_output=True)
            self.assertEqual(result.returncode, 0, (script, result.stdout, result.stderr))
            if script == 'tools/asset_library.py':
                self.assertEqual(json.loads(result.stdout.decode('utf-8'))['status'], 'search_plan')


if __name__ == '__main__':
    unittest.main()

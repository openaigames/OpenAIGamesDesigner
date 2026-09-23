"""Consent must precede submission, bind request/account and be consumed once."""
import http.client
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_workflow as workflow
import settings_server
from adapters.assets import api_worker, api_common, credential_store, generation_approval as approval, tripo


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        for context in (patch.object(credential_store, 'store_path', return_value=self.root / 'profile/credentials.json'),
                        patch.dict(os.environ, {'TRIPO_API_KEY': 'synthetic-consent-fixture'})):
            context.start(); self.addCleanup(context.stop)
        self.project = self.root / 'project'; self.project.mkdir()
        self.job = workflow.new_job(self.project, 'tripo', {'parameters': {'prompt': 'crate'}}, {'mode': 'api'})
        self.fingerprint = approval.for_job(self.project, self.job)

    def test_unapproved_run_does_not_launch_worker_or_modify_job(self):
        with patch.object(workflow.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, 'User approval required'):
                workflow.execute_job(self.project, self.job['job_id'], 10)
        process.assert_not_called()
        _, current = workflow.read_job(self.project, self.job['job_id'])
        self.assertEqual(current['status'], 'queued')
        self.assertEqual(current['attempts'], [])
        self.assertFalse(list(self.project.glob('.openaigame/asset-jobs/*/attempt-*')))

    def test_one_use_expiry_and_tamper(self):
        approval.approve(self.fingerprint)
        approval.require(self.fingerprint)
        approval.require(self.fingerprint, consume=True)
        with self.assertRaises(ValueError): approval.require(self.fingerprint, consume=True)
        with self.assertRaises(ValueError): approval.approve(self.fingerprint)
        another = 'b' * 64
        approval.approve(another)
        with patch.object(approval.time, 'time', return_value=10**12):
            with self.assertRaises(ValueError): approval.require(another)
        approval._path(another).write_bytes(b'corrupt fixture')
        with self.assertRaises(ValueError): approval.require(another)

    def test_request_project_job_and_account_changes_invalidate_approval(self):
        approval.approve(self.fingerprint)
        changed = json.loads(json.dumps(self.job))
        changed['request']['parameters']['prompt'] = 'another asset'
        fingerprints = [approval.for_job(self.project, changed), approval.for_job(self.root, self.job)]
        changed['job_id'] = 'AnotherJob'
        fingerprints.append(approval.for_job(self.project, changed))
        with patch.dict(os.environ, {'TRIPO_API_KEY': 'another-account-fixture'}):
            fingerprints.append(approval.for_job(self.project, self.job))
        for fingerprint in fingerprints:
            self.assertNotEqual(fingerprint, self.fingerprint)
            with self.assertRaises(ValueError): approval.require(fingerprint)

    def test_worker_consumes_before_submit_and_blocks_replay(self):
        request = {**self.job['request'], '_approval': {'project': str(self.project), 'job_id': self.job['job_id']}}
        output = self.root / 'output'; output.mkdir()
        client = Mock()
        client.submit.side_effect = ValueError('simulated lost response')
        with patch.object(tripo, 'Client', return_value=client):
            with self.assertRaises(ValueError): api_worker.run('tripo', self.job['settings'], request, output, self.root / 'result.json')
            client.submit.assert_not_called()
            approval.approve(self.fingerprint)
            with self.assertRaises(ValueError): api_worker.run('tripo', self.job['settings'], request, output, self.root / 'result.json')
            self.assertEqual(client.submit.call_count, 1)
            with self.assertRaises(ValueError): api_worker.run('tripo', self.job['settings'], request, output, self.root / 'result.json')
            self.assertEqual(client.submit.call_count, 1)

    def test_resume_only_queries_without_new_authorization(self):
        output = self.root / 'output'; output.mkdir()
        client = Mock()
        client.query.return_value = {'status': 'failed', 'done': False, 'pending': False}
        with patch.object(tripo, 'Client', return_value=client):
            with self.assertRaises(ValueError):
                api_worker.run('tripo', self.job['settings'], {**self.job['request'], 'provider_job_id': 'remote-existing'}, output, self.root / 'result.json')
        client.submit.assert_not_called()
        client.query.assert_called_once_with('remote-existing')

    def test_changed_image_is_rejected_before_upload(self):
        image = self.root / 'image.png'; image.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            api_common.image_input({'inputs': [{'snapshot': str(image), 'sha256': '0' * 64}]}, 100)

    def test_storage_denial_is_distinct_and_request_remains_visible(self):
        with settings_server.SettingsServer(project=self.project, job_id=self.job['job_id']) as server:
            with patch.object(approval, '_locked', side_effect=PermissionError('private path')):
                state = server.state()['approval']
            self.assertEqual(state.get('error_code'), 'approval_storage_unavailable')
            self.assertEqual(state['parameters'], {'prompt': 'crate'})
            self.assertNotIn('fingerprint', state)
            self.assertNotIn('private path', json.dumps(state))
            recovered = server.state()['approval']
            self.assertEqual(recovered['fingerprint'], self.fingerprint)
            self.assertFalse(recovered['approved'])

    def test_unwritable_store_fails_before_publishing_launch_url(self):
        ready = self.root / 'ready.json'
        output = io.StringIO()
        args = ['settings_server.py', '--no-open', '--project', str(self.project),
                '--approve-job', self.job['job_id'], '--ready-file', str(ready)]
        with patch.object(sys, 'argv', args), patch.object(approval, '_locked', side_effect=PermissionError('private path')), \
                patch.object(settings_server.SettingsServer, 'serve_forever') as serve, \
                patch.object(settings_server.webbrowser, 'open') as browser, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = settings_server.main()
        self.assertEqual(result, 2)
        self.assertFalse(ready.exists())
        serve.assert_not_called(); browser.assert_not_called()
        self.assertNotIn('http://', output.getvalue())
        self.assertNotIn('private path', output.getvalue())
        self.assertIn('授权记录', output.getvalue())

    def test_storage_probe_does_not_authorize_or_replace_receipts(self):
        approval.check_storage()
        self.assertFalse(approval._path(self.fingerprint).exists())
        with self.assertRaises(ValueError): approval.require(self.fingerprint)
        approval.approve(self.fingerprint)
        before = approval._path(self.fingerprint).read_bytes()
        approval.check_storage()
        self.assertEqual(approval._path(self.fingerprint).read_bytes(), before)
        self.assertEqual(list(approval._path(self.fingerprint).parent.glob('*.tmp')), [])

    def test_storage_probe_checks_receipt_directory_as_well_as_lock(self):
        with patch.object(approval.tempfile, 'TemporaryFile', side_effect=PermissionError('no receipt writes')):
            with self.assertRaises(PermissionError): approval.check_storage()

    def test_confirmation_endpoint_requires_charge_ack_and_displayed_fingerprint(self):
        server = settings_server.SettingsServer(project=self.project, job_id=self.job['job_id'])
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def stop(): server.shutdown(); server.server_close(); thread.join(timeout=3)
        self.addCleanup(stop)
        def post(path, body, headers):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            try:
                connection.request('POST', path, json.dumps(body), headers)
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), json.loads(response.read())
            finally: connection.close()
        headers = {'Origin': server.origin, 'Content-Type': 'application/json', 'X-Setup-Token': server.launch_token}
        status, response, _ = post('/session', {}, headers)
        self.assertEqual(status, 200)
        headers.update({'Cookie': response['Set-Cookie'].split(';')[0], 'X-CSRF-Token': server.csrf})
        body = {'fingerprint': self.fingerprint, 'accept_charge': False}
        self.assertEqual(post('/api/approve', body, headers)[0], 400)
        body['accept_charge'] = True
        self.assertEqual(post('/api/approve', {**body, 'fingerprint': 'b' * 64}, headers)[0], 409)
        with patch.object(approval, '_locked', side_effect=PermissionError('private path')):
            status, _, blocked = post('/api/approve', body, headers)
        self.assertEqual(status, 409)
        self.assertEqual(blocked.get('error_code'), 'approval_storage_unavailable')
        self.assertFalse(approval._path(self.fingerprint).exists())
        with patch.object(approval, 'approve', side_effect=PermissionError('late write failure')):
            status, _, blocked = post('/api/approve', body, headers)
        self.assertEqual(status, 409)
        self.assertEqual(blocked.get('error_code'), 'approval_storage_unavailable')
        status, _, response = post('/api/approve', body, headers)
        self.assertEqual(status, 200, response)
        self.assertTrue(response['approval']['approved'])
        self.assertNotIn('synthetic-consent-fixture', json.dumps(response))
        approval.require(self.fingerprint)


if __name__ == '__main__': unittest.main()

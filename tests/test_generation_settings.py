"""Offline service settings and request checks using synthetic credentials."""
import json
import os
from pathlib import Path
import sys
import shutil
import uuid
from contextlib import contextmanager
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from adapters.assets import generation_capabilities as caps, service_diagnostics as diagnostics
from adapters.assets import tripo_inputs, hunyuan_inputs, api_common, credential_store, model_prompt_policy
from adapters.assets import api_worker, tripo
from adapters.assets.api_errors import TaskResultError


@contextmanager
def test_directory():
    parent = (ROOT / 'dist').resolve()
    directory = parent / ('settings-test-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    try:
        yield directory
    finally:
        if directory.resolve().parent != parent:
            raise ValueError('Test directory escaped its workspace')
        shutil.rmtree(directory)


class GenerationSettingsTests(unittest.TestCase):
    def test_modes_reject_incompatible_inputs(self):
        requests = [
            ('tripo', {'parameters': {'type': 'multiview_to_model'}, 'inputs': [{'view': 'front'}]}),
            ('tripo', {'parameters': {'type': 'image_to_model', 'prompt': 'keep me'}, 'inputs': [{}]}),
            ('tripo', {'parameters': {'type': 'generate_multiview_image', 'model_version': 'unused'}, 'inputs': [{}]}),
            ('hunyuan3d', {'parameters': {'Model': '3.1', 'GenerateType': 'Sketch'}, 'inputs': [{'path': 'x', 'view': 'front'}]}),
            ('hunyuan3d', {'parameters': {'Model': '3.0', 'GenerateType': 'Sketch', 'Prompt': 'x'}, 'inputs': []}),
        ]
        for provider, request in requests:
            with self.subTest(provider=provider, request=request):
                with self.assertRaises(ValueError):
                    (tripo_inputs if provider == 'tripo' else hunyuan_inputs).validate(request)

    def test_image_output_and_model_output_have_different_addresses(self):
        a = caps.describe('tripo', {'parameters': {'type': 'generate_multiview_image'}, 'inputs': [{}]})
        b = caps.describe('tripo', {'parameters': {'type': 'multiview_to_model'}, 'inputs': [{}, {}]})
        self.assertEqual(a['output'], 'images')
        self.assertEqual(b['output'], 'model')
        self.assertNotEqual(a['submit_url'], b['submit_url'])
        self.assertFalse(a['prompt_with_images'])

    def test_prompt_policy_matches_allowed_joint_input(self):
        request = {'parameters': {'Model': '3.0', 'GenerateType': 'Sketch', 'Prompt': 'sleeves'},
                   'inputs': [{'path': 'front.png', 'view': 'front'}]}
        with patch.object(model_prompt_policy, 'policy', return_value={'require_3d_prompt': True}):
            result = model_prompt_policy.assess('hunyuan3d', request, {'mode': 'api'})
            self.assertFalse(result['blocked'])
            hunyuan_inputs.validate(request)
            request['parameters']['GenerateType'] = 'Normal'
            self.assertTrue(model_prompt_policy.assess('hunyuan3d', request, {'mode': 'api'})['blocked'])
            with self.assertRaises(ValueError):
                hunyuan_inputs.validate(request)

    def test_saved_settings_do_not_disclose_keys_or_contact_service(self):
        with test_directory() as tmp:
            root = Path(tmp)
            (root / '.openaigame').mkdir()
            (root / '.openaigame/asset-providers.json').write_text(json.dumps({
                'hunyuan3d': {'mode': 'api', 'auth': 'tc3', 'region': 'test-region',
                             'secret_id_env': 'TEST_ACCOUNT', 'secret_key_env': 'TEST_SECRET'}}))
            with patch.dict(os.environ, {'TEST_ACCOUNT': 'private-id', 'TEST_SECRET': 'private-key'}, clear=True), \
                 patch.object(credential_store, 'get', return_value='saved-secret'), \
                 patch('adapters.assets.http_io.json_request', side_effect=AssertionError('Unexpected network')):
                report = diagnostics.configuration(root, 'hunyuan3d')
            self.assertEqual(report['configuration_source'], 'project')
            self.assertEqual({x['source'] for x in report['credentials']}, {'environment'})
            self.assertIn('TC3', report['connection']['authentication'])
            self.assertFalse(report['network_checked'])
            text = json.dumps(report)
            for secret in ('private-id', 'private-key', 'saved-secret'):
                self.assertNotIn(secret, text)

    def test_local_default_uses_saved_key_and_key_api(self):
        with test_directory() as tmp, patch.dict(os.environ, {}, clear=True), \
             patch.object(credential_store, 'default_settings', return_value={'mode': 'api', 'auth': 'api_key'}), \
             patch.object(credential_store, 'get', return_value='secret-must-stay-private'):
            result = diagnostics.configuration(Path(tmp), 'hunyuan3d')
        self.assertEqual(result['configuration_source'], 'local_default')
        self.assertEqual(result['credentials'][0]['source'], 'local_store')
        self.assertEqual(result['connection']['authentication'], 'API Key')
        self.assertNotEqual(result['connection']['key_page'], result['connection']['submit_url'])

    def test_failures_are_distinguished_without_unsafe_messages(self):
        samples = [({'http_status': 401}, 'authentication'), ({'http_status': 403}, 'permission'),
                   ({'code': 'insufficient_quota'}, 'quota'), ({'http_status': 400}, 'parameters'),
                   ({'http_status': 429}, 'rate_limit'), ({'http_status': 503}, 'service'),
                   ({'kind': 'remote_task_failed'}, 'task'), ({'kind': 'output_invalid'}, 'output'),
                   ({'code': 'UnknownError'}, 'unknown')]
        for record, expected in samples:
            record.update(message='private prompt and key', body='private response', request_id='unsafe-private-value')
            result = diagnostics.explain(record, 'real-task-123')
            self.assertEqual(result['category'], expected)
            self.assertEqual(result['remote_id'], 'real-task-123')
            self.assertFalse(result['automatic_resubmit'])
            self.assertNotIn('private', json.dumps(result))

    def test_unknown_submission_never_recommends_auto_retry(self):
        result = diagnostics.explain({})
        self.assertIsNone(result['remote_id'])
        self.assertFalse(result['automatic_resubmit'])
        self.assertIn('控制台', result['next_step'])

    def test_failure_reads_current_attempt_only(self):
        with test_directory() as tmp:
            root = Path(tmp)
            folder = root / '.openaigame/asset-jobs/Aexample/attempt-2'
            folder.mkdir(parents=True)
            (folder / 'diagnostic.json').write_text(json.dumps({'kind': 'output_invalid'}))
            job = {'job_id': 'Aexample', 'attempts': [{}, {}], 'status': 'failed', 'provider_job_id': 'known-task'}
            result = diagnostics.job_failure(root, job)
            self.assertEqual(result['category'], 'output')
            self.assertEqual(result['remote_id'], 'known-task')
            job['status'] = 'succeeded'
            self.assertIsNone(diagnostics.job_failure(root, job))

    def test_generated_document_matches_installed_modes(self):
        self.assertEqual((ROOT / 'adapters/assets/generation-capabilities.md').read_text('utf8'), caps.markdown())

    def check_worker_failure(self, report, expected):
        with test_directory() as tmp:
            output = tmp / 'output'
            output.mkdir()
            client = Mock()
            client.query.return_value = report
            with patch.object(tripo, 'client_for_request', return_value=client):
                with self.assertRaises(TaskResultError) as error:
                    api_worker.run('tripo', {'mode': 'api'},
                        {'parameters': {'prompt': 'test object'}, 'inputs': [], 'provider_job_id': 'retained-task'},
                        output, tmp / 'result.json')
            self.assertEqual(error.exception.diagnostic['kind'], expected)
            self.assertEqual(json.loads((tmp / 'remote.json').read_text())['provider_job_id'], 'retained-task')
            client.submit.assert_not_called()

    def test_completed_task_with_invalid_output_retains_id(self):
        self.check_worker_failure({'status': 'success', 'done': True, 'pending': False, 'files': []}, 'output_invalid')

    def test_failed_cloud_task_retains_id(self):
        self.check_worker_failure({'status': 'failed', 'done': False, 'pending': False}, 'remote_task_failed')


if __name__ == '__main__':
    unittest.main()

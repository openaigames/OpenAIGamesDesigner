"""Local credential page: real DPAPI on Windows, isolated files, no provider calls."""
import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import settings_server
import asset_workflow
import package_skills
from adapters.assets import credential_store as store, api_common


class SettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.path = self.root / 'profile/credentials.json'
        for context in (patch.object(store, 'store_path', return_value=self.path),
                        patch.dict(os.environ, {'TRIPO_API_KEY': '', 'HUNYUAN3D_API_KEY': '', 'CUSTOM_ASSET_KEY': ''})):
            context.start(); self.addCleanup(context.stop)

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_encrypted_roundtrip_no_plaintext_or_status_echo_and_delete(self):
        secret = 'synthetic-fixture-not-a-service-key'
        store.save('tripo', secret)
        self.assertEqual(store.get('TRIPO_API_KEY'), secret)
        self.assertNotIn(secret, self.path.read_text())
        self.assertNotIn(secret, json.dumps(store.status()))
        self.assertTrue(store.status()['providers']['tripo']['saved'])
        store.save('hunyuan3d', 'synthetic-hunyuan-key')
        store.remove('tripo')
        self.assertEqual(store.get('TRIPO_API_KEY'), '')
        self.assertEqual(store.get('HUNYUAN3D_API_KEY'), 'synthetic-hunyuan-key')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_environment_precedence_and_custom_variable_has_no_silent_fallback(self):
        store.save('tripo', 'saved-fixture-value')
        self.assertEqual(api_common.credential({}, 'api_key_env', 'TRIPO_API_KEY'), 'saved-fixture-value')
        with patch.dict(os.environ, {'TRIPO_API_KEY': 'environment-fixture'}):
            self.assertEqual(api_common.credential({}, 'api_key_env', 'TRIPO_API_KEY'), 'environment-fixture')
            self.assertEqual(api_common.doctor('tripo', {'mode': 'api'})['credentials'][0]['source'], 'environment')
        with self.assertRaises(ValueError):
            api_common.credential({'api_key_env': 'CUSTOM_ASSET_KEY'}, 'api_key_env', 'TRIPO_API_KEY')

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_shared_settings_queue_without_project_config_and_explicit_override(self):
        store.save('hunyuan3d', 'shared-hunyuan-fixture')
        project = self.root / 'game-project'; project.mkdir()
        (project / 'request.json').write_text(json.dumps({'parameters': {'Prompt': 'crate'}, 'inputs': []}))
        def submit():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = asset_workflow.main(['--project', str(project), 'submit', '--provider', 'hunyuan3d', '--request', 'request.json'])
            return code, output.getvalue()
        code, text = submit()
        self.assertEqual(code, 0, text)
        job = json.loads(text)
        self.assertEqual(job['settings']['auth'], 'api_key')
        self.assertNotIn('shared-hunyuan-fixture', text)
        config = project / '.openaigame/asset-providers.json'
        config.write_text(json.dumps({'hunyuan3d': {'mode': 'api', 'auth': 'tc3', 'region': 'ap-guangzhou'}}))
        code, text = submit()
        self.assertEqual(code, 0, text)
        self.assertEqual(json.loads(text)['settings']['auth'], 'tc3')
        config.write_text(json.dumps({'hunyuan3d': None}))
        self.assertEqual(submit()[0], 2)  # Explicit project entry never silently falls back.

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_bad_or_empty_key_does_not_replace_and_corrupt_store_not_overwritten(self):
        store.save('tripo', 'valid-fixture-key')
        before = self.path.read_bytes()
        for key in ('', '  ', 'short', 'two separate words', None):
            with self.assertRaises(ValueError): store.save('tripo', key)
        self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text('corrupt fixture')
        with self.assertRaises(ValueError): store.save('tripo', 'replacement-key')
        self.assertEqual(self.path.read_text(), 'corrupt fixture')

    def start_server(self):
        server = settings_server.SettingsServer()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown(); server.server_close(); thread.join(timeout=3)
        self.addCleanup(stop)
        self.server = server
        return server

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            raw = json.dumps(body) if body is not None else None
            connection.request(method, path, raw, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def login(self):
        server = self.server
        status, headers, _ = self.request('POST', '/session', {}, {'Origin': server.origin, 'X-Setup-Token': server.launch_token})
        self.assertEqual(status, 200)
        return {'Cookie': headers['Set-Cookie'].split(';')[0], 'Origin': server.origin,
                'Content-Type': 'application/json', 'X-CSRF-Token': server.csrf}

    def test_no_unauthenticated_state_bad_host_cross_origin_or_token_reuse(self):
        server = self.start_server()
        self.assertEqual(self.request('GET', '/api/state')[0], 401)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'attacker.test'})[0], 403)
        token = server.launch_token
        self.assertEqual(self.request('POST', '/session', {}, {'Origin': 'https://attacker.test', 'X-Setup-Token': token})[0], 403)
        headers = self.login()
        self.assertEqual(self.request('POST', '/session', {}, {'Origin': server.origin, 'X-Setup-Token': token})[0], 401)
        self.assertEqual(self.request('POST', '/api/save', {'provider': 'tripo', 'key': 'synthetic'}, {**headers, 'Origin': 'https://attacker.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/save', {}, {**headers, 'X-CSRF-Token': 'wrong'})[0], 403)
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_http_save_status_delete_never_returns_key(self):
        self.start_server(); headers = self.login()
        secret = 'http-roundtrip-fixture'
        status, response_headers, body = self.request('POST', '/api/save', {'provider': 'tripo', 'key': secret}, headers)
        self.assertEqual(status, 200, body)
        self.assertNotIn(secret.encode(), body)
        self.assertEqual(response_headers['Cache-Control'], 'no-store')
        self.assertEqual(response_headers['X-Frame-Options'], 'DENY')
        self.assertTrue(json.loads(body)['providers']['tripo']['saved'])
        self.assertNotIn(secret.encode(), self.request('GET', '/api/state', headers=headers)[2])
        self.assertEqual(store.get('TRIPO_API_KEY'), secret)
        status, _, body = self.request('POST', '/api/remove', {'provider': 'tripo'}, headers)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)['providers']['tripo']['saved'])

    def test_unknown_path_and_non_json_input_rejected(self):
        self.start_server(); headers = self.login()
        self.assertEqual(self.request('GET', '/../../credentials.json', headers=headers)[0], 401)
        self.assertEqual(self.request('POST', '/api/save', {}, {**headers, 'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.request('POST', '/api/save', {'provider': 'unknown', 'key': 'synthetic-fixture'}, headers)[0], 400)
        self.assertFalse(self.path.exists())

    def test_two_windows_keep_independent_sessions_and_close(self):
        first = self.start_server(); first_headers = self.login()
        second = self.start_server(); second_headers = self.login()
        # Browsers share cookies for 127.0.0.1 across ports.
        from http.cookies import SimpleCookie
        jar = SimpleCookie()
        jar.load(first_headers['Cookie']); jar.load(second_headers['Cookie'])
        shared_cookie = '; '.join(key + '=' + value.value for key, value in jar.items())
        for server, headers in ((first, first_headers), (second, second_headers)):
            self.server = server
            self.assertEqual(self.request('GET', '/api/state', headers={**headers, 'Cookie': shared_cookie})[0], 200)
        status, response, _ = self.request('POST', '/api/close', {}, {**second_headers, 'Cookie': shared_cookie})
        self.assertEqual(status, 200)
        closed = SimpleCookie(response['Set-Cookie'])
        for key in closed: jar.pop(key, None)
        self.server = first
        remaining = '; '.join(key + '=' + value.value for key, value in jar.items())
        self.assertEqual(self.request('GET', '/api/state', headers={**first_headers, 'Cookie': remaining})[0], 200)

    def test_unsupported_os_does_not_write_plaintext(self):
        with patch.object(store, 'available', return_value=False):
            self.assertFalse(store.status()['storage_available'])
            self.assertEqual(store.get('TRIPO_API_KEY'), '')
            with self.assertRaises(ValueError): store.save('tripo', 'synthetic-fixture')
        self.assertFalse(self.path.exists())

    def test_settings_page_assets_are_in_portable_bundle(self):
        bundle = package_skills.package(self.root / 'bundle')
        runtime = bundle / 'game-preproduction/runtime'
        for name in ('index.html', 'style.css', 'app.js'):
            self.assertTrue((runtime / 'tools/settings-ui' / name).is_file())
        result = subprocess.run([sys.executable, '-B', str(runtime / 'tools/settings_server.py'), '--help'],
                                cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

"""Host proxy policy and streaming/secret boundaries; no external service calls."""
import ctypes
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.assets import host_proxy, http_io, proxy_transport

URL = 'https://api.example.com/balance'


class ProxyTests(unittest.TestCase):
    def setUp(self):
        isolated = patch.dict(os.environ, {}, clear=True)
        isolated.start(); self.addCleanup(isolated.stop)

    def test_explicit_environment_precedes_system(self):
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://proxy.example:8443'}), \
                patch.object(host_proxy, '_windows_proxy') as system:
            self.assertEqual(host_proxy.proxy_for(URL), 'https://proxy.example:8443')
            system.assert_not_called()

    def test_bypass_and_empty_env_do_not_contact_system(self):
        for env in ({'NO_PROXY': '.example.com'}, {'HTTPS_PROXY': ''}, {'ALL_PROXY': ''}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                    patch.object(host_proxy, '_windows_proxy') as system:
                self.assertIsNone(host_proxy.proxy_for(URL))
                system.assert_not_called()

    def test_all_proxy_and_unmatched_no_proxy(self):
        with patch.dict(os.environ, {'ALL_PROXY': 'socks5h://localhost:1080'}):
            self.assertEqual(host_proxy.proxy_for(URL), 'socks5h://localhost:1080')
        with patch.dict(os.environ, {'NO_PROXY': 'localhost'}), \
                patch.object(host_proxy.sys, 'platform', 'win32'), \
                patch.object(host_proxy, '_windows_proxy', return_value='http://system:80') as system:
            self.assertEqual(host_proxy.proxy_for(URL), 'http://system:80')
            system.assert_called_once_with(URL)

    def test_manual_endpoints_and_bypass(self):
        self.assertEqual(host_proxy._select_proxy('http=proxy:80;https=https://proxy:443'), 'https://proxy:443')
        self.assertEqual(host_proxy._select_proxy('proxy:80;backup:81'), 'http://proxy:80')
        self.assertTrue(host_proxy._bypass('machine', '<local>;*.internal'))
        self.assertTrue(host_proxy._bypass('asset.internal:443', '<local>;*.internal'))
        self.assertFalse(host_proxy._bypass('api.example.com', '<local>;*.internal'))
        for value in ('https://proxy/secret', 'file:///secret', 'https://proxy:bad', 'proxy\nheader'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                host_proxy._validate(value)

    def native(self, *, pac=True, autodetect=True, result=True, error=0, direct=False, manual=False):
        lib, kernel = Mock(), Mock()
        buffers = []
        def string(value):
            buf = ctypes.create_unicode_buffer(value); buffers.append(buf)
            return ctypes.cast(buf, ctypes.c_void_p).value
        def config(ptr):
            cfg = ptr._obj
            cfg.auto_detect = autodetect
            cfg.pac = string('http://localhost/private-pac') if pac else None
            cfg.proxy = string('https=static-proxy:80') if manual else None
            return True
        def resolve(session, url, options, ptr):
            self.assertFalse(options._obj.auto_logon)
            if result:
                ptr._obj.access_type = 1 if direct else 3
                ptr._obj.proxy = None if direct else string('https://resolved-proxy:8891')
            return result
        lib.WinHttpGetIEProxyConfigForCurrentUser.side_effect = config
        lib.WinHttpGetProxyForUrl.side_effect = resolve
        lib.WinHttpOpen.return_value = 42
        with patch.object(ctypes, 'WinDLL', side_effect=[lib, kernel], create=True), \
                patch.object(ctypes, 'get_last_error', return_value=error, create=True):
            value = host_proxy._windows_proxy(URL)
        self.assertEqual(kernel.GlobalFree.call_count, len(buffers))
        return value, lib

    def test_windows_pac_proxy_direct_and_manual_fallback(self):
        value, lib = self.native()
        self.assertEqual(value, 'https://resolved-proxy:8891')
        lib.WinHttpCloseHandle.assert_called_once_with(42)
        self.assertIsNone(self.native(direct=True, manual=True)[0])
        self.assertEqual(self.native(pac=False, autodetect=False, manual=True)[0], 'http://static-proxy:80')
        self.assertEqual(self.native(pac=False, result=False, error=12180, manual=True)[0], 'http://static-proxy:80')
        self.assertIsNone(self.native(pac=False, result=False, error=12180)[0])

    def test_configured_pac_failure_does_not_silently_go_direct(self):
        with self.assertRaisesRegex(ValueError, 'automatic proxy'):
            self.native(result=False, error=12167, manual=True)


class KeepBytes(io.BytesIO):
    def close(self):
        if not self.closed:
            self.saved = self.getvalue()
        super().close()


class TransportTests(unittest.TestCase):
    def process(self, wire=b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello', code=0):
        proc = Mock()
        proc.stdin = KeepBytes()
        proc.stdout = io.BytesIO(wire)
        proc.poll.return_value = code
        proc.wait.return_value = code
        return proc

    def test_stream_headers_body_and_secret_free_argv(self):
        proc = self.process()
        request = urllib.request.Request(URL, b'\x00binary\xff', {'Authorization': 'Bearer private-key'}, method='POST')
        with patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc) as spawn:
            with proxy_transport.Response(request, 'https://proxy:8891', 10) as response:
                self.assertEqual(response.headers['Content-Length'], '5')
                self.assertEqual(response.read(2), b'he')
                self.assertEqual(response.read(8), b'llo')
                self.assertEqual(response.read(8), b'')
                temp = Path(response._temp.name)
                self.assertEqual((temp/'body.bin').read_bytes(), request.data)
                self.assertNotIn('private-key', str(spawn.call_args))
                self.assertIn(b'private-key', proc.stdin.saved)
                self.assertNotIn(b'location', proc.stdin.saved)
                self.assertNotIn(b'insecure', proc.stdin.saved)
                self.assertNotIn(b'retry', proc.stdin.saved)
            self.assertFalse(temp.exists())
            self.assertTrue(proc.stdout.closed)

    def test_interim_headers_and_transport_failure_not_success(self):
        wire = b'HTTP/1.1 100 Continue\r\n\r\nHTTP/2 200\r\nContent-Type: audio/mpeg\r\n\r\nID3'
        proc = self.process(wire, code=18)
        with patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc):
            with proxy_transport.Response(urllib.request.Request(URL), 'http://proxy:80', 10) as response:
                self.assertEqual(response.code, 200)
                with self.assertRaises(OSError):
                    response.read()

    def test_early_close_kills_transfer(self):
        proc = self.process(); proc.poll.return_value = None
        with patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc):
            with proxy_transport.Response(urllib.request.Request(URL), 'http://proxy:80', 10):
                pass
        proc.kill.assert_called_once()
        self.assertTrue(proc.stdout.closed)

    def test_malformed_headers_cleanup(self):
        proc = self.process(b'not HTTP\n')
        with patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc), self.assertRaises(OSError):
            proxy_transport.Response(urllib.request.Request(URL), 'http://proxy:80', 10)
        self.assertTrue(proc.stdout.closed)

    def test_shared_opener_proxy_and_direct_routes(self):
        with patch.object(http_io, 'public_url'), \
                patch.object(host_proxy, 'proxy_for', return_value='https://proxy:8891'), \
                patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=self.process()):
            with http_io.open_url(URL) as response:
                self.assertEqual(response.read(), b'hello')
        request = urllib.request.Request(URL); request.timeout = 5
        with patch.object(host_proxy, 'proxy_for', return_value=None), \
                patch.object(proxy_transport, 'Response') as transport:
            self.assertIsNone(http_io.HostProxy().proxy_open(request, None, 'https'))
            transport.assert_not_called()

    def test_authenticated_redirect_rejected_and_closed(self):
        proc = self.process(b'HTTP/1.1 302 Found\r\nLocation: https://other.example/path\r\n\r\n')
        with patch.object(http_io, 'public_url'), \
                patch.object(host_proxy, 'proxy_for', return_value='https://proxy:8891'), \
                patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc) as spawn:
            with self.assertRaisesRegex(ValueError, 'Authenticated API redirects'):
                http_io.open_url(URL, headers={'xi-api-key': 'private-key'})
            self.assertEqual(spawn.call_count, 1)
            self.assertTrue(proc.stdout.closed)

    def test_download_redirect_re_resolves_proxy_and_closes_previous(self):
        first = self.process(b'HTTP/1.1 302 Found\r\nLocation: https://cdn.example/path\r\n\r\n')
        second = self.process()
        with patch.object(http_io, 'public_url'), \
                patch.object(host_proxy, 'proxy_for', side_effect=['https://proxy:8891', 'http://other:80']) as route, \
                patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', side_effect=[first, second]):
            with http_io.open_url(URL) as response:
                self.assertEqual(response.read(), b'hello')
            self.assertEqual([c.args[0] for c in route.call_args_list], [URL, 'https://cdn.example/path'])
            self.assertTrue(first.stdout.closed)

    def test_http_error_does_not_leak_provider_body_and_closes(self):
        proc = self.process(b'HTTP/1.1 401 Denied\r\n\r\nprivate-key')
        with patch.object(http_io, 'public_url'), \
                patch.object(host_proxy, 'proxy_for', return_value='https://proxy:8891'), \
                patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc):
            with self.assertRaisesRegex(ValueError, 'HTTP 401') as failure:
                http_io.open_url(URL)
            self.assertNotIn('private-key', str(failure.exception))
            self.assertTrue(proc.stdout.closed)

    def test_write_redirect_is_not_replayed_even_without_auth(self):
        response = Mock()
        with patch.object(http_io, 'public_url'), self.assertRaisesRegex(ValueError, 'write requests'):
            http_io.Redirects().redirect_request(urllib.request.Request(URL, b'payload'),
                response, 307, 'redirect', {}, 'https://other.example/path')
        response.close.assert_called_once()

    def test_oversized_header_is_rejected(self):
        proc = self.process(b'HTTP/1.1 200 OK\r\nX-Large: ' + b'x' * 9000 + b'\r\n\r\n')
        with patch.object(proxy_transport, '_curl', return_value='curl'), \
                patch.object(proxy_transport.subprocess, 'Popen', return_value=proc), self.assertRaises(OSError):
            proxy_transport.Response(urllib.request.Request(URL), 'http://proxy:80', 10)
        self.assertTrue(proc.stdout.closed)


if __name__ == '__main__':
    unittest.main()

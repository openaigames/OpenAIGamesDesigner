"""Streaming curl transport for host HTTP/HTTPS/SOCKS proxies; no retries or redirects."""
import email.parser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def _curl():
    native = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/curl.exe'
    path = str(native) if os.name == 'nt' and native.is_file() else shutil.which('curl')
    if not path:
        raise ValueError('Host proxy connections require curl on PATH (included in current Windows)')
    return path


def _quoted(value):
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Invalid control character in HTTPS request')
    return json.dumps(value, ensure_ascii=False)


class Response:
    def __init__(self, request, proxy, timeout):
        self._process = None
        self._temp = None
        self._closed = False
        self.url = request.full_url
        try:
            lines = ['silent', 'include', 'suppress-connect-headers', 'globoff',
                     'proto = "=https"', 'proxy = ' + _quoted(proxy), 'noproxy = ""',
                     'url = ' + _quoted(self.url), 'request = ' + _quoted(request.get_method()),
                     'connect-timeout = ' + str(min(timeout, 30)),
                     'speed-limit = 1', 'speed-time = ' + str(max(1, int(timeout)))]
            if request.get_method() == 'HEAD':
                lines.append('head')
            for key, value in request.header_items():
                lines.append('header = ' + _quoted(key + ': ' + value))
            if request.data is not None:
                if not isinstance(request.data, bytes):
                    raise ValueError('HTTPS request body must be bytes')
                # Only the request body is stored temporarily; keys stay in stdin.
                self._temp = tempfile.TemporaryDirectory(prefix='oagd-request-')
                body = Path(self._temp.name) / 'body.bin'
                body.write_bytes(request.data)
                lines.append('data-binary = ' + _quoted('@' + str(body)))
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self._process = subprocess.Popen([_curl(), '-q', '--config', '-'], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)
            self._process.stdin.write(('\n'.join(lines) + '\n').encode('utf-8'))
            self._process.stdin.close()
            self._read_headers()
        except BaseException:
            self.close()
            raise

    def _read_headers(self):
        count = 0
        while True:
            line = self._process.stdout.readline(8193)
            count += len(line)
            match = re.fullmatch(rb'HTTP/[^ ]+ ([0-9]{3})(?: ([^\r\n]*))?\r?\n', line)
            if not match:
                raise OSError('Proxy HTTPS transfer failed before response headers')
            self.status = self.code = int(match[1])
            self.reason = self.msg = (match[2] or b'').decode('latin1')
            lines = []
            while True:
                line = self._process.stdout.readline(8193)
                count += len(line)
                if count > 65536 or len(line) > 8192 or not line:
                    raise OSError('Invalid or incomplete HTTPS response headers')
                if line in (b'\r\n', b'\n'):
                    break
                lines.append(line)
            if not 100 <= self.code < 200:
                self.headers = email.parser.BytesParser().parsebytes(b''.join(lines))
                return

    def read(self, size=-1):
        if self._closed:
            return b''
        data = self._process.stdout.read(size)
        if size != 0 and (not data or size is None or size < 0):
            if self._process.wait(timeout=5) != 0:
                raise OSError('Proxy HTTPS transfer interrupted; request was not retried')
        return data

    def info(self):
        return self.headers

    def geturl(self):
        return self.url

    def getcode(self):
        return self.code

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._process is not None:
                if self._process.poll() is None:
                    self._process.kill()
                self._process.wait(timeout=5)
                for stream in (self._process.stdin, self._process.stdout):
                    if stream is not None:
                        stream.close()
        finally:
            if self._temp is not None:
                self._temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

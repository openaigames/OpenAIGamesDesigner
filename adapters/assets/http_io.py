"""Bounded HTTPS JSON and file transfers; credentials never accompany downloads."""
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import urllib.error
import urllib.parse
import urllib.request


def public_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('Use an HTTPS URL without embedded credentials')
    if parts.port not in (None, 443):
        raise ValueError('Only the HTTPS service port is supported')
    try:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError('Download host could not be resolved') from None
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('URL must resolve to a public Internet host')
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        if req.has_header('Authorization'):
            raise ValueError('Authenticated API redirects are not supported')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url, data=None, headers=None, method=None, timeout=45):
    public_url(url)
    request = urllib.request.Request(url, data=data, headers={
        'User-Agent': 'OpenAIGamesDesigner/1.0', **(headers or {})}, method=method)
    try:
        return urllib.request.build_opener(Redirects()).open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        # API bodies and signed URLs may contain secrets; retain the HTTP code only.
        raise ValueError(f'HTTP {error.code}; check provider console or refresh the download link') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError('HTTPS transfer failed; verify connectivity and resume rather than resubmit') from None


def json_request(url, payload=None, headers=None, method=None):
    data = None if payload is None else json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return json_bytes(url, data, {'Content-Type': 'application/json', **(headers or {})}, method)


def json_bytes(url, data, headers, method=None):
    with open_url(url, data, headers, method) as response:
        body = response.read(16 * 1024 * 1024 + 1)
    if len(body) > 16 * 1024 * 1024:
        raise ValueError('API response exceeds 16 MiB')
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise ValueError('API returned invalid JSON') from None
    if not isinstance(value, dict):
        raise ValueError('API response must be an object')
    return value


def download(url, target, max_bytes=1024 * 1024 * 1024, expected_sha256=None):
    target = Path(target)
    if target.exists():
        raise ValueError('Download destination already exists')
    if type(max_bytes) is not int or not 1 <= max_bytes <= 8 * 1024**3:
        raise ValueError('Invalid download size limit')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    digest, size = hashlib.sha256(), 0
    owned = False
    try:
        with open_url(url) as response, partial.open('xb') as output:
            owned = True
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                raise ValueError('Download returned a web/login page, not an asset')
            declared = response.headers.get('Content-Length')
            if declared and int(declared) > max_bytes:
                raise ValueError('Download exceeds size limit')
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Download exceeds size limit')
                digest.update(chunk)
                output.write(chunk)
            if declared and size != int(declared):
                raise ValueError('Incomplete download')
        if not size:
            raise ValueError('Empty download')
        actual = digest.hexdigest()
        if expected_sha256 and actual.lower() != expected_sha256.lower():
            raise ValueError('Downloaded file hash mismatch')
        partial.rename(target)
        return {'sha256': actual, 'bytes': size}
    finally:
        if owned:
            partial.unlink(missing_ok=True)

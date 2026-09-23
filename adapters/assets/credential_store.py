"""Per-user Windows DPAPI storage. Never return secrets from status operations."""
import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile
import threading

NAMES = {'tripo': 'TRIPO_API_KEY', 'hunyuan3d': 'HUNYUAN3D_API_KEY'}
_mutex = threading.RLock()


def available():
    return os.name == 'nt'


def store_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'OpenAIGamesDesigner' / 'credentials.dpapi.json'


def _crypt(data, decrypt=False):
    if not available():
        raise ValueError('The settings page currently supports Windows encrypted storage; use environment variables on other systems')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # UI_FORBIDDEN; no LOCAL_MACHINE flag: encryption belongs to the logged-in user.
    if not fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ValueError('Windows credential protection failed; verify the current user and local profile')
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel.LocalFree(outgoing.data)


def _read():
    path = store_path()
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 128 * 1024:
            raise ValueError()
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('version') != 1 or record.get('protection') != 'windows-dpapi-user':
            raise ValueError()
        values = json.loads(_crypt(base64.b64decode(record['ciphertext'], validate=True), True))
        if not isinstance(values, dict) or set(values) - set(NAMES.values()):
            raise ValueError()
        if any(not isinstance(v, str) or not v for v in values.values()):
            raise ValueError()
        return values
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('Saved credentials cannot be read by this Windows user; restore the profile or reconfigure the store') from None


@contextmanager
def _locked():
    if not available():
        raise ValueError('Encrypted credential settings require Windows')
    import msvcrt
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _mutex, path.with_suffix('.lock').open('a+b') as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError('Another settings window is saving; retry shortly') from None
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _write(values):
    path = store_path()
    record = {'version': 1, 'protection': 'windows-dpapi-user',
              'ciphertext': base64.b64encode(_crypt(json.dumps(values).encode('utf-8'))).decode('ascii')}
    fd, temporary = tempfile.mkstemp(prefix='credentials-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(record, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save(provider, value):
    if provider not in NAMES:
        raise ValueError('Unsupported provider')
    if not isinstance(value, str) or not 8 <= len(value.strip()) <= 8192 or any(c.isspace() for c in value.strip()):
        raise ValueError('Enter the complete API key without internal whitespace')
    with _locked():
        values = _read()
        values[NAMES[provider]] = value.strip()
        _write(values)


def remove(provider):
    if provider not in NAMES:
        raise ValueError('Unsupported provider')
    with _locked():
        values = _read()
        values.pop(NAMES[provider], None)
        _write(values)


def get(name):
    if name not in NAMES.values() or not available():
        return ''
    return _read().get(name, '')


def status():
    values = _read() if available() else {}
    return {'storage_available': available(), 'storage': 'Windows 用户加密存储' if available() else '当前系统请使用环境变量',
            'providers': {provider: {'saved': bool(values.get(name)),
                'environment_present': bool(os.environ.get(name)),
                'effective_source': 'environment' if os.environ.get(name) else 'local_store' if values.get(name) else 'missing'}
                for provider, name in NAMES.items()},
            'network_checked': False, 'generation_submitted': False}


def default_settings(provider):
    name = NAMES.get(provider)
    if not name or not (os.environ.get(name) or get(name)):
        return None
    settings = {'mode': 'api', 'api_key_env': name}
    if provider == 'hunyuan3d':
        settings['auth'] = 'api_key'
    return settings

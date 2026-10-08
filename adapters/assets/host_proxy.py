"""Resolve the current host's proxy per URL without changing system settings."""
import os
import re
import sys
import urllib.parse
import urllib.request


def _validate(proxy):
    if not proxy:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in proxy):
        raise ValueError('Invalid host proxy configuration')
    if '://' not in proxy:
        proxy = 'http://' + proxy
    try:
        parsed = urllib.parse.urlsplit(proxy)
        valid = (parsed.scheme in ('http', 'https', 'socks4', 'socks4a', 'socks5', 'socks5h')
                 and parsed.hostname and parsed.port != 0 and parsed.path in ('', '/')
                 and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Unsupported host proxy configuration')
    return proxy


def _select_proxy(value, scheme='https'):
    # WinHTTP lists endpoints in preference order; never retry another proxy after a POST.
    entries = re.split(r'[;\s]+', value.strip())
    choices = {}
    for entry in entries:
        if not entry:
            continue
        if '=' in entry and '://' not in entry.split('=', 1)[0]:
            key, endpoint = entry.split('=', 1)
            choices.setdefault(key.lower(), endpoint)
        else:
            choices.setdefault('*', entry)
    selected = choices.get(scheme, choices.get('*'))
    if not selected:
        raise ValueError('System proxy has no endpoint for HTTPS')
    return _validate(selected)


def _bypass(host, value):
    # Windows bypass lists also accept wildcard names and <local>.
    import fnmatch
    hostname = urllib.parse.urlsplit('//' + host).hostname or host
    for item in value.replace(';', ',').split(','):
        item = item.strip().lower()
        if item == '<local>' and '.' not in hostname:
            return True
        if item and (fnmatch.fnmatchcase(host.lower(), item) or fnmatch.fnmatchcase(hostname.lower(), item)):
            return True
    return urllib.request.proxy_bypass_environment(host, {'no': value.replace(';', ',')})


def proxy_for(url):
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc
    env = urllib.request.getproxies_environment()
    if env.get('no') and urllib.request.proxy_bypass_environment(host, env):
        return None
    # Empty HTTPS_PROXY/ALL_PROXY is an explicit opt-out; NO_PROXY alone is not.
    keys = {key.lower() for key in os.environ}
    for scheme in (parts.scheme, 'all'):
        if scheme + '_proxy' in keys:
            return _validate(env.get(scheme))
    if sys.platform == 'win32':
        return _windows_proxy(url)
    proxies = urllib.request.getproxies()
    if urllib.request.proxy_bypass(host):
        return None
    return _validate(proxies.get(parts.scheme) or proxies.get('all'))


def _windows_proxy(url):
    import ctypes
    from ctypes import wintypes as W

    class Config(ctypes.Structure):
        _fields_ = [('auto_detect', W.BOOL), ('pac', ctypes.c_void_p),
                    ('proxy', ctypes.c_void_p), ('bypass', ctypes.c_void_p)]

    class Options(ctypes.Structure):
        _fields_ = [('flags', W.DWORD), ('detect_flags', W.DWORD), ('pac', W.LPCWSTR),
                    ('reserved', ctypes.c_void_p), ('reserved2', W.DWORD), ('auto_logon', W.BOOL)]

    class ProxyInfo(ctypes.Structure):
        _fields_ = [('access_type', W.DWORD), ('proxy', ctypes.c_void_p), ('bypass', ctypes.c_void_p)]

    lib = ctypes.WinDLL('winhttp', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel.GlobalFree.restype = ctypes.c_void_p
    lib.WinHttpGetIEProxyConfigForCurrentUser.argtypes = [ctypes.POINTER(Config)]
    lib.WinHttpGetIEProxyConfigForCurrentUser.restype = W.BOOL
    lib.WinHttpOpen.argtypes = [W.LPCWSTR, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD]
    lib.WinHttpOpen.restype = W.HANDLE
    lib.WinHttpSetTimeouts.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.WinHttpSetTimeouts.restype = W.BOOL
    lib.WinHttpGetProxyForUrl.argtypes = [W.HANDLE, W.LPCWSTR, ctypes.POINTER(Options), ctypes.POINTER(ProxyInfo)]
    lib.WinHttpGetProxyForUrl.restype = W.BOOL
    lib.WinHttpCloseHandle.argtypes = [W.HANDLE]
    lib.WinHttpCloseHandle.restype = W.BOOL
    cfg, info, session = Config(), ProxyInfo(), None
    try:
        if not lib.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(cfg)):
            raise ValueError('Cannot read Windows proxy settings')
        pac = ctypes.wstring_at(cfg.pac) if cfg.pac else None
        if pac or cfg.auto_detect:
            session = lib.WinHttpOpen('OpenAIGamesDesigner/1.0', 1, None, None, 0)
            if not session:
                raise ValueError('Cannot initialize Windows automatic proxy resolution')
            lib.WinHttpSetTimeouts(session, 5000, 5000, 5000, 5000)
            opts = Options(2 if pac else 1, 0 if pac else 3, pac, None, 0, False)
            ok = lib.WinHttpGetProxyForUrl(session, url, ctypes.byref(opts), ctypes.byref(info))
            if ok:
                if info.access_type == 1:
                    return None
                if info.access_type != 3 or not info.proxy:
                    raise ValueError('Windows returned an unsupported proxy route')
                if info.bypass and _bypass(urllib.parse.urlsplit(url).netloc, ctypes.wstring_at(info.bypass)):
                    return None
                return _select_proxy(ctypes.wstring_at(info.proxy))
            # Ordinary networks may have WPAD enabled without a discoverable PAC.
            # An explicitly configured PAC must not silently fall back to direct.
            if pac or ctypes.get_last_error() != 12180:
                raise ValueError('System automatic proxy could not be resolved; check the host proxy connection')
        if cfg.proxy:
            if cfg.bypass and _bypass(urllib.parse.urlsplit(url).netloc, ctypes.wstring_at(cfg.bypass)):
                return None
            return _select_proxy(ctypes.wstring_at(cfg.proxy))
        return None
    finally:
        if session:
            lib.WinHttpCloseHandle(session)
        for pointer in (cfg.pac, cfg.proxy, cfg.bypass, info.proxy, info.bypass):
            if pointer:
                kernel.GlobalFree(pointer)

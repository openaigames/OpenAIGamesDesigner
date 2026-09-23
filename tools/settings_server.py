#!/usr/bin/env python3
"""Open a loopback-only credential page; never expose stored API key values."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.assets import credential_store
from adapters.assets import generation_approval

UI = Path(__file__).with_name('settings-ui')
APPROVAL_STORAGE_ERROR = ('无法读写本机授权记录。请让助手检查确认服务的启动权限：需要以当前登录用户运行，'
                          '并允许访问本机配置目录；若有其他设置页正在保存，请稍后刷新。无需重新填写密钥。')


class SettingsServer(HTTPServer):
    def __init__(self, port=0, project=None, job_id=None):
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)
        # Cookies are host-scoped, not port-scoped; concurrent windows must not overwrite each other.
        self.cookie_name = 'oagd_settings_' + str(self.server_port)
        self.launch_token = secrets.token_urlsafe(32)
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.last_access = time.monotonic()
        self.project = Path(project).resolve() if project else None
        self.job_id = job_id

    def state(self):
        state = {**credential_store.status(), 'csrf': self.csrf, 'approval': None}
        if self.project and self.job_id:
            try:
                from asset_workflow import read_job
                _, job = read_job(self.project, self.job_id)
                fingerprint = generation_approval.for_job(self.project, job)
                details = {'project': str(self.project), 'job_id': self.job_id,
                    'provider': job['provider'], 'parameters': job['request']['parameters'],
                    'inputs': [{k: item[k] for k in ('path', 'sha256')} for item in job['request']['inputs']]}
                try:
                    generation_approval.check_storage()
                except (OSError, ValueError):
                    state['approval'] = {**details, 'error_code': 'approval_storage_unavailable',
                                         'error': APPROVAL_STORAGE_ERROR}
                    return state
                try:
                    generation_approval.require(fingerprint)
                    approved = True
                except ValueError:
                    approved = False
                except OSError:
                    state['approval'] = {**details, 'error_code': 'approval_storage_unavailable',
                                         'error': APPROVAL_STORAGE_ERROR}
                    return state
                state['approval'] = {**details, 'fingerprint': fingerprint, 'approved': approved}
            except (OSError, ValueError, KeyError, TypeError):
                state['approval'] = {'job_id': self.job_id, 'error': '请先配置此任务的凭据，并确认任务仍在等待执行。'}
        return state

    @property
    def launch_url(self):
        return self.origin + '/#' + self.launch_token


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass  # No URL, body, request header or exception logging.

    def _reply(self, status, body, kind='application/json; charset=utf-8', cookie=None):
        data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(data)

    def _host(self):
        return self.headers.get('Host') == self.server.origin.split('//', 1)[1]

    def _session(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookies.get(self.server.cookie_name)
            return bool(value and secrets.compare_digest(value.value, self.server.session))
        except Exception:
            return False

    def do_GET(self):
        if not self._host():
            return self._reply(403, {'error': '请使用启动工具提供的本机地址。'})
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8'),
                 '/logos/openaigamesdesigner.png': ('logos/openaigamesdesigner.png', 'image/png'),
                 '/logos/tripo.png': ('logos/tripo.png', 'image/png'),
                 '/logos/hunyuan3d.png': ('logos/hunyuan3d.png', 'image/png')}
        if self.path in files:
            name, kind = files[self.path]
            return self._reply(200, (UI / name).read_bytes(), kind)
        if self.path == '/api/state' and self._session():
            self.server.last_access = time.monotonic()
            try:
                return self._reply(200, self.server.state())
            except (ValueError, OSError):
                return self._reply(409, {'error': '本机配置无法读取。请检查当前 Windows 用户与配置文件；原文件没有被覆盖。'})
        return self._reply(401, {'error': '设置会话已失效，请重新运行启动工具。'})

    def do_POST(self):
        if not self._host() or self.headers.get('Origin') != self.server.origin:
            return self._reply(403, {'error': '只接受当前本机设置页的请求。'})
        if self.path == '/session':
            token = self.headers.get('X-Setup-Token', '')
            if not self.server.launch_token or not secrets.compare_digest(token, self.server.launch_token):
                return self._reply(401, {'error': '启动链接已使用或失效，请重新打开设置。'})
            self.server.launch_token = ''
            return self._reply(200, {'connected': True}, cookie=self.server.cookie_name + '=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/')
        if not self._session() or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf):
            return self._reply(403, {'error': '设置会话校验失败，请重新打开设置。'})
        self.server.last_access = time.monotonic()
        if self.path == '/api/close':
            self._reply(200, {'closed': True}, cookie=self.server.cookie_name + '=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path not in ('/api/save', '/api/remove', '/api/approve'):
            return self._reply(404, {'error': '没有此操作。'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16 * 1024 or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                return self._reply(400, {'error': '请求格式或长度不正确。'})
            data = json.loads(self.rfile.read(size))
            if self.path == '/api/approve':
                if not isinstance(data, dict) or set(data) != {'fingerprint', 'accept_charge'} or data['accept_charge'] is not True:
                    return self._reply(400, {'error': '需要明确同意本次请求及可能的费用。'})
                current = self.server.state().get('approval') or {}
                if current.get('error'):
                    return self._reply(409, {'error': current['error'], 'error_code': current.get('error_code', 'approval_unavailable')})
                if not current.get('fingerprint') or data['fingerprint'] != current['fingerprint']:
                    return self._reply(409, {'error': '任务或账户配置已变化，请刷新并重新查看请求。'})
                try:
                    generation_approval.approve(current['fingerprint'])
                except OSError:
                    return self._reply(409, {'error': APPROVAL_STORAGE_ERROR, 'error_code': 'approval_storage_unavailable'})
                except ValueError:
                    return self._reply(409, {'error': '无法保存本次授权。请刷新状态；若请求已执行，请让助手检查已有任务记录。'})
                return self._reply(200, self.server.state())
            if not isinstance(data, dict) or set(data) - {'provider', 'key'}:
                return self._reply(400, {'error': '只接受服务名称和密钥。'})
            if self.path == '/api/save':
                credential_store.save(data.get('provider'), data.get('key'))
            else:
                credential_store.remove(data.get('provider'))
            data.clear()
            return self._reply(200, self.server.state())
        except (OSError, ValueError, TypeError):
            return self._reply(400, {'error': '未能保存。请检查完整密钥、当前系统和本机配置是否可用；已保存内容不会被空值替换。'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-open', action='store_true', help='Print a local URL instead of opening the default browser')
    parser.add_argument('--status', action='store_true', help='Read configuration presence only; no server or generation')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--idle-minutes', type=int, default=60)
    parser.add_argument('--ready-file', type=Path, help='Write an ephemeral launch URL for a local host to open')
    parser.add_argument('--project', type=Path, help='Game project containing the queued job to review')
    parser.add_argument('--approve-job', help='Review and authorize one new cloud generation; the user clicks approval')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(credential_store.status(), ensure_ascii=False, indent=2))
        return 0
    if not 0 <= args.port <= 65535 or not 1 <= args.idle_minutes <= 240:
        parser.error('Invalid port or idle timeout')
    if bool(args.project) != bool(args.approve_job):
        parser.error('--project and --approve-job must be supplied together')
    if args.approve_job:
        try:
            generation_approval.check_storage()
        except (OSError, ValueError):
            print(APPROVAL_STORAGE_ERROR + ' 确认页未启动，未提交生成。', file=sys.stderr)
            return 2
    with SettingsServer(args.port, args.project, args.approve_job) as server:
        url = server.launch_url
        if args.ready_file:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            with args.ready_file.open('x', encoding='utf-8') as stream:
                json.dump({'url': url}, stream)
        print('OpenAIGamesDesigner 本机密钥设置：' + url, flush=True)
        def expire():
            while time.monotonic() - server.last_access < args.idle_minutes * 60:
                time.sleep(10)
            server.shutdown()
        threading.Thread(target=expire, daemon=True).start()
        if not args.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            if args.ready_file:
                args.ready_file.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

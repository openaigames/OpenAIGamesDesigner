"""Tencent HY 3D professional API with TC3 or API-key authentication."""
import base64
import datetime
import hashlib
import hmac
import json
import time
from . import api_common, http_io, hunyuan_inputs, generation_capabilities
from .api_errors import ProviderAPIError

HOST = generation_capabilities.HUNYUAN_HOST
VERSION = '2025-05-13'


def signed_headers(action, payload_bytes, secret_id, secret_key, timestamp, region, token=''):
    def mac(key, value):
        return hmac.new(key, value.encode('utf-8'), hashlib.sha256).digest()
    date = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime('%Y-%m-%d')
    scope = date + '/ai3d/tc3_request'
    canonical_headers = 'content-type:application/json\nhost:' + HOST + '\n'
    canonical = 'POST\n/\n\n' + canonical_headers + '\ncontent-type;host\n' + hashlib.sha256(payload_bytes).hexdigest()
    to_sign = 'TC3-HMAC-SHA256\n' + str(timestamp) + '\n' + scope + '\n' + hashlib.sha256(canonical.encode()).hexdigest()
    key = mac(mac(mac(('TC3' + secret_key).encode(), date), 'ai3d'), 'tc3_request')
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {'Content-Type': 'application/json', 'Host': HOST, 'X-TC-Action': action,
               'X-TC-Version': VERSION, 'X-TC-Timestamp': str(timestamp), 'X-TC-Region': region,
               'Authorization': f'TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders=content-type;host, Signature={signature}'}
    if token:
        headers['X-TC-Token'] = token
    return headers


class Client:
    def __init__(self, settings):
        self.settings = settings
        self.auth = settings.get('auth', 'tc3')
        if self.auth == 'api_key':
            self.key = api_common.credential(settings, 'api_key_env', 'HUNYUAN3D_API_KEY')
        else:
            self.secret_id = api_common.credential(settings, 'secret_id_env', 'TENCENTCLOUD_SECRET_ID')
            self.secret_key = api_common.credential(settings, 'secret_key_env', 'TENCENTCLOUD_SECRET_KEY')
            self.token = api_common.credential(settings, 'token_env', 'TENCENTCLOUD_TOKEN', optional=True)
            if not isinstance(settings.get('region'), str) or not settings['region'].strip():
                raise ValueError('Configure the Tencent region enabled for the account')

    def call(self, action, payload):
        if self.auth == 'api_key':
            endpoint = 'submit' if action.startswith('Submit') else 'query'
            data = http_io.json_request(generation_capabilities.HUNYUAN_KEY_BASE + '/' + endpoint,
                                        payload, {'Authorization': self.key})
        else:
            body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            headers = signed_headers(action, body, self.secret_id, self.secret_key,
                                     int(time.time()), self.settings['region'], self.token)
            data = http_io.json_bytes('https://' + HOST + '/', body, headers)
        result = data.get('Response', data)
        if not isinstance(result, dict) or result.get('Error') or result.get('error'):
            raise ProviderAPIError(result)
        return result

    def submit(self, request):
        payload = hunyuan_inputs.build_payload(request)
        return api_common.task_id(self.call('SubmitHunyuanTo3DProJob', payload).get('JobId'))

    def query(self, remote_id):
        data = self.call('QueryHunyuanTo3DProJob', {'JobId': api_common.task_id(remote_id)})
        status = data.get('Status')
        files = [{'label': str(f.get('Type', 'model')).lower(), 'url': f['Url']}
                 for f in data.get('ResultFile3Ds') or [] if isinstance(f, dict) and f.get('Url')]
        return {'status': status, 'done': status == 'DONE', 'pending': status in ('WAIT', 'RUN'),
                'files': files, 'credit_consumed': data.get('ResultCreditConsumed')}

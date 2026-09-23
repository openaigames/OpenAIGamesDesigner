"""Tripo v2 OpenAPI: text/image generation and remote task lookup."""
import uuid
from . import api_common, http_io
from .hunyuan3d import validate

BASE = 'https://api.tripo3d.ai/v2/openapi'


def command(settings, request, output, result):
    return api_common.command('tripo', settings, request, output, result)


class Client:
    def __init__(self, settings):
        self.headers = {'Authorization': 'Bearer ' + api_common.credential(settings, 'api_key_env', 'TRIPO_API_KEY')}

    def call(self, path, payload=None, data=None, content_type=None):
        if data is None:
            value = http_io.json_request(BASE + path, payload, self.headers)
        else:
            value = http_io.json_bytes(BASE + path, data, {**self.headers, 'Content-Type': content_type})
        if value.get('code') != 0 or not isinstance(value.get('data'), dict):
            raise ValueError('Tripo API rejected the request; check account, credits and parameters')
        return value['data']

    def submit(self, request):
        payload = dict(request['parameters'])
        kind = payload.get('type', 'image_to_model' if request.get('inputs') else 'text_to_model')
        if kind not in ('text_to_model', 'image_to_model'):
            raise ValueError('This adapter supports text_to_model and image_to_model')
        payload['type'] = kind
        if kind == 'text_to_model':
            if request.get('inputs') or not isinstance(payload.get('prompt'), str) or not payload['prompt'].strip():
                raise ValueError('Text generation requires prompt and no image inputs')
        else:
            if 'file' in payload or 'prompt' in payload:
                raise ValueError('Supply the source image through inputs; do not mix prompt or file')
            image, image_type = api_common.image_input(request, 20 * 1024**2)
            boundary = 'OAGD' + uuid.uuid4().hex
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.{image_type}"\r\n'
                    f'Content-Type: image/{image_type}\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
            uploaded = self.call('/upload', data=body, content_type='multipart/form-data; boundary=' + boundary)
            token = uploaded.get('image_token')
            if not isinstance(token, str) or not token:
                raise ValueError('Tripo upload returned no image_token')
            payload['file'] = {'type': image_type, 'file_token': token}
        return api_common.task_id(self.call('/task', payload).get('task_id'))

    def query(self, remote_id):
        data = self.call('/task/' + api_common.task_id(remote_id))
        if data.get('task_id') != remote_id:
            raise ValueError('Tripo returned a different task ID')
        status = data.get('status')
        output = data.get('output') or {}
        files = [{'label': key, 'url': output[key]} for key in ('model', 'pbr_model', 'base_model') if output.get(key)]
        return {'status': status, 'done': status == 'success', 'pending': status in ('queued', 'running'),
                'files': files, 'credit_consumed': output.get('consumed_credit')}

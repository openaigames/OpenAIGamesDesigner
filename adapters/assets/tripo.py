"""Tripo v2 OpenAPI: text/image generation and remote task lookup."""
import uuid
from . import api_common, http_io, generation_capabilities, model_defaults
from .api_errors import TaskResultError
from .hunyuan3d import validate as validate_model


def validate(paths):
    if paths and all(p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp') for p in paths):
        from .tripo_multiview_images import validate_images
        return validate_images(paths)
    return validate_model(paths)


def client_for_request(settings, request):
    if request.get('parameters', {}).get('type') == 'generate_multiview_image':
        from .tripo_multiview_images import Client as ImageClient
        return ImageClient(settings)
    return Client(settings)

BASE = generation_capabilities.TRIPO_BASE


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

    def upload_image(self, image, image_type):
        boundary = 'OAGD' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.{image_type}"\r\n'
                f'Content-Type: image/{image_type}\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        uploaded = self.call('/upload', data=body, content_type='multipart/form-data; boundary=' + boundary)
        token = uploaded.get('image_token')
        if not isinstance(token, str) or not token:
            raise ValueError('Tripo upload returned no image_token')
        return {'type': image_type, 'file_token': token}

    def submit(self, request):
        from . import tripo_inputs
        tripo_inputs.validate(request)
        payload = model_defaults.prepare('tripo', request)['parameters']
        kind = tripo_inputs.kind(request)
        payload['type'] = kind
        # Read and hash every input before any upload or charged task submission.
        images = tripo_inputs.read_images(request)
        if kind == 'image_to_model':
            payload['file'] = self.upload_image(*images['front'])
        elif kind == 'multiview_to_model':
            payload['files'] = [self.upload_image(*images[view]) if view in images else {}
                                for view in tripo_inputs.VIEWS]
        return api_common.task_id(self.call('/task', payload).get('task_id'))

    def query(self, remote_id):
        data = self.call('/task/' + api_common.task_id(remote_id))
        if data.get('task_id') != remote_id:
            raise TaskResultError('output_invalid')
        status = data.get('status')
        output = data.get('output') or {}
        files = [{'label': key, 'url': output[key]} for key in ('model', 'pbr_model', 'base_model') if output.get(key)]
        return {'status': status, 'done': status == 'success', 'pending': status in ('queued', 'running'),
                'files': files, 'credit_consumed': output.get('consumed_credit')}

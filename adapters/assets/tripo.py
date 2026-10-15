"""Tripo V3 API: flagship text/image generation and remote task recovery."""
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


def payload(request, tokens):
    """Build the same token-based body for offline preview and submission."""
    from . import tripo_inputs
    kind = tripo_inputs.kind(request)
    if kind == 'generate_multiview_image':
        return {'input': tokens['front']}
    body = model_defaults.prepare('tripo', request)['parameters']
    body.pop('type', None)
    body['model'] = body.pop('model_version')
    if kind == 'image_to_model':
        body['input'] = tokens['front']
    elif kind == 'multiview_to_model':
        body['inputs'] = [{view: tokens[view]} for view in tripo_inputs.VIEWS if view in tokens]
    return body


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
        if image_type not in ('png', 'jpeg'):
            raise ValueError('Tripo file upload supports PNG/JPEG; export a reference in that format first')
        boundary = 'OAGD' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.{image_type}"\r\n'
                f'Content-Type: image/{image_type}\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        uploaded = self.call('/files', data=body, content_type='multipart/form-data; boundary=' + boundary)
        token = uploaded.get('file_token')
        if not isinstance(token, str) or not token:
            raise ValueError('Tripo upload returned no file_token')
        return token

    def submit(self, request):
        from . import tripo_inputs
        api_common.validate_request('tripo', request, {'mode': 'api'})
        kind = tripo_inputs.kind(request)
        if kind == 'generate_multiview_image':
            raise ValueError('Use the image-to-multiview client for image output')
        # Read and hash every input before any upload or charged task submission.
        images = tripo_inputs.read_images(request)
        tokens = {view: self.upload_image(*images[view]) for view in tripo_inputs.VIEWS if view in images}
        return api_common.task_id(self.call(generation_capabilities.TRIPO_ENDPOINTS[kind],
                                           payload(request, tokens)).get('task_id'))

    def query(self, remote_id):
        data = self.call('/tasks/' + api_common.task_id(remote_id))
        if data.get('task_id') != remote_id:
            raise TaskResultError('output_invalid')
        status = data.get('status')
        output = data.get('output') or {}
        if not isinstance(output, dict):
            raise TaskResultError('output_invalid')
        # V3 returns model_url; legacy keys allow recovery of tasks created in V2.
        files = []
        for key in ('model_url', 'model', 'pbr_model', 'base_model'):
            url = output.get(key)
            if url is None:
                continue
            if not isinstance(url, str) or not url.strip():
                raise TaskResultError('output_invalid')
            if url not in [entry['url'] for entry in files]:
                files.append({'label': key, 'url': url})
        if status == 'success' and not files:
            raise TaskResultError('output_invalid')
        return {'status': status, 'done': status == 'success', 'pending': status in ('queued', 'running'),
                'files': files, 'credit_consumed': data.get('credits_consumed',
                    data.get('consumed_credit', output.get('consumed_credit')))}

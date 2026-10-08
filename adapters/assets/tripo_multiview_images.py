"""Tripo v3 image-to-multiview: one input image, four reference image outputs."""
from pathlib import Path
import re
import uuid
from . import api_common, http_io, tripo_inputs, generation_capabilities
from .api_errors import TaskResultError

BASE = generation_capabilities.TRIPO_IMAGE_BASE
VIEWS = ('front', 'left', 'back', 'right')


def validate_images(paths):
    views = []
    for path in paths:
        match = re.fullmatch(r'\d{2}-(front|left|back|right)\.(png|jpe?g|webp)', path.name)
        if not match or not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Expected four nonempty labeled multiview images')
        with path.open('rb') as stream:
            header = stream.read(16)
        ext = path.suffix.lower()
        valid = ((ext == '.png' and header.startswith(b'\x89PNG\r\n\x1a\n')) or
                 (ext in ('.jpg', '.jpeg') and header.startswith(b'\xff\xd8\xff')) or
                 (ext == '.webp' and header[:4] == b'RIFF' and header[8:12] == b'WEBP'))
        if not valid:
            raise ValueError('Downloaded reference has an invalid image signature')
        views.append(match.group(1))
    if sorted(views) != sorted(VIEWS):
        raise ValueError('All four generated view images are required')


class Client:
    def __init__(self, settings):
        self.headers = {'Authorization': 'Bearer ' + api_common.credential(settings, 'api_key_env', 'TRIPO_API_KEY')}

    def call(self, path, payload=None, data=None, content_type=None):
        if data is None:
            value = http_io.json_request(BASE + path, payload, self.headers)
        else:
            value = http_io.json_bytes(BASE + path, data, {**self.headers, 'Content-Type': content_type})
        if value.get('code') != 0 or not isinstance(value.get('data'), dict):
            raise ValueError('Tripo image-to-multiview request was rejected; inspect provider console')
        return value['data']

    def submit(self, request):
        tripo_inputs.validate(request)
        if tripo_inputs.kind(request) != 'generate_multiview_image':
            raise ValueError('This client only generates multiview reference images')
        image, kind = api_common.image_input(request, 20 * 1024**2)
        if kind not in ('png', 'jpeg'):
            raise ValueError('The v3 file upload route supports PNG/JPEG images')
        boundary = 'OAGD' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="front.{kind}"\r\n'
                f'Content-Type: image/{kind}\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        uploaded = self.call('/files', data=body, content_type='multipart/form-data; boundary=' + boundary)
        token = uploaded.get('file_token')
        if not isinstance(token, str) or not token:
            raise ValueError('Tripo v3 upload did not return a file token')
        # The provider documents only input; local brief is never sent as prompt.
        result = self.call('/generation/image-to-multiview', {'input': token})
        return api_common.task_id(result.get('task_id'))

    def query(self, remote_id):
        data = self.call('/tasks/' + api_common.task_id(remote_id))
        if data.get('task_id') != remote_id:
            raise TaskResultError('output_invalid')
        status = data.get('status')
        output = data.get('output') or {}
        # Observed v3 response wraps the documented URL fields in this object.
        # Accept both the documented flat shape and the live nested shape.
        nested = output.get('generate_multiview_image')
        if isinstance(nested, dict):
            output = nested
        files = []
        for view in VIEWS:
            url = output.get(view + '_view_url')
            if isinstance(url, str) and url:
                files.append({'label': view, 'url': url})
        if status == 'success' and len(files) != 4:
            raise TaskResultError('output_invalid')
        return {'status': status, 'done': status == 'success', 'pending': status in ('queued', 'running'),
                'files': files, 'credit_consumed': data.get('credits_consumed', data.get('consumed_credit'))}

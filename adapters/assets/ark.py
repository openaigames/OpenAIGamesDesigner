"""Volcengine Ark: one image or one video per reviewed generation request."""
import base64
import json
from pathlib import Path
import re
import sys
from . import api_common, http_io, model_defaults

BASE = 'https://ark.cn-beijing.volces.com/api/v3'
DEFAULTS = {
    'seedream': {'model': model_defaults.SEEDREAM, 'size': '2K', 'watermark': True},
    'seedance': {'model': model_defaults.SEEDANCE, 'duration': 5, 'resolution': '720p',
                 'ratio': '16:9', 'generate_audio': True, 'watermark': True},
}


def prepare(provider, request):
    parameters = {**DEFAULTS[provider], **request.get('parameters', {})}
    prepared = {**request, 'parameters': parameters}
    validate_request(provider, prepared)
    return prepared


def validate_request(provider, request):
    p = request.get('parameters', {})
    allowed = set(DEFAULTS[provider]) | {'prompt'}
    if not isinstance(p, dict) or set(p) - allowed:
        raise ValueError('Only documented image/video generation parameters are accepted')
    p = {**DEFAULTS[provider], **p}
    if not isinstance(p.get('prompt'), str) or not 1 <= len(p['prompt'].strip()) <= 4000:
        raise ValueError('Prompt must contain 1..4000 characters')
    model = p['model']
    # Known model families keep parameter limits reviewable. Endpoint aliases are not guessed.
    pattern = r'doubao-seedream-(5-0-(pro|flash|lite)|4-5|4-0)-[0-9]{6}' if provider == 'seedream' else r'doubao-seedance-(2-5|2-0(?:-fast|-mini)?)-[0-9]{6}'
    if not isinstance(model, str) or not re.fullmatch(pattern, model):
        raise ValueError('Use a supported Seedream 4/5 or Seedance 2/2.5 Model ID from Ark')
    inputs = request.get('inputs', [])
    if not isinstance(inputs, list) or len(inputs) > 1:
        raise ValueError('This adapter accepts text plus at most one project reference image')
    for name in ('watermark', 'generate_audio'):
        if name in p and type(p[name]) is not bool:
            raise ValueError(name + ' must be boolean')
    if provider == 'seedream':
        sizes = ('1K', '1.5K', '2K') if '-5-0-pro-' in model or '-5-0-flash-' in model else (
            ('2K', '3K', '4K') if '-5-0-lite-' in model else ('2K', '4K') if '-4-5-' in model else ('1K', '2K', '4K'))
        if p['size'] not in sizes:
            raise ValueError('Image size is not supported by this Seedream model')
    else:
        maximum = 30 if '-2-5-' in model else 15
        if type(p['duration']) is not int or not 4 <= p['duration'] <= maximum:
            raise ValueError('Video duration must be an integer between 4 and ' + str(maximum))
        resolutions = ('480p', '720p') if '-fast-' in model or '-mini-' in model else ('480p', '720p', '1080p')
        if p['resolution'] not in resolutions or p['ratio'] not in ('16:9', '4:3', '1:1', '3:4', '9:16', '21:9', 'adaptive'):
            raise ValueError('Unsupported video resolution or aspect ratio')
        if inputs and '-2-5-' in model and p['ratio'] != 'adaptive':
            raise ValueError('Seedance 2.5 first-frame generation requires adaptive aspect ratio')


def image_kind(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if data.startswith(b'\xff\xd8\xff'): return 'jpeg'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'webp'
    raise ValueError('Expected PNG, JPEG or WebP image content')


def reference(request):
    data, kind = api_common.image_input(request, 10 * 1024**2)
    if image_kind(data) != kind:
        raise ValueError('Reference image contents do not match its extension')
    return 'data:image/' + kind + ';base64,' + base64.b64encode(data).decode('ascii')


def payload(provider, request):
    request = prepare(provider, request)
    p = dict(request['parameters'])
    if provider == 'seedream':
        p.update(response_format='url', stream=False)
        if '-5-0-pro-' not in p['model'] and '-5-0-flash-' not in p['model']:
            p['sequential_image_generation'] = 'disabled'
        if request.get('inputs'): p['image'] = reference(request)
    else:
        p['content'] = [{'type': 'text', 'text': p.pop('prompt')}]
        if request.get('inputs'):
            p['content'].append({'type': 'image_url', 'image_url': {'url': reference(request)}, 'role': 'first_frame'})
    return p


def command(provider, settings, request, output, result):
    api_common.settings_check(settings)
    return [sys.executable, '-B', str(Path(__file__).with_name('ark_worker.py')), '--provider', provider,
            '--settings', json.dumps(settings), '--request', str(request), '--output', str(output), '--result', str(result)]


def validate(paths, provider):
    if len(paths) != 1: raise ValueError('Expected exactly one generated artifact')
    path = paths[0]
    with path.open('rb') as stream: header = stream.read(32)
    if provider == 'seedream':
        kind = image_kind(header)
        if path.suffix.lower() not in ('.' + kind, '.jpg' if kind == 'jpeg' else '.' + kind):
            raise ValueError('Image file extension does not match content')
    elif path.suffix.lower() != '.mp4' or len(header) < 12 or header[4:8] != b'ftyp':
        raise ValueError('Expected an MP4 video container; playback must be checked separately')


class Client:
    def __init__(self, settings):
        self.headers = {'Authorization': 'Bearer ' + api_common.credential(settings, 'api_key_env', 'ARK_API_KEY')}

    def image(self, body):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        with http_io.open_url(BASE + '/images/generations', data,
                              {**self.headers, 'Content-Type': 'application/json'}, 'POST', timeout=300) as response:
            raw = response.read(16 * 1024**2 + 1)
        if len(raw) > 16 * 1024**2: raise ValueError('Ark image response exceeds the JSON size limit')
        result = json.loads(raw)
        items = result.get('data') if isinstance(result, dict) else None
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict) or not isinstance(items[0].get('url'), str):
            raise ValueError('Ark did not return one downloadable image; inspect the provider console')
        return items[0]['url']

    def submit_video(self, body):
        result = http_io.json_request(BASE + '/contents/generations/tasks', body, self.headers)
        return api_common.task_id(result.get('id'))

    def query_video(self, remote_id):
        result = http_io.json_request(BASE + '/contents/generations/tasks/' + api_common.task_id(remote_id), headers=self.headers)
        if result.get('id') != remote_id: raise ValueError('Ark returned a different video task ID')
        return result

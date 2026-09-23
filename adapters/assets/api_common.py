"""Configuration and worker entry for cloud 3D jobs."""
import json
import hashlib
import os
from pathlib import Path
import re
import sys
from . import credential_store


def settings_check(settings):
    allowed = {'mode', 'auth', 'api_key_env', 'secret_id_env', 'secret_key_env',
               'token_env', 'region', 'poll_seconds', 'max_download_bytes'}
    if settings.get('mode') != 'api' or set(settings) - allowed:
        raise ValueError('API configuration accepts named environment variables, not keys or command overrides')
    if settings.get('auth', 'tc3') not in ('tc3', 'api_key'):
        raise ValueError('Hunyuan auth must be tc3 or api_key')
    for key, value in settings.items():
        if key.endswith('_env') and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value)):
            raise ValueError('Credential fields must name environment variables')
    seconds = settings.get('poll_seconds', 5)
    if type(seconds) not in (int, float) or not 1 <= seconds <= 60:
        raise ValueError('poll_seconds must be 1..60')
    size = settings.get('max_download_bytes', 1024**3)
    if type(size) is not int or not 1 <= size <= 8 * 1024**3:
        raise ValueError('Invalid max_download_bytes')


def credential(settings, field, default, optional=False):
    name = settings.get(field, default)
    value = os.environ.get(name, '') or credential_store.get(name)
    if not value and not optional:
        raise ValueError('Missing credential; open settings_server.py or configure environment variable: ' + name)
    return value


def doctor(provider, settings):
    settings_check(settings)
    fields = [('api_key_env', 'TRIPO_API_KEY')] if provider == 'tripo' else (
        [('api_key_env', 'HUNYUAN3D_API_KEY')] if settings.get('auth') == 'api_key' else
        [('secret_id_env', 'TENCENTCLOUD_SECRET_ID'), ('secret_key_env', 'TENCENTCLOUD_SECRET_KEY')])
    credentials = [{'environment_variable': settings.get(field, default),
                    'present': bool(credential(settings, field, default, optional=True)),
                    'source': 'environment' if os.environ.get(settings.get(field, default)) else
                              'local_store' if credential_store.get(settings.get(field, default)) else 'missing'} for field, default in fields]
    region_ok = provider == 'tripo' or settings.get('auth') == 'api_key' or bool(settings.get('region'))
    return {'provider': provider, 'credentials': credentials, 'region_configured': region_ok,
            'ready_to_attempt': region_ok and all(c['present'] for c in credentials),
            'network_checked': False, 'generation_submitted': False}


def command(provider, settings, request, output, result):
    settings_check(settings)
    return [sys.executable, '-B', str(Path(__file__).with_name('api_worker.py')),
            '--provider', provider, '--settings', json.dumps(settings),
            '--request', str(request), '--output', str(output), '--result', str(result)]


def task_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Missing or invalid remote task ID')
    return value


def validate_request(provider, request, settings):
    settings_check(settings)
    params = request.get('parameters', {})
    # Only generation parameters are persisted. Authentication belongs in the environment.
    allowed = ({'type', 'prompt', 'model_version', 'negative_prompt', 'text_seed', 'model_seed',
                'texture_seed', 'image_seed', 'face_limit', 'auto_size', 'quad', 'texture', 'pbr',
                'texture_quality', 'texture_alignment', 'geometry_quality', 'export_uv', 'render_image',
                'style', 'orientation', 'smart_low_poly', 'generate_parts', 'enable_image_autofix'}
               if provider == 'tripo' else
               {'Model', 'Prompt', 'EnablePBR', 'FaceCount', 'GenerateType', 'PolygonType', 'ResultFormat'})
    if set(params) - allowed:
        raise ValueError('Unsupported API parameters; use documented generation fields and environment credentials')


def image_input(request, max_bytes):
    inputs = request.get('inputs', [])
    if len(inputs) != 1:
        raise ValueError('Image generation requires exactly one project input image')
    path = Path(inputs[0]['snapshot'])
    kind = path.suffix.lower().lstrip('.')
    kind = 'jpeg' if kind == 'jpg' else kind
    if kind not in ('jpeg', 'png', 'webp') or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError('Input must be PNG/JPEG/WebP within the provider size limit')
    data = path.read_bytes()
    expected = inputs[0].get('sha256')
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Input image changed after the generation request was prepared')
    return data, kind

"""ElevenLabs synchronous audio generation, bounded binary responses, no auto retry."""
import json
from pathlib import Path
import re
import sys
from . import api_common, audio_timing, http_io
from .audio_provider import validate
from . import model_defaults

BASE = 'https://api.elevenlabs.io/v1'
MODELS = {'sound_effect': (model_defaults.ELEVENLABS['sound_effect'],),
          'music': (model_defaults.ELEVENLABS['music'], 'music_v2', 'music_v1'),
          'speech': (model_defaults.ELEVENLABS['speech'], 'eleven_v3',
                     'eleven_multilingual_v2', 'eleven_flash_v2_5', 'eleven_turbo_v2_5')}


def validate_request(request):
    params = request.get('parameters', {})
    kind = params.get('kind')
    if kind not in MODELS: raise ValueError('Choose sound_effect, music or speech')
    allowed = {'kind', 'text', 'model_id'} | {
        'sound_effect': {'duration_seconds', 'loop', 'prompt_influence', 'timing'},
        'music': {'music_length_ms', 'force_instrumental'}, 'speech': {'voice_id'}}[kind]
    if set(params) - allowed: raise ValueError('Unsupported audio parameters')
    if not isinstance(params.get('text'), str) or not 1 <= len(params['text'].strip()) <= (4100 if kind == 'music' else 2500):
        raise ValueError('Supply a nonempty audio description or speech text within the input limit')
    if params.get('model_id', MODELS[kind][0]) not in MODELS[kind]: raise ValueError('Unsupported model for this audio type')
    for name in ('loop', 'force_instrumental'):
        if name in params and type(params[name]) is not bool: raise ValueError(name + ' must be boolean')
    if kind == 'sound_effect':
        if 'timing' in params:
            plan = audio_timing.timing_plan(params['timing'])
            if 'duration_seconds' in params or params.get('loop'):
                raise ValueError('A one-shot game window controls duration; do not combine it with duration_seconds or loop')
        else:
            audio_timing.number(params.get('duration_seconds'), 0.5, 30, 'duration_seconds')
        audio_timing.number(params.get('prompt_influence', 0.3), 0, 1, 'prompt_influence')
    if kind == 'music':
        if type(params.get('music_length_ms')) is not int: raise ValueError('music_length_ms must be an integer')
        audio_timing.number(params['music_length_ms'], 3000, 600000, 'music_length_ms')
    if kind == 'speech' and (not isinstance(params.get('voice_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', params['voice_id'])):
        raise ValueError('Supply an accessible ElevenLabs voice_id')
    inputs = request.get('inputs', [])
    timing = params.get('timing', {})
    expected = [timing['source']['path']] if timing.get('source') else []
    paths = [x.get('path') if isinstance(x, dict) else x for x in inputs]
    if paths != expected: raise ValueError('Only the linked timing configuration is accepted as an audio input; it stays local')


def payload(request):
    validate_request(request)
    p = request['parameters']; kind = p['kind']
    body = {'model_id': p.get('model_id', MODELS[kind][0])}
    if kind == 'sound_effect':
        body.update(text=p['text'], duration_seconds=p.get('duration_seconds'), loop=p.get('loop', False),
                    prompt_influence=p.get('prompt_influence', 0.3))
        if 'timing' in p:
            plan = audio_timing.timing_plan(p['timing'])
            body['duration_seconds'] = plan['generation_seconds']
            body['text'] += (f"\nSingle isolated game sound. Main gesture lasts {plan['body_seconds']:.4f} seconds, "
                             f"tail {plan['tail_seconds']:.4f} seconds. No extra hits or background music.")
        return '/sound-generation', body
    if kind == 'music':
        body.update(prompt=p['text'], music_length_ms=p['music_length_ms'], force_instrumental=p.get('force_instrumental', True))
        return '/music', body
    body['text'] = p['text']
    return '/text-to-speech/' + p['voice_id'], body


def command(settings, request, output, result):
    api_common.settings_check(settings)
    return [sys.executable, '-B', str(Path(__file__).with_name('elevenlabs_worker.py')),
            '--settings', json.dumps(settings), '--request', str(request), '--output', str(output), '--result', str(result)]


class Client:
    def __init__(self, settings):
        self.headers = {'xi-api-key': api_common.credential(settings, 'api_key_env', 'ELEVENLABS_API_KEY'),
                        'Content-Type': 'application/json', 'Accept': 'audio/mpeg'}
        self.limit = min(settings.get('max_download_bytes', 64 * 1024**2), 256 * 1024**2)

    def generate(self, request, target):
        endpoint, body = payload(request)
        partial = target.with_suffix('.part')
        if target.exists() or partial.exists(): raise ValueError('Audio response destination already exists')
        size = 0
        try:
            with http_io.open_url(BASE + endpoint + '?output_format=mp3_44100_128',
                    json.dumps(body, ensure_ascii=False).encode('utf-8'), self.headers, 'POST', timeout=600) as response:
                mime = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                if mime not in ('audio/mpeg', 'audio/mp3', 'application/octet-stream'):
                    raise ValueError('API did not return audio')
                declared = response.headers.get('Content-Length')
                if declared and (not declared.isdigit() or int(declared) > self.limit): raise ValueError('Invalid audio response size')
                with partial.open('xb') as stream:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk: break
                        size += len(chunk)
                        if size > self.limit: raise ValueError('Audio response exceeds size limit')
                        stream.write(chunk)
                if not size or (declared and size != int(declared)): raise ValueError('Incomplete audio response')
                with partial.open('rb') as stream: signature = stream.read(3)
                if not (signature == b'ID3' or (len(signature) >= 2 and signature[0] == 255 and signature[1] & 224 == 224)):
                    raise ValueError('Response is not MP3 audio')
                # Headers are observations only, never pollable jobs or executable instructions.
                receipt = {name: response.headers[name] for name in ('request-id', 'song-id', 'character-cost')
                           if isinstance(response.headers.get(name), str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', response.headers[name])}
            partial.rename(target)
            return {'headers': receipt, 'bytes': size, 'sha256': audio_timing.digest(target), 'output_format': 'mp3_44100_128'}
        finally:
            partial.unlink(missing_ok=True)

"""Game-window timing and non-destructive PCM editing; no perceptual approval."""
from array import array
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave


def number(value, low, high, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be a finite number in {low}..{high}')
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Audio source must be a project-relative path')
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Audio source escapes the project')
    return path


def read_window(root, source):
    if not isinstance(source, dict) or set(source) != {'path', 'pointer'}:
        raise ValueError('Timing source requires path and JSON pointer')
    path = local_path(root, source['path'])
    if path.stat().st_size > 4 * 1024**2:
        raise ValueError('Timing source exceeds 4 MiB')
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    pointer = source['pointer']
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('Use an RFC 6901 JSON pointer')
    try:
        for token in pointer.split('/')[1:] if pointer else []:
            token = token.replace('~1', '/').replace('~0', '~')
            value = value[int(token)] if isinstance(value, list) else value[token]
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('Timing source pointer was not found') from None
    window_seconds(value)
    return value


def window_seconds(window):
    if not isinstance(window, dict) or set(window) != {'start_seconds', 'end_seconds', 'play_rate'}:
        raise ValueError('Window requires start_seconds, end_seconds and constant play_rate')
    start = number(window['start_seconds'], 0, 3600, 'start_seconds')
    end = number(window['end_seconds'], 0, 3600, 'end_seconds')
    rate = number(window['play_rate'], 0.01, 100, 'play_rate')
    if end <= start:
        raise ValueError('Window end must be after its start')
    return (end - start) / rate


def timing_plan(timing):
    if not isinstance(timing, dict) or set(timing) - {'event', 'window', 'source', 'tail_seconds',
            'trim_start_seconds', 'fade_in_seconds', 'fade_out_seconds', 'fit'}:
        raise ValueError('Unsupported timing fields')
    event = timing.get('event')
    if not isinstance(event, str) or not 1 <= len(event.strip()) <= 160:
        raise ValueError('Timing requires the gameplay event name')
    body = window_seconds(timing.get('window'))
    tail = number(timing.get('tail_seconds', 0), 0, 10, 'tail_seconds')
    target = number(body + tail, 0.001, 30, 'window plus tail')
    trim = number(timing.get('trim_start_seconds', 0), 0, 30, 'trim_start_seconds')
    fade_in = number(timing.get('fade_in_seconds', min(0.002, target / 2)), 0, target / 2, 'fade_in_seconds')
    fade_out = number(timing.get('fade_out_seconds', min(0.008, target / 2)), 0, target / 2, 'fade_out_seconds')
    if type(timing.get('fit', True)) is not bool:
        raise ValueError('fit must be boolean')
    return {'event': event, 'body_seconds': body, 'tail_seconds': tail, 'target_seconds': target,
            'generation_seconds': max(0.5, target), 'trim_start_seconds': trim,
            'fade_in_seconds': fade_in, 'fade_out_seconds': fade_out, 'fit': timing.get('fit', True),
            'timebase': 'animation_seconds / constant_play_rate; tail in real seconds',
            'source_status': 'linked' if timing.get('source') else 'manual_unverified'}


def prepare(root, request):
    request = copy.deepcopy(request)
    timing = request.get('parameters', {}).get('timing')
    if timing is not None:
        if not isinstance(timing, dict):
            raise ValueError('timing must be an object')
        if 'source' in timing:
            window = read_window(root, timing['source'])
            if 'window' in timing and timing['window'] != window:
                raise ValueError('Timing source changed; prepare a fresh request')
            timing['window'] = window
            inputs = request.setdefault('inputs', [])
            name = timing['source']['path']
            if name not in [x.get('path') if isinstance(x, dict) else x for x in inputs]:
                inputs.append(name)
        timing_plan(timing)
    return request


def check_source(root, request):
    timing = request['parameters'].get('timing') or {}
    source = timing.get('source')
    if not source:
        return 'manual_unverified' if timing else 'not_linked'
    entries = [x for x in request['inputs'] if x['path'] == source['path']]
    if (len(entries) != 1 or digest(local_path(root, source['path'])) != entries[0]['sha256']
            or read_window(root, source) != timing['window']):
        raise ValueError('Game timing changed; prepare and review a new audio request')
    return 'current'


def ffmpeg_executable():
    executable = os.environ.get('OAGD_FFMPEG') or shutil.which('ffmpeg')
    if not executable:
        try:
            import imageio_ffmpeg
            executable = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            pass
    if not executable or not Path(executable).is_absolute() or not Path(executable).is_file():
        raise ValueError('Audio decoding needs FFmpeg on PATH, OAGD_FFMPEG, or imageio-ffmpeg in this Python')
    try:
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        check = subprocess.run([str(executable), '-version'], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=10, **flags)
        if check.returncode: raise ValueError('FFmpeg could not start')
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('FFmpeg could not start') from None
    return str(executable)


def decode(source, target):
    """Retain channel count and sample rate; decode only local audio into PCM16 WAV."""
    if target.exists():
        raise ValueError('Decoded destination exists')
    if source.suffix.lower() != '.mp3': raise ValueError('Use an MP3 source for this decoder')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([ffmpeg_executable(), '-nostdin', '-v', 'error', '-n',
        '-protocol_whitelist', 'file,pipe', '-f', 'mp3', '-i', str(source), '-map', '0:a:0', '-vn',
        '-c:a', 'pcm_s16le', '-t', '660', str(target)], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=180, **flags)
    if result.returncode:
        target.unlink(missing_ok=True)
        raise ValueError('Audio could not be decoded; original response was retained')
    return inspect(target)


def read_pcm(path):
    if Path(path).stat().st_size > 256 * 1024**2:
        raise ValueError('Audio exceeds local processing limit')
    with wave.open(str(path), 'rb') as sound:
        channels, rate, frames = sound.getnchannels(), sound.getframerate(), sound.getnframes()
        if sound.getsampwidth() != 2 or not 1 <= channels <= 8 or not 8000 <= rate <= 192000 or not 0 < frames <= rate * 660:
            raise ValueError('Use PCM16 WAV, 1..8 channels, 8..192 kHz, at most 660 seconds')
        data = sound.readframes(frames)
    if len(data) != frames * channels * 2:
        raise ValueError('Truncated WAV')
    samples = array('h', data)
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples, channels, rate


def inspect(path):
    samples, channels, rate = read_pcm(path)
    peak = 0; peak_index = None; first = None; last = None; squares = 0; clips = 0
    # -60 dBFS is a diagnostic threshold, not an audible-onset acceptance rule.
    threshold = 32768 * 0.001
    for i, sample in enumerate(samples):
        absolute = abs(sample); squares += sample * sample
        if absolute > peak: peak = absolute; peak_index = i // channels
        if absolute >= 32767: clips += 1
        if absolute >= threshold:
            if first is None: first = i // channels
            last = i // channels
    return {'duration_seconds': len(samples) / channels / rate, 'sample_rate': rate, 'channels': channels,
            'peak_dbfs': 20 * math.log10(peak / 32768) if peak else None,
            'rms_dbfs': 10 * math.log10(squares / len(samples) / 32768**2) if squares else None,
            'threshold_dbfs': -60, 'signal_start_seconds': first / rate if first is not None else None,
            'signal_end_seconds': (last + 1) / rate if last is not None else None,
            'peak_seconds': peak_index / rate if peak_index is not None else None,
            'clipped_samples': clips, 'silent': first is None, 'listening_validation': 'not_checked'}


def fit(source, target, timing):
    plan = timing_plan(timing)
    samples, channels, rate = read_pcm(source)
    start = round(plan['trim_start_seconds'] * rate)
    count = max(1, round(plan['target_seconds'] * rate))
    total = len(samples) // channels
    if start >= total: raise ValueError('Trim start is outside the source audio')
    if Path(target).exists(): raise ValueError('Output exists; choose a new revision')
    kept = samples[start * channels:(start + count) * channels]
    padded = max(0, count - len(kept) // channels)
    kept.extend(array('h', [0]) * (padded * channels))
    fades = (round(plan['fade_in_seconds'] * rate), round(plan['fade_out_seconds'] * rate))
    for frame in range(count):
        gain = min(1, frame / max(1, fades[0] - 1)) if fades[0] else 1
        if fades[1]: gain = min(gain, (count - 1 - frame) / max(1, fades[1] - 1), 1)
        if gain < 1:
            for channel in range(channels):
                index = frame * channels + channel
                kept[index] = round(kept[index] * gain)
    if sys.byteorder != 'little': kept.byteswap()
    with Path(target).open('xb') as stream, wave.open(stream, 'wb') as sound:
        sound.setnchannels(channels); sound.setsampwidth(2); sound.setframerate(rate); sound.writeframes(kept.tobytes())
    return {**plan, 'source_sha256': digest(source), 'output_sha256': digest(target),
            'trimmed_end_frames': max(0, total - start - count), 'padded_frames': padded,
            'pitch_changed': False, 'time_stretched': False, 'measurement': inspect(target),
            'quality_validation': 'not_checked'}

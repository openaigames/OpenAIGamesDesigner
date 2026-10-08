#!/usr/bin/env python3
"""Download one authorized audio response, preserve raw audio and make a timed revision."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.assets import api_common, audio_timing, elevenlabs, generation_approval


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def run(settings, request, output, result):
    api_common.settings_check(settings)
    elevenlabs.validate_request(request)
    audio_timing.ffmpeg_executable()  # Fail before spending credits when decoding is unavailable.
    approval = request.get('_approval') or {}
    project, job_id = approval.get('project'), approval.get('job_id')
    if not project or not job_id: raise ValueError('A reviewed asset job is required')
    audio_timing.check_source(project, request)
    client = elevenlabs.Client(settings)
    state = result.with_name('remote.json')
    if state.exists(): raise ValueError('This attempt may already have submitted; do not submit again')
    fingerprint = generation_approval.identity(project, job_id, 'elevenlabs', settings, request)
    generation_approval.require(fingerprint, consume=True)
    record = {'provider': 'elevenlabs', 'provider_job_id': None, 'status': 'submitting',
              'resumable': False, 'note': 'Synchronous response; request IDs cannot resume a generation. Never auto-resubmit.'}
    save(state, record)
    raw = output / 'original.mp3'
    receipt = client.generate(request, raw)
    record.update(status='response_saved', receipt=receipt)
    save(state, record)
    decoded = output / 'decoded.wav'
    measurement = audio_timing.decode(raw, decoded)
    files = [raw, decoded]
    observations = {'provider': 'elevenlabs', 'receipt': receipt, 'measurement': measurement,
                    'quality_validation': 'not_checked', 'license_validation': 'not_checked'}
    timing = request['parameters'].get('timing')
    if timing:
        observations['timing_plan'] = audio_timing.timing_plan(timing)
        if observations['timing_plan']['fit']:
            fitted = output / 'window.wav'
            observations['timing_fit'] = audio_timing.fit(decoded, fitted, timing)
            files.append(fitted)
    save(result, {'provider_job_id': None, 'artifacts': [{'path': p.name} for p in files], 'observations': observations})
    record['status'] = 'completed'; save(state, record)
    print('Audio saved; listening, event alignment, engine playback and license checks remain unverified.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('settings', 'request', 'output', 'result'): parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        run(json.loads(args.settings), json.loads(Path(args.request).read_text(encoding='utf-8')),
            Path(args.output), Path(args.result))
        return 0
    except Exception:
        # Provider bodies, URLs, prompts and credential-bearing exceptions must not enter logs.
        print('Audio task did not complete. Inspect local remote.json and provider console. Do not automatically submit again.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())

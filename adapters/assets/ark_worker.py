"""One authorized Ark submission; video resumes only by recorded task ID."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.assets import ark, api_common, generation_approval, http_io


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def run(provider, settings, request, output, result):
    api_common.settings_check(settings)
    ark.validate_request(provider, request)
    remote = result.with_name('remote.json')
    if remote.exists(): raise ValueError('Attempt already exists; recover it instead of submitting again')
    remote_id = request.get('provider_job_id')
    if provider == 'seedream' and remote_id:
        raise ValueError('Seedream synchronous generation cannot resume by task ID')
    # Validate and read snapshots before consuming approval or spending credits.
    body = None if remote_id else ark.payload(provider, request)
    client = ark.Client(settings)
    if remote_id:
        api_common.task_id(remote_id)
    else:
        approval = request.get('_approval') or {}
        if not approval.get('project') or not approval.get('job_id'):
            raise ValueError('A reviewed asset job is required')
        fingerprint = generation_approval.identity(approval['project'], approval['job_id'], provider, settings, request)
        generation_approval.require(fingerprint, consume=True)
    state = {'provider': provider, 'provider_job_id': remote_id, 'status': 'submitted' if remote_id else 'submitting',
             'resumable': provider == 'seedance'}
    save(remote, state)
    if provider == 'seedream':
        url = client.image(body)
        # Keep the expiring URL out of logs and project JSON. Failure requires manual inspection, never an automatic POST.
        save(remote, {**state, 'status': 'response_received', 'resumable': False})
        temporary = output / 'image.download'
        http_io.download(url, temporary, settings.get('max_download_bytes', 64 * 1024**2))
        with temporary.open('rb') as stream: kind = ark.image_kind(stream.read(32))
        target = output / ('image.' + ('jpg' if kind == 'jpeg' else kind))
        temporary.rename(target)
        observations = {'provider': provider, 'quality_validation': 'not_checked'}
    else:
        if not remote_id: remote_id = client.submit_video(body)
        state.update(provider_job_id=remote_id, status='submitted')
        save(remote, state)
        while True:
            report = client.query_video(remote_id)
            status = report.get('status')
            if status not in ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'expired'):
                raise ValueError('Unrecognized remote task status')
            state['status'] = status; save(remote, state)
            if status == 'succeeded': break
            if status not in ('queued', 'running'): raise ValueError('Video task stopped without success; inspect provider console')
            time.sleep(settings.get('poll_seconds', 5))
        content = report.get('content') or {}
        url = content.get('video_url')
        if not isinstance(url, str): raise ValueError('Successful task did not return a video URL')
        target = output / 'video.mp4'
        http_io.download(url, target, settings.get('max_download_bytes', 1024**3))
        observations = {'provider': provider, 'remote_status': 'succeeded', 'quality_validation': 'not_checked',
                        'playback_validation': 'not_checked'}
        for name in ('duration', 'resolution', 'ratio'):
            value = report.get(name)
            if isinstance(value, (int, float, str)) and len(str(value)) < 64: observations[name] = value
    ark.validate([target], provider)
    save(result, {'provider_job_id': remote_id, 'artifacts': [{'path': target.name}], 'observations': observations})
    state.update(status='completed', provider_job_id=remote_id); save(remote, state)
    print('Asset downloaded. Game integration and visual quality have not been verified.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['seedream', 'seedance'], required=True)
    for name in ('settings', 'request', 'output', 'result'): parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        run(args.provider, json.loads(args.settings), json.loads(Path(args.request).read_text('utf-8')),
            Path(args.output), Path(args.result))
        return 0
    except Exception:
        # Do not expose provider bodies, credentials, private prompts or signed URLs.
        print('Ark task did not complete. Inspect remote.json and the provider console; do not automatically resubmit.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())

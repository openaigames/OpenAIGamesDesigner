"""One remote task per attempt; the parent process owns timeout/cancellation."""
import argparse
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.assets import api_common, http_io, tripo, hunyuan_api, hunyuan3d
from adapters.assets import generation_approval
from adapters.assets.archive_io import extract_zip


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def run(provider, settings, request, output, result_path):
    api_common.validate_request(provider, request, settings)
    client = (tripo.Client if provider == 'tripo' else hunyuan_api.Client)(settings)
    remote_path = result_path.with_name('remote.json')
    remote_id = request.get('provider_job_id')
    if remote_id:
        api_common.task_id(remote_id)
    else:
        context = request.get('_approval') or {}
        if not context.get('project') or not context.get('job_id'):
            raise ValueError('Start new API generation through an approved asset workflow job')
        fingerprint = generation_approval.identity(context['project'], context['job_id'], provider, settings, request)
        generation_approval.require(fingerprint, consume=True)
        # If the response is lost, never automatically send this POST again.
        save(remote_path, {'provider': provider, 'status': 'submitting', 'provider_job_id': None})
        remote_id = client.submit(request)
    state = {'provider': provider, 'provider_job_id': remote_id, 'status': 'submitted'}
    save(remote_path, state)
    print('Remote task recorded; polling.', flush=True)
    while True:
        report = client.query(remote_id)
        state['status'] = report['status']
        save(remote_path, state)
        if report['done']:
            break
        if not report['pending']:
            raise ValueError('Remote task is not running or successful; inspect provider console')
        time.sleep(settings.get('poll_seconds', 5))
    files, seen = [], set()
    for index, entry in enumerate(report['files']):
        url = entry['url']
        if url in seen:
            continue
        seen.add(url)
        suffix = Path(urlsplit(url).path).suffix.lower()
        if suffix not in hunyuan3d.EXTENSIONS:
            raise ValueError('Unknown model download format; inspect provider output')
        label = re.sub(r'[^a-zA-Z0-9_-]', '_', entry['label'])[:50]
        target = output / f'{index:02d}-{label}{suffix}'
        http_io.download(url, target, settings.get('max_download_bytes', 1024**3))
        files.append(target)
        if suffix == '.zip':
            if not zipfile.is_zipfile(target):
                raise ValueError('Model archive is not a ZIP file')
            files.extend(extract_zip(target, output / f'{index:02d}-{label}'))
    hunyuan3d.validate(files)
    save(result_path, {'provider_job_id': remote_id,
                       'artifacts': [{'path': p.relative_to(output).as_posix()} for p in files],
                       'observations': {'provider': provider, 'remote_status': report['status'],
                                        'credit_consumed': report['credit_consumed'],
                                        'quality_validation': 'not_checked'}})
    print('Model files downloaded; engine import and quality checks are pending.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['tripo', 'hunyuan3d'], required=True)
    for name in ('settings', 'request', 'output', 'result'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        run(args.provider, json.loads(args.settings), json.loads(Path(args.request).read_text(encoding='utf-8')),
            Path(args.output), Path(args.result))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        # No exception/body/URL dump: providers can echo private prompts or keys.
        print('API task did not complete. Check credential configuration and provider console; remote.json retains recovery state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

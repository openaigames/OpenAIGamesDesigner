"""One-use local approval receipts, bound to one queued cloud generation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from contextlib import contextmanager
from . import credential_store, api_common


def identity(project, job_id, provider, settings, request):
    # Bind the actual credential, without persisting or exposing its value/hash separately.
    fields = api_common.credential_fields(provider, settings)
    keys = [api_common.credential(settings, field, default) for field, default in fields]
    value = {'project': os.path.normcase(str(Path(project).resolve())), 'job_id': job_id, 'provider': provider,
             'settings': settings, 'parameters': request['parameters'],
             'inputs': [{k: entry[k] for k in ('path', 'sha256', 'view') if k in entry} for entry in request.get('inputs', [])],
             'credentials': keys}
    if 'brief' in request:value['brief']=request['brief']
    if request.get('lineage'):value['lineage']=request['lineage']
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def _path(fingerprint):
    if len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
        raise ValueError('Invalid generation fingerprint')
    suffix = '.dpapi' if credential_store.available() else '.json'
    return credential_store.store_path().parent / 'generation-approvals' / (fingerprint + suffix)


@contextmanager
def _locked():
    if credential_store.available():
        with credential_store._locked(): yield
    else:
        import fcntl
        directory = credential_store.store_path().parent / 'generation-approvals'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / '.lock').open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)


def _read(fingerprint):
    path = _path(fingerprint)
    if not path.exists(): return None
    try:
        if path.stat().st_size > 8192: raise ValueError()
        data = path.read_bytes()
        return json.loads(credential_store._crypt(data, True) if credential_store.available() else data)
    except (OSError, ValueError, TypeError):
        raise ValueError('Generation approval cannot be read') from None


def _write(fingerprint, record):
    path = _path(fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record).encode('utf-8')
    encrypted = credential_store._crypt(encoded) if credential_store.available() else encoded
    fd, temporary = tempfile.mkstemp(prefix='approval-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream: stream.write(encrypted)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check_storage():
    """Probe the same user store and lock without creating an approval receipt."""
    with _locked():
        directory = credential_store.store_path().parent / 'generation-approvals'
        directory.mkdir(parents=True, exist_ok=True)
        probe = b'approval-storage-check'
        if credential_store.available():
            probe = credential_store._crypt(probe)
            if credential_store._crypt(probe, True) != b'approval-storage-check':
                raise ValueError('Generation approval protection is unavailable')
        with tempfile.TemporaryFile(prefix='approval-check-', suffix='.tmp', dir=directory) as stream:
            stream.write(probe); stream.flush(); stream.seek(0)
            if stream.read() != probe:
                raise OSError('Generation approval storage is unavailable')


def approve(fingerprint):
    with _locked():
        previous = _read(fingerprint)
        if previous and previous.get('state') == 'consumed':
            raise ValueError('This task already used its authorization; recover the cloud task or create a new task')
        _write(fingerprint, {'version': 1, 'fingerprint': fingerprint, 'state': 'approved',
                             'approved_at': time.time(), 'expires_at': time.time() + 3600})


def require(fingerprint, consume=False):
    with _locked():
        value = _read(fingerprint)
        if (not value or value.get('version') != 1 or value.get('fingerprint') != fingerprint
                or value.get('state') != 'approved' or value.get('expires_at', 0) < time.time()):
            raise ValueError('User approval required: open settings_server.py --project <project> --approve-job <job-id>; no generation was submitted')
        if consume:
            value.update(state='consumed', consumed_at=time.time())
            _write(fingerprint, value)


def for_job(project, job):
    from . import model_prompt_policy
    if job.get('status') == 'queued':
        model_prompt_policy.require(job['provider'], job['request'], job['settings'], project)
    if job['provider'] not in ('tripo', 'hunyuan3d', 'elevenlabs', 'seedream', 'seedance') or job['settings'].get('mode') != 'api' or job['status'] != 'queued':
        raise ValueError('Approval is for a queued API generation')
    if job['provider'] in ('seedream', 'seedance', 'hunyuan3d', 'tripo'):
        api_common.validate_request(job['provider'], job['request'], job['settings'])
    if job['provider'] == 'elevenlabs':
        from . import audio_timing
        api_common.validate_request('elevenlabs', job['request'], job['settings'])
        audio_timing.check_source(project, job['request'])
    return identity(project, job['job_id'], job['provider'], job['settings'], job['request'])

"""Shared project-local record IO, immutable evidence and optimistic updates."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('Expected a 1..64 character identifier (letters, digits, - or _).')
    return value


def local(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or ':' in relative or '\x00' in relative:
        raise ValueError('Expected a project-relative path.')
    relative = relative.replace('\\', '/')
    if relative.startswith('/') or '..' in relative.split('/'):
        raise ValueError('Path must remain in the project.')
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Path escapes project through a link.')
    return path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Record is larger than 16 MiB.')
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(path.read_text('utf-8-sig'), parse_constant=invalid_constant)


def write_json(path, value, *, create=False):
    path = Path(path)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if create:
        # Exclusive creation keeps existing evidence immutable.
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        return
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def project_lock(root, name='task-state'):
    path = local(root, '.openaigame/' + identifier(name) + '.lock')
    token = uuid.uuid4().hex
    try:
        write_json(path, {'pid':os.getpid(), 'token':token, 'created_at':now()}, create=True)
    except FileExistsError as error:
        raise ValueError('Another writer or interrupted operation holds ' + str(path) +
                         '; inspect the recorded process before recovering the lock.') from error
    try:
        yield
    finally:
        if path.exists() and read_json(path).get('token') == token:
            path.unlink()


def snapshot_files(root, paths):
    if not isinstance(paths, list) or len(paths) > 4096 or len(set(paths)) != len(paths):
        raise ValueError('Expected up to 4096 distinct project-relative files.')
    files = {}
    for relative in paths:
        path = local(root, relative)
        if not path.is_file():
            raise ValueError('Missing dependency: ' + relative)
        files[path.relative_to(Path(root).resolve()).as_posix()] = digest(path)
    return files


def changed_files(root, dependencies):
    changes = []
    for relative, expected in dependencies.items():
        try:
            path = local(root, relative)
            if not path.is_file() or digest(path) != expected:
                changes.append(relative)
        except (OSError, ValueError):
            changes.append(relative)
    return changes


def recover_lock(root, name, token, reason, evidence):
    """Release only an inspected dead writer's unchanged lock; never replay work."""
    from adapters.engines.sessions import process_alive
    if not isinstance(reason,str) or not reason.strip() or not evidence:raise ValueError('Lock recovery requires an actual inspection and evidence files')
    path=local(root,'.openaigame/'+identifier(name)+'.lock')
    previous=read_json(path)
    if previous.get('token')!=token:raise ValueError('Lock identity changed; inspect again')
    if type(previous.get('pid')) is not int or previous['pid']<=0:raise ValueError('Lock has no verifiable writer PID')
    if process_alive(previous['pid']):raise ValueError('Writer is still alive; do not remove its lock')
    record={'schema_version':1,'lock':previous,'reason':reason,'evidence':snapshot_files(root,evidence),'recovered_at':now(),
            'action':'remove dead unchanged lock only; no step retried'}
    out=local(root,'.openaigame/recovery/lock-'+uuid.uuid4().hex+'.json')
    write_json(out,record,create=True)
    if read_json(path)!=previous:raise ValueError('Lock changed during inspection; it was not removed')
    path.unlink()
    return {'receipt':out.relative_to(Path(root).resolve()).as_posix(),'released':name,'work_replayed':False}

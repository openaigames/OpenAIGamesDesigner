"""Engine-neutral sessions, process ownership, evidence, checkpoints and recovery."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

IGNORED = {'.git', 'Library', 'Temp', 'Logs', 'obj', 'Binaries', 'Intermediate',
           'Saved', 'DerivedDataCache', '__pycache__', '.vs'}




def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inside(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()) or p == root.resolve():
        raise ValueError('Path must be a child of ' + str(root))
    return p


def inventory(root):
    result = {}
    if not root.exists():
        return result
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED]
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Production snapshots do not follow links: ' + str(path))
        for name in files:
            p = Path(directory) / name
            result[p.relative_to(root).as_posix()] = digest(p)
    return result


def checkpoint(root, destination):
    before = inventory(root)
    for relative, expected in before.items():
        source, target = inside(root, relative), inside(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != expected:
            raise ValueError('Project changed during checkpoint: ' + relative)
    if inventory(root) != before:
        raise ValueError('Project changed during checkpoint; retry when idle')
    return before


def matching_editors(project, editor_names=()):
    """Read process identity, not window titles; never terminate unrelated editors."""
    if os.name != 'nt':
        raise ValueError('This production runner currently requires Windows process identity checks')
    if not editor_names:
        raise ValueError('Engine driver must supply editor process names')
    if any(not name or not all(c.isalnum() or c in '.-_' for c in name) for name in editor_names):
        raise ValueError('Invalid editor process name')
    names=','.join("'"+name+"'" for name in editor_names)
    command = ("[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $ErrorActionPreference='Stop'; "
               "Get-CimInstance Win32_Process | Where-Object { $_.Name -in @("+names+") } | "
               "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Process identity query failed; run with read access to Win32_Process: ' + result.stderr)
    entries = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(entries, dict):
        entries = [entries]
    project_text = str(project.resolve()).replace('\\', '/').lower()
    matches = []
    for row in entries:
        if not row.get('CommandLine'):
            raise ValueError('Cannot read an editor process command line; cannot verify project ownership')
        line = row['CommandLine'].replace('\\', '/').lower()
        if project_text in line:
            matches.append(row)
    return matches


def ensure_idle(project, editor_names=()):
    matches = matching_editors(project, editor_names)
    if matches:
        raise ValueError('Close this project editor before batch writes: ' + json.dumps(matches))


def process_alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:  # invalid PID: process no longer exists
                return False
            raise ValueError('Cannot verify session process ' + str(pid))
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ValueError('Cannot read session process exit status')
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def ensure_stopped(record):
    for key in ['owner_pid', 'pid']:
        if process_alive(record.get(key)):
            raise ValueError('Session process is still alive; do not recover or restore: ' + str(record[key]))


def run(argv, cwd, log, timeout, session, record):
    with log.open('wb') as stream:
        process = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        record.update(pid=process.pid, argv=argv, started=time.time(), status='running')
        write(session / 'session.json', record)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                process.kill()
            process.wait(timeout=30)
            raise ValueError('Engine timed out; native completion alone is not a successful session')
    record['exit_code'] = code
    if code:
        raise ValueError('Engine exited with code ' + str(code) + '; see ' + str(log))


def restore(project, session, editor_names=()):
    """Explicit rollback only; preserve new files in quarantine, refuse later edits."""
    record = read(session / 'session.json')
    if record.get('project') != str(project.resolve()):
        raise ValueError('Session belongs to another project')
    if record.get('status') in {'running', 'interrupted', 'restored'} or 'after' not in record:
        raise ValueError('Reconcile interrupted session before restore; restored sessions cannot be replayed')
    ensure_stopped(record)
    ensure_idle(project, editor_names)
    if inventory(project) != record['after']:
        raise ValueError('Project changed since this session; refusing to overwrite subsequent work')
    before, after = record['before'], record['after']
    for rel, value in before.items():
        if digest(inside(session / 'before', rel)) != value:
            raise ValueError('Checkpoint missing or corrupt: ' + rel)
    quarantine = session / ('displaced-' + uuid.uuid4().hex[:8])
    record['status'] = 'restoring'
    write(session / 'session.json', record)
    for rel in sorted(set(before) | set(after)):
        if before.get(rel) == after.get(rel):
            continue
        target = inside(project, rel)
        if target.exists():
            saved = inside(quarantine, rel)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(saved))
        if rel in before:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inside(session / 'before', rel), target)
    if inventory(project) != before:
        raise ValueError('Restore verification failed; inspect checkpoint and displaced files')
    record.update(status='restored', restored=time.time(), displaced=str(quarantine))
    write(session / 'session.json', record)


def native_result(session, project, engine, request_id):
    result = read(session / 'result.json')
    if (result.get('success') is not True or result.get('engine') != engine
            or result.get('request_id') != request_id
            or Path(result.get('project', '')).resolve() != project.resolve()
            or not result.get('version')):
        raise ValueError('Native result failed or identity mismatch: ' + str(result))
    return result


def execute(root, project, config, driver, request_path, timeout, related=None):
    request = read(request_path)
    driver.validate_request(request)
    related = related or {}
    for value in related.values():
        if Path(value).is_absolute() or not inside(root, value).is_file():
            raise ValueError('Related task/milestone record missing: ' + value)
    if request.get('mode') == 'playback':
        request['actions'] = sorted(request.get('actions', []), key=lambda a: a['at'])
    ensure_idle(project, driver.EDITOR_NAMES)
    sessions = root / 'runs'
    session = sessions / ('engine-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    session.mkdir(parents=True)
    lock = inside(root, '.openaigame/engine-production.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('x', encoding='utf-8') as f:
        f.write(str(session))
    record = {'schema_version': 1, 'project': str(project), 'engine': config['engine'],
              'owner_pid': os.getpid(),
              'related_records': related,
              'status': 'checkpointing', 'request_source': str(request_path.resolve()),
              'gameplay_validation': 'not_run', 'visual_validation': 'not_run'}
    write(session / 'session.json', record)
    try:
        record['before'] = checkpoint(project, session / 'before')
        input_files = [request_path.resolve()] + driver.input_files(request)
        record['input_hashes'] = {str(path): digest(path) for path in input_files}
        worker_files = driver.worker_files()
        record['worker_hashes'] = {str(path): digest(path) for path in worker_files}
        request.update(request_id=session.name, project=str(project), report=str(session / 'result.json'),
                       session=str(session))
        write(session / 'session.json', record)
        write(session / 'request.json', request)
        record['editor_names'] = list(driver.EDITOR_NAMES)
        record['native_result'] = driver.launch(config, project, session, request, timeout, record)
        record['status'] = 'completed'
        if any(not Path(path).is_file() or digest(Path(path)) != expected for path,expected in record['input_hashes'].items()):
            record.update(status='needs_review', input_changed_during_run=True)
        errors = driver.log_errors(session)
        if errors:
            record.update(status='needs_review', engine_log_errors=errors[:100])
    except BaseException as error:
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise
    finally:
        record.update(finished=time.time(), after=inventory(project))
        record['evidence_hashes'] = {str(path.relative_to(session)):digest(path)
            for path in session.rglob('*') if path.is_file() and path.suffix in {'.json','.jsonl','.csv','.log','.png'}
            and path.name!='session.json' and not path.is_relative_to(session / 'before') and not any(path.is_relative_to(session / name) for name in driver.EVIDENCE_EXCLUSIONS)}
        write(session / 'session.json', record)
        # Interrupted orchestration can leave an engine alive; preserve the lock then.
        if not matching_editors(project, driver.EDITOR_NAMES):
            lock.unlink(missing_ok=True)
    return session


def recover(root, project, driver, session_name, restore_requested=False):
    session = inside(root / 'runs', session_name)
    record = read(session / 'session.json')
    if record.get('project') != str(project):
        raise ValueError('Wrong session project identity')
    if record.get('engine') != driver.ENGINE:
        raise ValueError('Session engine does not match configured engine')
    ensure_stopped(record)
    ensure_idle(project, driver.EDITOR_NAMES)
    lock = root / '.openaigame/engine-production.lock'
    if lock.exists() and Path(lock.read_text(encoding='utf-8')).resolve() != session.resolve():
        raise ValueError('Another session owns the project lock')
    if restore_requested:
        restore(project, session, driver.EDITOR_NAMES)
    else:
        if record.get('status') not in {'running', 'interrupted', 'checkpointing', 'failed'}:
            raise ValueError('Only interrupted or failed sessions can be reconciled')
        if 'before' not in record:
            raise ValueError('No complete checkpoint; inspect partial creation manually')
        record.update(status='needs_review', after=inventory(project), reconciled=time.time())
        write(session / 'session.json', record)
    lock.unlink(missing_ok=True)
    return session

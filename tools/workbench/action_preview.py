"""Local test-scene mailbox. Never launches commands or writes gameplay config."""
import copy
import time
import uuid
import record_io
from . import action_edit as edit, action_review as review

PREFIX = '.openaigame/action-preview'
PROTOCOL = 'action-preview/1'
STALE_SECONDS = 4


def location(root, key):
    entry = edit.entry(root, key)
    preview = entry.get('preview')
    if not isinstance(preview, dict) or preview.get('protocol') != PROTOCOL:
        raise ValueError('此动作尚未接入原生测试场景；仍可使用实机参考录像')
    consumer = edit.identifier(preview.get('consumer'))
    return entry, review.contained(root, PREFIX + '/' + consumer)


def read_optional(path):
    # Godot's Windows rename briefly unlinks the old destination. Never turn that
    # narrow replacement window into a disconnect or a mismatched configuration.
    for attempt in range(5):
        try:
            return review.read_json(path)[0]
        except (FileNotFoundError, PermissionError):
            if attempt < 4:
                time.sleep(.005)
    return {}


def engine(root, key):
    entry, base = location(root, key)
    ready = read_optional(base / 'ready.json')
    stamp = ready.get('updated_at')
    if stamp is None and ready:
        try: stamp = (base / 'ready.json').stat().st_mtime
        except FileNotFoundError: stamp = 0
    online = (ready.get('schema') == PROTOCOL and ready.get('engine') == entry['engine']
              and key in ready.get('actions', [])
              and -1 <= time.time() - stamp <= STALE_SECONDS) if ready else False
    if online:
        edit.identifier(ready.get('instance'))
    return entry, base, ready, online


def status(root, key):
    entry = edit.entry(root, key)
    if not entry.get('preview'):
        return {'configured': False, 'online': False, 'message': '此动作尚未接入原生测试场景'}
    _, base, ready, online = engine(root, key)
    result = {'configured': True, 'online': online, 'message': '测试场景已连接' if online else '等待本机测试场景启动',
              'engine': entry['engine'], 'consumer': entry['preview']['consumer']}
    if not online:
        return result
    result.update(instance=ready['instance'], views=ready.get('views', []), controls=ready.get('controls', []), engine_version=ready.get('engine_version', ''))
    state = read_optional(base / 'status.json')
    if state.get('instance') == ready['instance'] and state.get('action') == key:
        # A prior engine process or another action can never acknowledge this action.
        result['state'] = state
    request = read_optional(base / 'request.json')
    if request.get('instance') == ready['instance']:
        result['latest_request'] = request.get('request')
    return result


def checked_sequence(root, data):
    entry, current, sha = edit.current(root, data['id'])
    if data.get('base_hash') != sha:
        raise ValueError('工程配置已变化，请重新载入后核对')
    candidate = edit.validate(copy.deepcopy(data['sequence']), current)
    for row in edit.changes(current, candidate):
        if row['field'] not in entry.get('editable', {}).get(row['id'], []):
            raise ValueError(row['label'] + ' 的这个参数尚未接入当前引擎')
    return candidate


def command(root, data):
    with record_io.project_lock(root, 'action-preview'):
        return _command(root, data)


def _command(root, data):
    key = edit.identifier(data['id'])
    entry, base, ready, online = engine(root, key)
    if not online or data.get('instance') != ready['instance']:
        raise ValueError('测试场景已离线或重新启动，请重新连接')
    owner = edit.identifier(data.get('client'))
    operation = data.get('operation')
    if operation not in ['replay', 'pause', 'resume', 'step', 'view', 'speed', 'stop']:
        raise ValueError('不支持的测试操作')
    if operation not in ready.get('controls', []):
        raise ValueError('当前测试场景尚未实现此操作')
    pulse = read_optional(base / 'client.json')
    if pulse and not pulse.get('released') and pulse.get('instance') == ready['instance'] and pulse.get('client') != owner and time.time() - (base / 'client.json').stat().st_mtime < 7:
        raise ValueError('另一个看板页面正在控制此测试场景；请先断开该页面')
    previous = read_optional(base / 'request.json')
    if operation != 'replay' and (previous.get('instance') != ready['instance'] or previous.get('client') != owner or data.get('run') != previous.get('run')):
        raise ValueError('预览已切换，请先重新播放当前草案')
    request = {'schema': PROTOCOL, 'request': uuid.uuid4().hex, 'instance': ready['instance'], 'client': owner,
               'operation': operation, 'action': key, 'issued_at': time.time()}
    if operation == 'replay':
        sequence = checked_sequence(root, data)
        run = uuid.uuid4().hex
        path = review.contained(root, PREFIX + '/' + entry['preview']['consumer'] + '/runs/' + run + '/sequence.json')
        edit.write(path, sequence)
        request.update(run=run, sequence_sha256=review.digest(path), base_hash=data['base_hash'])
    else:
        request.update(run=previous['run'], sequence_sha256=previous['sequence_sha256'], base_hash=previous['base_hash'])
    if operation == 'view':
        view = data.get('view')
        if view not in [row.get('id') for row in ready.get('views', [])]:
            raise ValueError('测试场景未提供此机位')
        request['view'] = view
    if operation == 'speed':
        speed = review.finite(data.get('speed'), '测试播放速度', .1)
        if speed > 2:
            raise ValueError('测试播放速度范围为 0.1–2')
        request['speed'] = speed
    edit.write(base / 'client.json', {'instance': ready['instance'], 'client': owner})
    edit.write(base / 'request.json', request)
    return request


def heartbeat(root, data):
    with record_io.project_lock(root, 'action-preview'):
        return _heartbeat(root, data)


def _heartbeat(root, data):
    _, base, ready, online = engine(root, edit.identifier(data['id']))
    owner = edit.identifier(data.get('client'))
    if not online or data.get('instance') != ready['instance']:
        raise ValueError('测试场景已离线')
    pulse = read_optional(base / 'client.json')
    if pulse.get('instance') != ready['instance'] or pulse.get('client') != owner:
        raise ValueError('此页面未连接测试场景')
    if pulse.get('released') and not data.get('release'):
        raise ValueError('预览已断开，请重新连接')
    if data.get('release'):
        edit.write(base / 'client.json', {'instance': ready['instance'], 'client': owner, 'released': True})
    else:
        edit.write(base / 'client.json', {'instance': ready['instance'], 'client': owner})
    return {'ok': True}


def frame_path(root, key, run, frame):
    edit.identifier(run)
    state = status(root, key)
    actual = state.get('state', {})
    if not state['online'] or actual.get('run') != run or not actual.get('applied') or not isinstance(frame, str) or not frame.isdigit():
        raise ValueError('没有此版本的实机画面')
    # Both bounded slots belong to this immutable run; no client-provided path.
    _, base = location(root, key)
    path = base / 'runs' / run / ('frame-' + str(int(frame) % 2) + '.png')
    path = review.contained(root, path.relative_to(root).as_posix())
    if not path.is_file() or path.stat().st_size > 8 * 1024**2:
        raise ValueError('实机画面尚未返回')
    return path


def preserve(root, data):
    with record_io.project_lock(root, 'action-preview'):
        return _preserve(root, data)


def _preserve(root, data):
    key, run = edit.identifier(data['id']), edit.identifier(data['run'])
    _, base = location(root, key)
    folder = review.contained(root, (base / 'runs' / run).relative_to(root).as_posix())
    captured, _ = review.read_json(folder / 'capture.json')
    review.validate_capture(captured)
    sequence, sha = review.read_json(folder / 'sequence.json')
    if captured['action'] != key or captured['revision'] != sha or not captured['complete']:
        raise ValueError('本次动作尚未完整执行或记录版本不符')
    if captured.get('preview_sequence') != sequence:
        raise ValueError('记录中的实际配置与预览版本不符')
    saved = read_optional(folder / 'saved.json')
    if saved:
        return saved
    saved = review.register(root, {'capture': (folder / 'capture.json').relative_to(root).as_posix(), 'title': sequence['title'] + ' · 原生测试场景'})
    edit.write(folder / 'saved.json', saved)
    return saved

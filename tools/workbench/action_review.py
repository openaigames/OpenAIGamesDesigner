"""Project-contained snapshots of engine event recordings. No gameplay configuration writes."""
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import uuid

ENGINES = ('unreal', 'unity', 'godot', 'threejs', 'phaser', 'web')
PREFIX = '.openaigame/action-runs'
MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 10000


def contained(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ':' in relative:
        raise ValueError('请填写项目内相对路径')
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('文件必须位于当前项目内')
    return path


def read_json(path, maximum=MAX_BYTES):
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('记录超过 8 MB，请分段录制')
    value = json.loads(data.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('需要 JSON 对象')
    return value, hashlib.sha256(data).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def label(value, name, limit=300):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(name + '缺失或格式无效')
    return value


def finite(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(name + '必须是有效数字')
    return value


@lru_cache(maxsize=1)
def analyzer():
    # Reuse the standalone animation tool; there is one timing implementation.
    root = Path(__file__).resolve().parents[2]
    relative = 'game-animation-pipeline/scripts/action_timeline.py'
    candidates = (root / 'skills' / relative, root.parent.parent / relative)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None: raise ValueError('缺少动作管线工具，请安装 game-animation-pipeline')
    spec = importlib.util.spec_from_file_location('_action_timeline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_capture(cap):
    if cap.get('schema') != 'action-events/1': raise ValueError('不支持的动作记录格式')
    if cap.get('engine') not in ENGINES: raise ValueError('引擎类型无效')
    for field in ('revision', 'source', 'action', 'engine_version', 'input_description'):
        label(cap.get(field), field)
    if cap.get('input_mode') not in ('human', 'software', 'mixed', 'unknown'):
        raise ValueError('请记录输入方式')
    if cap.get('clock') != 'monotonic_seconds': raise ValueError('需要同一进程的单调时钟（秒）')
    if not isinstance(cap.get('complete'), bool): raise ValueError('请记录是否完成')
    if type(cap.get('dropped_events')) is not int or cap['dropped_events'] < 0: raise ValueError('事件丢失数无效')
    origin = finite(cap.get('zero_s'), 'zero_s')
    duration = finite(cap.get('duration_s'), 'duration_s')
    rows = cap.get('events')
    if not isinstance(rows, list) or len(rows) > MAX_EVENTS: raise ValueError('事件数量无效')
    keys, previous = set(), origin
    for row in rows:
        if not isinstance(row, dict): raise ValueError('事件格式无效')
        key = (label(row.get('track'), '轨道', 160), label(row.get('id'), '事件', 160))
        if key in keys: raise ValueError('重复事件需带不同的次数编号')
        keys.add(key)
        t = finite(row.get('t_s'), 't_s')
        finite(row.get('uncertainty_s', 0), 'uncertainty_s')
        if t < previous or t > origin + duration + 1e-6: raise ValueError('事件时刻不在记录区间内或顺序倒退')
        previous = t
    return cap


def validate_spec(spec, cap):
    if not isinstance(spec, dict) or spec.get('schema') != 'action-timeline/1': raise ValueError('不支持的动作设定格式')
    label(spec.get('revision'), '设定版本')
    if spec.get('action') != cap['action']: raise ValueError('设定与记录的动作名称不一致')
    for name in ('events', 'clips', 'windows', 'synchronize', 'delays'):
        if not isinstance(spec.get(name, []), list) or len(spec.get(name, [])) > MAX_EVENTS:
            raise ValueError('设定条目数量无效')
    for name in ('events', 'clips', 'windows'):
        for row in spec.get(name, []):
            if not isinstance(row, dict): raise ValueError('设定条目格式无效')
            label(row.get('track'), '轨道', 160); label(row.get('id'), '事件', 160)
        analyzer().keyed(spec.get(name, []), name)
    for group, keys in [('synchronize', ('a', 'b')), ('delays', ('from', 'to'))]:
        for row in spec.get(group, []):
            if not isinstance(row, dict): raise ValueError('事件对照格式无效')
            for key in keys:
                pair = row.get(key)
                if not isinstance(pair, list) or len(pair) != 2: raise ValueError('事件引用需要轨道与事件名')
                for value in pair: label(value, '事件引用', 160)
    for name in ('track_labels', 'event_labels'):
        labels = spec.get(name, {})
        if not isinstance(labels, dict): raise ValueError('显示名称格式无效')
        for track, value in labels.items():
            label(track, '轨道名', 160)
            if name == 'track_labels': label(value, '显示名称', 160)
            else:
                if not isinstance(value, dict): raise ValueError('事件显示名称格式无效')
                for key, text in value.items(): label(key, '事件名', 160); label(text, '显示名称', 160)
    # Validate references even when the corresponding recorded event is missing.
    windows = analyzer().keyed(spec.get('windows', []), 'windows')
    for row in spec.get('events', []):
        if row.get('window') and (row['track'], row['window']) not in windows:
            raise ValueError('设定引用了不存在的操作窗口')
    return analyzer().analyze(spec, cap)


def evaluate(cap, spec=None):
    validate_capture(cap)
    report = validate_spec(spec, cap) if spec is not None else None
    checked = sum(len(spec.get(k, [])) for k in ('events', 'synchronize', 'delays')) if spec else 0
    status = ('incomplete' if not cap['complete'] or cap['dropped_events'] else
              'observed' if not checked else 'issues' if report['issues'] else 'within_tolerance')
    return {'status': status, 'checks': checked, 'report': report,
            'visual_review': 'not_performed', 'audio_review': 'not_performed', 'network_test': 'not_performed'}


def register(root, data):
    root = Path(root).resolve()
    cap_path = contained(root, data['capture'])
    cap, cap_hash = read_json(cap_path)
    spec, spec_hash, spec_path = None, None, None
    if data.get('spec'):
        spec_path = contained(root, data['spec'])
        spec, spec_hash = read_json(spec_path)
    result = evaluate(cap, spec)
    media = None
    if data.get('video'):
        path = contained(root, data['video'])
        if path.suffix.lower() not in ('.mp4', '.webm') or not path.is_file(): raise ValueError('请选择项目内 MP4 或 WebM 录像')
        offset = finite(data.get('video_zero_s'), '视频中动作起点')
        media = {'path': path.relative_to(root).as_posix(), 'sha256': digest(path), 'zero_s': offset}
    run_id = uuid.uuid4().hex
    folder = contained(root, PREFIX + '/' + run_id)
    folder.mkdir(parents=True, exist_ok=False)
    files = {'capture': {'path': cap_path.relative_to(root).as_posix(), 'sha256': cap_hash}}
    if spec is not None: files['spec'] = {'path': spec_path.relative_to(root).as_posix(), 'sha256': spec_hash}
    record = {'schema': 'action-run/1', 'id': run_id, 'title': label(data.get('title', cap['action']), '名称'),
              'capture': cap, 'spec': spec, 'result': result, 'files': files, 'video': media}
    # A completed immutable file is the only discoverable record. Concurrent imports have different IDs.
    temp = folder/'run.pending'
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False), 'utf8')
    temp.replace(folder/'run.json')
    return summary(record)


def detail(root, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[a-f0-9]{32}', run_id): raise ValueError('记录编号无效')
    record, _ = read_json(contained(root, PREFIX + '/' + run_id + '/run.json'), 64 * 1024 * 1024)
    if record.get('schema') != 'action-run/1' or record.get('id') != run_id: raise ValueError('记录身份不符')
    record['result'] = evaluate(record['capture'], record['spec'])
    return record


def summary(record):
    cap = record['capture']
    return {k: record[k] for k in ('id', 'title')} | {k: cap[k] for k in (
        'engine', 'engine_version', 'action', 'revision', 'input_mode', 'input_description', 'duration_s')} | {
        'events': len(cap['events']), 'status': record['result']['status'], 'checks': record['result']['checks']}


def snapshot(root):
    base = contained(root, PREFIX)
    rows, errors = [], []
    if base.is_dir():
        paths = sorted(base.glob('*/run.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:200]:
            try: rows.append(summary(detail(root, path.parent.name)))
            except (OSError, ValueError, KeyError, TypeError): errors.append(path.parent.name)
        return {'runs': rows, 'unreadable': errors, 'older_runs': max(0, len(paths)-200)}
    return {'runs': [], 'unreadable': [], 'older_runs': 0}


def compare(root, a, b):
    left, right = detail(root, a), detail(root, b)
    ca, cb = left['capture'], right['capture']
    for key in ('action', 'clock', 'input_mode', 'input_description'):
        if ca[key] != cb[key]: raise ValueError('动作或输入条件不同，请分别查看；不能作为同条件对照')
    def times(c): return {(r['track'], r['id']): r['t_s']-c['zero_s'] for r in c['events']}
    ta, tb = times(ca), times(cb)
    return {'a': summary(left), 'b': summary(right), 'rows': [
        {'track': k[0], 'id': k[1], 'a_s': ta.get(k), 'b_s': tb.get(k),
         'delta_s': tb[k]-ta[k] if k in ta and k in tb else None}
        for k in sorted(ta.keys() | tb.keys())], 'conditions': 'declared_by_capture',
        'note': '按记录中声明的输入条件比较。不同机器、帧率和网络仍需单独核对。'}


def media_path(root, run_id):
    media = detail(root, run_id).get('video')
    if not media: raise ValueError('未关联录像')
    path = contained(root, media['path'])
    if path.suffix.lower() not in ('.mp4', '.webm') or digest(path) != media['sha256']:
        raise ValueError('录像文件已变化，请重新登记')
    return path

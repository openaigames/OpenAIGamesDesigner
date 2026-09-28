"""Version/use-specific review records. Acquisition and engine usage remain independent."""
import copy
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import art_registry, asset_usage

GATES = {'source': '来源与依赖', 'external': '源资产检查', 'engine': '引擎校对', 'game': '游戏用途验收'}
STAGES = ('candidate', 'testing', 'qualified')
KINDS = ('model', 'animation', 'weapon', 'vfx', 'audio', 'image', 'other')
MAX_BYTES = 4 * 1024 * 1024


class ReviewError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def safe_path(root, relative, metadata=False):
    """No absolute paths, ADS, hidden secrets, junctions or symlinks (including parents)."""
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative or any(ord(c) < 32 for c in relative):
        raise ReviewError('请使用项目内的相对路径（/ 分隔）')
    parts = relative.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts):
        raise ReviewError('路径无效')
    if not metadata and any(p.startswith('.') for p in parts):
        # Generated/acquired files already have a narrow allowlist in the shared registry.
        if relative.startswith(('.openaigame/asset-library/', '.openaigame/asset-jobs/')):
            return art_registry.asset_path(root, relative)
        raise ReviewError('不能读取隐藏配置或凭据文件')
    current = Path(root).resolve()
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ReviewError('路径不能包含符号链接或目录联接')
    if not current.resolve().is_relative_to(Path(root).resolve()):
        raise ReviewError('路径超出项目')
    return current


def registry_path(root):
    return safe_path(root, '.openaigame/asset-review/registry.json', metadata=True)


def load(root):
    path = registry_path(root)
    raw = path.read_bytes() if path.exists() else b''
    if len(raw) > MAX_BYTES:
        raise ReviewError('看板记录过大，请拆分项目')
    try:
        data = json.loads(raw.decode('utf-8-sig')) if raw else {'schemaVersion': 1, 'records': []}
        if data['schemaVersion'] != 1 or not isinstance(data['records'], list) or len(data['records']) > 2000:
            raise ValueError()
        ids = set()
        for row in data['records']:
            if row['id'] in ids or row['stage'] not in STAGES or not isinstance(row['checks'], dict):
                raise ValueError()
            ids.add(row['id'])
    except (ValueError, KeyError, TypeError):
        raise ReviewError('看板记录无法读取，原文件已保留；请修复后刷新') from None
    return data, hashlib.sha256(raw).hexdigest()


def text(value, label, limit=2000, required=False):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ReviewError(label + '格式无效或过长')
    value = value.strip()
    if required and not value:
        raise ReviewError('请填写' + label)
    return value


def fields(root, values):
    out = {}
    for key, label, limit in [('title', '名称', 150), ('use', '用途 / 动作片段', 500), ('plan', '关联方案', 500),
                              ('version', '版本', 100), ('sourceUrl', '来源地址', 2000), ('license', '许可与费用依据', 2000),
                              ('enginePath', '引擎资源路径', 500), ('environment', '目标环境', 500),
                              ('testPlan', '测试范围', 3000), ('notes', '备注', 5000), ('issues', '阻塞问题', 3000),
                              ('objectId', '美术对象', 100)]:
        out[key] = text(values.get(key, ''), label, limit, key == 'title')
    out['version'] = out['version'] or 'v1'
    out['role'] = values.get('role', 'unassigned')
    out['kind'] = values.get('kind', 'other')
    if out['kind'] not in KINDS or out['role'] not in ('player', 'boss', 'shared', 'unassigned'):
        raise ReviewError('请选择素材类型和拟用角色')
    if out['sourceUrl']:
        url = urlsplit(out['sourceUrl'])
        if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password:
            raise ReviewError('来源只支持不含凭据的 http / https 页面')
    if out['objectId']:
        if out['objectId'] not in art_registry.load(root)['objects']:
            raise ReviewError('美术对象不存在，请在资产库维护对象与标签')
    paths = values.get('files', [])
    if not isinstance(paths, list) or len(paths) > 100:
        raise ReviewError('每个用途最多关联 100 个源文件、派生文件和依赖')
    out['files'] = list(dict.fromkeys(paths))
    for rel in out['files']:
        if not safe_path(root, rel).is_file():
            raise ReviewError('文件不存在：' + rel)
    if not out['files'] and not out['sourceUrl']:
        raise ReviewError('候选需要真实来源页面或项目内文件')
    return out


def file_hashes(root, paths):
    return {rel: digest(safe_path(root, rel)) for rel in paths}


def version_key(row):
    scope = {k: row.get(k) for k in ('use', 'role', 'objectId', 'kind', 'version', 'files', 'enginePath', 'environment', 'snapshot', 'sourceUrl', 'license', 'testPlan')}
    return hashlib.sha256(json.dumps(scope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def assess(root, row, cache=None):
    cache = {} if cache is None else cache
    def current(rel):
        if rel not in cache:
            try:
                cache[rel] = digest(safe_path(root, rel))
            except (OSError, ValueError):
                cache[rel] = None
        return cache[rel]
    stale = [rel for rel, expected in row.get('snapshot', {}).items() if current(rel) != expected]
    blockers = []
    if not row.get('snapshot'):
        blockers.append('尚未建立实际文件版本')
    if stale:
        blockers.append('源文件或依赖已变化，请建立新版本复测')
    if row.get('issues'):
        blockers.append('仍有阻塞问题')
    checks = {}
    for gate, label in GATES.items():
        check = copy.deepcopy(row['checks'].get(gate, {'status': 'not_run'}))
        if check['status'] in ('pass', 'na'):
            changed = check.get('versionKey') != version_key(row) or bool(stale)
            changed |= any(current(item['path']) != item['sha256'] for item in check.get('evidence', []))
            if changed:
                check['status'] = 'stale'
        checks[gate] = check
        if check['status'] not in ('pass', 'na'):
            blockers.append(label + '尚未通过当前版本验收')
    stage = 'testing' if row['stage'] == 'qualified' and blockers else row['stage']
    return {**row, 'effectiveStage': stage, 'checkResults': checks, 'blockers': blockers,
            'staleFiles': stale, 'canQualify': row['stage'] == 'testing' and not blockers}


def snapshot(root):
    data, revision = load(root)
    usage, audit = asset_usage.read(Path(root))
    cache = {}
    rows = []
    for row in data['records']:
        result = assess(root, row, cache)
        # Usage manifests are independent facts, and must match this reviewed file revision.
        bound = [p for p in row['files'] if p in usage]
        result['usage'] = {'status': 'used' if bound and row.get('snapshot') and not result['staleFiles'] else 'unverified',
                           'paths': bound, 'roles': list(dict.fromkeys(role for p in bound for role in usage[p].get('roles', [])))}
        rows.append(result)
    return {'schemaVersion': 1, 'revision': revision, 'records': rows, 'usageAudit': audit}


def event(row, action):
    row['updatedAt'] = now()
    row.setdefault('history', []).append({'at': row['updatedAt'], 'action': action})


def apply(root, data, request):
    action = request.get('action')
    if action == 'create':
        row = fields(root, request.get('record', {}))
        row.update(id=uuid.uuid4().hex, stage='candidate', checks={}, snapshot={}, archived=False, history=[], createdAt=now())
        row['lineageId'] = row['id']
        data['records'].append(row)
        event(row, '建立候选')
        return row['id']
    row = next((r for r in data['records'] if r['id'] == request.get('id')), None)
    if row is None:
        raise ReviewError('记录不存在')
    if action == 'archive':
        if not isinstance(request.get('archived'), bool):
            raise ReviewError('归档状态无效')
        row['archiveReason'] = text(request.get('reason', ''), '归档 / 恢复原因', required=True)
        row['archived'] = request['archived']
        event(row, ('归档：' if row['archived'] else '恢复：') + row['archiveReason'])
    elif row['archived']:
        raise ReviewError('请先恢复归档记录')
    elif action in ('edit', 'new_version'):
        updated = fields(root, {**row, **request.get('record', {})})
        changed_scope = any(updated.get(k) != row.get(k) for k in updated if k not in ('notes', 'issues', 'title', 'plan'))
        if action == 'edit':
            if changed_scope and row['stage'] != 'candidate':
                raise ReviewError('测试范围或版本发生变化，请建立新版本，保留原结论')
            row.update(updated)
            if row.get('issues') and row['stage'] == 'qualified':
                row['stage'] = 'testing'
            event(row, '更新资料 / 问题')
        else:
            if updated['version'] == row['version']:
                raise ReviewError('请为新版本填写不同的版本名称')
            new = {**updated, 'id': uuid.uuid4().hex, 'lineageId': row['lineageId'], 'supersedes': row['id'],
                   'stage': 'candidate', 'checks': {}, 'snapshot': {}, 'archived': False, 'history': [], 'createdAt': now()}
            data['records'].append(new)
            event(new, '建立新版本，原版保留；需要重新开始测试')
            return new['id']
    elif action == 'start':
        if row['stage'] != 'candidate' or not row['files'] or not row['use'] or not row['testPlan'] or not row['environment']:
            raise ReviewError('开始测试需要：候选阶段、实际文件、明确用途、测试范围及目标环境')
        row['snapshot'] = file_hashes(root, row['files'])
        row['stage'] = 'testing'
        row['checks'] = {}
        event(row, '开始测试；文件与依赖版本已记录')
    elif action == 'check':
        if assess(root, row)['effectiveStage'] != 'testing' or not row['snapshot']:
            raise ReviewError('请先开始测试，合格版本需退回测试或建立新版本')
        if assess(root, row)['staleFiles']:
            raise ReviewError('文件已变化，请建立新版本后记录结果')
        gate, status = request.get('gate'), request.get('status')
        if gate not in GATES or status not in ('pass', 'fail', 'blocked', 'na'):
            raise ReviewError('检查项或结果无效')
        if status == 'na' and gate != 'external':
            raise ReviewError('仅源资产外部检查可声明不适用；仍须完成引擎与游戏验收')
        method = text(request.get('method', ''), '检查方法 / 不适用原因', required=True)
        reviewer = text(request.get('reviewer', ''), '执行者 / 复核者', 150, True)
        conclusion = text(request.get('conclusion', ''), '结论与适用范围', required=True)
        entries = request.get('evidence', [])
        if not isinstance(entries, list) or len(entries) > 20:
            raise ReviewError('证据列表无效')
        evidence = []
        for item in entries:
            if not isinstance(item, dict) or item.get('type') not in ('report', 'video', 'image', 'run_report', 'license'):
                raise ReviewError('证据类型无效')
            rel = item.get('path', '')
            path = safe_path(root, rel)
            expected = {'report': ('.md', '.txt', '.json'), 'run_report': ('.md', '.txt', '.json'),
                        'video': ('.mp4', '.webm', '.mov'), 'image': ('.png', '.jpg', '.jpeg', '.webp'),
                        'license': ('.md', '.txt', '.pdf')}[item['type']]
            if not path.is_file() or path.suffix.lower() not in expected:
                raise ReviewError('证据文件不存在或格式不匹配：' + rel)
            evidence.append({'path': rel, 'type': item['type'], 'sha256': digest(path)})
        if status == 'pass' and not evidence:
            raise ReviewError('通过必须关联真实项目证据')
        if status == 'pass' and gate in ('engine', 'game') and row['kind'] in ('animation', 'model', 'weapon', 'vfx'):
            if not any(e['type'] in ('video', 'run_report') for e in evidence):
                raise ReviewError('动态用途需运行报告或视频，截图不能代替动作 / 手感检查')
        if gate == 'source' and status == 'pass' and not row['license']:
            raise ReviewError('请先填写许可与费用依据')
        row['stage'] = 'testing'
        row['checks'][gate] = {'status': status, 'method': method, 'reviewer': reviewer, 'conclusion': conclusion,
                               'evidence': evidence, 'versionKey': version_key(row), 'at': now()}
        row.setdefault('checkHistory', []).append({'gate': gate, **copy.deepcopy(row['checks'][gate])})
        event(row, GATES[gate] + '：' + status)
    elif action == 'qualify':
        result = assess(root, row)
        if not result['canQualify']:
            raise ReviewError('不能纳入合格资产：' + '；'.join(result['blockers'] or ['请先进入测试阶段']))
        row['stage'] = 'qualified'
        row['qualifiedAt'] = now()
        event(row, '当前版本 / 用途验收合格（不代表已绑定到游戏）')
    elif action == 'return':
        reason = text(request.get('reason', ''), '退回原因', required=True)
        if row['stage'] == 'candidate':
            raise ReviewError('此记录已在候选阶段')
        row['stage'] = 'testing' if row['stage'] == 'qualified' else 'candidate'
        # Re-entry always requires current evidence, even if bytes did not change.
        row['checks'] = {}
        event(row, '退回：' + reason)
    else:
        raise ReviewError('不支持的看板操作')
    return row['id']


def mutate(root, request):
    """Exclusive writer + revision CAS. Lock is project-local and never silently stolen."""
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = safe_path(root, '.openaigame/asset-review/write.lock', metadata=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise art_registry.RevisionConflict('另一处正在保存看板，请稍后刷新；若进程中断请检查 write.lock') from None
    temp = path.with_name('registry-' + uuid.uuid4().hex + '.tmp')
    try:
        os.close(descriptor)
        data, revision = load(root)
        if request.get('revision') != revision:
            raise art_registry.RevisionConflict('看板已被另一处更新。当前输入已保留，请刷新记录后核对再提交')
        selected = apply(root, data, request)
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'
        if len(raw) > MAX_BYTES or len(data['records']) > 2000:
            raise ReviewError('记录数量或大小超出限制')
        with temp.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
        lock.unlink()
    return {**snapshot(root), 'selectedId': selected}


def evidence_path(root, row_id, gate, index):
    data, _ = load(root)
    row = next(r for r in data['records'] if r['id'] == row_id)
    if int(index) < 0:
        raise ReviewError('证据编号无效')
    item = row['checks'][gate]['evidence'][int(index)]
    path = safe_path(root, item['path'])
    if digest(path) != item['sha256']:
        raise ReviewError('此证据已变化，请重新复核')
    return path

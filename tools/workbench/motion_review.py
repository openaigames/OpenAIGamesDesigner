"""Version-bound motion decisions; never modify assets or runtime combat settings."""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import art_registry as registry, asset_browser, model_previews

MAX_BYTES = 4 * 1024 * 1024
DECISIONS = {'pending', 'keep', 'reject'}
ROLES = {'unassigned', 'player', 'boss', 'other'}
ROOT_MOTION = {'unknown', 'in_place', 'root_motion'}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _path(root):
    """Reject symlink/junction metadata locations, including dangling links."""
    path = root / '.asset-browser' / 'motion-review.json'
    for node in (path.parent, path):
        if node.is_symlink() or (hasattr(node, 'is_junction') and node.is_junction()):
            raise ValueError('动作审阅目录不能使用链接')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('动作审阅记录必须位于当前项目')
    return path


def _gltf_dependencies(root, path):
    """Hash external buffers/images too; data URIs are covered by the model hash."""
    if path.suffix.lower() == '.glb':
        with path.open('rb') as stream:
            magic, version, _ = struct.unpack('<4sII', stream.read(12))
            size, kind = struct.unpack('<II', stream.read(8))
            if magic != b'glTF' or version != 2 or kind != 0x4E4F534A or size > MAX_BYTES:
                raise ValueError('GLB 无效')
            document = json.loads(stream.read(size))
    else:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('glTF JSON 过大')
        document = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(document, dict):
        raise ValueError('glTF JSON 无效')
    entries = document.get('buffers', []) + document.get('images', [])
    if not isinstance(entries, list) or len(entries) > 4096:
        raise ValueError('glTF 依赖过多或无效')
    dependencies = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('glTF 依赖无效')
        uri = entry.get('uri')
        if uri is None or (isinstance(uri, str) and uri.startswith('data:')):
            continue
        if not isinstance(uri, str):
            raise ValueError('glTF 依赖无效')
        parsed = urlsplit(uri)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('动作审阅仅支持项目内 glTF 依赖')
        relative = (path.parent.relative_to(root) / unquote(parsed.path)).as_posix()
        dependency = registry.asset_path(root, relative)
        dependencies[dependency.relative_to(root).as_posix()] = registry.digest(dependency)
    return dependencies


def source_version(root, asset):
    """Fingerprint exactly the native model or validated engine preview being shown."""
    if asset.get('preview') not in ('native', 'derived'):
        raise ValueError('请先提供有效的动作预览')
    source = registry.asset_path(root, asset['path'])
    preview = registry.asset_path(root, asset.get('previewPath', asset['path']))
    if preview.suffix.lower() not in ('.glb', '.gltf'):
        raise ValueError('动作审阅需要 GLB/glTF 或有效的关联 GLB 预览')
    hashes = {source.relative_to(root).as_posix(): registry.digest(source),
              preview.relative_to(root).as_posix(): registry.digest(preview)}
    if asset.get('previewPath'):
        records, error = model_previews.read(root)
        record = records.get(asset['path'])
        if error or not record:
            raise ValueError('关联预览映射无效')
        current = model_previews.resolve(root, asset['path'], record, asset_browser.gltf_info)
        if current.get('previewPath') != asset['previewPath']:
            raise ValueError('关联预览已变化')
        hashes.update(record.get('dependencies', {}))
    try:
        hashes.update(_gltf_dependencies(root, preview))
    except struct.error as error:
        raise ValueError('GLB 文件不完整') from error
    return {'fingerprint': _hash(_json(hashes)), 'files': hashes,
            'preview_path': preview.relative_to(root).as_posix()}


def _validate_choice(choice):
    if not isinstance(choice, dict) or set(choice) != {'decision', 'role', 'semantic', 'mirror', 'root_motion', 'note'}:
        raise ValueError('动作审阅字段无效')
    for key, allowed in (('decision', DECISIONS), ('role', ROLES), ('root_motion', ROOT_MOTION)):
        if not isinstance(choice[key], str) or choice[key] not in allowed:
            raise ValueError('动作审阅选项无效')
    if type(choice['mirror']) is not bool:
        raise ValueError('镜像须为布尔值')
    for key, limit in (('semantic', 80), ('note', 2000)):
        if not isinstance(choice[key], str) or len(choice[key]) > limit or '\x00' in choice[key]:
            raise ValueError('动作审阅文本过长或无效')
    if choice['decision'] == 'keep' and (choice['role'] == 'unassigned' or not choice['semantic'].strip()):
        raise ValueError('保留动作前请填写角色用途和动作语义')


def load(root):
    """Read without initializing files; reject damaged records rather than resetting."""
    path = _path(root)
    raw = path.read_bytes() if path.exists() else b''
    if len(raw) > MAX_BYTES:
        raise ValueError('动作审阅记录超过 4 MB')
    value = json.loads(raw) if path.exists() else {'schema_version': 1, 'history': []}
    if not isinstance(value, dict) or value.get('schema_version') != 1 or not isinstance(value.get('history'), list):
        raise ValueError('动作审阅记录格式无效')
    for record in value['history']:
        if not isinstance(record, dict):
            raise ValueError('动作审阅条目无效')
        _validate_choice(record.get('choice'))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(record.get('asset_id', ''))):
            raise ValueError('动作资产 ID 无效')
        if type(record.get('clip_index')) is not int or record['clip_index'] < 0:
            raise ValueError('动作序号无效')
        if not isinstance(record.get('clip_name'), str) or not isinstance(record.get('source'), dict):
            raise ValueError('动作来源无效')
        if not re.fullmatch(r'[a-f0-9]{64}', str(record['source'].get('fingerprint', ''))):
            raise ValueError('动作来源版本无效')
    return value, _hash(raw)


def snapshot(root):
    """Retain unavailable/rejected records in the report; only current keeps can export."""
    stored, revision = load(root)
    scanned = asset_browser.scan(root)
    if scanned['artAudit'].get('error'):
        raise ValueError('请先建立或修复 Art Direction 资产登记')
    latest = {(r['asset_id'], r['clip_index']): r for r in stored['history']}
    entries = []
    seen = set()
    for asset in scanned['assets']:
        if not asset.get('art') or not asset.get('animations'):
            continue
        try:
            source = source_version(root, asset)
        except (OSError, ValueError, TypeError, KeyError, struct.error):
            continue
        for index, name in enumerate(asset['animations']):
            key = (asset['art']['id'], index)
            seen.add(key)
            record = latest.get(key)
            state = 'unreviewed' if not record else ('current' if record['source'] == source and record['clip_name'] == name else 'stale')
            entries.append({'asset_id': key[0], 'path': asset['path'], 'clip_index': index,
                            'clip_name': name, 'source': source, 'state': state, 'review': record})
    for key, record in latest.items():
        if key not in seen:
            entries.append({'asset_id': key[0], 'path': record.get('path', ''), 'clip_index': key[1],
                            'clip_name': record['clip_name'], 'state': 'unavailable', 'review': record})
    return {'schema_version': 1, 'revision': revision, 'entries': entries,
            'history_count': len(stored['history'])}


def save(root, payload):
    """Caller serializes writes; optimistic revision guards multiple browser editors."""
    if set(payload) != {'revision', 'asset_id', 'clip_index', 'fingerprint', 'choice'}:
        raise ValueError('动作审阅请求字段无效')
    _validate_choice(payload['choice'])
    if type(payload['clip_index']) is not int or not isinstance(payload['asset_id'], str):
        raise ValueError('动作标识无效')
    view = snapshot(root)
    if payload['revision'] != view['revision']:
        raise registry.RevisionConflict('动作审阅已被修改，请重新加载后核对')
    entry = next((e for e in view['entries'] if e['asset_id'] == payload['asset_id'] and e['clip_index'] == payload['clip_index']), None)
    if not entry or entry['state'] == 'unavailable' or entry['source']['fingerprint'] != payload['fingerprint']:
        raise registry.RevisionConflict('动作源文件或预览已变化，请重新扫描并观看后再保存')
    stored, revision = load(root)
    if revision != view['revision']:
        raise registry.RevisionConflict('动作审阅已被修改，请重新加载后核对')
    record = {k: entry[k] for k in ('asset_id', 'path', 'clip_index', 'clip_name', 'source')}
    record.update(choice=payload['choice'], reviewed_at=datetime.now(timezone.utc).isoformat())
    stored['history'].append(record)
    raw = _json(stored)
    if len(raw) > MAX_BYTES:
        raise ValueError('动作审阅记录超过 4 MB，请先归档历史')
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.motion-review-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
        if load(root)[1] != revision:
            raise registry.RevisionConflict('动作审阅已被修改，请重新加载后核对')
        os.replace(temporary, _path(root))
    finally:
        temporary.unlink(missing_ok=True)
    return snapshot(root)


def handoff(root):
    """Export candidate decisions only, not an executable attack/animation configuration."""
    view = snapshot(root)
    candidates, excluded = [], []
    for entry in view['entries']:
        record = entry['review']
        if entry['state'] == 'current' and record['choice']['decision'] == 'keep':
            candidates.append({**record, 'path': entry['path']})
        else:
            excluded.append({k: entry[k] for k in ('asset_id', 'path', 'clip_index', 'clip_name', 'state')} | {
                'decision': record['choice']['decision'] if record else 'pending', 'review': record})
    return {'schema_version': 1, 'kind': 'motion-candidate-handoff', 'revision': view['revision'],
            'runtime_validation': 'not_checked', 'candidates': candidates, 'excluded': excluded}

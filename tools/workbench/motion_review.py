"""Version-bound clip decisions. Browser FBX observations never imply engine approval."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import struct
from urllib.parse import unquote, urlsplit
import record_io as io
from . import art_registry as registry, asset_browser, model_previews

MAX_BYTES = 4 * 1024 * 1024
DECISIONS = {'pending', 'keep', 'reject'}
ROLES = {'unassigned', 'player', 'boss', 'other'}
ROOT_MOTION = {'unknown', 'in_place', 'root_motion'}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _path(root):
    path = Path(root) / '.asset-browser' / 'motion-review.json'
    for node in (path.parent, path):
        try:
            attributes = getattr(node.lstat(), 'st_file_attributes', 0)
        except FileNotFoundError:
            attributes = 0
        if node.is_symlink() or attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise ValueError('动作审阅目录不能使用链接')
    return io.local(root, '.asset-browser/motion-review.json')


def _document(path):
    if path.suffix.lower() == '.glb':
        with path.open('rb') as stream:
            magic, version, _ = struct.unpack('<4sII', stream.read(12))
            size, kind = struct.unpack('<II', stream.read(8))
            if magic != b'glTF' or version != 2 or kind != 0x4E4F534A or size > MAX_BYTES:
                raise ValueError('GLB 无效')
            value = json.loads(stream.read(size))
    else:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('glTF JSON 过大')
        value = io.read_json(path)
    if not isinstance(value, dict):
        raise ValueError('glTF JSON 无效')
    return value


def _gltf_dependencies(root, path):
    document = _document(path)
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
        target = (path.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(root):
            raise ValueError('glTF 依赖越过项目目录')
        dependencies.update(io.snapshot_files(root, [target.relative_to(root).as_posix()]))
    return dependencies


def source_version(root, asset):
    root = Path(root).resolve()
    if asset.get('preview') not in ('native', 'derived'):
        raise ValueError('请先提供有效的动作预览')
    source = registry.asset_path(root, asset['path'])
    preview = registry.asset_path(root, asset.get('previewPath', asset['path']))
    if preview.suffix.lower() not in ('.glb', '.gltf', '.fbx'):
        raise ValueError('动作审阅需要 GLB/glTF、FBX 或有效的关联预览')
    hashes = io.snapshot_files(root, list(dict.fromkeys([source.relative_to(root).as_posix(), preview.relative_to(root).as_posix()])))
    mapping = None
    if asset.get('previewPath'):
        records, error = model_previews.read(root)
        mapping = records.get(asset['path'])
        if error or not mapping:
            raise ValueError('关联预览映射无效')
        current = model_previews.resolve(root, asset['path'], mapping, asset_browser.gltf_info)
        if current.get('previewPath') != asset['previewPath']:
            raise ValueError('关联预览已变化')
        hashes.update(mapping.get('dependencies', {}))
    if preview.suffix.lower() in ('.glb', '.gltf'):
        hashes.update(_gltf_dependencies(root, preview))
    basis = {'files': hashes, 'preview_path': preview.relative_to(root).as_posix(), 'mapping': mapping}
    return {**basis, 'fingerprint': _hash(_json(basis))}


def _context(value):
    if not isinstance(value, dict) or set(value) != {'character_id', 'role', 'use', 'rig_path'}:
        raise ValueError('动作上下文字段无效')
    if not isinstance(value['role'], str) or value['role'] not in ROLES:
        raise ValueError('角色用途无效')
    if not isinstance(value['use'], str) or not value['use'].strip() or len(value['use']) > 80 or '\x00' in value['use']:
        raise ValueError('用途 ID 须为 1–80 字符')
    for key, limit in (('character_id', 100), ('rig_path', 2000)):
        if value[key] is not None and (not isinstance(value[key], str) or not value[key] or len(value[key]) > limit):
            raise ValueError('角色或预览角色标识无效')
    return dict(value)


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


def _clips(value):
    if not isinstance(value, list) or len(value) > 512:
        raise ValueError('片段观测格式无效或过多')
    for clip in value:
        if not isinstance(clip, dict) or set(clip) != {'name', 'duration'}:
            raise ValueError('片段观测字段无效')
        if not isinstance(clip['name'], str) or len(clip['name']) > 1000:
            raise ValueError('片段名无效')
        if type(clip['duration']) not in (int, float) or not math.isfinite(clip['duration']) or clip['duration'] < 0:
            raise ValueError('片段时长无效')
    return value


def _key(path, index, context):
    return _hash(_json([path, index, context]))


def load(root):
    """v1 is read-only until explicit save, which preserves an exact backup."""
    path = _path(root)
    if path.exists() and path.stat().st_size > MAX_BYTES:
        raise ValueError('动作审阅记录超过 4 MB')
    raw = path.read_bytes() if path.exists() else b''
    value = json.loads(raw) if path.exists() else {'schema_version': 2, 'history': []}
    if not isinstance(value, dict) or value.get('schema_version') not in (1, 2) or not isinstance(value.get('history'), list):
        raise ValueError('动作审阅记录格式无效')
    for record in value['history']:
        if not isinstance(record, dict):
            raise ValueError('动作审阅条目无效')
        _validate_choice(record.get('choice'))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(record.get('asset_id', ''))):
            raise ValueError('动作资产 ID 无效')
        if type(record.get('clip_index')) is not int or record['clip_index'] < 0:
            raise ValueError('动作序号无效')
        if not isinstance(record.get('clip_name'), str) or not isinstance(record.get('path'), str) or not isinstance(record.get('source'), dict):
            raise ValueError('动作来源无效')
        io.local(root, record['path'])
        if not re.fullmatch(r'[a-f0-9]{64}', str(record['source'].get('fingerprint', ''))):
            raise ValueError('动作来源版本无效')
        files = record['source'].get('files')
        if not isinstance(files, dict) or not files or len(files) > 4096:
            raise ValueError('动作来源文件无效')
        for relative, digest in files.items():
            io.local(root, relative)
            if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                raise ValueError('动作依赖哈希无效')
        if value['schema_version'] == 1:
            record['legacy_asset_id'] = record['asset_id']
            record['asset_id'] = _hash(record['path'].encode())[:16]
            record['context'] = {'character_id': None, 'role': record['choice']['role'], 'use': 'general', 'rig_path': None}
            record['legacy'] = True
            record['id'] = _key(record['path'], record['clip_index'], record['context'])
        _context(record.get('context'))
        if record.get('id') != _key(record['path'], record['clip_index'], record['context']):
            raise ValueError('动作上下文 ID 无效')
        if record['choice']['role'] != record['context']['role']:
            raise ValueError('结论角色与上下文不一致')
        if not record.get('legacy'):
            basis = {k: v for k, v in record['source'].items() if k != 'fingerprint'}
            if _hash(_json(basis)) != record['source']['fingerprint']:
                raise ValueError('动作来源校验失败；请恢复有效记录')
            observation = record.get('observation')
            if observation is not None:
                if not isinstance(observation, dict):
                    raise ValueError('片段观测无效')
                _clips(observation.get('clips'))
    return value, _hash(raw)


def describe(root, payload, scanned=None, stored=None):
    """Pre-load identity and post-load clip description for the actual shown source."""
    root = Path(root).resolve()
    if not isinstance(payload, dict) or not {'path', 'context'} <= set(payload) or set(payload) - {'path', 'context', 'observation'}:
        raise ValueError('动作预览请求字段无效')
    context = _context(payload['context'])
    scanned = scanned or asset_browser.scan(root)
    assets = {a['path']: a for a in scanned['assets']}
    asset = assets.get(payload['path'])
    if not asset:
        raise ValueError('动作资产不存在')
    source = source_version(root, asset)
    binding = None
    if context['character_id']:
        character = next((c for c in scanned['characters'] if c['id'] == context['character_id']), None)
        if not character:
            raise ValueError('角色绑定已变化或不可用；请重新从引擎同步')
        if payload['path'] not in [character['model'], *[a['path'] for a in character['actions']]]:
            raise ValueError('实际动作不属于所选角色')
        data = io.read_json(io.local(root, '.asset-browser/characters.json'))
        row = next(c for c in data['characters'] if c['id'] == character['id'])
        deps = row.get('dependencies', data.get('dependencies', {}))
        source['files'].update(io.snapshot_files(root, list(deps)))
        model_version = source_version(root, assets[character['model']])
        source['files'].update(model_version['files'])
        binding = {k: character[k] for k in ('id', 'model', 'actions', 'consumer')}
        binding['model_preview'] = model_version
    if context['rig_path']:
        rig = assets.get(context['rig_path'])
        if not rig or (rig.get('previewExt') or rig['ext']) != 'FBX' or rig['path'] == asset['path']:
            raise ValueError('临时预览角色须为另一份有效 FBX')
        source['rig'] = source_version(root, rig)
        source['files'].update(source['rig']['files'])
    source.update(context=context, binding=binding)
    source.pop('fingerprint')
    source['fingerprint'] = _hash(_json(source))
    observation = payload.get('observation')
    preview = io.local(root, source['preview_path'])
    provenance = 'browser_fbx_observation' if preview.suffix.lower() == '.fbx' else 'local_gltf_metadata'
    if observation is not None:
        if not isinstance(observation, dict) or set(observation) != {'fingerprint', 'clips'}:
            raise ValueError('动作观测字段无效')
        _clips(observation['clips'])
        if observation['fingerprint'] != source['fingerprint']:
            raise registry.RevisionConflict('预览加载后源文件、角色或依赖已变化，请刷新并重新观看')
    if provenance == 'browser_fbx_observation':
        clips = observation['clips'] if observation else []
    else:
        clips = [{'name': a.get('name', f'Animation {i+1}'), 'duration': None} for i, a in enumerate(_document(preview).get('animations', []))]
        if observation and [c['name'] for c in clips] != [c['name'] for c in observation['clips']]:
            raise registry.RevisionConflict('实际加载片段与当前源文件不一致，请刷新')
    value, revision = stored or load(root)
    latest = {r['id']: r for r in value['history']}
    entries = []
    for index, clip in enumerate(clips):
        key = _key(asset['path'], index, context)
        record = latest.get(key)
        current = record and not record.get('legacy') and record['source'] == source and record['clip_name'] == clip['name']
        if current and provenance == 'browser_fbx_observation':
            current = record.get('observation') == observation
        entries.append({'id': key, 'asset_id': asset['id'], 'art_asset_id': (asset.get('art') or {}).get('id'),
                        'path': asset['path'], 'context': context, 'clip_index': index, 'clip_name': clip['name'],
                        'source': source, 'provenance': provenance, 'state': ('current' if current else 'stale') if record else 'unreviewed',
                        'review': record})
    return {'schema_version': 2, 'revision': revision, 'source': source, 'provenance': provenance,
            'entries': entries, 'history_count': len(value['history'])}


def snapshot(root):
    value, revision = load(root)
    scanned = asset_browser.scan(root)
    latest = {r['id']: r for r in value['history']}
    entries = []
    for record in latest.values():
        entry = {k: record[k] for k in ('id', 'asset_id', 'path', 'clip_index', 'clip_name', 'context')}
        entry.update(state='stale', review=record, reason='旧版本记录，需对当前上下文重新审阅')
        if not record.get('legacy'):
            request = {'path': record['path'], 'context': record['context']}
            if record.get('observation'):
                request['observation'] = record['observation']
            try:
                view = describe(root, request, scanned, (value, revision))
                found = next((e for e in view['entries'] if e['id'] == record['id']), None)
                if found:
                    entry = found
                else:
                    entry.update(state='unavailable', reason='片段已移除')
            except registry.RevisionConflict as error:
                entry.update(state='stale', reason=str(error))
            except (OSError, ValueError, TypeError, KeyError, struct.error) as error:
                entry.update(state='unavailable', reason=str(error))
        entries.append(entry)
    return {'schema_version': 2, 'revision': revision, 'entries': entries, 'history_count': len(value['history'])}


def save(root, payload):
    if not isinstance(payload, dict) or set(payload) != {'revision', 'preview', 'clip_index', 'fingerprint', 'choice'}:
        raise ValueError('动作审阅请求字段无效')
    _validate_choice(payload['choice'])
    if type(payload['clip_index']) is not int or payload['clip_index'] < 0:
        raise ValueError('动作序号无效')
    with io.project_lock(root, 'motion-review'):
        stored, revision = load(root)
        if payload['revision'] != revision:
            raise registry.RevisionConflict('动作审阅已被修改；文本已保留，请重新加载后核对')
        view = describe(root, payload['preview'], stored=(stored, revision))
        entry = next((e for e in view['entries'] if e['clip_index'] == payload['clip_index']), None)
        if not entry or entry['source']['fingerprint'] != payload['fingerprint']:
            raise registry.RevisionConflict('动作源或上下文已变化，请重新观看后保存')
        if entry['context']['role'] != payload['choice']['role']:
            raise ValueError('角色用途与预览上下文不一致')
        record = {k: entry[k] for k in ('id', 'asset_id', 'art_asset_id', 'path', 'context', 'clip_index', 'clip_name', 'source', 'provenance')}
        record.update(choice=payload['choice'], reviewed_at=io.now(), observation=payload['preview'].get('observation'))
        updated = {'schema_version': 2, 'history': [*stored['history'], record]}
        if len(json.dumps(updated, ensure_ascii=False, indent=2).encode('utf-8')) > MAX_BYTES:
            raise ValueError('动作审阅记录超过 4 MB，请先归档历史')
        if load(root)[1] != revision:
            raise registry.RevisionConflict('记录在保存期间已变化')
        if stored['schema_version'] == 1:
            backup = io.local(root, '.asset-browser/motion-review.v1.' + revision + '.json')
            raw = _path(root).read_bytes()
            if backup.exists():
                if backup.read_bytes() != raw:
                    raise ValueError('旧版本备份冲突；原记录保持不变')
            else:
                with backup.open('xb') as stream:
                    stream.write(raw)
        io.write_json(_path(root), updated)
    return describe(root, payload['preview'])


def handoff(root, character_id=None):
    view = snapshot(root)
    candidates, excluded = [], []
    for entry in view['entries']:
        if character_id is not None and entry['context']['character_id'] != character_id:
            continue
        record = entry['review']
        if entry['state'] == 'current' and record['choice']['decision'] == 'keep':
            candidates.append(record)
        else:
            excluded.append(entry)
    return {'schema_version': 2, 'kind': 'motion-candidate-handoff', 'revision': view['revision'],
            'record_path': '.asset-browser/motion-review.json', 'character_id': character_id,
            'runtime_validation': 'not_checked', 'candidates': candidates, 'excluded': excluded}

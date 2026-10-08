"""Purpose categories are independent of format, usage, Art Direction tags and approval."""
import hashlib
import json
from functools import lru_cache
from pathlib import PurePosixPath
from . import art_registry
from .asset_review import safe_path
from record_io import project_lock, write_json

CATEGORIES = [
    ('character', '人物角色', 'avatar'), ('weapon', '武器装备', 'sword'),
    ('prop', '道具模型', 'tree'), ('environment', '地图场景', 'map'),
    ('animation', '动画资源', 'film'), ('vfx', '特效美术', 'spark'),
    ('material', '材质贴图', 'puzzle'), ('audio', '音乐音效', 'music'),
    ('ui', '二维美术与 UI', 'image'), ('code', '插件代码', 'code'),
    ('template', '蓝图与玩法模板', 'gamepad'), ('unclassified', '未分类', 'file')]
AUDIO_KINDS = {'music': '配乐', 'sfx': '音效', 'speech': '配音'}
TOPICS = {'archviz': '建筑可视化'}
CATEGORY_IDS = {row[0] for row in CATEGORIES}
DIRECTORIES = {
    'character': {'character', 'characters', '人物', '角色', '人物角色', 'metahumans'},
    'weapon': {'weapon', 'weapons', 'equipment', '武器', '装备', '武器装备'},
    'prop': {'prop', 'props', '道具', '道具模型'},
    'environment': {'map', 'maps', 'levels', 'scenes', 'environments', '场景', '地图', '地图场景'},
    'animation': {'animation', 'animations', 'motions', '动画', '动作', '动画资源'},
    'vfx': {'vfx', 'effects', '特效', '特效美术'},
    'material': {'material', 'materials', 'texture', 'textures', '材质', '贴图', '材质贴图'},
    'ui': {'ui', 'sprites', 'icons', 'illustrations', '界面', '精灵', '图标', '插画'},
    'code': {'plugins', 'scripts', '插件', '脚本'},
    'template': {'templates', 'gameplaytemplates', '玩法模板', '系统模板', '蓝图模板'}}
AUDIO_DIRS = {'music': {'music', 'bgm', '配乐', '音乐'},
              'sfx': {'sfx', 'soundeffects', '音效'},
              'speech': {'voice', 'voices', 'dialogue', 'speech', 'vo', '配音', '台词'}}
ENGINE_CLASSES = {'AnimSequence': 'animation', 'AnimMontage': 'animation', 'BlendSpace': 'animation',
                  'NiagaraSystem': 'vfx', 'NiagaraEmitter': 'vfx', 'ParticleSystem': 'vfx',
                  'Material': 'material', 'MaterialInstanceConstant': 'material', 'Texture2D': 'material',
                  'SoundWave': 'audio', 'SoundCue': 'audio', 'WidgetBlueprint': 'ui', 'World': 'environment'}


def definition():
    return {'categories': [{'id': key, 'label': label, 'icon': icon} for key, label, icon in CATEGORIES],
            'audioKinds': AUDIO_KINDS, 'topics': TOPICS}


def fields(value):
    if not isinstance(value, dict) or set(value) - {'category', 'audioKind', 'topics'}:
        raise ValueError('分类字段无效')
    category = value.get('category')
    audio = value.get('audioKind', '')
    topics = value.get('topics', [])
    if not isinstance(category, str) or category not in CATEGORY_IDS or not isinstance(audio, str) or audio not in {'', *AUDIO_KINDS}:
        raise ValueError('请选择有效的资产分类')
    if audio and category != 'audio':
        raise ValueError('配乐、音效、配音仅用于音乐音效分类')
    if not isinstance(topics, list) or len(topics) > len(TOPICS) or any(not isinstance(x, str) or x not in TOPICS for x in topics):
        raise ValueError('专题无效')
    return {'category': category, 'audioKind': audio, 'topics': list(dict.fromkeys(topics))}


def record_fields(value):
    result = fields({k: v for k, v in value.items() if k != 'sha256'})
    if 'sha256' in value:
        digest = value['sha256']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('分类文件版本无效')
        result['sha256'] = digest
    return result


def signature(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


@lru_cache(maxsize=4096)
def _version(path, stamp):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if signature(path) != stamp:
        raise art_registry.RevisionConflict('资产读取时已变化，请刷新目录')
    return digest.hexdigest()


def file_version(root, relative):
    path = art_registry.asset_path(root, relative)
    return _version(path, signature(path))


def load(root):
    path = safe_path(root, '.openaigame/asset-taxonomy.json', metadata=True)
    if path.exists() and path.stat().st_size > 4 * 1024**2:
        raise ValueError('资产分类记录过大')
    raw = path.read_bytes() if path.exists() else b''
    try:
        data = json.loads(raw.decode('utf-8-sig')) if raw else {'schemaVersion': 1, 'assignments': {}}
        if data.get('schemaVersion') != 1 or not isinstance(data.get('assignments'), dict):
            raise ValueError()
        for key, value in data['assignments'].items():
            art_registry.asset_path(root, key)
            record_fields(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('资产分类记录无法读取，原文件已保留；请修复后再保存') from None
    return data['assignments'], hashlib.sha256(raw).hexdigest()


def save(root, payload, assets):
    paths = payload.get('paths')
    if not isinstance(paths, list) or not 1 <= len(paths) <= 500 or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        raise ValueError('每次请选择 1–500 个不同资产')
    known = {a['path']: a for a in assets if not a.get('previewCopy')}
    for path in paths:
        if path not in known or not art_registry.asset_path(root, path).is_file():
            raise ValueError('资产不存在或已变化，请刷新目录')
    action = payload.get('action', 'set')
    if action not in ('set', 'reset'):
        raise ValueError('分类操作无效')
    value = fields(payload.get('classification')) if action == 'set' else None
    expected = payload.get('versions', {})
    if not isinstance(expected, dict) or set(expected) - set(paths):
        raise ValueError('分类文件版本无效')
    target = safe_path(root, '.openaigame/asset-taxonomy.json', metadata=True)
    with project_lock(root, 'asset-taxonomy'):
        assignments, revision = load(root)
        if revision != payload.get('revision'):
            raise art_registry.RevisionConflict('分类已被其他窗口修改，请刷新后再保存')
        # Validate the whole batch before changing any assignments.
        versions = {}
        for path in paths:
            versions[path] = file_version(root, path)
            observed = expected.get(path, known[path].get('classification', {}).get('version'))
            if observed != versions[path]:
                raise art_registry.RevisionConflict('资产内容已变化，请刷新后核对分类')
        previous = payload.get('previousPath')
        previous_record = {}
        if previous:
            if len(paths) != 1 or previous not in assignments or art_registry.asset_path(root, previous).exists():
                raise ValueError('原分类路径无效或仍然存在')
            if assignments[previous].get('sha256') != versions[paths[0]]:
                raise art_registry.RevisionConflict('文件内容与原分类不同，不能迁移分类')
            if known[paths[0]].get('classification', {}).get('previousPath') != previous:
                raise ValueError('无法唯一确认文件移动，请按当前资产重新分类')
            previous_record = assignments.pop(previous)
        for path in paths:
            if action == 'reset': assignments.pop(path, None)
            else:
                # Retain legacy topic metadata when the new UI only changes category.
                topics = value['topics'] if 'topics' in payload['classification'] else assignments.get(path, previous_record).get('topics', [])
                assignments[path] = {**value, 'topics': topics, 'sha256': versions[path]}
        data = {'schemaVersion': 1, 'assignments': assignments}
        if len(json.dumps(data, ensure_ascii=False).encode('utf-8')) > 4 * 1024**2:
            raise ValueError('资产分类记录过大')
        write_json(target, data)
    return {'updated': len(paths), 'revision': load(root)[1]}


def classify(asset, assignments, characters):
    path = asset['path']; kind = asset['kind']; ext = asset['ext'].lower()
    folders = [part.casefold() for part in PurePosixPath(path).parts[:-1]]
    topics = ['archviz'] if any(p in {'archviz', 'architecturalvisualization', '建筑可视化'} for p in folders) else []
    category, basis, audio = 'unclassified', '待分类', ''
    if path in assignments:
        return {**fields({k: v for k, v in assignments[path].items() if k != 'sha256'}), 'basis': '已保存分类', 'manual': True}
    if isinstance(asset.get('assetClass'), str) and asset['assetClass'] in ENGINE_CLASSES:
        category, basis = ENGINE_CLASSES[asset['assetClass']], '引擎类型记录'
    elif path in {c['model'] for c in characters}:
        category, basis = 'character', '角色绑定清单'
    elif path in {a['path'] for c in characters for a in c.get('actions', [])}:
        category, basis = 'animation', '角色动作关联'
    elif kind in {'audio', 'animation', 'vfx', 'texture', 'code'}:
        category, basis = {'texture': 'material'}.get(kind, kind), '资源格式'
    elif kind == 'model' and asset.get('animations') and asset.get('meshes') == 0:
        category, basis = 'animation', '已读取动作片段，文件无网格'
    elif ext in {'umap', 'unity'}:
        category, basis = 'environment', '场景格式'
    elif ext in {'vfx', 'efkefc'}:
        category, basis = 'vfx', '特效格式'
    elif ext in {'shader', 'gdshader', 'hlsl', 'usf'}:
        category, basis = 'material', '着色器格式'
    elif ext in {'ttf', 'otf'}:
        category, basis = 'ui', '字体格式'
    elif isinstance(asset.get('sourceKind'), str) and asset['sourceKind'] in {'animation', 'vfx', 'ui', 'texture', 'hdri', 'font'}:
        proposed = {'texture': 'material', 'hdri': 'material', 'font': 'ui'}.get(asset['sourceKind'], asset['sourceKind'])
        # Pack-level labels never turn dependency textures into characters/animations.
        allowed = {'animation': {'model', 'animation'}, 'vfx': {'vfx', 'engine'},
                   'ui': {'image', 'other', 'engine'}, 'material': {'image', 'texture', 'engine'}}
        if kind in allowed[proposed]: category, basis = proposed, '素材来源登记'
    if category == 'unclassified':
        compatible = {
            'character': {'model', 'engine'}, 'weapon': {'model', 'engine'},
            'prop': {'model', 'engine'}, 'environment': {'model', 'engine'},
            'animation': {'animation', 'model', 'engine'}, 'vfx': {'vfx', 'engine'},
            'material': {'image', 'texture', 'engine'}, 'ui': {'image', 'engine', 'other'},
            'code': {'code'}, 'template': {'engine', 'code'}}
        for folder in reversed(folders):
            found = [key for key, names in DIRECTORIES.items() if folder in names and kind in compatible[key]]
            if found:
                category, basis = found[0], '按目录建议，可手动调整'
                break
    if category == 'audio':
        if isinstance(asset.get('sourceAudioKind'), str) and asset['sourceAudioKind'] in AUDIO_KINDS:
            audio = asset['sourceAudioKind']
        for folder in reversed(folders):
            if audio: break
            audio = next((key for key, names in AUDIO_DIRS.items() if folder in names), '')
            if audio: break
    return {'category': category, 'audioKind': audio, 'topics': topics, 'basis': basis, 'manual': False}


def attach(root, assets, characters):
    error = None
    try: assignments, revision = load(root)
    except (ValueError, OSError) as exc: assignments, revision, error = {}, None, str(exc)
    missing = {p: r for p, r in assignments.items() if not art_registry.asset_path(root, p).exists()}
    versions = {}
    for asset in assets:
        try: versions[asset['path']] = file_version(root, asset['path'])
        except (OSError, ValueError): versions[asset['path']] = None
    # A duplicate or a format change is not evidence of a rename.
    identities = {}
    for asset in assets:
        if not asset.get('previewCopy'):
            key = (versions[asset['path']], PurePosixPath(asset['path']).suffix.lower())
            identities.setdefault(key, []).append(asset['path'])
    for asset in assets:
        path = asset['path']; version = versions[path]
        record = assignments.get(path); previous = None; review = None
        if record and (not record.get('sha256') or record['sha256'] != version):
            review = '旧分类未记录文件版本，请核对后保存' if not record.get('sha256') else '文件内容已变化，请重新核对分类'
        if record is None and version and not asset.get('previewCopy'):
            key = (version, PurePosixPath(path).suffix.lower())
            matches = [p for p, r in missing.items() if (r.get('sha256'), PurePosixPath(p).suffix.lower()) == key]
            if len(matches) == 1 and len(identities.get(key, [])) == 1:
                previous = matches[0]; record = missing[previous]
                review = '检测到文件移动，请核对原分类后保存'
        confirmed = {path: record} if record and version and not review else {}
        value = classify(asset, confirmed, characters)
        value.update(version=version, saved=bool(record), needsReview=bool(review))
        if review:
            value.update(reviewReason=review, previousCategory=record['category'], previousAudioKind=record.get('audioKind', ''))
        if previous: value['previousPath'] = previous
        asset['classification'] = value
    return {**definition(), 'revision': revision, 'error': error,
            'missingRecords': sorted(missing),
            'needsReview': [a['path'] for a in assets if a['classification']['needsReview']]}

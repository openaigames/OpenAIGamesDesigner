"""Production handoff in the existing Art Direction authority, not a second ledger."""
from copy import deepcopy
import hashlib
import re
from pathlib import Path
from record_io import local, digest, snapshot_files, changed_files, project_lock, now
from . import art_registry as registry

LEVELS = ('recorded', 'integrated', 'verified')


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000 or '\x00' in value:
        raise ValueError('Missing or invalid ' + name)
    return value.strip()


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        raise ValueError('Invalid asset/object ID')
    return value


def paths(value, *, empty=True):
    if not isinstance(value, list) or len(value) > 4096 or any(not isinstance(x, str) or not x for x in value):
        raise ValueError('Expected explicit project-relative paths')
    if not empty and not value:
        raise ValueError('An explicit nonempty asset scope is required')
    if len(set(value)) != len(value):
        raise ValueError('Duplicate asset path')
    return value


def validate_scope(scope):
    if not isinstance(scope, dict) or set(scope) - {'paths', 'require'}:
        raise ValueError('Asset scope accepts paths and require')
    paths(scope.get('paths'), empty=False)
    if scope.get('require', 'recorded') not in LEVELS:
        raise ValueError('Unknown asset delivery requirement')
    return scope


def object_definition(value):
    if not isinstance(value, dict) or set(value) != {'id', 'label', 'tags'}:
        raise ValueError('Object requires id, label and tags')
    return {'id': identity(value['id']), 'label': text(value['label'], 'object purpose'),
            'tags': registry.validate_tags(value['tags'])}


def request_context(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - {'object', 'source', 'license'}:
        raise ValueError('art_record accepts object, source and license only')
    out = deepcopy(value)
    if 'object' in out:
        out['object'] = object_definition(out['object'])
    for key in ('source', 'license'):
        if key in out:
            out[key] = text(out[key], key)
    return out


def file_refs(root, value):
    # Consumers may name a function/scene node after #; hash the actual file.
    names = paths(value)
    return snapshot_files(root, list(dict.fromkeys(p.split('#', 1)[0] for p in names)))


def normalize_details(root, patch, previous, version):
    allowed = {'production', 'selection', 'integration', 'verification', 'derivedFrom', 'legacyRef'}
    if not isinstance(patch, dict) or set(patch) - allowed:
        raise ValueError('Unknown production record fields')
    detail = deepcopy(previous)
    detail.update(deepcopy(patch))
    if previous.get('sha256') != version:
        # A file replacement never inherits an earlier runtime/quality conclusion.
        for field in ('integration', 'verification'):
            if field not in patch:
                detail.pop(field, None)
    detail['sha256'] = version
    if 'production' in patch:
        item = patch['production']
        if not isinstance(item, dict) or set(item) - {'method', 'source', 'license', 'evidence'}:
            raise ValueError('Invalid production provenance')
        if item.get('method') not in {'generated', 'acquired', 'authored', 'converted', 'procedural', 'existing'}:
            raise ValueError('Unknown production method')
        item = {**item, 'source': text(item.get('source'), 'source'), 'license': text(item.get('license'), 'license or explicit unknown')}
        item['evidence'] = paths(item.get('evidence', []), empty=False)
        item['dependencies'] = file_refs(root, item['evidence'])
        detail['production'] = item
    if 'selection' in patch:
        item = patch['selection']
        if not isinstance(item, dict) or set(item) != {'state', 'basis'} or item.get('state') not in {'candidate', 'adopted', 'replaced', 'unknown'}:
            raise ValueError('Selection needs state and actual basis')
        detail['selection'] = {**item, 'basis': text(item['basis'], 'selection basis')}
    if 'integration' in patch:
        item = patch['integration']
        if not isinstance(item, dict) or set(item) - {'state', 'consumers', 'evidence'} or item.get('state') not in {'not_run', 'imported', 'procedural', 'failed'}:
            raise ValueError('Invalid integration record')
        consumers = paths(item.get('consumers', []))
        evidence = paths(item.get('evidence', []))
        if item['state'] in {'imported', 'procedural'} and (not consumers or not evidence):
            raise ValueError('Engine integration needs actual consumers and evidence')
        detail['integration'] = {**item, 'consumers': consumers, 'evidence': evidence,
                                 'dependencies': file_refs(root, consumers + [p for p in evidence if p not in consumers])}
        if detail['integration'] != previous.get('integration') and 'verification' not in patch:
            detail.pop('verification', None)
    if 'derivedFrom' in patch:
        sources = paths(patch['derivedFrom'])
        detail['derivedFrom'] = snapshot_files(root, sources)
    if 'legacyRef' in patch:
        ref = text(patch['legacyRef'], 'legacy record reference')
        if not local(root, ref.split('#', 1)[0]).is_file():
            raise ValueError('Historical authority does not exist')
        detail['legacyRef'] = ref
    if 'verification' in patch:
        item = patch['verification']
        if not isinstance(item, dict) or set(item) - {'state', 'scope', 'evidence'} or item.get('state') not in {'not_run', 'passed', 'failed', 'partial'}:
            raise ValueError('Invalid verification record')
        evidence = paths(item.get('evidence', []))
        if item['state'] != 'not_run' and not evidence:
            raise ValueError('Executed verification requires saved evidence')
        detail['verification'] = {**item, 'scope': text(item.get('scope'), 'verification scope'),
                                  'evidence': evidence, 'dependencies': file_refs(root, evidence)}
        # Bind an observation to the consumer/import snapshot, not only the mesh.
        detail['verification']['dependencies'].update(detail.get('integration', {}).get('dependencies', {}))
    if detail.get('production', {}).get('method') == 'converted' and not detail.get('derivedFrom'):
        raise ValueError('Converted assets need actual source files')
    return detail


def stage_label(detail):
    labels = {'generated':'已生成', 'acquired':'已获取', 'authored':'已制作', 'converted':'已转换', 'procedural':'程序实现', 'existing':'既有资产'}
    integration = {'not_run':'未接入', 'imported':'已接入', 'procedural':'代码内置，无独立导入', 'failed':'接入失败'}
    verification = {'not_run':'未验证', 'passed':'指定范围验证通过', 'failed':'验证失败', 'partial':'部分验证'}
    return '；'.join([labels.get(detail.get('production', {}).get('method'), '来源待补'),
                     integration.get(detail.get('integration', {}).get('state'), '接入待记录'),
                     verification.get(detail.get('verification', {}).get('state'), '未验证')])


def apply(root, manifest, *, only_missing=False):
    """One validated batch, optimistic revision, shared lock, no engine execution."""
    if not isinstance(manifest, dict) or set(manifest) - {'schema_version', 'revision', 'objects', 'assets'} or manifest.get('schema_version') != 1:
        raise ValueError('Expected asset handoff schema_version 1')
    rows = manifest.get('assets')
    if not isinstance(rows, list) or not rows or len(rows) > 4096:
        raise ValueError('Expected a nonempty bounded asset batch')
    with project_lock(root, 'art-registry'):
        initializing = registry.can_initialize(root)
        if initializing:
            # Validate everything before even creating the optional record tables.
            data = {'objects': {}, 'assets': {}, 'lifecycle': {}, 'revision': None}
        else:
            data = registry.load(root)
        if 'revision' in manifest and manifest['revision'] != data['revision']:
            raise registry.RevisionConflict('Asset authority changed; reread before applying')
        before = deepcopy(data)
        for definition in manifest.get('objects', []):
            obj = object_definition(definition)
            if obj['id'] in data['objects'] and data['objects'][obj['id']] != obj:
                raise ValueError('Existing object differs; edit its shared purpose explicitly before handoff')
            data['objects'][obj['id']] = obj
        seen = set()
        for entry in rows:
            if not isinstance(entry, dict) or set(entry) - {'id', 'path', 'sha256', 'objectId', 'title', 'details', 'previousPath'}:
                raise ValueError('Unknown asset handoff fields')
            rel = entry.get('path')
            path = registry.asset_path(root, rel)
            if path.relative_to(root).as_posix() != rel:
                raise ValueError('Use canonical project-relative file paths')
            if rel in seen or not path.is_file():
                raise ValueError('Duplicate or missing file in asset handoff')
            seen.add(rel)
            version = digest(path)
            if entry.get('sha256') != version:
                raise ValueError('Asset bytes changed before handoff: ' + rel)
            previous_path = entry.get('previousPath')
            old = data['assets'].get(rel)
            if previous_path:
                previous_file = registry.asset_path(root, previous_path)
                if old or previous_file.exists() or previous_path not in data['assets']:
                    raise ValueError('Move requires a missing old path and an unregistered destination')
                old = data['assets'][previous_path]
                if old['sha256'] != version or Path(previous_path).suffix.lower() != path.suffix.lower():
                    raise ValueError('Move must preserve exact file content and format')
                del data['assets'][previous_path]
            if only_missing and old:
                if old['sha256'] != version:
                    raise registry.RevisionConflict('Existing production record names another version: '+rel)
                continue
            key = identity(entry.get('id', old['id'] if old else 'A' + hashlib.sha256(rel.encode()).hexdigest()[:20]))
            if old and key != old['id']:
                raise ValueError('Preserve the existing stable asset ID')
            if any(a['id'] == key and p != rel for p, a in data['assets'].items()):
                raise ValueError('Asset ID is already assigned to another file; use a derived ID')
            object_id = entry.get('objectId', old['objectId'] if old else '')
            if object_id and object_id not in data['objects']:
                raise ValueError('Unknown object ID')
            prior_detail = deepcopy(data['lifecycle'].get(key, {}))
            if previous_path:
                prior_detail.pop('integration', None)
                prior_detail.pop('verification', None)
            detail = normalize_details(root, entry.get('details', {}), prior_detail, version)
            production = detail.get('production', {})
            data['assets'][rel] = {'id': key, 'objectId': object_id, 'kind': path.suffix.lstrip('.').upper() or 'FILE',
                                  'title': text(entry.get('title', old['title'] if old else path.stem), 'asset name'),
                                  'path': rel, 'sha256': version, 'stage': stage_label(detail),
                                  'source': production.get('source', old['source'] if old else '待核实') + '；许可：' + production.get('license', '待核实')}
            data['lifecycle'][key] = detail
        if initializing:
            registry._initialize(root)
            fresh = registry.load(root)
            fresh.update(objects=data['objects'], assets=data['assets'], lifecycle=data['lifecycle'])
            data = fresh
        if initializing or any(before.get(k) != data.get(k) for k in ('objects', 'assets', 'lifecycle')):
            # Preserve recoverable authority text before the one-file commit.
            original = registry.document_path(root).read_bytes()
            backup = local(root, '.openaigame/art-history/' + hashlib.sha256(original).hexdigest() + '.md')
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(original)
            registry._write(root, data, data['revision'])
        return {'document': registry.document_path(root).relative_to(root).as_posix(),
                'paths': sorted(seen), 'revision': registry.load(root)['revision']}


def check(root, scope):
    validate_scope(scope)
    level = scope.get('require', 'recorded')
    issues, warnings = [], []
    try:
        data = registry.load(root)
    except (OSError, ValueError) as error:
        return {'ok': False, 'require': level, 'paths': scope['paths'], 'issues': [str(error)], 'warnings': []}
    for rel in scope['paths']:
        problems = []
        row = data['assets'].get(rel)
        if not row:
            issues.append(rel + ': 未登记到权威资产清单')
            continue
        try:
            path = registry.asset_path(root, rel)
            if not path.is_file() or digest(path) != row['sha256']:
                problems.append('文件缺失或登记版本已变化')
            obj = data['objects'].get(row['objectId'])
            if not obj or not obj['label']:
                problems.append('缺少对象/用途')
            detail = data['lifecycle'].get(row['id'], {})
            if not detail or detail.get('sha256') != row['sha256']:
                problems.append('缺少当前版本生产交接记录；需关联历史依据或补齐本轮事实')
            production = detail.get('production', {})
            if not production.get('source') or not production.get('license') or not production.get('evidence'):
                problems.append('缺少来源、许可状态或制作依据')
            # Production evidence is historical; mutable task files need not stay byte-identical.
            for evidence in production.get('evidence', []):
                if not local(root, evidence.split('#', 1)[0]).is_file():
                    problems.append('来源依据丢失：' + evidence)
            if any(word in production.get('license', '').lower() for word in ('unknown','unverified','待核实','未知')):
                warnings.append(rel + ': 许可依据仍待核实，登记通过不代表可发布')
            if not detail.get('selection', {}).get('basis'):
                problems.append('缺少选用/候选依据')
            integration = detail.get('integration', {})
            if level in {'integrated', 'verified'}:
                if detail.get('selection', {}).get('state') != 'adopted':
                    problems.append('没有采用依据')
                if integration.get('state') not in {'imported', 'procedural'} or not integration.get('consumers') or not integration.get('evidence'):
                    problems.append('缺少实际接入、消费者或导入证据')
                if changed_files(root, integration.get('dependencies', {})):
                    problems.append('消费者/导入依据已变化，需复核接入')
            if level == 'verified':
                verification = detail.get('verification', {})
                if verification.get('state') != 'passed' or not verification.get('scope') or not verification.get('evidence'):
                    problems.append('指定范围验证未通过或缺少证据')
                if changed_files(root, verification.get('dependencies', {})):
                    problems.append('验证依据或消费者已变化')
            if detail.get('derivedFrom') and changed_files(root, detail['derivedFrom']):
                warnings.append(rel + ': 派生源已变化或移走；当前产物未被自动替换')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            problems.append('生产记录无效：' + str(error))
        issues.extend(rel + ': ' + problem for problem in problems)
    return {'ok': not issues, 'require': level, 'paths': scope['paths'], 'issues': issues, 'warnings': warnings,
            'quality_validation': 'record completeness and version checks only; recorded scope is not independently judged'}


def automatic(root, files, context, provenance, method, source, *, derived=None):
    context = request_context(context)
    manifest = {'schema_version': 1, 'objects': [context['object']] if context.get('object') else [], 'assets': []}
    for item in files:
        details = {'production': {'method': method, 'source': context.get('source', source),
                                  'license': context.get('license', '待核实'), 'evidence': [provenance]},
                   'selection': {'state': 'candidate', 'basis': '制作/获取任务输出；尚未声明工程采用'},
                   'integration': {'state': 'not_run'},
                   'verification': {'state': 'not_run', 'scope': '未执行游戏内验证'}}
        if derived:
            details['derivedFrom'] = derived
        row = {'path': item['path'], 'sha256': item['sha256'], 'details': details}
        if context.get('object'):
            row['objectId'] = context['object']['id']
        manifest['assets'].append(row)
    return apply(root, manifest, only_missing=True)

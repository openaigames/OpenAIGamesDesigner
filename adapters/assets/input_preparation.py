"""Offline asset requirements, input compilation and frozen submission evidence.

Semantic reviews are Agent declarations, never measurements of output quality.
This module does not access credentials, upload references or call a model.
"""
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path

from . import api_common, ark, elevenlabs, generation_capabilities, model_defaults
from . import hunyuan_inputs, tripo_inputs
from tools.validate_records import contained, contract, digest

PROVIDERS = ('tripo', 'hunyuan3d', 'seedream', 'seedance', 'elevenlabs', 'image')
REVIEW_CHECKS = ('brief_accounted_for', 'requirements_preserved',
                 'no_unrequested_features', 'reference_roles_checked')


def validate_documents(spec, plan):
    errors = contract('asset-requirements', spec) + contract('asset-input-plan', plan)
    if errors:
        raise ValueError('; '.join(errors))
    for rows, label in ((spec['requirements'], 'requirement'), (spec['references'], 'reference')):
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate ' + label + ' ID')
    for row in spec['requirements']:
        if ('attribute' in row) != ('value' in row):
            raise ValueError('Structured constraints need both attribute and value')
    for text in [spec['brief']] + [r['text'] for r in spec['requirements']]:
        if not text.strip():
            raise ValueError('Brief and requirements must not be blank')


def capabilities(provider, request):
    if provider in ('tripo', 'hunyuan3d'):
        return generation_capabilities.describe(provider, request)
    if provider not in PROVIDERS:
        raise ValueError('Unsupported input preparation provider')
    return {'provider': provider, 'prompt': 'required',
            'output': {'image': 'image', 'seedream': 'image', 'seedance': 'video',
                       'elevenlabs': request['parameters'].get('kind')}[provider]}


def effective_settings(root, provider):
    """Read project routing only; preparation works without configured secrets."""
    path = contained(root, '.openaigame/asset-providers.json')
    config = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError('Provider configuration must be an object')
    settings = config.get(provider, {'mode': 'host' if provider == 'image' else 'api'})
    if not isinstance(settings, dict):
        raise ValueError('Provider settings must be an object')
    if provider == 'image':
        if settings != {'mode': 'host'}:
            raise ValueError('Input preparation supports host image generation, not arbitrary command wrappers')
    else:
        api_common.settings_check(settings)
    return settings


def reference_files(root, spec):
    result = []
    for ref in spec['references']:
        path = contained(root, ref['path'])
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or empty reference: ' + ref['path'])
        result.append({**ref, 'sha256': digest(path), 'snapshot': ref['path']})
    return result


def absolute_request(root, request):
    result = deepcopy(request)
    for item in result['inputs']:
        path = contained(root, item.get('snapshot', item['path']))
        if not path.is_file() or digest(path) != item['sha256']:
            raise ValueError('Prepared reference changed: ' + item['path'])
        item['snapshot'] = str(path)
    return result


def wire_preview(provider, request, settings):
    """Use adapter payload builders; replace binary data/tokens with hash labels."""
    parameters = deepcopy(request['parameters'])
    inputs = request['inputs']
    labels = ['<reference sha256=' + item['sha256'] + '>' for item in inputs]
    if provider == 'tripo':
        images = tripo_inputs.read_images(request)
        tokens = {view: '<file_token sha256=' + next(
            i['sha256'] for i in inputs if i.get('view', 'front') == view) + '>' for view in images}
        from .tripo import payload
        body = payload(request, tokens)
        endpoint = generation_capabilities.connection(provider, settings, mode=tripo_inputs.kind(request))['submit_url']
    elif provider == 'hunyuan3d':
        body = hunyuan_inputs.build_payload(request)
        for item, label in zip(inputs, labels):
            view = item.get('view', 'front')
            if view == 'front':
                body['ImageBase64'] = label
            else:
                for row in body.get('MultiViewImages', []):
                    if row['ViewType'] == view:
                        row['ViewImageBase64'] = label
        connection = generation_capabilities.connection(provider, settings)
        endpoint = connection['submit_url']
    elif provider in ('seedream', 'seedance'):
        body = ark.payload(provider, request)
        if provider == 'seedream' and inputs:
            body['image'] = labels[0]
        if provider == 'seedance' and inputs:
            body['content'][1]['image_url']['url'] = labels[0]
        endpoint = ark.BASE + ('/images/generations' if provider == 'seedream' else '/contents/generations/tasks')
    elif provider == 'elevenlabs':
        path, body = elevenlabs.payload(request)
        endpoint = elevenlabs.BASE + path
    else:
        body = {'prompt': parameters['prompt'], 'references': labels}
        endpoint = 'host image tool (Agent dispatch; arguments depend on the available host tool)'
    return {'endpoint': endpoint, 'body': body, 'reference_values': 'hash placeholders; no upload performed',
            'submitted': False}


def compile_inputs(root, spec, plan, settings, files=None):
    validate_documents(spec, plan)
    files = reference_files(root, spec) if files is None else deepcopy(files)
    errors, warnings, coverage = [], [], []

    def error(code, message):
        errors.append({'code': code, 'message': message})

    refs = {r['id']: r for r in files}
    decisions = plan['references']
    chosen = [r['id'] for r in decisions if r['send']]
    decision_ids = [r['id'] for r in decisions]
    if len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != set(refs):
        error('reference_decisions', 'Decide whether to send every reference exactly once; explain exclusions')
    for decision in decisions:
        if not decision['send'] and not decision.get('reason', '').strip():
            error('reference_exclusion', 'Excluded references need a reason: ' + decision['id'])
    if len(chosen) != len(set(chosen)):
        error('duplicate_reference', 'The same reference cannot be sent twice')
    inputs = [{k: refs[rid][k] for k in ('path', 'snapshot', 'sha256', 'view') if k in refs[rid]}
              for rid in chosen if rid in refs]
    if len({item['sha256'] for item in inputs}) != len(inputs):
        error('duplicate_image', 'Do not send identical files as distinct references or views')
    provider = plan['provider']
    p = deepcopy(plan['parameters'])
    if any(field in p for field in ('prompt', 'Prompt', 'text')):
        error('prompt_override', 'Use the brief or rewrite; do not override the compiled prompt in parameters')
    if provider == 'elevenlabs' and 'timing' in p:
        error('timing_route', 'Use the existing audio window workflow for timing-linked requests')
    request = model_defaults.prepare(provider, {'parameters': p, 'inputs': inputs, 'brief': spec['brief']},
                                     settings, new_job=True)
    p = request['parameters']
    try:
        capability = capabilities(provider, request)
    except ValueError as exc:
        capability = {'prompt': 'none', 'output': None}
        error('capability', str(exc))
    output = 'image' if capability['output'] == 'images' else capability['output']
    if spec['kind'] != output:
        error('output_kind', 'Asset kind does not match the selected generation route')
    text_allowed = capability['prompt'] != 'none'
    if not text_allowed and plan.get('rewrite'):
        error('unsent_rewrite', 'This route cannot receive the rewritten prompt')

    routes = {}
    for route in plan['routes']:
        rid = route['requirement']
        if rid in routes:
            error('duplicate_route', 'Duplicate route for ' + rid)
        routes[rid] = route
    requirements = {r['id']: r for r in spec['requirements']}
    if set(routes) != set(requirements):
        error('coverage', 'Every requirement needs exactly one route; missing=' +
              ','.join(sorted(set(requirements) - set(routes))) + '; unknown=' +
              ','.join(sorted(set(routes) - set(requirements))))
    attributes = {}
    clauses = []
    for rid, requirement in requirements.items():
        if requirement['priority'] == 'must' and 'attribute' in requirement:
            key, value = requirement['attribute'], requirement['value']
            if key in attributes and attributes[key] != value:
                error('conflicting_constraint', 'Conflicting required values for ' + key)
            attributes[key] = value
        route = routes.get(rid, {'via': 'unresolved'})
        via = route['via']
        row = {'requirement': rid, 'text': requirement['text'], 'priority': requirement['priority'],
               'via': via, 'output_verified': False}
        if via == 'prompt':
            if not text_allowed:
                error('unsupported_prompt', 'Text cannot be sent for requirement ' + rid)
            if spec['kind'] == 'speech':
                error('speech_instructions', 'Speech text must stay literal; do not append production instructions')
            clauses.append('[' + rid + '] ' + requirement['text'])
        elif via == 'reference':
            targets = route.get('references', [])
            if not targets or len(targets) != len(set(targets)) or any(r not in chosen for r in targets):
                error('unsent_reference', 'Requirement ' + rid + ' needs selected, distinct reference IDs')
            if not route.get('evidence', '').strip():
                error('reference_evidence', 'Describe what was actually observed for ' + rid)
            row.update(references=targets, evidence=route.get('evidence', ''),
                       evidence_kind='agent_declaration; visual correctness not measured')
        elif via == 'postprocess':
            if not route.get('reason', '').strip() or not route.get('check', '').strip():
                error('deferred_check', 'Deferred requirement ' + rid + ' needs an operation and acceptance check')
            row.update(reason=route.get('reason', ''), check=route.get('check', ''), status='pending')
            warnings.append('Deferred; not guaranteed by generation: ' + rid)
        else:
            error('unresolved_requirement', 'Unresolved requirement: ' + rid)
        coverage.append(row)

    review = plan.get('review', {})
    if (not review.get('reviewer', '').strip() or not review.get('notes', '').strip()
            or any(review.get(key) is not True for key in REVIEW_CHECKS)):
        error('semantic_review', 'Agent must review brief coverage, preserved intent, additions and reference roles')
    rewrite = plan.get('rewrite')
    if rewrite and spec['kind'] == 'speech':
        error('speech_rewrite', 'Speech uses the exact brief; edit the specification explicitly to change spoken words')
    base = rewrite['text'] if rewrite else spec['brief']
    if rewrite and (not base.strip() or not rewrite['reason'].strip()):
        error('rewrite_reason', 'Rewriting needs nonblank text and a reason')
    prompt = base + ('\n\n' + '\n'.join(clauses) if clauses else '')
    field = 'Prompt' if provider == 'hunyuan3d' else 'text' if provider == 'elevenlabs' else 'prompt'
    if text_allowed:
        p[field] = prompt
    preview = None
    try:
        for item in inputs:
            path = contained(root, item['snapshot'])
            if path.stat().st_size > 20 * 1024**2:
                raise ValueError('Reference exceeds the preparation limit of 20 MiB')
            data = path.read_bytes()
            kind = ark.image_kind(data)
            expected = 'jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else path.suffix.lower()[1:]
            if expected != kind or min(hunyuan_inputs.image_size(data, kind)) <= 0:
                raise ValueError('Reference signature or dimensions do not match its file type')
            if provider not in ('tripo', 'hunyuan3d') and 'view' in item:
                raise ValueError('View metadata is supported only by 3D adapters')
        if provider in ('seedream', 'seedance'):
            request = ark.prepare(provider, request)
        if provider == 'image':
            if set(p) != {'prompt'} or not prompt.strip() or len(inputs) > 5:
                raise ValueError('Host image preparation accepts a prompt and up to five image references')
            for item in inputs:
                path = contained(root, item['snapshot'])
                if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                    raise ValueError('Host references must be PNG/JPEG/WebP')
                ark.image_kind(path.read_bytes()[:32])
                if 'view' in item:
                    raise ValueError('View metadata is supported only by 3D adapters')
        else:
            api_common.validate_request(provider, request, settings)
        preview = wire_preview(provider, absolute_request(root, request), settings)
        from . import model_prompt_policy
        model_prompt_policy.require(provider, request, settings, root)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error('adapter_validation', str(exc))
    if not text_allowed:
        warnings.append('The brief and requirement text stay local; only selected reference images are sent')
    warnings.append('Input review does not verify visual consistency, generated quality or engine readiness')
    return {'schema_version': 1, 'asset_id': spec['asset_id'], 'provider': provider,
            'status': 'blocked' if errors else 'ready', 'errors': errors, 'warnings': warnings,
            'request': request, 'coverage': coverage, 'preview': preview,
            'prompt_diff': '\n'.join(difflib.unified_diff(spec['brief'].splitlines(), base.splitlines(),
                                                        fromfile='original brief', tofile='prepared base', lineterm='')),
            'review': {**review, 'kind': 'agent_declaration', 'quality_verified': False},
            'references': files, 'spec': deepcopy(spec), 'plan': deepcopy(plan), 'settings': deepcopy(settings)}


def request_identity(request):
    """Snapshot locations may move during queuing/retry; content and roles may not."""
    return {'parameters': request.get('parameters', {}), 'brief': request.get('brief'),
            'inputs': [{k: item[k] for k in ('path', 'sha256', 'view') if k in item}
                       for item in request.get('inputs', [])],
            **{k: request[k] for k in ('lineage', 'art_record', 'iteration') if k in request}}


def verify_request(root, provider, request, settings, *, fresh=False):
    link = request.get('preparation')
    if link is None:
        if request.get('iteration'):
            raise ValueError('Iteration requests require their input preparation')
        return None
    if not isinstance(link, dict) or set(link) != {'path', 'sha256'}:
        raise ValueError('Invalid preparation record link')
    root = Path(root).resolve()
    path = contained(root, link['path'])
    if not path.is_file() or digest(path) != link['sha256']:
        raise ValueError('Preparation record is missing or changed')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schema_version') != 1 or record.get('status') != 'ready':
        raise ValueError('Input preparation has unresolved requirements')
    if record['provider'] != provider or record['settings'] != settings:
        raise ValueError('Provider or settings changed after input preparation; prepare again')
    if request_identity(request) != request_identity(record['request']):
        raise ValueError('Generation request changed after input preparation; prepare again')
    for ref in record['references']:
        target = contained(root, ref['snapshot'])
        if not target.is_file() or digest(target) != ref['sha256']:
            raise ValueError('Prepared reference snapshot changed: ' + ref['path'])
    if fresh:
        for source in record['sources'] + record['references']:
            target = contained(root, source['path'])
            if not target.is_file() or digest(target) != source['sha256']:
                raise ValueError('Source changed after input preparation: ' + source['path'])
    # Queued jobs use new snapshots; check those too, including worker absolute paths.
    for item in request['inputs']:
        target = Path(item.get('snapshot', item['path']))
        target = target.resolve() if target.is_absolute() else contained(root, str(target))
        if not target.is_relative_to(root) or not target.is_file() or digest(target) != item['sha256']:
            raise ValueError('Queued preparation input changed')
    if request.get('iteration'):
        from . import iteration
        iteration.verify_request(root, provider, request, settings)
    return record


def render_preview(record):
    lines = ['# Asset Input Preparation', '', 'Asset: ' + record['asset_id'],
             'Provider: ' + record['provider'], 'State: ' + record['status'], '',
             'This records intended inputs, not generation, payment approval or output quality.', '',
             '## Constraint coverage', '']
    for row in record['coverage']:
        lines.append('- ' + row['requirement'] + ' (' + row['via'] + '): ' + row['text'])
        if row.get('check'):
            lines.append('  Acceptance check: ' + row['check'])
    lines += ['', '## Reference decisions', '']
    references = {r['id']: r for r in record['references']}
    for decision in record['plan']['references']:
        ref = references.get(decision['id'], {})
        lines.append('- ' + decision['id'] + ': ' + ('send' if decision['send'] else 'local only') +
                     '; role=' + ref.get('role', '?') + '; path=' + ref.get('path', '?') +
                     '; ' + decision.get('reason', ''))
        if Path(ref.get('snapshot', '')).suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
            lines += ['', '![' + decision['id'] + '](references/' + Path(ref['snapshot']).name + ')', '']
    lines += ['', '## Prompt change', '', '```diff', record['prompt_diff'] or '(original brief retained)', '```',
              '', '## Submission preview', '', '```json', json.dumps(record['preview'], ensure_ascii=False, indent=2), '```',
              '', '## Checks', '']
    lines += ['- ' + e['code'] + ': ' + e['message'] for e in record['errors']]
    lines += ['- ' + warning for warning in record['warnings']]
    return '\n'.join(lines) + '\n'


def prepare(root, spec_path, plan_path, output, *, context=None):
    root = Path(root).resolve()
    destination = contained(root, output)
    if destination.exists():
        raise ValueError('Preparation output already exists; use a new directory to preserve history')
    sources = []
    documents = []
    for relative in (spec_path, plan_path):
        source = contained(root, relative)
        data = source.read_bytes()
        sources.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
        documents.append(json.loads(data.decode('utf-8-sig')))
    spec, plan = documents
    validate_documents(spec, plan)
    settings = effective_settings(root, plan['provider'])
    files = reference_files(root, spec)
    # Validate before creating files; malformed schema/path inputs leave no output.
    compile_inputs(root, spec, plan, settings, files)
    destination.mkdir(parents=True)
    for index, ref in enumerate(files):
        source = contained(root, ref['path'])
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != ref['sha256']:
            raise ValueError('Reference changed during preparation')
        target = destination / 'references' / (str(index) + source.suffix.lower())
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
        ref['snapshot'] = target.relative_to(root).as_posix()
    record = compile_inputs(root, spec, plan, settings, files)
    if context:
        if set(context) - {'iteration', 'lineage'}:
            raise ValueError('Unsupported preparation context')
        record['request'].update(deepcopy(context))
    record['sources'] = sources
    record_path = destination / 'preparation.json'
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    request = {**record['request'], 'preparation': {'path': record_path.relative_to(root).as_posix(),
                                                   'sha256': digest(record_path)}}
    (destination / 'request.json').write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
    (destination / 'preview.md').write_text(render_preview(record), encoding='utf-8')
    return record

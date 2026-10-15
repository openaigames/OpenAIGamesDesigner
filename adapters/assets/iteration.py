"""Evidence-driven, bounded input revisions. This module never dispatches generation."""
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json
from pathlib import Path

from . import input_preparation as prep, quality as q
from tools.validate_records import contract

ACTIVE = ContextVar('asset_iteration_active', default=())
SESSION = ContextVar('asset_iteration_verification_session', default=None)
POLICY = {'max_rounds': 3, 'max_stalled_rounds': 2}


def operation(function):
    """Reuse verified ancestors within one operation, never across later commands."""
    @wraps(function)
    def call(*args, **kwargs):
        token = SESSION.set({}) if SESSION.get() is None else None
        try:
            return function(*args, **kwargs)
        finally:
            if token is not None:
                SESSION.reset(token)
    return call


def memoized(function):
    @operation
    @wraps(function)
    def call(root, *args, **kwargs):
        key = (function.__name__, str(Path(root).resolve()), json.dumps([args, kwargs], sort_keys=True))
        cache = SESSION.get()
        if key not in cache:
            cache[key] = function(root, *args, **kwargs)
        return deepcopy(cache[key])
    return call


def identity(request):
    return {k: v for k, v in prep.request_identity(request).items() if k != 'iteration'}


def catalog(report, evidence, review):
    result = {}
    judgments = {r['id']: r for r in review['criteria']}
    for c in evidence['plan']['criteria']:
        r = judgments[c['id']]
        state = 'unknown' if r['confidence'] == 'low' and r['status'] in ('pass', 'fail') else r['status']
        result['criterion:' + c['id']] = {'status': state, 'priority': c['priority'],
            'expected': c['description'], 'observed': r['observed'], 'evidence': r['evidence']}
    for c in evidence['checks']:
        result['check:' + c['id']] = {'status': c['status'], 'priority': c['priority'],
            'expected': {'metric': c['metric'], 'tolerance': c['tolerance']},
            'observed': {'value': c['value'], 'reason': c['reason']}, 'evidence': c['evidence']}
    findings = {f['id']: f for f in review['findings']}
    for f in evidence['findings']:
        judgment = findings.get(f['id'], {})
        state = {'confirmed': 'fail', 'explained': 'pass'}.get(judgment.get('status'), 'unknown')
        result['finding:' + f['id']] = {'status': state, 'priority': 'must',
            'expected': f['reason'], 'observed': judgment.get('reason', f['reason']), 'evidence': f['evidence']}
    return result


@memoized
def reviewed(root, relative):
    report, evidence = q.inspect(root, relative)
    review = q.read(root, report['review'])
    return report, evidence, catalog(report, evidence, review)


def base_preparation(root, evidence):
    relative = evidence['plan'].get('preparation')
    return q.read(root, relative) if relative else None


@operation
def draft(root, report_path, output, previous=None):
    target = q.path(root, output)
    if target.exists():
        raise ValueError('Use a new draft directory')
    report, evidence, issues = reviewed(root, report_path)
    failed = [key for key, value in issues.items() if value['status'] == 'fail']
    unknown = [key for key, value in issues.items() if value['status'] == 'unknown']
    action = 'accept' if report['result']['status'] == 'pass' else 'regenerate' if failed and base_preparation(root, evidence) else 'postprocess' if failed else 'collect_evidence'
    targets = [] if action == 'accept' else [{'issue': key, 'recheck': key if not key.startswith('finding:') else ''} for key in failed or unknown]
    policy = POLICY
    if previous:
        policy = inspect_comparison(root, previous)['policy']
    plan = {'schema_version': 1, 'report': report_path, 'action': action, 'policy': policy,
            'targets': targets, 'changes': [], 'tasks': [],
            'review': {'reviewer': 'REPLACE_WITH_REVIEWER', 'notes': 'Describe the evidence and chosen correction.',
                       **dict.fromkeys(prep.REVIEW_CHECKS, False)}}
    if previous:
        plan['previous'] = previous
    target.mkdir(parents=True)
    q.write(target / 'issues.json', {'asset_id': evidence['plan']['asset_id'], 'issues': issues,
                                    'quality_status': report['result']['status']})
    q.write(target / 'plan.json', plan)
    return {'status': 'draft', 'action': action, 'issues': issues, 'generation_submitted': False}


def validate_plan(plan):
    errors = contract('asset-iteration-plan', plan)
    if errors:
        raise ValueError('; '.join(errors[:5]))
    policy = plan['policy']
    if not 1 <= policy['max_rounds'] <= 8 or not 1 <= policy['max_stalled_rounds'] <= policy['max_rounds']:
        raise ValueError('Use 1–8 rounds and a stall limit within the round limit')
    review = plan['review']
    if (not review['reviewer'].strip() or review['reviewer'] == 'REPLACE_WITH_REVIEWER'
            or not review['notes'].strip() or any(review[k] is not True for k in prep.REVIEW_CHECKS)):
        raise ValueError('The Agent must review the correction, preserved requirements and reference roles')
    targets = [t['issue'] for t in plan['targets']]
    if len(targets) != len(set(targets)):
        raise ValueError('Duplicate iteration target')


def context(root, plan):
    validate_plan(plan)
    report, evidence, issues = reviewed(root, plan['report'])
    prepared = base_preparation(root, evidence)
    previous, round_number = None, 1
    origin = prepared.get('request', {}).get('iteration') if prepared else None
    if plan.get('previous'):
        previous = inspect_comparison(root, plan['previous'])
        if previous['after']['path'] != plan['report'] or previous['after']['sha256'] != q.digest(q.path(root, plan['report'])):
            raise ValueError('Previous comparison must end at this exact review')
        if previous['policy'] != plan['policy']:
            raise ValueError('Keep the chain policy; choose a new explicit baseline to change strategy')
        # The exact after-report is already verified by inspect_comparison. Its
        # preparation may belong to an older regeneration when the preceding
        # action collected evidence or processed the asset without generating.
        round_number = previous['round'] + 1
    elif origin:
        raise ValueError('A reviewed iteration needs its previous comparison; do not reset the retry counter')
    action = plan['action']
    if action == 'regenerate' and previous and previous['result']['recommendation'] in ('stop', 'change_method', 'complete'):
        raise ValueError('This chain has stopped regeneration: ' + previous['result']['recommendation'])
    if action == 'regenerate' and round_number > plan['policy']['max_rounds']:
        raise ValueError('Iteration round limit reached')
    targets = {t['issue']: t['recheck'] for t in plan['targets']}
    if action in ('regenerate', 'postprocess', 'collect_evidence') and not targets:
        raise ValueError('Choose an observed issue to address')
    for key, recheck in targets.items():
        if key not in issues or issues[key]['status'] not in ('fail', 'unknown'):
            raise ValueError('Targets must refer to an actual failed or unknown review item')
        if action in ('regenerate', 'postprocess') and issues[key]['status'] != 'fail':
            raise ValueError('Unknown or low-confidence observations require evidence, not a speculative correction')
        if action == 'collect_evidence' and issues[key]['status'] != 'unknown':
            raise ValueError('Evidence collection targets unknown items')
        if key.startswith('finding:'):
            if recheck not in issues or not recheck.startswith('criterion:'):
                raise ValueError('A multiview finding needs an existing Agent criterion for semantic reinspection')
        elif recheck != key:
            raise ValueError('Recheck the same criterion or measurement; do not substitute an easier one')
    if action == 'accept' and report['result']['status'] != 'pass':
        raise ValueError('Cannot accept an incomplete or failed source review')
    if action in ('accept', 'stop') and (targets or plan['changes'] or plan['tasks']):
        raise ValueError('Accept/stop records contain no correction or dispatch')
    if action != 'regenerate' and plan['changes']:
        raise ValueError('Only regeneration produces modified generation inputs')
    if action == 'regenerate' and (not prepared or prepared.get('status') != 'ready'):
        raise ValueError('Regeneration requires a ready input preparation linked by the quality report')
    if action == 'regenerate' and (not plan['changes'] or plan['tasks']):
        raise ValueError('Regeneration needs concrete input changes; processing/evidence tasks use their own action')
    if action in ('postprocess', 'collect_evidence') and not plan['tasks']:
        raise ValueError('State the operation and observable completion condition')
    covered = set()
    for row in plan['changes'] + plan['tasks']:
        if not row['issues'] or len(row['issues']) != len(set(row['issues'])) or not set(row['issues']).issubset(targets):
            raise ValueError('Every change/task must cite distinct selected issues')
        covered.update(row['issues'])
    if targets and covered != set(targets):
        raise ValueError('Every selected issue needs a concrete change or evidence task')
    return report, evidence, issues, prepared, previous, round_number


def revised_inputs(root, plan, prepared, output, *, frozen=False):
    """Append corrections without changing the original brief or requirement definitions."""
    spec, inputs = deepcopy(prepared['spec']), deepcopy(prepared['plan'])
    inputs['parameters'] = {k: deepcopy(v) for k, v in prepared['request']['parameters'].items() if k not in ('prompt', 'Prompt', 'text')}
    inputs['review'] = deepcopy(plan['review'])
    snapshots = {r['id']: r for r in prepared['references']}
    for ref in spec['references']:
        ref['path'] = snapshots[ref['id']]['snapshot']
    refs = {r['id']: r for r in spec['references']}
    decisions = {r['id']: r for r in inputs['references']}
    routes = {r['requirement']: r for r in inputs['routes']}
    touched, changed_refs, changed_routes, copies = set(), set(), set(), []
    base = inputs.get('rewrite', {}).get('text', spec['brief'])
    additions = []
    for change in plan['changes']:
        kind, value = change['kind'], change['value']
        if not change['reason'].strip() or not change['expected'].strip():
            raise ValueError('Explain the observed cause and expected result of each input change')
        if kind == 'prompt':
            if not isinstance(value, str) or not value.strip() or value in base or value in additions:
                raise ValueError('A prompt correction must add a nonblank, new instruction')
            additions.append(value)
            continue
        if not isinstance(value, dict):
            raise ValueError('Reference, parameter and route changes need structured values')
        key = value.get('id') if kind == 'reference' else value.get('key') if kind == 'parameter' else value.get('requirement')
        if not isinstance(key, str) or not key or (kind, key) in touched:
            raise ValueError('Each parameter/reference/requirement can be changed only once per round')
        touched.add((kind, key))
        if kind == 'parameter':
            if set(value) != {'key', 'value'} or key in ('prompt', 'Prompt', 'text'):
                raise ValueError('Use a prompt change for text; parameter edits need key/value')
            if inputs['parameters'].get(key) == value['value']:
                raise ValueError('Parameter change does not change its value')
            inputs['parameters'][key] = deepcopy(value['value'])
        elif kind == 'reference':
            if not isinstance(value.get('send'), bool) or not isinstance(value.get('observed'), str) or not value['observed'].strip():
                raise ValueError('Reference changes need send and an actual visual observation')
            ref = {k: deepcopy(v) for k, v in value.items() if k not in ('send', 'observed')}
            # Reuse the requirement schema to validate names, roles and view metadata.
            trial = {**spec, 'references': [ref]}
            errors = contract('asset-requirements', trial)
            if errors:
                raise ValueError('; '.join(errors))
            source = q.path(root, ref['path'])
            frozen_path = output + '/references/' + key + source.suffix.lower()
            sha = q.bind(root, {}, frozen_path if frozen else ref['path'])
            if key in snapshots and sha == snapshots[key]['sha256'] and value['send'] == decisions[key]['send'] and all(ref.get(k) == refs[key].get(k) for k in ('role', 'view', 'note')):
                raise ValueError('Reference change does not change content or its role')
            copies.append({'source': ref['path'], 'path': frozen_path, 'sha256': sha})
            ref['path'] = frozen_path
            refs[key] = ref
            decisions[key] = {'id': key, 'send': value['send'], 'reason': change['reason']}
            changed_refs.add(key)
        else:
            if key not in routes or value == routes[key]:
                raise ValueError('Change an existing requirement route without removing its requirement')
            routes[key] = deepcopy(value)
            changed_routes.add(key)
    for route in prepared['plan']['routes']:
        if set(route.get('references', [])) & changed_refs and route['requirement'] not in changed_routes:
            raise ValueError('Reinspect every requirement route that uses a changed reference')
    spec['references'], inputs['references'], inputs['routes'] = list(refs.values()), list(decisions.values()), list(routes.values())
    if additions:
        inputs['rewrite'] = {'text': base + '\n\nRevision instructions:\n' + '\n'.join(additions),
                             'reason': 'Targeted corrections linked to reviewed evidence; original requirements retained'}
    prep.validate_documents(spec, inputs)
    return spec, inputs, copies


@operation
def create(root, plan_path, output):
    root = Path(root).resolve()
    target = q.path(root, output)
    if target.exists():
        raise ValueError('Use a new iteration directory')
    deps = {}
    q.bind(root, deps, plan_path)
    plan = q.read(root, plan_path)
    report, evidence, issues, prepared, previous, number = context(root, plan)
    q.bind(root, deps, plan['report'])
    if plan.get('previous'):
        q.bind(root, deps, plan['previous'])
    state = {'regenerate': 'ready', 'postprocess': 'needs_processing', 'collect_evidence': 'needs_evidence',
             'accept': 'accepted', 'stop': 'stopped'}[plan['action']]
    record = {'schema_version': 1, 'format': 'asset-iteration', 'plan_path': plan_path,
        'plan': plan, 'status': state, 'asset_id': evidence['plan']['asset_id'], 'round': number,
        'policy': plan['policy'], 'issues': issues, 'dependencies': deps,
        'prepared': None, 'expected_request': None, 'generation_submitted': False}
    spec = inputs = compiled = lineage = None
    if plan['action'] == 'regenerate':
        spec, inputs, copies = revised_inputs(root, plan, prepared, output)
        # Validate snapshots and provider compatibility before saving a ready request.
        files = []
        copy_map = {c['path']: c for c in copies}
        for ref in spec['references']:
            source = copy_map.get(ref['path'], {}).get('source', ref['path'])
            files.append({**ref, 'snapshot': source, 'sha256': q.bind(root, {}, source)})
        settings = prep.effective_settings(root, inputs['provider'])
        if settings != prepared['settings']:
            raise ValueError('Provider routing changed; establish a new reviewed input baseline')
        compiled = prep.compile_inputs(root, spec, inputs, settings, files)
        if compiled['status'] != 'ready':
            raise ValueError('Revised input is blocked: ' + '; '.join(e['message'] for e in compiled['errors']))
        # Compare the adapter's wire representation, including its endpoint and
        # implicit defaults, not just parameter names in the local request.
        def sent(value):
            return {key: value['preview'][key] for key in ('endpoint', 'body')}
        if sent(compiled) == sent(prepared):
            raise ValueError('Provider input is unchanged; a routing note alone is not a generation correction')
        # A parent is provenance, not implicit permission to send its images to a model.
        if evidence['plan'].get('version'):
            link = evidence['plan']['version']
            lineage = {'group': link['group'], 'parent': link['version'], 'references': [],
                       'note': 'Evidence-driven revision: ' + ', '.join(t['issue'] for t in plan['targets'])}
            compiled['request']['lineage'] = lineage
        record['expected_request'] = identity(compiled['request'])
        record['provider'], record['settings'] = inputs['provider'], settings
        record['prepared'] = output + '/prepared/preparation.json'
    q.verify_dependencies(root, deps)
    target.mkdir(parents=True)
    if spec is not None:
        for item in copies:
            source, destination = q.path(root, item['source']), q.path(root, item['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            q.bind(root, deps, item['path'], item['sha256'])
        for name, value in (('requirements.json', spec), ('input-plan.json', inputs)):
            q.write(target / name, value)
            q.bind(root, deps, output + '/' + name)
    relative = output + '/iteration.json'
    q.write(target / 'iteration.json', record)
    if compiled:
        link = {'path': relative, 'sha256': q.digest(target / 'iteration.json')}
        context_fields = {'iteration': link, **({'lineage': lineage} if lineage else {})}
        actual = prep.prepare(root, output + '/requirements.json', output + '/input-plan.json', output + '/prepared', context=context_fields)
        if actual['status'] != 'ready' or identity(actual['request']) != record['expected_request']:
            raise ValueError('Inputs changed during preparation; partial output retained, do not submit it')
    else:
        q.write(target / 'tasks.json', {'action': plan['action'], 'tasks': plan['tasks'], 'executed': False})
    lines = ['# Asset Iteration', '', 'Asset: ' + record['asset_id'], 'Action: ' + plan['action'],
             'State: ' + state, '', 'Generation submitted: no. Source acceptance does not approve engine or game use.',
             '', '## Targets', '']
    lines += ['- ' + t['issue'] + ' → recheck ' + t['recheck'] for t in plan['targets']]
    lines += ['', '## Adjustments', '']
    lines += ['- ' + c['kind'] + ': ' + json.dumps(c['value'], ensure_ascii=False) + '; reason: ' + c['reason'] + '; expected: ' + c['expected'] for c in plan['changes']]
    lines += ['- ' + t['operation'] + '; expected: ' + t['expected'] for t in plan['tasks']]
    lines += ['', '## Preserved constraints', '']
    lines += ['- ' + r['id'] + ': ' + r['text'] for r in (prepared['spec']['requirements'] if prepared else [])]
    lines += ['', 'The original brief and every requirement definition are retained. Reinspect all previously passing checks.',
              '', '## Stop conditions', '', json.dumps(plan['policy']), '', plan['review']['notes']]
    (target / 'preview.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    inspect(root, relative)
    return record


@memoized
def inspect(root, relative, expected=None):
    active = ACTIVE.get()
    if relative in active or len(active) >= 24:
        raise ValueError('Cyclic or excessively deep iteration provenance')
    token = ACTIVE.set(active + (relative,))
    try:
        q.bind(root, {}, relative, expected)
        record = q.read(root, relative)
        if record.get('format') != 'asset-iteration' or record.get('schema_version') != 1:
            raise ValueError('Invalid iteration record')
        q.verify_dependencies(root, record['dependencies'])
        if record['plan'] != q.read(root, record['plan_path']):
            raise ValueError('Iteration decision changed')
        _, evidence, issues, prepared, previous, number = context(root, record['plan'])
        if record['asset_id'] != evidence['plan']['asset_id'] or record['issues'] != issues or record['round'] != number or record['policy'] != record['plan']['policy']:
            raise ValueError('Iteration context differs from its evidence')
        status = {'regenerate':'ready','postprocess':'needs_processing','collect_evidence':'needs_evidence','accept':'accepted','stop':'stopped'}[record['plan']['action']]
        if record['status'] != status:
            raise ValueError('Iteration state differs from its action')
        if record['plan']['action'] == 'regenerate':
            output = str(Path(relative).parent).replace('\\', '/')
            spec, inputs, copies = revised_inputs(root, record['plan'], prepared, output, frozen=True)
            if spec != q.read(root, output + '/requirements.json') or inputs != q.read(root, output + '/input-plan.json'):
                raise ValueError('Iteration inputs differ from the approved corrections')
            if record['prepared'] != output + '/prepared/preparation.json':
                raise ValueError('Iteration preparation path changed')
            compiled = prep.compile_inputs(root, spec, inputs, prepared['settings'])
            if evidence['plan'].get('version'):
                link = evidence['plan']['version']
                compiled['request']['lineage'] = {'group': link['group'], 'parent': link['version'], 'references': [],
                    'note': 'Evidence-driven revision: ' + ', '.join(t['issue'] for t in record['plan']['targets'])}
            if (compiled['status'] != 'ready' or identity(compiled['request']) != record['expected_request']
                    or record['provider'] != inputs['provider'] or record['settings'] != prepared['settings']):
                raise ValueError('Iteration request does not match its frozen inputs')
        return record
    finally:
        ACTIVE.reset(token)


@operation
def verify_request(root, provider, request, settings):
    link = request.get('iteration')
    if link is None:
        return
    if not isinstance(link, dict) or set(link) != {'path', 'sha256'} or not request.get('preparation'):
        raise ValueError('Iteration request needs linked preparation and iteration records')
    record = inspect(root, link['path'], link['sha256'])
    if (record['status'] != 'ready' or record['plan']['action'] != 'regenerate'
            or provider != record['provider'] or settings != record['settings']
            or identity(request) != record['expected_request']
            or request['preparation']['path'] != record['prepared']):
        raise ValueError('Generation request differs from the reviewed iteration')


def rubric(evidence):
    plan = evidence['plan']
    return {k: plan.get(k, []) for k in ('asset_id', 'kind', 'use', 'environment', 'criteria', 'checks', 'model_checks', 'required_views', 'deferred')}


def distance(item):
    value = item['observed'].get('value')
    tolerance = item['expected']['tolerance']
    if type(value) not in (float, int):
        return None
    if isinstance(tolerance, dict):
        return max(tolerance['minimum'] - value, value - tolerance['maximum'], 0)
    return max(tolerance - value if item['expected']['metric'] == 'silhouette_iou' else value - tolerance, 0)


@operation
def comparison(root, iteration_path, after_path):
    record = inspect(root, iteration_path)
    action = record['plan']['action']
    if action not in ('regenerate', 'postprocess', 'collect_evidence'):
        raise ValueError('Accept/stop actions do not produce candidate comparisons')
    before_report, before, old = reviewed(root, record['plan']['report'])
    after_report, after, new = reviewed(root, after_path)
    if after_path == record['plan']['report'] or rubric(before) != rubric(after):
        raise ValueError('Use a new review with the same asset, use, environment and acceptance rubric')
    old_views = {v['id']: (v['set'], v['direction']) for v in before['plan']['views']}
    new_views = {v['id']: (v['set'], v['direction']) for v in after['plan']['views']}
    if any(new_views.get(key) != value for key, value in old_views.items()):
        raise ValueError('Retain existing view identities and directions when adding evidence')
    if action == 'regenerate':
        if after['plan'].get('preparation') != record['prepared']:
            raise ValueError('Candidate review must cite the input preparation produced by this iteration')
        candidate = q.read(root, record['prepared'])
        if candidate['request'].get('iteration') != {'path': iteration_path, 'sha256': q.digest(q.path(root, iteration_path))}:
            raise ValueError('Candidate preparation belongs to another iteration')
        if before['plan'].get('version') and after['version_snapshot']:
            if (after['plan']['version']['group'] != before['plan']['version']['group']
                    or after['version_snapshot']['parent'] != before['plan']['version']['version']):
                raise ValueError('Candidate version must be a child of the reviewed baseline')
        if after['version_snapshot'] and after['version_snapshot']['provenance'].get('iteration') != candidate['request']['iteration']:
            raise ValueError('Candidate version provenance does not identify this iteration')
    elif after['plan'].get('preparation') != before['plan'].get('preparation'):
        raise ValueError('Processing/evidence work must retain the generation requirement baseline')
    resolved, unresolved = [], []
    for target in record['plan']['targets']:
        key, recheck = target['issue'], target['recheck']
        passed = new.get(recheck, {}).get('status') == 'pass'
        if key.startswith('finding:'):
            passed &= new.get(key, {}).get('status', 'pass') == 'pass'
        (resolved if passed else unresolved).append(key)
    regressions = [key for key, item in old.items() if item['status'] == 'pass' and item['priority'] == 'must'
                   and not key.startswith('finding:') and new.get(key, {}).get('status') != 'pass']
    # Resolving uncertainty into a confirmed defect is evidence, not proof that
    # this revision introduced it. Preserve the unresolved target instead.
    new_failures = [key for key, item in new.items() if item['priority'] == 'must' and item['status'] == 'fail'
                    and (key not in old or old[key]['status'] == 'pass')]
    preferences = [key for key, item in old.items() if item['status'] == 'pass' and item['priority'] == 'preference'
                   and new.get(key, {}).get('status') != 'pass']
    measured_improvements, measured_worsening = [], []
    for target in record['plan']['targets']:
        key = target['issue']
        if key.startswith('check:') and old[key]['status'] == new.get(key, {}).get('status') == 'fail':
            a, b = distance(old[key]), distance(new[key])
            if a is not None and b is not None:
                if b < a - 1e-9:
                    measured_improvements.append(key)
                elif b > a + 1e-9:
                    measured_worsening.append(key)
    unchanged = action != 'collect_evidence' and sorted(before['sources'].values()) == sorted(after['sources'].values())
    previous = inspect_comparison(root, record['plan']['previous']) if record['plan'].get('previous') else None
    progress = bool(resolved or measured_improvements) and not regressions and not new_failures and not unchanged and not measured_worsening
    stalled = 0 if progress else (previous['result']['stalled_rounds'] if previous else 0) + 1
    if regressions or new_failures:
        status, recommendation = 'regressed', 'change_method'
    elif unchanged:
        status, recommendation = 'unchanged_output', 'continue'
    elif after_report['result']['status'] == 'pass' and not unresolved:
        status, recommendation = 'complete', 'complete'
    else:
        status = 'improved' if progress else 'inconclusive' if after_report['result']['pending'] else 'no_progress'
        recommendation = 'collect_evidence' if after_report['result']['pending'] else 'continue'
    if recommendation != 'complete' and (record['round'] >= record['policy']['max_rounds'] or stalled >= record['policy']['max_stalled_rounds']):
        recommendation = 'stop'
    return {'status': status, 'recommendation': recommendation, 'resolved': resolved, 'unresolved': unresolved,
            'regressions': regressions, 'new_failures': new_failures, 'unchanged_source_bytes': unchanged,
            'preference_regressions': preferences, 'measured_improvements': measured_improvements, 'measured_worsening': measured_worsening,
            'stalled_rounds': stalled, 'after_quality_status': after_report['result']['status'],
            'engine_verified': False, 'game_verified': False}


@operation
def compare(root, iteration_path, after_path, output):
    target = q.path(root, output)
    if target.exists():
        raise ValueError('Use a new comparison directory')
    deps = {}
    for relative in (iteration_path, after_path):
        q.bind(root, deps, relative)
    result = comparison(root, iteration_path, after_path)
    record = inspect(root, iteration_path)
    value = {'schema_version': 1, 'format': 'asset-iteration-comparison',
             'iteration': {'path': iteration_path, 'sha256': deps[iteration_path]},
             'after': {'path': after_path, 'sha256': deps[after_path]}, 'dependencies': deps,
             'policy': record['policy'], 'round': record['round'], 'result': result}
    q.verify_dependencies(root, deps)
    target.mkdir(parents=True)
    q.write(target / 'comparison.json', value)
    (target / 'report.md').write_text('# Asset Iteration Comparison\n\n' + '\n'.join(
        '- ' + key + ': ' + json.dumps(v, ensure_ascii=False) for key, v in result.items()) + '\n', encoding='utf-8')
    return value


@memoized
def inspect_comparison(root, relative):
    record = q.read(root, relative)
    if record.get('format') != 'asset-iteration-comparison' or record.get('schema_version') != 1:
        raise ValueError('Invalid iteration comparison')
    q.verify_dependencies(root, record['dependencies'])
    if record['dependencies'] != {record['iteration']['path']: record['iteration']['sha256'], record['after']['path']: record['after']['sha256']}:
        raise ValueError('Comparison dependencies changed')
    source = inspect(root, record['iteration']['path'], record['iteration']['sha256'])
    if (record['round'] != source['round'] or record['policy'] != source['policy']
            or record['result'] != comparison(root, record['iteration']['path'], record['after']['path'])):
        raise ValueError('Comparison no longer matches the reviewed evidence')
    return record

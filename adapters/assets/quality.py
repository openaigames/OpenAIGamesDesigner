"""Local, version-bound evidence collection and explicit Agent quality review."""
from copy import deepcopy
import json
import math
from pathlib import Path

from tools.validate_records import contract, digest
from . import multiview


def path(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or any(ord(c) < 32 for c in relative) or relative.startswith('/')
            or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in relative.split('/'))):
        raise ValueError('Use a project-relative path with forward slashes')
    parts = relative.split('/')
    if any(p.startswith('.') for p in parts):
        if parts[0] != '.openaigame' or len(parts) < 3 or parts[1] not in ('asset-jobs', 'asset-library', 'asset-versions') or any(p.startswith('.') for p in parts[1:]):
            raise ValueError('Private project metadata is not quality evidence')
    root = Path(root).resolve()
    target = root / relative
    for item in [target, *target.parents]:
        if item == root:
            break
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('Evidence paths must not traverse links')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Evidence path escapes project')
    return target


def read(root, relative):
    target = path(root, relative)
    if target.stat().st_size > 8 * 1024**2:
        raise ValueError('Quality JSON exceeds 8 MiB')
    return json.loads(target.read_text(encoding='utf-8-sig'))


def write(target, value):
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def bind(root, deps, relative, expected=None):
    target = path(root, relative)
    if not target.is_file() or not target.stat().st_size:
        raise ValueError('Missing or empty evidence: ' + relative)
    sha = digest(target)
    if expected and sha != expected:
        raise ValueError('Evidence changed: ' + relative)
    if relative in deps and deps[relative] != sha:
        raise ValueError('Evidence changed while collecting: ' + relative)
    deps[relative] = sha
    return sha


def verify_dependencies(root, dependencies):
    for relative, expected in dependencies.items():
        bind(root, {}, relative, expected)


def unique(rows, label):
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate ' + label + ' ID')
    return {r['id']: r for r in rows}


def finite(value, minimum=0, maximum=None):
    if type(value) not in (float, int) or not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError('Invalid numeric calibration, coordinate or threshold')


def validate_plan(plan):
    errors = contract('asset-evidence-plan', plan)
    if errors:
        raise ValueError('; '.join(errors[:6]))
    for key in ('asset_id', 'use', 'environment'):
        if not plan[key].strip():
            raise ValueError('Blank evidence scope: ' + key)
    unique(plan['criteria'], 'criterion')
    unique(plan.get('checks', []), 'check')
    all_checks = plan.get('checks', []) + plan.get('model_checks', [])
    unique(all_checks, 'automatic check')
    if {c['id'] for c in plan['criteria']} & {c['id'] for c in all_checks}:
        raise ValueError('Automatic and Agent criterion IDs must be distinct')
    for c in plan.get('model_checks', []):
        finite(c['minimum'])
        finite(c['maximum'], c['minimum'])
        if c['metric'].startswith('size_') != ('units' in c):
            raise ValueError('Dimension checks require declared units; counts do not')
    views = unique(plan['views'], 'view')
    unique(plan.get('media', []), 'media')
    if set(views) & {m['id'] for m in plan.get('media', [])}:
        raise ValueError('View and media IDs must be distinct')
    required = [(v['set'], d) for v in plan.get('required_views', []) for d in v['directions']]
    if len(required) != len(set(required)):
        raise ValueError('Duplicate required view direction')
    for v in views.values():
        seg = v.get('segmentation', {})
        if len(seg) != 1 and seg:
            raise ValueError('Choose alpha or an explicit mask')
        if 'alpha' in seg and seg['alpha'] is not True:
            raise ValueError('alpha must be true')
        if 'calibration' in v:
            finite(v['calibration']['pixels_per_unit'], 0.000001)
            finite(v['calibration']['baseline_y'])
        for landmark in v.get('landmarks', {}).values():
            finite(landmark['x'], 0, 1)
            finite(landmark['y'], 0, 1)
    for c in plan['checks']:
        if c['a'] not in views or c['b'] not in views or c['a'] == c['b']:
            raise ValueError('A measurement needs two distinct existing views')
        finite(c['tolerance'], 0, 1 if c['metric'] in ('height', 'silhouette_iou') else None)
        if (c['metric'] == 'landmark_height') != ('landmark' in c):
            raise ValueError('Only landmark_height requires a landmark name')
    if len(set(plan['files'])) != len(plan['files']):
        raise ValueError('Duplicate source file')


def version_identity(root, link):
    from tools.workbench import asset_versions
    _, version = asset_versions.version(asset_versions.load(root), link['group'], link['version'])
    return deepcopy(version)


def collect(root, plan_path, output):
    root = Path(root).resolve()
    destination = path(root, output) if output is not None else None
    if destination is not None and destination.exists():
        raise ValueError('Use a new evidence directory to preserve history')
    deps = {}
    bind(root, deps, plan_path)
    plan = read(root, plan_path)
    original = deepcopy(plan)
    model_metrics = None
    if plan.get('capture'):
        bind(root, deps, plan['capture'])
        capture = read(root, plan['capture'])
        if capture.get('format') != 'asset-model-capture' or capture.get('schema_version') != 1:
            raise ValueError('Invalid model capture')
        verify_dependencies(root, capture['dependencies'])
        deps.update(capture['dependencies'])
        if capture['source']['path'] not in plan['files']:
            raise ValueError('Capture source must be among reviewed source files')
        plan['views'] = plan['views'] + capture['views']
        plan.setdefault('media', []).append({'id':'model_metrics','type':'report','path':capture['metrics']})
        model_metrics = read(root, capture['metrics'])
    validate_plan(plan)
    sources = {p: bind(root, deps, p) for p in plan['files']}
    requirements, deferred = [], plan.get('deferred', [])
    if plan.get('preparation'):
        bind(root, deps, plan['preparation'])
        prepared = read(root, plan['preparation'])
        if prepared.get('schema_version') != 1 or prepared.get('status') != 'ready' or prepared.get('asset_id') != plan['asset_id']:
            raise ValueError('Preparation must be ready and match the asset ID')
        from .input_preparation import verify_request
        request = {**prepared['request'], 'preparation': {'path': plan['preparation'], 'sha256': deps[plan['preparation']]}}
        verify_request(root, prepared['provider'], request, prepared['settings'])
        for ref in prepared['references']:
            bind(root, deps, ref['snapshot'], ref['sha256'])
        requirements = prepared['spec']['requirements']
        ids = {r['id'] for r in requirements}
        covered = [c['requirement'] for c in plan['criteria'] if c.get('requirement')]
        later = [d['requirement'] for d in deferred]
        if (set(covered + later) - ids or set(covered) & set(later) or len(later) != len(set(later))
                or {r['id'] for r in requirements if r['priority'] == 'must'} - set(covered + later)):
            raise ValueError('Every mandatory prepared requirement needs review coverage or an explicit later gate')
        required = {r['id'] for r in requirements if r['priority'] == 'must'}
        if any(c.get('requirement') in required and c['priority'] != 'must' for c in plan['criteria']):
            raise ValueError('A mandatory requirement cannot become a preference')
    elif deferred or any(c.get('requirement') for c in plan['criteria']):
        raise ValueError('Requirement links need a preparation record')
    version = None
    if plan.get('version'):
        version = version_identity(root, plan['version'])
        for f in version['files']:
            bind(root, deps, f['path'], f['sha256'])
        if {f['path']: f['sha256'] for f in version['files']} != sources:
            raise ValueError('Reviewed files must match the entire pinned asset version')
    views = {v['id']: v for v in plan['views']}
    measured, evidence, pixels = {}, {}, 0
    for view in views.values():
        bind(root, deps, view['path'])
        if view.get('segmentation', {}).get('mask'):
            bind(root, deps, view['segmentation']['mask'])
        measured[view['id']] = multiview.measure(root, view, path)
        pixels += measured[view['id']][0].width * measured[view['id']][0].height
        if pixels > 64_000_000:
            raise ValueError('A collection is limited to 64 million source image pixels')
        if view.get('calibration', {}).get('baseline_y', 0) > measured[view['id']][0].height:
            raise ValueError('Baseline must lie on the image canvas')
        evidence[view['id']] = {'path': view['path'], 'type': 'image'}
    for media in plan.get('media', []):
        bind(root, deps, media['path'])
        evidence[media['id']] = {k: media[k] for k in ('path', 'type')}
    if not evidence:
        raise ValueError('Collect at least one view or media item')
    checks = [multiview.compare(c, views, measured) for c in plan['checks']]
    for c in plan.get('model_checks', []):
        value, reason = None, 'Model measurement needs a linked capture'
        if model_metrics:
            if c['metric'].startswith('size_'):
                if model_metrics['units'] == c['units'] and c['units'] != 'unknown':
                    value = model_metrics['dimensions']['xyz'.index(c['metric'][-1])]
                else:
                    reason = 'Dimension units are unknown or differ from the declared requirement'
            else:
                value = model_metrics[c['metric']]
        checks.append({'id':c['id'],'metric':c['metric'],'priority':c['priority'],
            'evidence':['model_metrics'] if model_metrics else [], 'value':value,
            'tolerance':{'minimum':c['minimum'],'maximum':c['maximum']},
            'status':'unknown' if value is None else 'pass' if c['minimum'] <= value <= c['maximum'] else 'fail',
            'reason':reason if value is None else 'Evaluated Blender geometry at the recorded static frame'})
    findings = multiview.findings(plan, views, measured)
    record = {'schema_version': 1, 'format': 'asset-quality-evidence', 'plan': plan,
              'plan_source': plan_path, 'original_plan': original, 'sources': sources,
              'requirements': requirements, 'version_snapshot': version,
              'evidence': evidence, 'measurements': {k: v[2] for k, v in measured.items()},
              'checks': checks, 'findings': findings, 'dependencies': deps,
              'engine_verified': False, 'game_verified': False}
    verify_dependencies(root, deps)
    if destination is None:
        return record
    destination.mkdir(parents=True)
    if views:
        sheet = destination / 'contact-sheet.png'
        multiview.contact_sheet(views, measured, sheet)
        bind(root, deps, sheet.relative_to(root).as_posix())
        record['contact_sheet'] = sheet.relative_to(root).as_posix()
    # Unknown entries are deliberate: collection cannot invent a visual review.
    template = {'schema_version': 1, 'reviewer': 'REPLACE_WITH_REVIEWER', 'criteria': [
        {'id': c['id'], 'status': 'unknown', 'score': None, 'confidence': 'low',
         'expected': c['description'], 'observed': 'Not reviewed', 'evidence': []} for c in plan['criteria']],
        'findings': [{'id': f['id'], 'status': 'unknown', 'reason': 'Not reviewed', 'evidence': []}
                     for f in findings if f['kind'] != 'missing_view']}
    write(destination / 'review-template.json', template)
    write(destination / 'evidence.json', record)
    return record


def evidence_record(root, relative):
    record = read(root, relative)
    if record.get('format') != 'asset-quality-evidence' or record.get('schema_version') != 1:
        raise ValueError('Invalid quality evidence record')
    validate_plan(record['plan'])
    verify_dependencies(root, record['dependencies'])
    # Recompute automatic facts. Editing the collection JSON cannot waive a failure.
    current = collect(root, record['plan_source'], None)
    for key in ('plan', 'original_plan', 'sources', 'requirements', 'version_snapshot',
                'evidence', 'measurements', 'checks', 'findings'):
        if record[key] != current[key]:
            raise ValueError('Evidence facts changed or do not match current inputs: ' + key)
    expected_dependencies = {**current['dependencies']}
    if record.get('contact_sheet'):
        bind(root, expected_dependencies, record['contact_sheet'])
    if record['dependencies'] != expected_dependencies:
        raise ValueError('Evidence dependency set differs from collected inputs')
    return record


def evaluate(record, review):
    errors = contract('asset-quality-review', review)
    if errors:
        raise ValueError('; '.join(errors[:6]))
    if not review['reviewer'].strip() or review['reviewer'] == 'REPLACE_WITH_REVIEWER':
        raise ValueError('Name the actual reviewer')
    expected = {c['id']: c for c in record['plan']['criteria']}
    actual = unique(review['criteria'], 'review criterion')
    if set(expected) != set(actual):
        raise ValueError('Review must cover every criterion exactly once')
    available = record['evidence']
    def citations(row):
        if len(row['evidence']) != len(set(row['evidence'])) or any(e not in available for e in row['evidence']):
            raise ValueError('Review cites unknown or duplicate evidence')
        if row['status'] != 'unknown' and not row['evidence']:
            raise ValueError('A judgment needs actual evidence IDs')
        for box in row.get('regions', []):
            if box['evidence'] not in row['evidence'] or available[box['evidence']]['type'] != 'image':
                raise ValueError('Image regions must cite an attached image')
            for n in ('x', 'y', 'width', 'height'):
                finite(box[n], 0, 1)
            if box['width'] <= 0 or box['height'] <= 0 or box['x'] + box['width'] > 1 or box['y'] + box['height'] > 1:
                raise ValueError('Invalid evidence region')
    failed, pending, dimensions = [], [], {}
    for key, c in expected.items():
        r = actual[key]
        citations(r)
        if not r['expected'].strip() or not r['observed'].strip():
            raise ValueError('State expected and observed evidence')
        status, score = r['status'], r['score']
        if status in ('pass', 'fail'):
            if type(score) is not int or not 0 <= score <= 4 or (status == 'pass') != (score >= 3):
                raise ValueError('Scores use 0–2 for fail and 3–4 for pass')
        elif score is not None:
            raise ValueError('Unknown and not-applicable criteria have no score')
        if status == 'na' and c['priority'] == 'must':
            raise ValueError('Mandatory criteria cannot be not applicable')
        if c['priority'] == 'must':
            if status == 'fail':
                failed.append(key)
            elif status == 'unknown' or (status == 'pass' and r['confidence'] == 'low'):
                pending.append(key)
        dimension = dimensions.setdefault(c['dimension'], {'reviewed': 0, 'total': 0, 'scores': []})
        dimension['total'] += 1
        if status in ('pass', 'fail') and r['confidence'] != 'low':
            dimension['reviewed'] += 1
            dimension['scores'].append(score)
    for c in record['checks']:
        if c['priority'] == 'must':
            if c['status'] == 'fail':
                failed.append(c['id'])
            elif c['status'] != 'pass':
                pending.append(c['id'])
    judgments = unique(review['findings'], 'finding judgment')
    cues = {f['id']: f for f in record['findings'] if f['kind'] != 'missing_view'}
    if set(judgments) != set(cues):
        raise ValueError('Review must explicitly address every duplicate or mirror cue')
    pending += [f['id'] for f in record['findings'] if f['kind'] == 'missing_view']
    for key, r in judgments.items():
        citations(r)
        if not r['reason'].strip():
            raise ValueError('Explain the multiview judgment')
        if r['status'] != 'unknown' and not set(cues[key]['evidence']).issubset(r['evidence']):
            raise ValueError('A multiview judgment must cite both implicated views')
        if r['status'] == 'confirmed':
            failed.append(key)
        elif r['status'] == 'unknown':
            pending.append(key)
    for dimension in dimensions.values():
        scores = dimension.pop('scores')
        dimension['mean_score'] = round(sum(scores)/len(scores), 2) if scores else None
    return {'status': 'fail' if failed else 'needs_review' if pending else 'pass',
            'failed': failed, 'pending': pending, 'dimensions': dimensions,
            'deferred': record['plan'].get('deferred', []),
            'scope': 'external asset review', 'engine_verified': False, 'game_verified': False}


def assess(root, evidence_path, review_path, output):
    destination = path(root, output)
    if destination.exists():
        raise ValueError('Use a new assessment directory to preserve history')
    deps = {}
    bind(root, deps, evidence_path)
    bind(root, deps, review_path)
    evidence = evidence_record(root, evidence_path)
    review = read(root, review_path)
    result = evaluate(evidence, review)
    verify_dependencies(root, deps)
    record = {'schema_version': 1, 'format': 'asset-quality-review',
              'evidence_record': evidence_path, 'review': review_path,
              'dependencies': deps, 'result': result, 'reviewer': review['reviewer']}
    destination.mkdir(parents=True)
    write(destination / 'quality.json', record)
    lines = ['# Asset Quality Review', '', 'Asset: ' + evidence['plan']['asset_id'],
             'Use: ' + evidence['plan']['use'], 'Environment: ' + evidence['plan']['environment'],
             'External review: ' + result['status'], '',
             'Source evidence and Agent judgments are version-bound. Engine and game acceptance remain separate.',
             '', '## Automatic measurements', '']
    lines += ['- ' + c['id'] + ': ' + c['status'] + '; value=' + str(c['value']) + '; ' + c['reason'] for c in evidence['checks']]
    lines += ['', '## Agent judgments', '']
    lines += ['- ' + c['id'] + ': ' + c['status'] + ' (' + c['confidence'] + '); expected: ' + c['expected'] + '; observed: ' + c['observed'] + '; evidence: ' + ', '.join(c['evidence']) for c in review['criteria']]
    lines += ['', '## Multiview findings', '']
    judgments = {f['id']: f for f in review['findings']}
    lines += ['- ' + f['id'] + ': ' + judgments.get(f['id'], {}).get('status', 'unknown') + '; ' + judgments.get(f['id'], {}).get('reason', f['reason']) for f in evidence['findings']]
    lines += ['', '## Deferred requirements', '']
    lines += ['- ' + d['requirement'] + ' -> ' + d['gate'] + ': ' + d['reason'] for d in result['deferred']]
    lines += ['', '## Evidence files', '']
    # Relative links work in a downloaded project as well as in the workbench.
    import os
    from urllib.parse import quote
    for key, item in evidence['evidence'].items():
        rel = Path(os.path.relpath(path(root, item['path']), destination)).as_posix()
        lines.append('- [' + key + '](' + quote(rel) + ')')
    (destination / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return record


def inspect(root, relative, expected_hash=None):
    bind(root, {}, relative, expected_hash)
    report = read(root, relative)
    if report.get('format') != 'asset-quality-review' or report.get('schema_version') != 1:
        raise ValueError('Invalid quality report')
    verify_dependencies(root, report['dependencies'])
    if set(report['dependencies']) != {report['evidence_record'], report['review']}:
        raise ValueError('Quality report is missing its evidence/review dependency')
    evidence = evidence_record(root, report['evidence_record'])
    review = read(root, report['review'])
    if evaluate(evidence, review) != report['result'] or review['reviewer'] != report['reviewer']:
        raise ValueError('Quality conclusion differs from its evidence and judgments')
    return report, evidence


def bind_review(root, row, relative, status):
    report, evidence = inspect(root, relative)
    expected = {'pass': 'pass', 'fail': 'fail', 'needs_review': 'blocked'}[report['result']['status']]
    if status != expected or evidence['sources'] != row['snapshot']:
        raise ValueError('Quality report status or source version differs from the review record')
    if any(evidence['plan'][k] != row[k] for k in ('use', 'environment')):
        raise ValueError('Quality report use/environment differs from the review record')
    kinds = {'model': ('model', 'weapon', 'animation'), 'image': ('image',), 'audio': ('audio',),
             'video': ('animation', 'vfx', 'other'), 'other': ('other',)}
    if row['kind'] not in kinds[evidence['plan']['kind']]:
        raise ValueError('Quality report asset kind differs from the review record')
    return {'path': relative, 'sha256': digest(path(root, relative))}


def publish(root, relative, record_id):
    from tools.workbench import asset_review
    report, _ = inspect(root, relative)
    status = {'pass': 'pass', 'fail': 'fail', 'needs_review': 'blocked'}[report['result']['status']]
    return asset_review.mutate(root, {'action': 'check', 'revision': asset_review.load(root)[1],
        'id': record_id, 'gate': 'external', 'status': status, 'quality_report': relative,
        'method': 'Measured evidence and explicit Agent review', 'reviewer': report['reviewer'],
        'conclusion': 'External asset review: ' + report['result']['status'] + '; engine/game acceptance remains separate',
        'evidence': [{'type': 'report', 'path': relative}]})

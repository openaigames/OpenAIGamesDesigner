"""Repeat fixed views through an existing project runner and compare actual receipts."""
import html
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
from .common import digest, identity, inside, issue, issues_report, number, read, unique, write


def png_size(path):
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError('Expected actual PNG image: ' + str(path))
    return list(struct.unpack('>II', header[16:24]))


def validate_plan(plan):
    if plan.get('schema') != 'environment-views/1':
        raise ValueError('Expected environment-views/1')
    for key in ('revision', 'engine', 'scene', 'coordinate', 'unit', 'rotation_order', 'conditions'):
        if not plan.get(key):
            raise ValueError('View plan needs ' + key)
    if plan['unit'] not in ('m', 'cm'):
        raise ValueError('Views support m or cm')
    if len(plan['resolution']) != 2:
        raise ValueError('Resolution requires width and height')
    for x in plan['resolution']:
        number(x, 'resolution', 1, 32768)
        if int(x) != x:
            raise ValueError('Resolution must be integer')
    views = unique(plan['views'])
    if not views:
        raise ValueError('At least one view is required')
    for name, view in views.items():
        if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            raise ValueError('View ID must be a safe filename')
        for key in ('position', 'rotation_deg'):
            if len(view[key]) != 3:
                raise ValueError(key + ' requires three components')
            for x in view[key]:
                number(x, key)
        projection = view.get('projection', 'perspective')
        if projection not in ('perspective', 'orthographic'):
            raise ValueError('Unknown projection')
        number(view['fov_deg'] if projection == 'perspective' else view['ortho_size'], projection, .001, 179.999 if projection == 'perspective' else None)
    return views


def record(plan, capture_dir, root):
    views = validate_plan(plan)
    capture_dir = Path(capture_dir).resolve()
    issues, results = [], []
    tolerance = plan.get('tolerance', {})
    for k, v in tolerance.items():
        if k not in ('position', 'rotation_deg', 'projection'):
            raise ValueError('Unknown camera tolerance')
        number(v, k, 0)
    for name, expected in views.items():
        image = inside(capture_dir, name+'.png')
        receipt_path = inside(capture_dir, name+'.json')
        observed = read(receipt_path)
        if observed.get('id') != name or not observed.get('source'):
            raise ValueError('Capture needs actual ID and source')
        if observed.get('schema') != 'environment-view/1':
            raise ValueError('Runner must return environment-view/1 readback')
        for key in ('engine', 'scene', 'unit', 'coordinate', 'rotation_order'):
            if observed.get(key) != plan[key]:
                issues.append(issue('capture_context_mismatch', view=name, field=key))
        for key in ('position', 'rotation_deg'):
            values = observed.get(key)
            if not isinstance(values, list) or len(values) != 3:
                raise ValueError('Missing actual camera ' + key)
            for v in values:
                number(v, key)
        distance = math.dist(expected['position'], observed['position'])
        rotation = max(abs((a-b+180)%360-180) for a,b in zip(expected['rotation_deg'], observed['rotation_deg']))
        if distance > tolerance.get('position', .0001) or rotation > tolerance.get('rotation_deg', .001):
            issues.append(issue('camera_mismatch', view=name, position_error=distance, rotation_error_deg=rotation))
        projection = expected.get('projection', 'perspective')
        field = 'fov_deg' if projection == 'perspective' else 'ortho_size'
        number(observed.get(field), 'actual '+field, .001)
        if observed.get('projection', 'perspective') != projection or abs(expected[field]-observed[field]) > tolerance.get('projection', .001):
            issues.append(issue('projection_mismatch', view=name))
        dimensions = png_size(image)
        if dimensions != plan['resolution'] or observed.get('resolution') != dimensions:
            issues.append(issue('resolution_mismatch', view=name, image_size=dimensions))
        conditions = observed.get('conditions', {})
        for key, value in plan['conditions'].items():
            if conditions.get(key) != value:
                issues.append(issue('condition_unverified_or_changed', 'warning', view=name, field=key,
                                    requested=value, observed=conditions.get(key)))
        results.append({'id':name, 'image':str(image), 'image_sha256':digest(image),
                        'receipt_sha256':digest(receipt_path), 'readback':observed})
    return issues_report('environment-view-report', issues, plan=plan, views=results,
                         dependencies=identity(root, plan.get('dependencies', [])),
                         capture_claim='Readback supplied by the selected runner; review originals, not only this report.')


def capture(plan_path, runner_path, root, output):
    plan = read(plan_path)
    validate_plan(plan)
    runner = read(runner_path)
    argv = runner.get('argv')
    if not isinstance(argv, list) or not argv or not all(isinstance(s, str) for s in argv):
        raise ValueError('Runner needs an explicit argv array')
    if not any('{plan}' in s for s in argv) or not any('{output}' in s for s in argv):
        raise ValueError('Runner needs {plan} and {output} arguments')
    timeout = number(runner.get('timeout_s', 300), 'timeout_s', 1, 3600)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write(output/'plan.json', plan)
    before = identity(root, plan.get('dependencies', []))
    write(output/'dependencies-before.json', before)
    replacements = {'{plan}':str(output/'plan.json'), '{output}':str(output), '{project}':str(Path(root).resolve())}
    command = []
    for arg in argv:
        for key, value in replacements.items():
            arg = arg.replace(key, value)
        command.append(arg)
    try:
        with (output/'runner.log').open('w', encoding='utf8') as stream:
            completed = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=timeout, shell=False)
        if completed.returncode:
            raise ValueError('Capture runner failed: ' + str(completed.returncode))
        report = record(plan, output, root)
        if before != report['dependencies']:
            report['issues'].append(issue('source_changed_during_capture'))
            report['checks_ok'] = False
        write(output/'report.json', report)
        return report
    except Exception as error:
        write(output/'failure.json', {'error':str(error), 'completed':False})
        raise


def compare(before, after, output):
    if before.get('schema') != 'environment-view-report/1' or after.get('schema') != before['schema']:
        raise ValueError('Expected two environment-view-report/1 files')
    for report in (before, after):
        planned = validate_plan(report['plan'])
        if set(unique(report['views'])) != set(planned):
            raise ValueError('Report view IDs differ from the recorded plan')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    a, b = unique(before['views']), unique(after['views'])
    rows, issues = [], []
    for label, report in (('before',before),('after',after)):
        if not report.get('checks_ok'):
            issues.append(issue('source_capture_checks_failed', capture=label))
    if before['plan']['coordinate'] != after['plan']['coordinate'] or before['plan']['unit'] != after['plan']['unit'] or before['plan']['rotation_order'] != after['plan']['rotation_order']:
        raise ValueError('Normalize both reports to the same coordinate system before comparison')
    for name in sorted(set(a)|set(b)):
        pair = []
        for label, items in (('before', a), ('after', b)):
            if name not in items:
                pair.append('<p>该版没有此机位</p>')
                continue
            view = items[name]
            src = Path(view['image'])
            if digest(src) != view['image_sha256']:
                raise ValueError('Captured image changed: '+str(src))
            filename = label+'-'+name+'.png'
            shutil.copy2(src, output/filename)
            pair.append('<figure><figcaption>'+label+'</figcaption><img src="'+filename+'"></figure>')
        changes = []
        if name in a and name in b:
            x, y = a[name]['readback'], b[name]['readback']
            for key in ('position','rotation_deg','projection','fov_deg','ortho_size','resolution','conditions','engine','scene'):
                if x.get(key) != y.get(key):
                    # Small roundoff in readbacks is not a camera change.
                    if key == 'position' and math.dist(x[key], y[key]) <= .0001:
                        continue
                    if key == 'rotation_deg' and max(abs((i-j+180)%360-180) for i,j in zip(x[key],y[key])) <= .001:
                        continue
                    changes.append(key)
            if changes:
                issues.append(issue('comparison_conditions_changed', 'warning', view=name, fields=changes))
        note = ', '.join(changes) or ('机位与已记录条件一致' if name in a and name in b else '仅一版有此机位')
        rows.append('<section><h2>'+html.escape(name)+'</h2><p>'+html.escape(note)+'</p><div>'+''.join(pair)+'</div></section>')
    page = '<!doctype html><meta charset="utf-8"><title>场景前后对照</title><style>body{font:16px system-ui;background:#171c22;color:#eee;margin:24px}section{margin:30px 0}section>div{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%}</style><h1>场景前后对照</h1><p>真实采集图片。条件变化会列出；本页不自动判断美术通过。</p>'+''.join(rows)
    (output/'index.html').write_text(page, encoding='utf8')
    report = issues_report('environment-comparison', issues, view_count=len(rows),
                           dependencies_changed=before['dependencies'] != after['dependencies'])
    write(output/'comparison.json', report)
    return report

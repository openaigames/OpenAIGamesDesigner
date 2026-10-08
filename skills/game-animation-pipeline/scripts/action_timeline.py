"""Compare declared action timing with recorded events. Python standard library only."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path


def number(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected a finite number')
    if minimum is not None and value < minimum:
        raise ValueError(f'{label}: must be >= {minimum}')
    return value


def keyed(rows, label):
    out = {}
    for row in rows:
        key = (row['track'], row['id'])
        if not all(isinstance(x, str) and x for x in key) or key in out:
            raise ValueError(f'{label}: duplicate or empty track/id {key}')
        out[key] = row
    return out


def analyze(spec, capture):
    if spec['schema'] != 'action-timeline/1' or capture['schema'] != 'action-events/1':
        raise ValueError('Unsupported schema')
    duration = number(spec['duration_s'], 'duration_s', 0.000001)
    origin = number(capture['zero_s'], 'zero_s')
    if not capture.get('source') or not capture.get('revision'):
        raise ValueError('Capture needs source and revision')
    expected = keyed(spec.get('events', []), 'events')
    windows = keyed(spec.get('windows', []), 'windows')
    observed = keyed(capture['events'], 'capture events')
    for collection in (spec.get('clips', []), spec.get('windows', [])):
        for row in collection:
            a = number(row['start_s'], 'start_s', 0)
            b = number(row['end_s'], 'end_s', 0)
            if not a <= b <= duration:
                raise ValueError('Interval outside duration')
    for key, row in expected.items():
        if not 0 <= number(row['time_s'], 'time_s') <= duration:
            raise ValueError(f'{key}: expected event outside duration')
        number(row.get('tolerance_s', 0), 'tolerance_s', 0)
    events = []
    issues = []
    actual = {}
    for key, row in observed.items():
        t = number(row['t_s'], 't_s') - origin
        u = number(row.get('uncertainty_s', 0), 'uncertainty_s', 0)
        actual[key] = (t, u)
        if t < 0 or t > duration:
            issues.append({'kind': 'outside_capture', 'track': key[0], 'id': key[1]})
    for key, row in expected.items():
        r = {'track': key[0], 'id': key[1], 'expected_s': row['time_s']}
        if key not in actual:
            r['status'] = 'missing'
            issues.append({'kind': 'missing_event', **r})
        else:
            t, uncertainty = actual[key]
            delta = t - row['time_s']
            tolerance = row.get('tolerance_s', 0)
            # Samples represent the whole possible time interval, not an exact timestamp.
            nearest = max(0, abs(delta) - uncertainty)
            furthest = abs(delta) + uncertainty
            status = 'within_tolerance' if furthest <= tolerance + 1e-9 else (
                'outside_tolerance' if nearest > tolerance + 1e-9 else 'uncertain')
            r.update(actual_s=t, delta_s=delta, uncertainty_s=uncertainty, status=status)
            if status != 'within_tolerance':
                issues.append({'kind': 'timing', **r})
            if row.get('window'):
                win = windows.get((key[0], row['window']))
                if win is None:
                    raise ValueError(f'{key}: unknown window')
                if t + uncertainty < win['start_s'] or t - uncertainty > win['end_s']:
                    issues.append({'kind': 'outside_window', 'track': key[0], 'id': key[1]})
                elif t - uncertainty < win['start_s'] or t + uncertainty > win['end_s']:
                    issues.append({'kind': 'window_uncertain', 'track': key[0], 'id': key[1]})
        events.append(r)
    pairs = []
    for pair in spec.get('synchronize', []):
        a, b = tuple(pair['a']), tuple(pair['b'])
        if len(a) != 2 or len(b) != 2:
            raise ValueError('Synchronization keys must be [track, id]')
        tolerance = number(pair['tolerance_s'], 'sync tolerance_s', 0)
        r = {'a': a, 'b': b}
        if a not in actual or b not in actual:
            r['status'] = 'missing'
        else:
            dt = abs(actual[a][0] - actual[b][0])
            u = actual[a][1] + actual[b][1]
            r.update(delta_s=dt, uncertainty_s=u, status=(
                'within_tolerance' if dt + u <= tolerance + 1e-9 else
                'outside_tolerance' if max(0, dt - u) > tolerance + 1e-9 else 'uncertain'))
        pairs.append(r)
        if r['status'] != 'within_tolerance':
            issues.append({'kind': 'synchronization', **r})
    delays = []
    for delay in spec.get('delays', []):
        a, b = tuple(delay['from']), tuple(delay['to'])
        if len(a) != 2 or len(b) != 2:
            raise ValueError('Delay keys must be [track, id]')
        minimum = number(delay['min_s'], 'delay min_s', 0)
        maximum = number(delay['max_s'], 'delay max_s', minimum)
        r = {'from': a, 'to': b, 'min_s': minimum, 'max_s': maximum}
        if a not in actual or b not in actual:
            r['status'] = 'missing'
        else:
            dt = actual[b][0] - actual[a][0]
            u = actual[a][1] + actual[b][1]
            r.update(actual_s=dt, uncertainty_s=u, status=(
                'within_tolerance' if dt-u >= minimum-1e-9 and dt+u <= maximum+1e-9 else
                'outside_tolerance' if dt+u < minimum-1e-9 or dt-u > maximum+1e-9 else 'uncertain'))
        delays.append(r)
        if r['status'] != 'within_tolerance':
            issues.append({'kind': 'delay', **r})
    return {'schema': 'action-timeline-report/1', 'revision': spec['revision'],
            'capture_source': capture['source'], 'capture_revision': capture['revision'],
            'events': events, 'synchronization': pairs, 'delays': delays, 'issues': issues,
            'unplanned_events': [list(k) for k in observed if k not in expected],
            'visual_review': 'not_performed', 'network_test': 'not_performed'}


def render(spec, capture, report):
    esc = lambda x: html.escape(str(x), quote=True)
    statuses = {'within_tolerance':'在容差内','outside_tolerance':'超出容差','missing':'未记录','uncertain':'采样精度不足'}
    kinds = {'missing_event':'缺少事件记录','timing':'时间需要核对','outside_window':'发生在允许区间外',
             'window_uncertain':'区间边缘的采样精度不足','synchronization':'两条轨道的时间需要核对','delay':'事件之间的间隔需要核对','outside_capture':'记录时刻超出比较范围'}
    track_label = lambda key: spec.get('track_labels', {}).get(key,key)
    event_label = lambda track,key: spec.get('event_labels', {}).get(track,{}).get(key,key)
    def cell(row,key):
        value=row.get(key,'—')
        if key=='status':return statuses.get(value,value)
        if key=='track':return track_label(value)
        if key=='id':return event_label(row['track'],value)
        return f'{value:.3f}' if isinstance(value,(int,float)) else value
    tracks = sorted({r['track'] for name in ('clips', 'windows', 'events') for r in spec.get(name, [])}
                    | {r['track'] for r in capture['events']})
    duration = spec['duration_s']
    x = lambda t: 180 + 900 * t / duration
    svg = [f'<svg viewBox="0 0 1120 {100 + len(tracks)*100}" role="img" aria-label="动作时间对照">']
    for i in range(11):
        t = i * duration / 10
        svg.append(f'<text x="{x(t)}" y="25">{t:.2f}s</text>')
    for i, track in enumerate(tracks):
        y = 65 + i * 100
        svg.append(f'<text x="8" y="{y+20}">{esc(track_label(track))}</text>')
        for kind, color, shift in [('clips', '#587ca8', 0), ('windows', '#58958c', 22)]:
            for row in spec.get(kind, []):
                if row['track'] == track:
                    svg.append(f'<rect x="{x(row["start_s"])}" y="{y+shift}" width="{max(1,x(row["end_s"])-x(row["start_s"]))}" height="17" fill="{color}"><title>{esc(row["id"])}</title></rect>')
        for row in spec.get('events', []):
            if row['track'] == track:
                xx = x(row['time_s'])
                svg.append(f'<path d="M{xx} {y-6}v60" stroke="#ddd" stroke-dasharray="3 3"><title>设定 {esc(row["id"])}</title></path>')
        for row in capture['events']:
            if row['track'] == track:
                xx = x(row['t_s']-capture['zero_s'])
                svg.append(f'<circle cx="{xx}" cy="{y+52}" r="5" fill="#ffbf69"><title>记录 {esc(row["id"])}</title></circle>')
    svg.append('</svg>')
    rows = ''.join('<tr>' + ''.join(f'<td>{esc(cell(r,k))}</td>' for k in (
        'track', 'id', 'expected_s', 'actual_s', 'delta_s', 'uncertainty_s', 'status')) + '</tr>' for r in report['events'])
    return '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>动作时间对照</title>
<style>body{background:#142028;color:#e7edf0;font:16px/1.6 system-ui;margin:32px}svg{width:100%;background:#202f39}svg text{fill:#eee;font-size:12px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #46525c;text-align:left}pre{white-space:pre-wrap}</style>
<h1>动作时间对照</h1><p>蓝条：动作片段　绿条：操作窗口　虚线：设定时刻　橙点：记录时刻</p>''' + ''.join(svg) + (
        '<p>记录来源：' + esc(capture['source']) + '。本报告没有执行画面、听音或网络同步验收。</p>'
        '<table><tr><th>轨道</th><th>事件</th><th>设定秒</th><th>记录秒</th><th>差值秒</th><th>时间误差±秒</th><th>结果</th></tr>' + rows + '</table>'
        '<h2>需要核对</h2><ul>' + (''.join('<li>'+esc(kinds.get(i['kind'],i['kind']))+'：'+esc(i.get('track',i.get('a','')))+' '+esc(i.get('id',i.get('b','')))+'</li>' for i in report['issues']) or '<li>本次指定的事件没有发现超差或缺失。</li>') + '</ul></html>')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True, help='New output directory')
    args = p.parse_args()
    spec, cap = [json.loads(f.read_text('utf-8-sig')) for f in (args.spec, args.capture)]
    report = analyze(spec, cap)
    report['inputs'] = {str(f.resolve()): hashlib.sha256(f.read_bytes()).hexdigest() for f in (args.spec, args.capture)}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    (args.out/'index.html').write_text(render(spec, cap, report), 'utf8')
    print(json.dumps({'issues': len(report['issues']), 'out': str(args.out)}))
    return 2 if report['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

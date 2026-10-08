"""Measure recorded channels under comparable inputs; JSON report and SVG plots."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path


def metric(rows, channel, fire_end_s, threshold, dwell_s):
    key = channel['key']
    if len(rows) < 3:
        raise ValueError('At least three recorded samples required')
    t = [r['t_s'] for r in rows]; y = [r[key] for r in rows]
    if any(not isinstance(v, (int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in t+y):
        raise ValueError('Nonfinite or missing sample value')
    if any(b <= a for a,b in zip(t,t[1:])):
        raise ValueError('Sample times must increase')
    if not t[0] <= fire_end_s <= t[-1]:
        raise ValueError('Firing end outside recorded samples')
    baseline = channel['baseline']
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (baseline,threshold,dwell_s,fire_end_s)):
        raise ValueError('Invalid numeric channel configuration')
    y = [v-baseline for v in y]
    firing = [v for tt,v in zip(t,y) if tt <= fire_end_s]
    post = [(tt,v) for tt,v in zip(t,y) if tt >= fire_end_s]
    recovery = None
    for i,(tt,v) in enumerate(post):
        tail = [(tx,vx) for tx,vx in post[i:] if tx <= tt+dwell_s]
        if tail and tail[-1][0]-tt >= dwell_s-1e-6 and all(abs(vx) <= threshold for tx,vx in tail):
            recovery = tt-fire_end_s; break
        # Allow the sample following the dwell boundary; it must also be in tolerance.
        until = next((j for j in range(i,len(post)) if post[j][0] >= tt+dwell_s), None)
        if until is not None and all(abs(vx) <= threshold for tx,vx in post[i:until+1]):
            recovery = tt-fire_end_s; break
    signs = [1 if v>threshold else -1 if v < -threshold else 0 for _,v in post]
    signs = [s for s in signs if s]
    energy = sum((a*a+b*b)/2*(tb-ta) for ta,tb,a,b in zip(t,t[1:],y,y[1:]))/(t[-1]-t[0])
    return {'unit': channel['unit'], 'layer': channel['layer'], 'baseline': baseline,
        'min': min(y), 'max': max(y), 'peak_abs': max(abs(v) for v in y),
        'end_of_firing': firing[-1], 'rms': math.sqrt(energy),
        'recovery_s': recovery, 'recovery_observed': recovery is not None,
        'post_fire_zero_crossings': sum(a != b for a,b in zip(signs,signs[1:])),
        'max_sample_gap_s': max(b-a for a,b in zip(t,t[1:]))}


def analyze(spec, captures):
    if spec['schema'] != 'response-comparison/1' or len(captures) < 1:
        raise ValueError('Unsupported or empty comparison')
    keys=[c['key'] for c in spec['channels']]
    if not keys or len(set(keys))!=len(keys):raise ValueError('Empty or duplicate channels')
    base = captures[0]
    reports, issues = [], []
    ids = set()
    for cap in captures:
        if cap['schema'] != 'response-capture/1' or cap['id'] in ids or not cap.get('source'):
            raise ValueError('Missing source, unsupported capture or duplicate id')
        ids.add(cap['id'])
        comparable = (cap['conditions'] == base['conditions'] and cap['inputs'] == base['inputs'])
        if not comparable:
            issues.append({'kind': 'different_inputs_or_conditions', 'id': cap['id']})
        if not cap['inputs']:
            comparable = False
            issues.append({'kind':'input_record_missing','id':cap['id']})
        metrics = {}
        for ch in spec['channels']:
            threshold = ch['threshold']
            if threshold <= 0 or spec['recovery_dwell_s'] <= 0:
                raise ValueError('Positive recovery thresholds and dwell required')
            metrics[ch['key']] = metric(cap['samples'], ch, cap['fire_end_s'], threshold, spec['recovery_dwell_s'])
        reports.append({'id': cap['id'], 'source': cap['source'], 'comparable_to_first': comparable, 'channels': metrics})
    return {'schema':'response-report/1','captures':reports,'issues':issues,
            'note':'Measurements describe recordings, not algorithm identity or human feel. Randomness needs repeated trials and seed/source records.',
            'feel_review':'not_performed'}


def plot(spec, captures):
    esc = lambda x:html.escape(str(x),quote=True)
    colors = ['#75c9ba','#ffc57a','#91baff','#dc9dcb','#ee897d','#b6c980']
    graphs = []
    for ch in spec['channels']:
        values = [r[ch['key']] for c in captures for r in c['samples']]
        lo,hi=min(values),max(values); span=max(hi-lo,1e-6)
        tmax=max(c['samples'][-1]['t_s'] for c in captures)
        tmin=min(c['samples'][0]['t_s'] for c in captures)
        paths=[]
        for i,c in enumerate(captures):
            pts=' '.join(f'{40+1000*(r["t_s"]-tmin)/(tmax-tmin):.2f},{220-180*(r[ch["key"]]-lo)/span:.2f}' for r in c['samples'])
            paths.append(f'<polyline points="{pts}" fill="none" stroke="{colors[i%len(colors)]}" stroke-width="1.5"><title>{esc(c["id"])}</title></polyline>')
        graphs.append(f'<h2>{esc(ch["key"])} · {esc(ch["layer"])} · {esc(ch["unit"])}</h2><p>纵轴 {lo:.4g}–{hi:.4g}；横轴 {tmin:.3f}–{tmax:.3f} 秒</p><svg viewBox="0 0 1080 250">'+''.join(paths)+'</svg>')
    legend=' '.join(f'<span style="color:{colors[i%len(colors)]}">{esc(c["id"])}</span>' for i,c in enumerate(captures))
    issues=analyze(spec,captures)['issues']
    note='输入记录缺失或测试条件不同，以下曲线不能作为严格的同输入比较。' if issues else '输入与条件记录一致；曲线测量不代表真人手感已验收。'
    return '<!doctype html><meta charset="utf-8"><title>运动响应对照</title><style>body{background:#142028;color:#eee;font:16px system-ui;margin:30px}svg{background:#20303b;width:100%}span{padding:12px}</style><h1>运动响应对照</h1><p>'+note+'</p><p>'+legend+'</p>'+''.join(graphs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',required=True,type=Path)
    p.add_argument('--captures',required=True,nargs='+',type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args(); spec=json.loads(a.spec.read_text('utf-8-sig'))
    caps=[json.loads(f.read_text('utf-8-sig')) for f in a.captures]
    report=analyze(spec,caps)
    report['inputs_sha256']={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [a.spec]+a.captures}
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),'utf8')
    (a.out/'index.html').write_text(plot(spec,caps),'utf8')
    print(json.dumps({'issues':len(report['issues'])}))
    return 2 if report['issues'] else 0


if __name__=='__main__':raise SystemExit(main())

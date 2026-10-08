"""Validate a recorded weapon fit and compare measured points with project targets."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def vec(value):
    if len(value)!=3 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in value):
        raise ValueError('Expected finite vector3')
    return value


def distance(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def analyze(fit):
    if fit['schema']!='weapon-fit/1' or fit['unit']!='cm' or not fit.get('coordinate') or not fit.get('source'):
        raise ValueError('Expected weapon-fit/1, cm, coordinate and source')
    if fit['space'] not in ('weapon_local','world','component'):
        raise ValueError('Unknown measurement space')
    bones=fit['bones']; points=fit['points']; issues=[]; result={}
    for key,p in points.items():
        vec(p['position_cm'])
        if p.get('bone') and p['bone'] not in bones:
            issues.append({'kind':'missing_bone','point':key,'bone':p['bone']})
    for role in fit.get('required_points',[]):
        if role not in points:issues.append({'kind':'missing_point','point':role})
    for key,target in fit.get('targets',{}).items():
        vec(target['position_cm']); limit=target['tolerance_cm']
        if not math.isfinite(limit) or limit<0:raise ValueError('Invalid target tolerance')
        if key not in points:
            issues.append({'kind':'missing_point','point':key});continue
        error=distance(target['position_cm'],points[key]['position_cm']); result[key]={'error_cm':error,'tolerance_cm':limit}
        if error>limit:issues.append({'kind':'fit_error','point':key,**result[key]})
    dimensions={}
    for part in fit.get('parts',[]):
        lo,hi=map(vec,(part['bounds_cm']['min'],part['bounds_cm']['max']))
        if any(b<a for a,b in zip(lo,hi)):raise ValueError('Inverted part bounds')
        dimensions[part['id']]=[b-a for a,b in zip(lo,hi)]
        if part.get('moving') and (not part.get('bone') or part['bone'] not in bones):
            issues.append({'kind':'moving_part_binding_missing','part':part['id']})
    sight=None
    if fit.get('sight_line'):
        rear,front=fit['sight_line']
        a,b=[points[k]['position_cm'] for k in (rear,front)]
        d=distance(a,b)
        if d<1e-8:issues.append({'kind':'sight_line_zero_length'})
        else:sight={'length_cm':d,'direction':[(v-u)/d for u,v in zip(a,b)]}
    return {'schema':'weapon-fit-report/1','source':fit['source'],'point_errors':result,
        'part_dimensions_cm':dimensions,'sight_line':sight,'issues':issues,
        'note':'All measurements must already be in the declared space. Animated contact and muzzle traces require runtime samples.',
        'visual_review':'not_performed'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();r=analyze(json.loads(a.input.read_text('utf-8-sig')))
    r['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
    with a.out.open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'issues':len(r['issues'])}));return 2 if r['issues'] else 0


if __name__=='__main__':raise SystemExit(main())

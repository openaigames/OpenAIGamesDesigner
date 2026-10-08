"""Check extruded planar polygons and route clearance; draw plans, elevations and sections.
No external dependencies. This is a drawing-data checker, not an engine collision or navigation test.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path

EPS=1e-8


def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def edges(poly):return list(zip(poly,poly[1:]+poly[:1]))
def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])


def point_segment(p,a,b):
    l=(b[0]-a[0])**2+(b[1]-a[1])**2
    if l<EPS*EPS:return distance(p,a)
    t=max(0,min(1,((p[0]-a[0])*(b[0]-a[0])+(p[1]-a[1])*(b[1]-a[1]))/l))
    return distance(p,[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])


def intersects(a,b,c,d):
    x,y,z,w=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if ((x>EPS and y< -EPS) or (x< -EPS and y>EPS)) and ((z>EPS and w< -EPS) or (z< -EPS and w>EPS)):return True
    return any(point_segment(p,q,r)<EPS for p,q,r in ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))


def segment_distance(a,b,c,d):
    if intersects(a,b,c,d):return 0.
    return min(point_segment(p,q,r) for p,q,r in ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))


def inside(p,poly):
    if any(point_segment(p,a,b)<EPS for a,b in edges(poly)):return True
    hit=False
    for a,b in edges(poly):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit


def segment_polygon_distance(a,b,poly):
    if inside(a,poly) or inside(b,poly):return 0.
    return min(segment_distance(a,b,c,d) for c,d in edges(poly))


def validate_polygon(poly):
    if len(poly)<3 or any(len(p)!=2 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in p) for p in poly):
        raise ValueError('Invalid polygon coordinates')
    if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in edges(poly)))<EPS:
        raise ValueError('Polygon has zero area')
    ee=edges(poly)
    for i,(a,b) in enumerate(ee):
        if distance(a,b)<EPS:raise ValueError('Duplicate polygon vertex')
        for j,(c,d) in enumerate(ee):
            if j>i and j!=i+1 and not (i==0 and j==len(ee)-1) and intersects(a,b,c,d):
                raise ValueError('Self-intersecting polygon')


def contained(poly,boundary):
    if not all(inside(p,boundary) for p in poly):return False
    # Split each edge at every boundary crossing; endpoints alone miss concave notches.
    for a,b in edges(poly):
        ts=[0.,1.]
        for c,d in edges(boundary):
            den=(b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0])
            if abs(den)>EPS:
                t=((c[0]-a[0])*(d[1]-c[1])-(c[1]-a[1])*(d[0]-c[0]))/den
                u=((c[0]-a[0])*(b[1]-a[1])-(c[1]-a[1])*(b[0]-a[0]))/den
                if 0<t<1 and 0<=u<=1:ts.append(t)
        ts.sort()
        for t0,t1 in zip(ts,ts[1:]):
            t=(t0+t1)/2
            if not inside([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])],boundary):return False
    return True


def analyze(data):
    def finite(value):
        if isinstance(value,dict):
            for v in value.values():finite(v)
        elif isinstance(value,list):
            for v in value:finite(v)
        elif isinstance(value,float) and not math.isfinite(value):raise ValueError('Nonfinite geometry')
    finite(data)
    if data['schema']!='spatial-drawings/1' or data['unit'] not in ('m','cm') or data['up']!='+Z':
        raise ValueError('Supported: planar XY polygons, +Z up, m or cm')
    if not data.get('coordinate') or not data.get('source') or not data.get('revision'):
        raise ValueError('Coordinate, source and revision required')
    objects=data['objects'];ids=[o['id'] for o in objects]+[r['id'] for r in data.get('routes',[])]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate object/route ID')
    boundary=data.get('boundary')
    if boundary:validate_polygon(boundary)
    issues=[];checks=[];limits=data.get('limits',{})
    for obj in objects:
        validate_polygon(obj['footprint'])
        if not all(math.isfinite(obj[k]) for k in ('z_min','z_max')) or obj['z_max']<=obj['z_min']:
            raise ValueError('Invalid object height')
        if boundary and not contained(obj['footprint'],boundary):issues.append({'kind':'outside_boundary','object':obj['id']})
        if 'wall_thickness' in obj and 'min_wall_thickness' in limits and obj['wall_thickness']<limits['min_wall_thickness']:
            issues.append({'kind':'wall_too_thin','object':obj['id'],'measured':obj['wall_thickness']})
        for op in obj.get('openings',[]):
            a,b=edges(obj['footprint'])[op['edge']];length=distance(a,b)
            if not 0<=op['start']<op['end']<=length+EPS or not obj['z_min']<=op['z_min']<op['z_max']<=obj['z_max']:
                issues.append({'kind':'opening_outside_wall','object':obj['id'],'opening':op['id']})
        if obj.get('kind')=='stairs':
            count=obj['risers'];run=obj['run'];treads=obj['treads']
            if not isinstance(count,int) or count<1 or not isinstance(treads,int) or treads<1 or run<=0:raise ValueError('Invalid stair dimensions')
            rise=(obj['z_max']-obj['z_min'])/count; tread=run/treads
            checks.append({'kind':'stair_dimensions','object':obj['id'],'rise':rise,'tread':tread,'risers':count,'treads':treads})
            if 'max_step_height' in limits and rise>limits['max_step_height']+EPS:issues.append({'kind':'step_too_high','object':obj['id'],'rise':rise})
            if 'min_tread_depth' in limits and tread<limits['min_tread_depth']-EPS:issues.append({'kind':'tread_too_short','object':obj['id'],'tread':tread})
        if obj.get('kind')=='cover' and 'cover_height_range' in limits:
            lo,hi=limits['cover_height_range'];height=obj['z_max']-obj['z_min']
            if not lo<=height<=hi:issues.append({'kind':'cover_height','object':obj['id'],'height':height})
    for route in data.get('routes',[]):
        if len(route['centerline'])<2 or route['width']<=0 or route['z_max']<=route['z_min']:
            raise ValueError('Invalid route dimensions')
        if any(len(p)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in p) for p in route['centerline']):
            raise ValueError('Invalid route coordinate')
        r=route['width']/2
        for i,(a,b) in enumerate(zip(route['centerline'],route['centerline'][1:])):
            if distance(a,b)<EPS:raise ValueError('Zero length route segment')
            if boundary and (not inside(a,boundary) or not inside(b,boundary) or min(segment_distance(a,b,c,d) for c,d in edges(boundary))<r-EPS):
                issues.append({'kind':'route_outside_boundary','route':route['id'],'segment':i})
            for obj in objects:
                if not obj.get('blocks_routes',True) or max(obj['z_min'],route['z_min'])>=min(obj['z_max'],route['z_max'])-EPS:continue
                d=segment_polygon_distance(a,b,obj['footprint'])
                if d<r-EPS:
                    issues.append({'kind':'route_clearance','route':route['id'],'segment':i,'object':obj['id'],
                                   'centerline_distance':d,'required_half_width':r,'intrusion':r-d})
    return {'schema':'spatial-report/1','revision':data['revision'],'unit':data['unit'],
        'issues':issues,'measurements':checks,'engine_collision_test':'not_performed',
        'note':'Routes use a full-width sweep with round joins. Openings are annotations; split walls into solid polygons before clearance checks. Terrain, curved surfaces and arbitrary volumes are outside this checker.'}


def section_intervals(poly,axis,at):
    other=1-axis;xs=[]
    for a,b in edges(poly):
        if (a[other]>at)!=(b[other]>at):
            xs.append(a[axis]+(b[axis]-a[axis])*(at-a[other])/(b[other]-a[other]))
    xs.sort()
    return [(a,b) for a,b in zip(xs[::2],xs[1::2]) if b-a>EPS]


def drawings(data):
    esc=lambda x:html.escape(str(x),quote=True)
    allpoints=[p for o in data['objects'] for p in o['footprint']]+data.get('boundary',[])
    if not allpoints:raise ValueError('No drawing geometry')
    panels=[]
    for view in data.get('views',[{'id':'plan','type':'plan'}]):
        shapes=[];extent=[]
        if view['type']=='plan':
            for o in data['objects']:
                if 'height' in view and not o['z_min']<=view['height']<=o['z_max']:continue
                pts=[(p[0],-p[1]) for p in o['footprint']];extent+=pts
                points=' '.join(f'{x},{y}' for x,y in pts)
                cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts)
                shapes.append(f'<polygon points="{points}"/><text x="{cx}" y="{cy}">{esc(o["id"])}</text>')
                for op in o.get('openings',[]):
                    a,b=edges(o['footprint'])[op['edge']];length=distance(a,b)
                    aa=[a[i]+(b[i]-a[i])*op['start']/length for i in range(2)]
                    bb=[a[i]+(b[i]-a[i])*op['end']/length for i in range(2)]
                    shapes.append(f'<path d="M{aa[0]} {-aa[1]}L{bb[0]} {-bb[1]}" style="stroke:#ffc57a;stroke-width:.15"><title>{esc(op["id"])}: {op["end"]-op["start"]:.3f} {esc(data["unit"])}</title></path>')
            for r in data.get('routes',[]):
                pts=[(p[0],-p[1]) for p in r['centerline']];extent+=pts
                points=' '.join(f'{x},{y}' for x,y in pts)
                shapes.append(f'<polyline points="{points}" style="fill:none;stroke:#56bca4;stroke-opacity:.35;stroke-width:{r["width"]};stroke-linecap:round;stroke-linejoin:round"/>')
            if data.get('boundary'):
                pts=[(p[0],-p[1]) for p in data['boundary']];extent+=pts
                shapes.append('<polygon style="fill:none;stroke:#ddd;stroke-dasharray:1 1" points="'+' '.join(f'{x},{y}' for x,y in pts)+'"/>')
        elif view['type'] in ('elevation','section'):
            axis={'X':0,'Y':1}[view['axis']]
            for o in data['objects']:
                intervals=section_intervals(o['footprint'],axis,view['at']) if view['type']=='section' else [(min(p[axis] for p in o['footprint']),max(p[axis] for p in o['footprint']))]
                for lo,hi in intervals:
                    extent.extend([(lo,-o['z_min']),(hi,-o['z_max'])])
                    shapes.append(f'<rect x="{lo}" y="{-o["z_max"]}" width="{hi-lo}" height="{o["z_max"]-o["z_min"]}"/><text x="{lo}" y="{-o["z_max"]}">{esc(o["id"])}</text>')
        else:raise ValueError('Unknown view type')
        if not extent:
            panels.append(f'<h2>{esc(view["id"])}</h2><p>此截面没有对象。</p>');continue
        lo=[min(p[i] for p in extent) for i in range(2)];hi=[max(p[i] for p in extent) for i in range(2)]
        span=max(hi[0]-lo[0],hi[1]-lo[1],1);pad=span*.04;font=span*.013
        svg=f'<svg viewBox="{lo[0]-pad} {lo[1]-pad} {hi[0]-lo[0]+2*pad} {hi[1]-lo[1]+2*pad}"><g style="stroke-width:{span*.001};font-size:{font}px">'+''.join(shapes)+'</g></svg>'
        label={'plan':'平面','elevation':'体块立面','section':'剖面'}[view['type']]
        detail=(' · 水平轴 '+view['axis']) if 'axis' in view else ''
        if 'at' in view:detail+=' · 切面位置 '+str(view['at'])
        panels.append(f'<h2>{esc(view["id"])}</h2><p>{label}{esc(detail)} · 单位 {esc(data["unit"])}</p>'+svg)
    return '<!doctype html><html lang="zh"><meta charset="utf-8"><title>空间图纸检查</title><style>body{background:#142028;color:#eee;font:16px system-ui;margin:30px}svg{width:100%;max-height:760px;background:#20303b}polygon,rect{fill:#8197a0;fill-opacity:.2;stroke:#c8d0c3}text{fill:white;stroke:none}pre{white-space:pre-wrap}</style><h1>空间图纸检查 · '+esc(data['revision'])+'</h1><p>由同一份空间数据生成。立面为体块投影，不处理遮挡；剖面为实际切线与占地的交集。洞口仅标注，通行检测需要完整的墙体实体。</p>'+''.join(panels)+'</html>'


def compare(before,after):
    if any(before[k]!=after[k] for k in ('unit','coordinate','up')):raise ValueError('Coordinate/unit mismatch')
    a={o['id']:o for o in before['objects']};b={o['id']:o for o in after['objects']}
    return {'before_revision':before['revision'],'after_revision':after['revision'],
        'added':sorted(set(b)-set(a)),'removed':sorted(set(a)-set(b)),
        'changed':[{'id':k,'before':a[k],'after':b[k]} for k in sorted(set(a)&set(b)) if a[k]!=b[k]],
        'route_changes': before.get('routes',[])!=after.get('routes',[]),
        'before':analyze(before),'after':analyze(after)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--before',type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();data=json.loads(a.input.read_text('utf-8-sig'));report=analyze(data)
    if a.before:report['comparison']=compare(json.loads(a.before.read_text('utf-8-sig')),data)
    report['inputs_sha256']={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [a.input]+([a.before] if a.before else [])}
    page=drawings(data);a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),'utf8')
    (a.out/'index.html').write_text(page,'utf8');print(json.dumps({'issues':len(report['issues'])}))
    return 2 if report['issues'] else 0


if __name__=='__main__':raise SystemExit(main())

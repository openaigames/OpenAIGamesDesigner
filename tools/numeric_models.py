"""Bounded numeric predictions and source-linked measurements, never game authority."""
import math,bisect,html
from record_io import local,read_json,write_json,snapshot_files,changed_files,identifier,now

def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Expected finite numeric model value')
    return value

def pointer(data,path):
    if not isinstance(path,str) or (path and not path.startswith('/')):raise ValueError('Explicit JSON pointer required')
    for key in path.split('/')[1:]:
        key=key.replace('~1','/').replace('~0','~')
        if isinstance(data,list):
            if not key.isdigit():raise ValueError('Array pointer requires nonnegative index')
            data=data[int(key)]
        else:data=data[key]
    return data

def expression(node,x,params,depth=0):
    if depth>16:raise ValueError('Expression nesting exceeds 16')
    if type(node) in (int,float):return number(node)
    if node=='x':return x
    if isinstance(node,str) and node in params:return params[node]
    if not isinstance(node,dict) or set(node)!={'op','args'}:raise ValueError('Use explicit arithmetic tree; code/eval is unsupported')
    op=node['op'];args=node['args']
    counts={'add':2,'subtract':2,'multiply':2,'divide':2,'min':2,'max':2,'ceil':1,'floor':1,'clamp':3}
    if op not in counts or not isinstance(args,list) or len(args)!=counts[op]:raise ValueError('Unsupported arithmetic or arity')
    a=[expression(v,x,params,depth+1) for v in args]
    if op=='divide' and a[1]==0:raise ValueError('Model denominator is zero')
    if op=='clamp' and a[1]>a[2]:raise ValueError('Clamp bounds reversed')
    functions={'add':lambda:a[0]+a[1],'subtract':lambda:a[0]-a[1],'multiply':lambda:a[0]*a[1],
        'divide':lambda:a[0]/a[1],'min':lambda:min(a),'max':lambda:max(a),'ceil':lambda:math.ceil(a[0]),
        'floor':lambda:math.floor(a[0]),'clamp':lambda:max(a[1],min(a[2],a[0]))}
    return number(functions[op]())

def calculate(model,x,params):
    kind=model['kind']
    if kind=='expression':return expression(model['expression'],x,params)
    if kind not in ('piecewise_linear','step'):raise ValueError('Unsupported model kind')
    points=model['points']
    if not isinstance(points,list) or not 2<=len(points)<=256:raise ValueError('Use 2..256 ordered curve/threshold points')
    for i,p in enumerate(points):
        if not isinstance(p,list) or len(p)!=2:raise ValueError('Expected [input,output]')
        number(p[0]);number(p[1])
        if i and p[0]<=points[i-1][0]:raise ValueError('Model inputs must strictly increase')
    boundary=model.get('boundary','reject')
    if boundary not in ('reject','clamp'):raise ValueError('Explicit bounded extrapolation policy required')
    if x<points[0][0] or x>points[-1][0]:
        if boundary=='reject':raise ValueError('Requested input outside model support')
        return points[0 if x<points[0][0] else -1][1]
    i=bisect.bisect_right([p[0] for p in points],x)-1
    if i==len(points)-1 or kind=='step':return points[i][1]
    a,b=points[i:i+2];return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])

def evaluate(root,request,out):
    spec=read_json(local(root,request));identifier(spec['id'])
    if spec.get('schema_version')!=1 or set(spec)-{'schema_version','id','title','object','input_unit','output_unit','basis','conditions','inputs','model','parameters','measurements'}:raise ValueError('Invalid numeric model request')
    for key in ['title','object','input_unit','output_unit','basis']:
        if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('Model requires '+key)
    if not isinstance(spec.get('conditions'),list) or any(not isinstance(c,str) for c in spec['conditions']):raise ValueError('Explicit model conditions required')
    dependencies=[request]
    def source(ref):
        if not isinstance(ref,dict) or set(ref)-{'file','pointer','authority','provenance','unit'} or not ref.get('file') or 'pointer' not in ref:raise ValueError('Measured values need actual file and JSON pointer')
        dependencies.append(ref['file'])
        if ref.get('authority'):dependencies.append(ref['authority'])
        return pointer(read_json(local(root,ref['file'])),ref['pointer'])
    params={}
    for key,ref in spec.get('parameters',{}).items():
        identifier(key)
        if not ref.get('authority') or not ref.get('provenance') or not ref.get('unit'):raise ValueError('Parameter requires authoritative source, origin and units')
        params[key]=number(source(ref))
    model=dict(spec['model'])
    if 'points_source' in model:model['points']=source(model.pop('points_source'))
    inputs=spec['inputs']
    if not isinstance(inputs,list) or not 1<=len(inputs)<=2000:raise ValueError('Model needs 1..2000 explicit samples')
    samples=[[number(x),calculate(model,x,params)] for x in inputs]
    measured=[]
    if not isinstance(spec.get('measurements',[]),list) or len(spec.get('measurements',[]))>2000:raise ValueError('Bounded measurements required')
    for m in spec.get('measurements',[]):
        if set(m)-{'x','y','conditions','execution_ref','basis'} or not m.get('conditions') or not m.get('basis'):raise ValueError('Measurement conditions and basis required')
        if m['basis'] not in ('runtime','reference'):raise ValueError('Measurement basis must be runtime or reference')
        x=number(source(m['x']) if isinstance(m['x'],dict) else m['x']);y=number(source(m['y']))
        if m['basis']=='runtime':
            run=m.get('execution_ref');record=read_json(local(root,run))
            if record.get('status') not in ('completed','passed'):raise ValueError('Actual completed runtime record required for runtime comparison')
            dependencies.append(run)
        predicted=calculate(model,x,params)
        measured.append({**m,'input':x,'actual':y,'predicted':predicted,'difference':y-predicted})
    result={'schema_version':1,'id':spec['id'],'created_at':now(),'title':spec['title'],'object':spec['object'],
        'input_unit':spec['input_unit'],'output_unit':spec['output_unit'],'basis':spec['basis'],'conditions':spec['conditions'],
        'parameters':params,'samples':samples,'measurements':measured,'dependencies':snapshot_files(root,list(dict.fromkeys(dependencies))),
        'scope':'Prediction and measured comparison only; does not modify author data or approve game feel'}
    path=local(root,out)
    if path.exists() or path.with_suffix('.html').exists():raise ValueError('Model outputs already exist; choose a new report version')
    write_json(path,result,create=True)
    render(path.with_suffix('.html'),result)
    return result

def render(path,row):
    esc=lambda v:html.escape(str(v));points=row['samples'];actual=row['measurements']
    xs=[p[0] for p in points]+[p['input'] for p in actual];ys=[p[1] for p in points]+[p['actual'] for p in actual]
    a,b=min(xs),max(xs);c,d=min(ys),max(ys)
    xy=lambda x,y:(60+760*(x-a)/(b-a or 1),320-260*(y-c)/(d-c or 1))
    line=' '.join('%.2f,%.2f'%xy(x,y) for x,y in points)
    marks=''.join('<circle cx="%.2f" cy="%.2f" r="5" fill="#c95040"/>'%xy(m['input'],m['actual']) for m in actual)
    table=''.join('<tr>'+''.join('<td>'+esc(m[k])+'</td>' for k in ['input','predicted','actual','difference','conditions'])+'</tr>' for m in actual)
    page=f'<!doctype html><meta charset="utf-8"><title>{esc(row["title"])}</title><style>body{{font:16px system-ui;margin:32px;max-width:1000px}}td,th{{padding:8px;text-align:left}}svg{{width:100%;border:1px solid #ddd}}</style><h1>{esc(row["title"])}</h1><p>{esc(row["basis"])}</p><p>预测为蓝线，实测为红点；X：{esc(row["input_unit"])}；Y：{esc(row["output_unit"])}。模型和实测条件须一致才能比较。</p><svg viewBox="0 0 900 360" role="img" aria-label="数值预测与实测"><path d="M60 40 V320 H830" fill="none" stroke="#888"/><polyline points="{line}" fill="none" stroke="#276aa5" stroke-width="2"/>{marks}<text x="60" y="345">{a:g}</text><text x="780" y="345">{b:g}</text><text x="5" y="60">{d:g}</text><text x="5" y="320">{c:g}</text></svg><table><tr><th>输入</th><th>预测</th><th>实测</th><th>差值</th><th>条件</th></tr>{table}</table><p>{esc(row["scope"])}</p><pre>{esc(chr(10).join(row["conditions"]))}</pre>'
    with path.open('x',encoding='utf-8') as f:f.write(page)

def assess(root,path):
    row=read_json(local(root,path));changed=changed_files(root,row['dependencies'])
    return {'status':'stale' if changed else 'current','changed':changed,'model':row}

def snapshots(root):
    rows=[]
    for path in sorted(local(root,'production/numeric-models').glob('*.json')):
        relative=path.relative_to(root).as_posix()
        try:rows.append({'path':relative,**assess(root,relative)})
        except (ValueError,OSError,KeyError,TypeError) as error:rows.append({'path':relative,'status':'invalid','error':str(error)})
    return rows

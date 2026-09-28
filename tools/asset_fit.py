"""Versioned asset combination evidence, separate from download/usage/quality."""
from urllib.parse import urlsplit
from record_io import local,identifier,read_json,write_json,now,snapshot_files,changed_files
from content_roots import in_game

def text(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>4000:raise ValueError('Missing/bounded text: '+label)
    return value

def validate(root,spec):
    if not isinstance(spec,dict) or set(spec)-{'schema_version','id','title','object','role','use','goal_ref','sources','members','requirements','tradeoffs','supersedes'} or spec.get('schema_version')!=1:raise ValueError('Invalid asset fit record')
    identifier(spec['id'])
    for key in ['title','object','role','use','goal_ref']:text(spec.get(key),key)
    deps=[spec['goal_ref']]
    sources=spec.get('sources',[])
    if not sources or len(sources)>128:raise ValueError('Asset fit needs actual selected sources')
    urls=set()
    for source in sources:
        if set(source)-{'url','title','version','price','license','evidence'}:raise ValueError('Invalid selected source fields')
        parsed=urlsplit(source['url'])
        if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:raise ValueError('Use original HTTPS source URL without credentials')
        for key in ['title','version','price','license']:text(source.get(key),key)
        if source['url'] in urls:raise ValueError('Duplicate selected source')
        urls.add(source['url']);deps.extend(source.get('evidence',[]))
    members={}
    for member in spec.get('members',[]):
        if set(member)-{'id','path','source_url','capabilities','note'} or member.get('source_url') not in urls:raise ValueError('Member needs actual source')
        mid=identifier(member['id'])
        if mid in members:raise ValueError('Duplicate fit member')
        members[mid]={}
        if member.get('path'):deps.append(member['path'])
        for cap in member.get('capabilities',[]):
            if set(cap)-{'id','kind','label','availability','preview_type','evidence','conditions'}:raise ValueError('Invalid capability fields')
            cid=identifier(cap['id'])
            if cid in members[mid]:raise ValueError('Duplicate capability')
            if cap.get('kind') not in ('motion','rig','model','vfx','audio','environment','other') or cap.get('availability') not in ('observed','claimed','missing','unknown'):raise ValueError('Invalid capability claim')
            for key in ['label','conditions']:text(cap.get(key),key)
            if cap.get('preview_type') not in ('motion','image','native','audio','none'):raise ValueError('Distinguish actual preview type')
            if cap['availability']=='observed':
                if not cap.get('evidence'):raise ValueError('Observed capability needs local versioned evidence')
                if cap['kind'] in ('motion','vfx') and cap['preview_type'] not in ('motion','native'):raise ValueError('Static image does not establish animation coverage')
                if cap['kind']=='audio' and cap['preview_type']!='audio':raise ValueError('Audio capability requires actual listening evidence')
            deps.extend(cap.get('evidence',[]));members[mid][cid]=cap
    if not members:raise ValueError('At least one concrete candidate member required')
    requirements=spec.get('requirements',[]);ids=set()
    if not requirements:raise ValueError('Record target requirements and gaps')
    for req in requirements:
        if set(req)-{'id','description','coverage','member','capability','notes'}:raise ValueError('Invalid fit requirement')
        rid=identifier(req['id']);text(req.get('description'),'requirement description');text(req.get('notes'),'comparison basis/gap')
        if rid in ids:raise ValueError('Duplicate requirement')
        ids.add(rid)
        if req.get('coverage') not in ('supported','partial','missing','unknown'):raise ValueError('Invalid fit coverage')
        cap=members.get(req.get('member'),{}).get(req.get('capability'))
        if req['coverage']=='supported' and (not cap or cap['availability']!='observed'):raise ValueError('Supported requirement needs an observed capability, not source advertising')
        if req.get('member') and req['member'] not in members:raise ValueError('Unknown member')
    for tradeoff in spec.get('tradeoffs',[]):text(tradeoff,'tradeoff')
    if spec.get('supersedes'):identifier(spec['supersedes'])
    return sorted(set(deps))

def register(root,spec):
    deps=validate(root,spec)
    if spec.get('supersedes'):
        old=read(root,spec['supersedes'])
        if (old['spec']['object'],old['spec']['goal_ref'])!=(spec['object'],spec['goal_ref']):raise ValueError('Revision cannot silently replace another object/goal')
    record={'schema_version':1,'id':spec['id'],'created_at':now(),'spec':spec,'dependencies':snapshot_files(root,deps)}
    write_json(local(root,'.openaigame/asset-library/fit/'+spec['id']+'.json'),record,create=True)
    return read(root,spec['id'])

def read(root,fit_id):
    row=read_json(local(root,'.openaigame/asset-library/fit/'+identifier(fit_id)+'.json'))
    expected=validate(root,row['spec'])
    if row.get('id')!=fit_id or set(row.get('dependencies',{}))!=set(expected):raise ValueError('Fit dependency identity missing')
    changed=changed_files(root,row['dependencies'])
    paths=[m['path'] for m in row['spec']['members'] if m.get('path')]
    # A mixed or remote-only combination stays a candidate. This never imports,
    # promotes or judges an asset merely because a fit record exists.
    game=bool(paths) and len(paths)==len(row['spec']['members']) and all(in_game(p,root) for p in paths)
    return {**row,'status':'stale' if changed else 'current','changed':changed,'location':'game' if game else 'candidate',
            'gaps':[r for r in row['spec']['requirements'] if r['coverage']!='supported']}

def snapshot(root):
    rows=[];errors=[]
    for path in sorted(local(root,'.openaigame/asset-library/fit').glob('*.json')):
        try:rows.append(read(root,path.stem))
        except (OSError,ValueError,KeyError,TypeError) as e:errors.append({'path':str(path),'error':str(e)})
    superseded={r['spec'].get('supersedes') for r in rows if r['status']=='current'}
    return {'fits':[r for r in rows if r['id'] not in superseded],'historical_fits':[r['id'] for r in rows if r['id'] in superseded],'fit_errors':errors}

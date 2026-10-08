"""Immutable asset revisions, explicit selection and pinned production references."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from contextlib import contextmanager
from uuid import uuid4
from urllib.parse import quote
from game_workflow import atomic_json, now
from validate_records import contract
from . import art_registry, asset_taxonomy

RECORD='.openaigame/asset-versions/index.json'
PREFIX='.openaigame/asset-versions/'
KINDS={'image','model','animation','texture','audio','video','vfx','engine','code','other'}
EXTENSIONS={'.png':'image','.jpg':'image','.jpeg':'image','.webp':'image','.svg':'image','.psd':'image',
 '.glb':'model','.gltf':'model','.fbx':'model','.obj':'model','.blend':'model','.wav':'audio','.mp3':'audio',
 '.ogg':'audio','.flac':'audio','.mp4':'video','.webm':'video','.bvh':'animation','.anim':'animation',
 '.uasset':'engine','.umap':'engine','.tga':'texture','.exr':'texture','.hdr':'texture','.dds':'texture'}

def safe(root,relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('版本文件路径无效')
    root=Path(root).resolve();target=root/relative
    for p in [target,*target.parents]:
        if p==root.parent:break
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('版本路径不能经过链接目录')
    if not target.resolve().is_relative_to(root):raise ValueError('版本路径超出项目')
    return target

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def text(value,name,limit=4000,empty=False):
    if not isinstance(value,str) or len(value)>limit or (not empty and not value.strip()):raise ValueError(name+'无效')
    return value.strip()

def load(root):
    path=safe(root,RECORD)
    if not path.exists():return {'schemaVersion':1,'revision':0,'groups':{}}
    if path.stat().st_size>32*1024**2:raise ValueError('版本清单过大')
    data=json.loads(path.read_text('utf-8'))
    errors=contract('asset-versions',data)
    if errors:raise ValueError('版本清单无效：'+'; '.join(errors[:3]))
    if data.get('schemaVersion')!=1 or type(data.get('revision')) is not int or not isinstance(data.get('groups'),dict):raise ValueError('版本清单无效')
    for gid,g in data['groups'].items():
        if not re.fullmatch(r'VG[0-9a-f]{16}',gid) or g.get('id')!=gid or g.get('kind') not in KINDS:raise ValueError('资产版本组无效')
        ids=set()
        for v in g['versions']:
            vid=v['id']
            if not re.fullmatch(r'V[0-9a-f]{16}',vid) or vid in ids:raise ValueError('资产版本标识无效')
            if v.get('parent') and v['parent'] not in ids:raise ValueError('修改底稿不存在')
            ids.add(vid)
            for f in v['files']:
                if not f['path'].startswith(PREFIX+gid+'/'+vid+'/files/'):raise ValueError('版本快照路径不符')
                safe(root,f['path']);safe(root,f['sourcePath'])
                if not re.fullmatch('[0-9a-f]{64}',f['sha256']):raise ValueError('版本摘要无效')
        if g.get('selected') and g['selected'] not in ids:raise ValueError('选用版本不存在')
    return data

def version(data,gid,vid):
    group=data['groups'].get(gid)
    if not group:raise ValueError('资产版本组不存在')
    result=next((v for v in group['versions'] if v['id']==vid),None)
    if not result:raise ValueError('资产版本不存在')
    return group,result

def intact(root,v):
    try:return all(safe(root,f['path']).is_file() and digest(safe(root,f['path']))==f['sha256'] for f in v['files'])
    except (OSError,ValueError):return False

def lineage(root,value):
    if not isinstance(value,dict) or set(value)-{'group','parent','references','note'}:raise ValueError('制作版本关联无效')
    data=load(root);group=data['groups'].get(value.get('group'))
    if value.get('group') and not group:raise ValueError('请选择实际资产版本组')
    if not group and value.get('parent'):raise ValueError('修改底稿必须属于已存在的资产')
    result={'group':group['id'] if group else None,'parent':value.get('parent'),'references':[],
            'note':text(value.get('note',''),'修改说明',empty=True)}
    if result['parent']:
        _,v=version(data,group['id'],result['parent'])
        if not intact(root,v):raise ValueError('修改底稿文件缺失或已变化')
    refs=value.get('references',[])
    if not isinstance(refs,list) or len(refs)>40:raise ValueError('参考数量无效')
    for ref in refs:
        _,v=version(data,ref['group'],ref['version'])
        if not intact(root,v):raise ValueError('参考版本文件缺失或已变化')
        result['references'].append({'group':ref['group'],'version':v['id'],'role':text(ref.get('role','参考'),'参考用途',80)})
    return result

@contextmanager
def locked(root):
    path=safe(root,PREFIX+'write.lock');path.parent.mkdir(parents=True,exist_ok=True)
    try:stream=path.open('x',encoding='utf-8')
    except FileExistsError:raise art_registry.RevisionConflict('版本记录正在保存，请刷新后重试') from None
    try:
        stream.write(now());stream.close();yield
    finally:path.unlink(missing_ok=True)

def add(root,data,g,payload):
    entries=payload.get('files',[])
    if not isinstance(entries,list) or not 1<=len(entries)<=200:raise ValueError('请提供本次版本的实际文件')
    parent=payload.get('parent')
    context={'group':g['id'],'parent':parent,'references':[],'note':text(payload.get('note',''),'修改说明',empty=True)}
    if parent:
        _,base=version(data,g['id'],parent)
        if not intact(root,base):raise ValueError('底稿文件已变化')
    refs=payload.get('references',[])
    if not isinstance(refs,list) or len(refs)>40:raise ValueError('参考数量无效')
    for ref in refs:
        _,base=version(data,ref['group'],ref['version'])
        if not intact(root,base):raise ValueError('参考文件已变化')
        context['references'].append({'group':ref['group'],'version':ref['version'],'role':text(ref.get('role','参考'),'参考用途',80)})
    sources=[];seen=set()
    for i,entry in enumerate(entries):
        entry={'path':entry} if isinstance(entry,str) else entry
        relative=entry['path'];source=art_registry.asset_path(root,relative)
        if relative in seen or not source.is_file() or not source.stat().st_size:raise ValueError('输入文件重复、为空或不存在')
        seen.add(relative)
        h=digest(source)
        if entry.get('sha256') and entry['sha256']!=h:raise ValueError('源文件已变化，请刷新后再登记')
        sources.append((source,relative,h,text(entry.get('role','主文件' if i==0 else '配套文件'),'文件用途',80)))
    from .asset_browser import KINDS as browser_kinds
    first=sources[0][0]
    kind='vfx' if first.name.endswith('.vfx.json') else browser_kinds.get(first.suffix.lower(),EXTENSIONS.get(first.suffix.lower(),'other'))
    if kind!=g['kind'] and not ({kind,g['kind']}<={'image','texture'} or (g['kind']=='animation' and kind in ('model','engine'))):raise ValueError('不同类型的交付物不能作为同一资产的版本')
    provenance=payload.get('provenance',{})
    if not isinstance(provenance,dict) or len(json.dumps(provenance,ensure_ascii=False))>65536:raise ValueError('制作来源记录无效')
    # Exact input/output retries are idempotent; differing references remain distinct decisions.
    fingerprint=hashlib.sha256(json.dumps({'files':[(h,role) for _,_,h,role in sources], 'context':context,
        'provenance':provenance},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    existing=next((v for v in g['versions'] if v.get('fingerprint')==fingerprint),None)
    if existing:
        if not intact(root,existing):raise ValueError('已登记的相同版本文件缺失或已变化')
        return existing
    vid='V'+uuid4().hex[:16];files=[]
    for source,relative,h,role in sources:
        # Keep project-relative directories so accompanying glTF/OBJ files retain relative references.
        stored=PREFIX+g['id']+'/'+vid+'/files/'+relative
        target=safe(root,stored);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if digest(target)!=h or digest(source)!=h:raise ValueError('复制期间文件发生变化；未登记不完整版本')
        row={'path':relative,'kind':browser_kinds.get(source.suffix.lower(),'other'),'ext':source.suffix[1:].upper()}
        asset_taxonomy.attach(root,[row],[])
        display={'classification':row['classification']}
        try:
            art=art_registry.classify(root,row,art_registry.load(root))
            if art:display.update(art=art,tags=art['tags'])
        except (OSError,ValueError):pass
        files.append({'path':stored,'sourcePath':relative,'sha256':h,'bytes':target.stat().st_size,'role':role,'display':display})
    v={'id':vid,'number':len(g['versions'])+1,'createdAt':now(),'parent':context['parent'],
       'references':context['references'],'note':context['note'],'files':files,'provenance':provenance,
       'fingerprint':fingerprint,'archived':False}
    g['versions'].append(v);return v

def mutate(root,payload):
    with locked(root):
        data=load(root)
        if payload.get('revision') is not None and payload['revision']!=data['revision']:raise art_registry.RevisionConflict('版本记录已更新，请刷新后重试')
        action=payload.get('action');gid=payload.get('group');vid=None
        if action=='create':
            kind=payload.get('kind')
            if kind not in KINDS:raise ValueError('资产类型无效')
            gid='VG'+uuid4().hex[:16]
            g={'id':gid,'title':text(payload.get('title'),'资产名称',100),'kind':kind,
               'objectId':text(payload.get('objectId',''),'对象',100,True),'selected':None,'versions':[],'decisions':[]}
            data['groups'][gid]=g
            if payload.get('files'):vid=add(root,data,g,payload)['id']
        elif action=='add':
            if gid not in data['groups']:raise ValueError('资产版本组不存在')
            vid=add(root,data,data['groups'][gid],payload)['id']
        elif action in ('select','archive'):
            g,v=version(data,gid,payload.get('version'));vid=v['id']
            if action=='select':
                if not intact(root,v):raise ValueError('版本文件缺失或已变化，不能重新选用')
                before=g['selected'];g['selected']=vid;v['archived']=False
                g['decisions'].append({'at':now(),'from':before,'to':vid,'reason':text(payload.get('reason'),'选用依据')})
            else:
                if type(payload.get('archived')) is not bool:raise ValueError('归档状态无效')
                if payload['archived'] and g['selected']==vid:raise ValueError('当前选用版本不能归档，请先选择其他版本')
                v['archived']=payload['archived']
        else:raise ValueError('版本操作无效')
        data['revision']+=1
        atomic_json(safe(root,RECORD),data)
        result={'group':gid,'version':vid,'revision':data['revision']}
        if action in ('create','add') and vid:
            from . import asset_handoff
            try:
                _,v=version(data,gid,vid)
                context={}
                object_id=data['groups'][gid].get('objectId')
                if object_id:
                    obj=art_registry.load(root)['objects'].get(object_id)
                    if obj:context['object']=obj
                result['artRegistration']=asset_handoff.automatic(root,
                    [{'path':f['sourcePath'],'sha256':f['sha256']} for f in v['files']],context,
                    RECORD,'existing','手工/工具保存的资产版本 '+gid+'/'+vid)
            except (OSError,ValueError,KeyError,TypeError) as error:
                result['artRegistrationError']=str(error)
        try:sync_document(root,data)
        except (OSError,ValueError) as error:result['documentWarning']='版本已保存，美术入口尚未同步：'+str(error)
        return result

def sync_document(root,data):
    from record_io import project_lock
    with project_lock(root,'art-registry'):
        return _sync_document(root,data)

def _sync_document(root,data):
    """Project prose points at the ledger; it does not duplicate the revision history."""
    path=art_registry.document_path(root)
    if not path.exists():return
    original=path.read_text('utf-8-sig');start='<!-- asset-version-selections:start -->';end='<!-- asset-version-selections:end -->'
    link=lambda relative:Path(os.path.relpath(safe(root,relative),path.parent)).as_posix()
    lines=[start,'## 资产版本选用','', '版本历史以[资产版本记录](<'+link(RECORD)+'>)为准；选用制作依据不代表工程已经替换。','',
           '| 资产 | 当前选用 | 最新版本 |','| --- | --- | --- |']
    for g in data['groups'].values():
        if not g['versions']:continue
        selected=next((v for v in g['versions'] if v['id']==g['selected']),None)
        label=g['title'].replace('|','\\|').replace('\n',' ')
        selected_label=('[V'+str(selected['number'])+'](<'+link(selected['files'][0]['path'])+'>)') if selected else '尚未选用'
        lines.append(f'| {label} | {selected_label} | V{g["versions"][-1]["number"]} |')
    section='\n'.join(lines)+ '\n'+end
    if (start in original)!=(end in original):raise ValueError('版本摘要区块不完整')
    updated=original[:original.index(start)]+section+original[original.index(end)+len(end):] if start in original else original.rstrip()+'\n\n'+section+'\n'
    if updated==original:return
    if path.read_text('utf-8-sig')!=original:raise art_registry.RevisionConflict('美术文档同时被修改')
    backup=safe(root,PREFIX+'document-backups/'+uuid4().hex+'.md');backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(original,'utf-8')
    temporary=path.with_name(path.name+'.versions-'+uuid4().hex+'.tmp');temporary.write_text(updated,'utf-8')
    if path.read_text('utf-8-sig')!=original:
        temporary.unlink(missing_ok=True);raise art_registry.RevisionConflict('美术文档同时被修改')
    temporary.replace(path)

def metadata(root):
    rows={}
    for g in load(root)['groups'].values():
        for v in g['versions']:
            for i,f in enumerate(v['files']):
                rows[f['path']]={'title':g['title'] if i==0 else Path(f['sourcePath']).name,'versionGroup':g['id'],
                                'versionId':v['id'],'versionPart':i,'versionSource':f['sourcePath']}
    return rows

def file_path(root,relative):
    for g in load(root)['groups'].values():
        for v in g['versions']:
            for f in v['files']:
                if f['path']==relative:
                    path=safe(root,relative)
                    if not path.is_file() or digest(path)!=f['sha256']:raise ValueError('版本文件缺失或已变化')
                    return path
    raise ValueError('版本文件未登记')

def snapshot(root):
    try:data=load(root)
    except (OSError,ValueError,KeyError,TypeError) as error:return {'revision':None,'groups':[],'error':str(error)}
    result=copy.deepcopy(data)
    for g in result['groups'].values():
        g['latest']=g['versions'][-1]['id'] if g['versions'] else None
        g['current']=g['selected'] or next((v['id'] for v in reversed(g['versions']) if not v['archived']),g['latest'])
        for v in g['versions']:
            v['intact']=intact(root,v);v['warnings']=[]
            for f in v['files']:f['url']='/asset/current/'+quote(f['path'],safe='/')
            for ref in v['references']:
                target=data['groups'].get(ref['group'])
                if not target:v['warnings'].append('关联资产已无法读取')
                elif target['selected'] and target['selected']!=ref['version']:
                    v['warnings'].append(target['title']+'的当前选用版本已改变；此版本仍使用原参考，需复核')
            v['gameFiles']=[]
    return {'revision':data['revision'],'groups':list(result['groups'].values()),'error':None}

def attach(root,items):
    report=snapshot(root);groups={g['id']:g for g in report['groups']};lookup={a['path']:a for a in items}
    for g in groups.values():
        for v in g['versions']:
            primary=v['files'][0]['path'];row=lookup.get(primary)
            for i,f in enumerate(v['files']):
                saved=lookup.get(f['path'])
                if saved:
                    display=f.get('display',{})
                    saved.update({k:val for k,val in display.items() if k in ('tags','art') and not saved.get(k)})
                    if display.get('classification') and not saved.get('classification',{}).get('manual'):
                        saved['classification']={**display['classification'],'manual':False,'basis':'保存版本时的分类'}
                for p in [f['path'],f['sourcePath']]:
                    a=lookup.get(p)
                    if not a:continue
                    if p==f['sourcePath'] and (not safe(root,p).is_file() or digest(safe(root,p))!=f['sha256']):continue
                    # Explicit membership only; identical unrelated files are not automatically grouped.
                    a.update(versionGroup=g['id'],versionId=v['id'],versionPart=i,versionNumber=v['number'],versionSource=f['sourcePath'])
                    if i==0:a.update(versionCount=len(g['versions']),versionSelected=g['selected']==v['id'],versionLatest=g['latest']==v['id'])
                    a['versionHidden']=p!=primary or v['id']!=g['current']
                    if a['location']=='game':v['gameFiles'].append(p);a['versionHidden']=False
                    if p==f['sourcePath'] and row and i==0:
                        row.update(tags=a.get('tags',[]),art=a.get('art'),source=a.get('source'),license=a.get('license'))
                        if not row.get('classification',{}).get('manual'):
                            current=row.get('classification',{});row['classification']={**a.get('classification',{}),'version':current.get('version'),'manual':False,'basis':'版本源文件分类'}
            if row:
                row['title']=g['title'];row['versionCount']=len(g['versions']);row['versionSelected']=g['selected']==v['id']
                row['versionLatest']=g['latest']==v['id'];row['versionWarnings']=v['warnings']
    return report

def complete_job(root,job):
    """Register immutable alternatives and companion sets; never select or edit game files."""
    if job['status'] not in ('succeeded','registered') or not job.get('artifacts'):return None
    outputs={a['path']:a for a in job['artifacts']}
    sets=job.get('output_sets')
    if sets is None:
        files=list(outputs)
        if job['provider'] in ('hunyuan3d','tripo','blender'):
            # A model's downloaded archive/texture may arrive first. Keep all companions,
            # but use a directly previewable mesh as the default version primary.
            priority={ext:i for i,ext in enumerate(('.glb','.gltf','.fbx','.blend','.obj'))}
            files.sort(key=lambda p:priority.get(Path(p).suffix.lower(),len(priority)))
        sets=[[p] for p in files] if job['provider'] in ('image','seedream') else [files]
    if not isinstance(sets,list) or not sets or any(not isinstance(x,list) or not x for x in sets):raise ValueError('输出分组无效')
    flattened=[p for files in sets for p in files]
    if len(flattened)!=len(set(flattened)) or set(flattened)!=set(outputs):raise ValueError('每个实际输出必须且只能归入一个方案')
    previous={}
    for g in load(root)['groups'].values():
        for v in g['versions']:
            if v['provenance'].get('job')==job['job_id']:
                previous[v['provenance'].get('variant',0)]={'group':g['id'],'version':v['id']}
    context=job['request'].get('lineage')
    gid=context['group'] if context else next((r['group'] for r in previous.values()),None)
    parameters=job['request']['parameters'];prompt=parameters.get('prompt',parameters.get('Prompt',parameters.get('text','')))
    results=[]
    for i,files in enumerate(sets):
        if i in previous:results.append(previous[i]);continue
        from .asset_browser import KINDS as browser_kinds
        kind=browser_kinds.get(Path(files[0]).suffix.lower(),EXTENSIONS.get(Path(files[0]).suffix.lower(),'other'))
        spec={'action':'add' if gid else 'create','title':(str(prompt).splitlines() or [''])[0][:100] or job['job_id'],
              'kind':kind,'files':[{'path':p,'sha256':outputs[p]['sha256']} for p in files],
              'provenance':{'job':job['job_id'],'variant':i,'tool':job.get('execution_source',job['provider']),
                            'parameters':parameters,'inputs':job['request']['inputs']}}
        if context:spec.update(context)
        if gid:spec['group']=gid
        result=mutate(root,spec);gid=result['group'];results.append(result)
    return {**results[0],'versions':[r['version'] for r in results]}

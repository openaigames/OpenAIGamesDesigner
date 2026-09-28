"""Shared board reads the same task/observation files as the CLI."""
from pathlib import Path
import json
import task_state
import observation
import content_roots
import project_links
import record_evidence
import numeric_models
from check_installation import bundle_id
from record_io import local,identifier,read_json,write_json,now,digest,changed_files,snapshot_files


def diagnostics():
    runtime=Path(__file__).resolve().parents[2]
    tracked=[p for folder in ('tools','adapters','workflows','schemas') for p in (runtime/folder).rglob('*')
        if p.is_file() and p.suffix in {'.py','.gd','.js','.css','.html','.json'}
        and not set(p.parts)&{'__pycache__','vendor','node_modules'}]
    files={p.relative_to(runtime).as_posix():digest(p) for p in tracked if p.is_file()}
    result={'version':bundle_id(files)[:12],
            'runtime':str(runtime),'files':files,'distribution':'source'}
    manifest=runtime/'bundle-manifest.json'
    if manifest.is_file():
        data=read_json(manifest)
        result.update(distribution='installed-bundle',bundle_id=data.get('bundle_id'))
    return result


def snapshot(root):
    links=None
    config=local(root,'.openaigame/project.json')
    try:
        spec=read_json(config).get('links_spec') if config.is_file() else None
        if spec:
            links=project_links.inspect(root,spec)
            links['impacts']=[project_links.impact(root,p.stem) for p in sorted(local(root,'.openaigame/link-snapshots').glob('*.json'))
                              if read_json(p).get('spec')==spec]
    except (ValueError,OSError,KeyError,TypeError,IndexError) as error:
        links={'error':str(error)}
    return {**task_state.snapshot(root),**observation.snapshots(root),'layout':content_roots.layout(root),
            'professions':sorted(task_state.PROFESSIONS),'links':links,'numeric_models':numeric_models.snapshots(root)}


def detail(root,oid):
    record=observation.read(root,oid)
    notes=[]
    for path in local(root,'.openaigame/review-notes').glob('*.json'):
        row=read_json(path)
        if row['observation']==oid:
            notes.append({**row,'status':'stale' if changed_files(root,row['dependencies']) else 'current'})
    return {**record,'notes':notes}


def annotate(root,spec):
    if not isinstance(spec,dict) or set(spec)-{'id','observation','object','text','author','anchor'}:
        raise ValueError('Unsupported review note fields')
    note_id=identifier(spec.get('id'))
    record=observation.read(root,spec['observation'])
    if spec['object'] not in {o['id'] for o in record['data']['objects']}:
        raise ValueError('Note object was not observed')
    if any(not isinstance(spec.get(k),str) or not spec[k].strip() or len(spec[k])>4000 for k in ('text','author')):
        raise ValueError('Note needs an author and concrete observation')
    anchor=spec.get('anchor')
    if not isinstance(anchor,dict) or anchor.get('kind') not in {'time','position'}:
        raise ValueError('Choose a time or position anchor')
    if anchor['kind']=='time':
        if set(anchor)!={'kind','clock','time'} or anchor['clock'] not in {c['id'] for c in record['data']['clocks']}:
            raise ValueError('Time note needs the actual clock')
        observation.finite(anchor['time'],'note time',0)
    else:
        if set(anchor)!={'kind','position'} or not record['data'].get('space'):raise ValueError('Position requires spatial evidence')
        observation.vector(anchor['position'],record['data']['space']['dimensions'],'note position')
    dependencies={**record['dependencies'],**snapshot_files(root,['.openaigame/observations/'+spec['observation']+'.json'])}
    value={**spec,'schema_version':1,'created_at':now(),'dependencies':dependencies,
           'observation_status_at_creation':record['status']}
    write_json(local(root,'.openaigame/review-notes/'+note_id+'.json'),value,create=True)
    return value


def media_path(root,oid,index):
    record=observation.read(root,oid)
    entries=record['data'].get('media',[])
    if type(index) is not int or not 0<=index<len(entries):raise ValueError('Invalid media index')
    row=entries[index]
    path=local(root,row['path'])
    if row['path'] not in record['dependencies'] or not path.is_file() or digest(path)!=record['dependencies'][row['path']]:
        raise ValueError('Evidence media changed or disappeared; recapture/register its actual version')
    if path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4','.webm','.wav','.mp3','.ogg'}:
        raise ValueError('Unsupported evidence media type')
    return path


def link_note(root,spec):
    """Link an actual versioned annotation to a scoped task issue, never approval."""
    if not isinstance(spec,dict) or set(spec)!={'note','task','revision','issue','stages'}:raise ValueError('Link requires note, task revision, issue id and affected stages')
    path='.openaigame/review-notes/'+identifier(spec['note'])+'.json'
    note=read_json(local(root,path));task=task_state.read(root,spec['task'])
    if task['revision']!=spec['revision']:raise ValueError('Task changed; refresh before linking')
    if changed_files(root,note['dependencies']):raise ValueError('Historical note must be re-observed against current dependencies before opening a current issue')
    if note['object'] not in {o['id'] for o in task['objects']}:raise ValueError('Task does not contain the observed object')
    if not isinstance(spec['stages'],list) or not spec['stages'] or any(type(s) is not int or not task['start_stage']<=s<=task['end_stage'] for s in spec['stages']):raise ValueError('Select affected stages inside this task')
    identifier(spec['issue'])
    import hashlib
    eid='note-'+hashlib.sha256((spec['note']+'\0'+spec['task']+'\0'+spec['issue']).encode()).hexdigest()[:32]
    ref='.openaigame/evidence/'+eid+'.json'
    if not local(root,ref).exists():
        record_evidence.register(root,{'id':eid,'source_type':'manual','description':note['text'],'observer':note['author'],
            'files':[path],'dependencies':list(note['dependencies']),'objects':[note['object']],'task':task_state.path_for(root,spec['task']).relative_to(root).as_posix(),
            'result':'observed','limitations':['Versioned annotation; no automated quality approval']})
    else:
        status=record_evidence.assess(root,ref)
        if status['status']!='current':raise ValueError('Existing linked note evidence changed; register a new actual observation')
    updated=task_state.update(root,spec['task'],spec['revision'],{'action':'issue','id':spec['issue'],'objects':[note['object']],
        'stages':spec['stages'],'state':'open','reason':note['text'],'evidence':[ref]})
    return {'task':updated,'evidence':ref,'note':path}

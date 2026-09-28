#!/usr/bin/env python3
"""Sync verified native consumer exports to the existing character/preview board."""
import argparse,json
from pathlib import Path
from record_io import local,read_json,write_json,digest,snapshot_files,project_lock,identifier
from content_roots import in_game

def sync(root,session_id):
    root=Path(root).resolve();identifier(session_id)
    folder=local(root,'runs/'+session_id);record=read_json(folder/'session.json');result=read_json(folder/'result.json')
    if record.get('status')!='completed' or result.get('success') is not True or result.get('request_id')!=session_id:raise ValueError('Completed actual native export session required')
    if digest(folder/'result.json')!=record.get('evidence_hashes',{}).get('result.json'):raise ValueError('Native result changed after session')
    native_root=Path(record['project']).resolve()
    if not native_root.is_relative_to(root):raise ValueError('Session belongs to another game project')
    rows=result.get('characters',[])
    if not rows:raise ValueError('Session has no actual exported character consumers')
    def relative(path):
        p=Path(path).resolve()
        if not p.is_relative_to(root) or not p.is_file():raise ValueError('Export dependency outside/missing in project')
        return p.relative_to(root).as_posix()
    def source(path):
        rel=relative(path);p=local(root,rel)
        if not p.is_relative_to(native_root):raise ValueError('Native source outside engine root')
        native_rel=p.relative_to(native_root).as_posix()
        if record.get('before',{}).get(native_rel)!=digest(p) or record.get('after',{}).get(native_rel)!=digest(p):raise ValueError('Native source changed since read-only export: '+rel)
        return rel
    characters=[];new_mappings={};deps=['runs/'+session_id+'/session.json','runs/'+session_id+'/result.json']
    # Actual consumer/availability source includes native scene and project code,
    # not only the mesh that happens to live beside the animations.
    for p,sha in record.get('after',{}).items():
        if p.endswith(('.umap','.cpp','.h','.ini','.uproject')):
            deps.append(source(str(native_root/p)))
    for row in rows:
        dependencies=[source(p) for p in row['dependencies']]
        model=source(row['model'])
        if not in_game(model,root):raise ValueError('Consumer model is outside configured game content')
        actions=[]
        for action in row['actions']:
            path=source(action['file'])
            if not in_game(path,root):raise ValueError('Consumer animation is outside game content')
            actions.append({'label':action['label'],'path':path,'basis':action['basis'],'asset':action['asset']})
        entries=[(model,row.get('preview'),row.get('preview_sha256'))]+[(source(a['file']),a.get('preview'),a.get('preview_sha256')) for a in row['actions']]
        for original,preview,expected in entries:
            if not preview:continue
            rel=relative(preview)
            if not rel.startswith('previews/engine/'+session_id+'/'):raise ValueError('Unexpected derived preview destination')
            if not expected or digest(local(root,rel))!=expected:raise ValueError('Exported preview missing frozen hash or changed after export; export again')
            new_mappings[original]={'path':rel,'sha256':digest(local(root,rel)),'source_sha256':digest(local(root,original)),
                'dependencies':snapshot_files(root,list(dict.fromkeys(dependencies+deps[:2]))),'material':'neutral',
                'note':'Actual native asset FBX export; browser preview excludes engine blending, attachments and runtime material behavior'}
        characters.append({'id':row['id'],'title':row['title'],'role':row['role'],'model':model,'actions':actions,
            'note':row['scope'],'consumer':row['consumer']['path'],'session':'runs/'+session_id+'/session.json',
            'dependencies':snapshot_files(root,list(dict.fromkeys(dependencies+deps)))})
    # Build both documents before writing; a cross-file interruption cannot make
    # stale bytes valid because all entries retain individual source hashes.
    with project_lock(root,'character-sync'):
        target=local(root,'.asset-browser/characters.json');mapping=local(root,'.asset-browser/previews.json')
        old=read_json(target) if target.exists() else {'version':1,'dependencies':{},'characters':[]}
        previews=read_json(mapping) if mapping.exists() else {'version':1,'assets':{}}
        if old.get('version')!=1 or previews.get('version')!=1:raise ValueError('Unsupported existing board manifest')
        ids={c['id'] for c in characters}
        old['characters']=[c for c in old['characters'] if c['id'] not in ids]+characters
        # Each new consumer has its own dependency set. Never refresh legacy
        # hashes for unrelated characters just because this character synced.
        previews['assets'].update(new_mappings)
        write_json(mapping,previews);write_json(target,old)
    return {'characters':[c['id'] for c in characters],'previews':len(new_mappings),'source':'actual native consumer export','quality':'not_approved_by_sync'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--session',required=True);a=p.parse_args()
    try:print(json.dumps(sync(a.project,a.session),ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())

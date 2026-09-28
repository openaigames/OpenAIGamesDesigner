#!/usr/bin/env python3
"""Explicit author-source/consumer links; inspect changes without copying authority."""
import argparse
import json
from pathlib import Path
from record_io import local,read_json,write_json,identifier,digest,now


def pointer(document,path):
    if not isinstance(path,str) or not path.startswith('/'):
        raise ValueError('JSON source requires an explicit RFC6901 pointer')
    value=document
    for token in path[1:].split('/'):
        if '~' in token.replace('~0','').replace('~1',''):raise ValueError('Invalid JSON pointer escape')
        key=token.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not key.isdigit() or str(int(key))!=key:raise ValueError('Array pointer requires a canonical index')
            value=value[int(key)]
        elif isinstance(value,dict):value=value[key]
        else:raise ValueError('Pointer passes through a scalar')
    return value


def inspect(root,spec):
    from validate_records import contract
    path=local(root,spec)
    data=read_json(path)
    errors=contract('project-links',data)
    if errors:raise ValueError('; '.join(errors))
    objects={identifier(o['id']):o for o in data['objects']}
    if len(objects)!=len(data['objects']):raise ValueError('Duplicate linked object')
    for obj in objects.values():
        for link in obj.get('links',[]):
            if not local(root,link['source']).is_file():raise ValueError('Object link source missing: '+link['source'])
    constraints=[]
    known=set()
    for definition in data['constraints']:
        cid=identifier(definition['id'])
        if cid in known:raise ValueError('Duplicate constraint id')
        known.add(cid)
        source=definition['source'];file=local(root,source['path'])
        if not file.is_file():raise ValueError('Author source missing: '+source['path'])
        row={**definition,'source_sha256':digest(file),'resolution':'file_version_only','current_value':None,
             'evidence_status':'not_linked'}
        if source['kind']=='json':
            row.update(current_value=pointer(read_json(file),source.get('pointer')),resolution='exact_json_pointer')
        elif source.get('pointer'):
            raise ValueError('Only JSON sources may declare a JSON pointer')
        if source.get('evidence'):
            import record_evidence
            row['evidence_status']=record_evidence.assess(root,source['evidence'])['status']
        for consumer in definition['consumers']:
            if consumer['object'] not in objects:raise ValueError('Constraint consumer object is undeclared')
            if not local(root,consumer['source']).is_file():raise ValueError('Consumer source missing: '+consumer['source'])
        constraints.append(row)
    return {'schema_version':1,'spec':spec,'spec_sha256':digest(path),'objects':data['objects'],'constraints':constraints}


def snapshot(root,spec,snapshot_id):
    value={**inspect(root,spec),'id':identifier(snapshot_id),'created_at':now()}
    write_json(local(root,'.openaigame/link-snapshots/'+snapshot_id+'.json'),value,create=True)
    return value


def impact(root,snapshot_id):
    previous=read_json(local(root,'.openaigame/link-snapshots/'+identifier(snapshot_id)+'.json'))
    current=inspect(root,previous['spec'])
    old={c['id']:c for c in previous['constraints']};new={c['id']:c for c in current['constraints']}
    affected=[]
    for cid in sorted(old.keys()|new.keys()):
        a,b=old.get(cid),new.get(cid)
        reason=None
        if not a:reason='constraint_added'
        elif not b:reason='constraint_removed'
        elif any(a.get(k)!=b.get(k) for k in ['domain','unit','source','consumers','description']):reason='contract_changed'
        elif a['resolution']=='exact_json_pointer' and b['current_value']!=a['current_value']:reason='author_value_changed'
        elif a['resolution']!='exact_json_pointer' and b['source_sha256']!=a['source_sha256']:reason='source_changed_requires_review'
        elif b['evidence_status']=='stale':reason='linked_evidence_stale'
        if reason:
            consumers=[]
            for consumer in (a or {}).get('consumers',[])+(b or {}).get('consumers',[]):
                if consumer not in consumers:consumers.append(consumer)
            affected.append({'constraint':cid,'reason':reason,'consumers':consumers,
                'before':a.get('current_value') if a else None,'after':b.get('current_value') if b else None,
                'scope':'declared consumers only; unlinked impacts remain unknown'})
    return {'snapshot':snapshot_id,'spec':current['spec'],'affected':affected,
            'unaffected':[cid for cid in new if cid not in {r['constraint'] for r in affected}],
            'automatic_revalidation':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',required=True,type=Path)
    actions=parser.add_subparsers(dest='action',required=True)
    for name in ('inspect','snapshot'):
        p=actions.add_parser(name);p.add_argument('--spec',required=True)
        if name=='snapshot':p.add_argument('--id',required=True)
    p=actions.add_parser('impact');p.add_argument('--id',required=True)
    args=parser.parse_args(argv)
    try:
        root=args.project.resolve()
        result=inspect(root,args.spec) if args.action=='inspect' else snapshot(root,args.spec,args.id) if args.action=='snapshot' else impact(root,args.id)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,KeyError,IndexError,TypeError) as error:
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':raise SystemExit(main())

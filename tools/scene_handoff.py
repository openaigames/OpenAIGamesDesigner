"""Create and verify explicit, relocatable project file snapshots.

Checks bytes and declared entry points. Native import/build/run remain separate
receiver evidence; this tool never executes received scripts.
"""
import argparse,json,re,shutil
from pathlib import Path,PurePosixPath
from static_scene import sha,fingerprint
from environment.handoff import build as build_environment_handoff

VERSION='0.1.0'
SCHEMA='oagd.scene-handoff/1'
MANIFEST='scene-handoff.json'

def path(root,name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.startswith('/') or any(p in ('','..','.') for p in name.split('/')):
        raise ValueError('Use normalized relative file paths')
    current=root
    for part in PurePosixPath(name).parts:
        current=current/part
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):
            raise ValueError('Linked files/directories are not portable')
    resolved=current.resolve()
    if not resolved.is_relative_to(root.resolve()):raise ValueError('Path escapes snapshot')
    return resolved

def spec_validate(spec):
    if set(spec)!={'id','files','engines','entrypoints','provenance'} or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',spec['id']):
        raise ValueError('Expected id, files, engines, entrypoints and provenance')
    files=spec['files']
    if not isinstance(files,list) or not files or any(not isinstance(n,str) for n in files) or len(files)!=len(set(n.casefold() for n in files)) or MANIFEST.casefold() in [n.casefold() for n in files]:
        raise ValueError('Nonempty distinct file inventory required')
    if not spec['engines'] or not set(spec['engines'])<= {'godot','unreal'} or any(not isinstance(v,str) or not v for v in spec['engines'].values()):raise ValueError('Declare engine versions')
    if not spec['entrypoints'] or not isinstance(spec['provenance'],list) or not spec['provenance']:raise ValueError('Declare entry points and provenance files')
    if any(v not in files for v in [*spec['entrypoints'].values(),*spec['provenance']]):raise ValueError('Declared entry point/provenance missing from inventory')

def create(project,spec,output):
    root,out=Path(project).resolve(),Path(output).resolve()
    if out.exists() or out.is_relative_to(root) or root.is_relative_to(out):raise ValueError('Use a new directory outside the source project')
    spec_validate(spec)
    files={}
    for name in spec['files']:
        p=path(root,name)
        if not p.is_file():raise ValueError('Missing declared file: '+name)
        files[name]=sha(p)
    if {'handoff-report.json','交接说明.txt'} & set(files):raise ValueError('Environment handoff output names are reserved')
    authority=spec['provenance'][0]
    plan={'schema':'environment-handoff/1','revision':spec['id'],'selection_source':authority,'selection_sha256':files[authority],
          'coordinate':'RH_Y_UP','unit':'m','target_engine':', '.join(k+' '+v for k,v in spec['engines'].items()),
          'files':[{'id':'file_'+str(i),'path':n,'sha256':h,'role':'provenance' if n in spec['provenance'] else 'project-input','transfer':'portable'} for i,(n,h) in enumerate(files.items())]}
    # Reuse the existing selection/provenance and glTF dependency packer.
    build_environment_handoff(plan,root,out)
    files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    manifest={'schema':SCHEMA,'version':VERSION,**{k:v for k,v in spec.items() if k!='files'},'files':files}
    manifest['snapshot_id']=fingerprint(manifest)
    # Completion is written last. Interrupted destinations remain diagnosable.
    (out/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return check(out)

def check(directory,pristine=False):
    root=Path(directory).resolve()
    data=json.loads((root/MANIFEST).read_text(encoding='utf8'))
    if data.get('schema')!=SCHEMA or fingerprint({k:v for k,v in data.items() if k!='snapshot_id'})!=data.get('snapshot_id'):raise ValueError('Invalid or changed handoff manifest')
    spec_validate({k:(list(data['files']) if k=='files' else data[k]) for k in ['id','files','engines','entrypoints','provenance']})
    for name,expected in data['files'].items():
        p=path(root,name)
        if not p.is_file() or sha(p)!=expected:raise ValueError('Missing/changed file: '+name)
    if pristine:
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        if actual!=set(data['files'])|{MANIFEST}:raise ValueError('Unexpected files in pristine snapshot')
    return {'ok':True,'snapshot_id':data['snapshot_id'],'files':len(data['files']),'engines':data['engines'],'scope':'Declared files and entry points verified; native execution and human acceptance are separate'}

def receive(snapshot,output):
    source=Path(snapshot).resolve();check(source,True)
    data=json.loads((source/MANIFEST).read_text(encoding='utf8'))
    out=Path(output).resolve()
    if out.exists() or out.is_relative_to(source) or source.is_relative_to(out):raise ValueError('Use a new receiver directory outside the snapshot')
    out.mkdir(parents=True)
    for name,digest in data['files'].items():
        target=path(out,name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path(source,name),target)
        if sha(target)!=digest:raise ValueError('Source changed while receiving')
    shutil.copy2(source/MANIFEST,out/MANIFEST)
    result=check(out,True)
    if result['snapshot_id']!=data['snapshot_id']:raise ValueError('Received identity differs')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('create');p.add_argument('--project',required=True);p.add_argument('--spec',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('check');p.add_argument('directory');p.add_argument('--pristine',action='store_true')
    p=sub.add_parser('receive');p.add_argument('snapshot');p.add_argument('--output',required=True)
    a=parser.parse_args()
    try:
        if a.command=='create':result=create(a.project,json.loads(Path(a.spec).read_text(encoding='utf8')),a.output)
        elif a.command=='check':result=check(a.directory,a.pristine)
        else:result=receive(a.snapshot,a.output)
        print(json.dumps(result,ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError) as exc:parser.exit(1,str(exc)+'\n')

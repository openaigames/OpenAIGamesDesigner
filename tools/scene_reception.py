"""Scaffold a six-group scene reception example from authorized frozen inputs.

This is a specific test layout, not an automatic general-purpose level designer.
Requires the fixture box/door and the declared Clockhill node subset.
"""
import argparse,json,shutil
from pathlib import Path
from static_scene import read_plan
from scene_handoff import path

def prepare(revisions,provenance,output):
    source,prov,out=map(lambda p:Path(p).resolve(),[revisions,provenance,output])
    runtime=Path(__file__).resolve().parents[1];template=runtime/'templates/static_scene/reception'
    if out.exists() or out.is_relative_to(source) or out.is_relative_to(prov) or source.is_relative_to(out) or prov.is_relative_to(out):raise ValueError('Use a new case outside the source/provenance directories')
    plans={k:read_plan(source/k) for k in ['box','door','clockhill']}
    if {n['id'] for n in plans['door']['nodes']}!={0,1,2,3,4,5,6} or not {1,3,25}<={n['id'] for n in plans['clockhill']['nodes']} or {n['id'] for n in plans['box']['nodes']}!={0}:raise ValueError('The reception example needs the documented box, door and building node contract')
    if not (prov/'SELECTION.md').is_file():raise ValueError('Supply authoritative provenance/SELECTION.md and referenced source records')
    shutil.copytree(template,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for aid,p in plans.items():
        for relative in ['plan.json',*p['files']]:
            target=path(out,'Godot/revisions/'+aid+'/'+relative);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path(source/aid,relative),target)
    for p in prov.rglob('*'):
        if p.is_file():
            relative=p.relative_to(prov).as_posix();origin=path(prov,relative);dest=path(out,'provenance/'+relative);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,dest)
    copies={**{'tools/'+n:'toolkit/tools/'+n for n in ['static_scene.py','scene_replacement.py']},
            **{'adapters/engines/static_scene/unreal/'+n:'toolkit/unreal/'+n for n in ['static_scene_import.py','scene_replacement_import.py']},
            **{'adapters/engines/static_scene/godot/'+n:'Godot/'+n for n in ['static_scene.gd','scene_replacement.gd']},
            'adapters/engines/static_scene/unreal/ScenePassage.h':'Unreal/Source/OAGDExamples/ScenePassage.h'}
    for a,b in copies.items():
        target=out/b;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(runtime/a,target)
    data=json.loads((out/'layout.json').read_text());assets={k:{'revision':'Godot/revisions/'+k,'plan_id':p['plan_id']} for k,p in plans.items()};data['assets']=assets;data['mapping']['assets']=assets
    for name,d in [('case.json',data),('Godot/case.json',data),('Unreal/Content/OAGDData/case.json',data),('mapping.json',data['mapping'])]:
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
    files=sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
    spec={'id':'E073Reception','files':files,'engines':{'godot':'4.7.2','unreal':'5.8.2'},'entrypoints':{'instructions':'RECEIVE.md','runner':'runner.py','godot':'Godot/project.godot','unreal':'Unreal/OAGDExamples.uproject'},'provenance':['provenance/SELECTION.md']}
    (out/'handoff-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')
    return {'ok':True,'case':str(out),'files':len(files),'handoff_spec':'handoff-spec.json','native_validation':'not_run'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['revisions','provenance','output']:p.add_argument('--'+key,required=True)
    a=p.parse_args()
    try:print(json.dumps(prepare(a.revisions,a.provenance,a.output)))
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(1,str(exc)+'\n')

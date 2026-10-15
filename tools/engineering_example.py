#!/usr/bin/env python3
"""Create a project-owned integration example from an adopted motion revision."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import motion_playback
import static_assets
from adapters.processing.procedural_worker import write as generate
from templates.runtime_feedback.generate_audio import generate as audio

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'


def create(project, engine, revision, bindings, ue_root=None):
    project = Path(project).resolve()
    definitions = json.loads(Path(bindings).read_text(encoding='utf-8-sig'))
    motion_playback.checked_bindings(Path(revision).resolve(), definitions)
    if not definitions.get('constraints', {}).get('feet') or not definitions.get('constraints', {}).get('grip'):
        raise ValueError('Combined example requires the adopted feet + grip profile')
    if any(definitions.get(k) for k in ('root_motion', 'layers', 'turning', 'locomotion')):
        raise ValueError('This combined consumer uses controller movement and contacts; other playback modes have separate examples')
    motion_playback.create(project, engine, revision, bindings, ue_root)
    shutil.copytree(ROOT/'templates/engineering_example'/engine, project, dirs_exist_ok=True)
    content = project if engine == 'godot' else project/'Content'
    data = content if engine == 'godot' else content/'OAGDData'
    data.mkdir(parents=True,exist_ok=True)
    identity = 'engineering-' + uuid.uuid4().hex
    profile = json.loads((ROOT/'templates/runtime_input/input-profile.json').read_text())
    profile['id'] = identity
    profile['actions']['act']['keys'] = ['E', 'PadSouth']
    for name, key in [('cancel', 'Q'), ('save', 'K'), ('load', 'L'), ('restart', 'R'), ('scene', 'Tab')]:
        profile['actions'][name] = {'context':'game', 'keys':[key], 'rebindable':True}
    (data/'input-profile.json').write_text(json.dumps(profile, indent=2))
    (data/'project-config.json').write_text(json.dumps({'schema':1, 'id':identity, 'version':VERSION, 'start_room':'a', 'save_version':1}, indent=2))
    shutil.copy2(ROOT/'templates/runtime_feedback/feedback-profile.json', data/'feedback-profile.json')
    audio(data/'audio')
    spec = json.loads((ROOT/'templates/procedural/scene.json').read_text())
    spec['rooms'] = spec['rooms'][:2]; spec['paths'] = spec['paths'][:1]; spec['queries'] = spec['queries'][:1]
    # Keep the established portal scale and source coordinates; the player starts in curve_a.
    generate(spec, content/'generated/scene')
    inputs = content/'generated/static-input'; inputs.mkdir(parents=True)
    shutil.copy2(ROOT/'templates/runtime_static/assets/portal.glb', inputs/'portal.glb')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {'schema':'oagd.static-assets/1','scene_sha256':digest(content/'generated/scene/scene.json'),
                'assets':[{'id':'portal','source':'generated/static-input/portal.glb','sha256':digest(inputs/'portal.glb')}],
                'replacements':[{'id':'curve_a_portal','targets':['curve_a__east__before_curve_a_door','curve_a__east__before_end','curve_a__lintel_curve_a_door'],
                                 'asset':'portal','position':[-5,0,0],'yaw_degrees':0,'scale':1,'collision':'source_mesh'}]}
    (inputs/'manifest.json').write_text(json.dumps(manifest, indent=2))
    static_assets.prepare(content,'generated/scene/scene.json','generated/static-input/manifest.json',content/'generated/static')
    if engine == 'godot':
        for name in ('pulse.gd','pulse.tscn'): shutil.copy2(ROOT/'templates/runtime_feedback/godot'/name,project/name)
        shutil.copy2(ROOT/'templates/runtime_static/godot/build_assets.gd',project/'build_assets.gd')
        path = project/'project.godot'; path.write_text(path.read_text().replace('OAGD Playable Motion',identity))
        with (project/'project.godot').open('a') as f: f.write('\n[physics]\ncommon/physics_ticks_per_second=60\n')
        path=project/'export_presets.cfg'
        path.write_text(path.read_text().replace('include_filter="bindings.json"','include_filter="bindings.json,input-profile.json,project-config.json,feedback-profile.json,generated/**/*.json"'))
    else:
        for name in ('static_replacement.py','static_meshes.py','mesh_contract.py'):
            shutil.copy2(ROOT/'adapters/engines/unreal'/name,project/name)
        path = project/'Config/DefaultEngine.ini'
        path.write_text(path.read_text().replace('/Script/MotionPlay.ConstraintsGame','/Script/MotionPlay.CombinedGame')+'''
[/Script/NavigationSystem.RecastNavMesh]
RuntimeGeneration=Dynamic
AgentRadius=50.0
AgentHeight=190.0
CellSize=10.0
CellHeight=5.0
bForceRebuildOnLoad=True
[/Script/NavigationSystem.NavigationSystemV1]
bAutoCreateNavigationData=True

[SystemSettings]
; This small example prioritizes visible short-lived feedback over PSO proxy delay.
; PSO creation can still stall; this is not a performance fix or a shared plugin default.
r.PSOPrecache.ProxyCreationStrategy=0
''')
        with (project/'Config/DefaultGame.ini').open('a') as f: f.write('''
[/Script/UnrealEd.ProjectPackagingSettings]
+MapsToCook=(FilePath="/Game/Combined/Room_a")
+MapsToCook=(FilePath="/Game/Combined/Room_b")
+DirectoriesToAlwaysCook=(Path="/Game/Feedback")
+DirectoriesToAlwaysCook=(Path="/Game/Scene")
+DirectoriesToAlwaysCook=(Path="/Game/Static")
+DirectoriesToAlwaysStageAsNonUFS=(Path="OAGDData")
+DirectoriesToAlwaysStageAsNonUFS=(Path="generated")
''')
    for name in ('README.md','SUPPORT.md','TRIAL_REPORT.md','KNOWN_ISSUES.md'):
        shutil.copy2(ROOT/'templates/engineering_example'/name,project/name)
        localized = name[:-3] + '.zh-CN.md'
        shutil.copy2(ROOT/'templates/engineering_example'/localized,project/localized)
    # Creation pin captures this consumer, not the replaced playback example scripts.
    pin = json.loads((project/motion_playback.LOCK).read_text())
    pin['files'] = {p.relative_to(project).as_posix():digest(p) for p in project.rglob('*') if p.is_file() and p != project/motion_playback.LOCK}
    pin['consumer'] = 'engineering-example/'+VERSION
    (project/motion_playback.LOCK).write_text(json.dumps(pin,indent=2))
    return {'project':str(project),'engine':engine,'identity':identity,'version':VERSION}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--engine',choices=['godot','unreal'],required=True)
    p.add_argument('--revision',type=Path,required=True);p.add_argument('--bindings',type=Path,required=True);p.add_argument('--ue-root',type=Path)
    a=p.parse_args()
    try: print(json.dumps(create(a.project,a.engine,a.revision,a.bindings,a.ue_root),indent=2))
    except (ValueError,OSError,KeyError) as e:p.exit(1,str(e)+'\n')

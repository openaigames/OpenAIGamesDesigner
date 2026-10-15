#!/usr/bin/env python3
"""Opt-in native runtime components. Projects own pinned copies, never symlinks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import re
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adapters.processing.procedural_worker import write as generate

VERSION='0.9.0'
LOCK='.openaigame/runtime-components.json'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def engine_version(engine, ue_root=None):
    if engine=='unreal':
        if not ue_root: raise ValueError('Unreal requires --ue-root for an explicit UE 5.8 installation')
        version=json.loads((Path(ue_root)/'Engine/Build/Build.version').read_text(encoding='utf-8-sig'))
        if (version.get('MajorVersion'),version.get('MinorVersion'))!=(5,8): raise ValueError('This component release targets UE 5.8 only')
        return '.'.join(str(version[k]) for k in ('MajorVersion','MinorVersion','PatchVersion'))
    return 'Godot 4.x; validated environment is recorded separately'


def safe(root, relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root) or path==root: raise ValueError('Component path escapes project')
    return path


def status(project):
    root=Path(project).resolve()
    data=json.loads((root/LOCK).read_text(encoding='utf-8'))
    missing=[]; changed=[]
    for relative,expected in data['files'].items():
        path=safe(root,relative)
        if not path.is_file(): missing.append(relative)
        elif digest(path)!=expected: changed.append(relative)
    return {**data,'missing':missing,'changed':changed}


def install(project, engine, ue_root=None):
    root=Path(project).resolve()
    if not root.is_dir(): raise ValueError('Project must exist')
    target_version=engine_version(engine,ue_root)
    if engine=='godot' and not (root/'project.godot').is_file(): raise ValueError('Not a Godot project')
    if engine=='unreal':
        projects=list(root.glob('*.uproject'))
        if len(projects)!=1: raise ValueError('Expected one .uproject')
        association=json.loads(projects[0].read_text(encoding='utf-8-sig')).get('EngineAssociation','')
        numeric=re.match(r'^(\d+)\.(\d+)(?:\.\d+)?$',str(association))
        if numeric and tuple(map(int,numeric.group(1,2)))!=(5,8):
            raise ValueError('Project EngineAssociation differs from UE 5.8; convert the project explicitly first')
    if (root/LOCK).exists():
        current=status(root)
        if current['engine']!=engine or current['component_version']!=VERSION or current['missing'] or current['changed']:
            raise ValueError('Pinned component version or local edits differ; preserve changes and migrate explicitly')
        return current
    source=ROOT/'adapters/engines/runtime_components'/engine
    destination='addons/oagd' if engine=='godot' else 'Plugins'
    files={}
    for origin in source.rglob('*'):
        if not origin.is_file() or '__pycache__' in origin.parts: continue
        relative=(Path(destination)/origin.relative_to(source)).as_posix()
        target=safe(root,relative)
        if target.exists(): raise ValueError('Refusing to overwrite an unowned project file: '+relative)
        files[relative]=digest(origin)
    data={'schema_version':1,'engine':engine,'target_engine':target_version,'component_version':VERSION,
          'files':files,'ownership':'project-local copy; toolkit updates do not modify this project'}
    # Stage all source reads first, then exclusively create project files. Catchable
    # I/O failures remove only this attempt's new files, allowing an ordinary retry.
    stage=root/('.oagd-install-'+uuid.uuid4().hex);stage.mkdir()
    created=[]
    try:
        for index,relative in enumerate(files):
            shutil.copy2(source/Path(relative).relative_to(destination),stage/str(index))
            if digest(stage/str(index))!=files[relative]: raise OSError('Component changed during staging')
        (stage/'lock').write_text(json.dumps(data,indent=2),encoding='utf-8')
        for index,relative in enumerate([*files,LOCK]):
            target=safe(root,relative);target.parent.mkdir(parents=True,exist_ok=True)
            staged=stage/(str(index) if relative!=LOCK else 'lock')
            with target.open('xb') as out:
                created.append(target)
                with staged.open('rb') as content: shutil.copyfileobj(content,out)
    except BaseException:
        for path in reversed(created): path.unlink()
        raise
    finally:
        shutil.rmtree(stage)
    return data


def create(project,engine,scenario,ue_root=None,scene_spec=None):
    root=Path(project).resolve()
    if scenario not in ('training','puzzle','input','state','feedback','interaction','navigation','scene','static'): raise ValueError('Unknown example scenario')
    engine_version(engine,ue_root)
    if scene_spec is not None and scenario!='scene': raise ValueError('--scene-spec requires --scenario scene; static is a fixed calibration example, use static_assets.py for custom replacement plans')
    if scenario in ('scene','static'):
        from adapters.processing.procedural_worker import generate as inspect_scene
        scene_spec=json.loads(Path(scene_spec or ROOT/'templates/procedural/scene.json').read_text(encoding='utf-8-sig'))
        if scene_spec.get('kind')!='scene': raise ValueError('Scene example requires a kind: scene specification')
        preview=inspect_scene(scene_spec)
        if not preview['navigation']['queries']: raise ValueError('Scene example requires at least one query')
    if root.exists(): raise ValueError('New example requires a new directory')
    root.mkdir(parents=True)
    template=ROOT/'templates/runtime_examples'/engine
    shutil.copytree(template,root,dirs_exist_ok=True)
    if scenario=='input':
        shutil.copytree(ROOT/'templates/runtime_input'/engine,root,dirs_exist_ok=True)
    if scenario in ('state','feedback'):
        shutil.copytree(ROOT/'templates/runtime_state'/engine,root,dirs_exist_ok=True)
    if scenario=='feedback':
        shutil.copytree(ROOT/'templates/runtime_feedback'/engine,root,dirs_exist_ok=True)
    if scenario=='interaction':
        shutil.copytree(ROOT/'templates/runtime_interaction'/engine,root,dirs_exist_ok=True)
    if scenario=='navigation':
        shutil.copytree(ROOT/'templates/runtime_navigation'/engine,root,dirs_exist_ok=True)
    if scenario in ('scene','static'):
        shutil.copytree(ROOT/'templates/runtime_scene'/engine,root,dirs_exist_ok=True)
    if scenario=='static':
        shutil.copytree(ROOT/'templates/runtime_static'/engine,root,dirs_exist_ok=True)
    if engine=='godot':
        (root/'project.godot').write_text('''config_version=5
[application]
config/name="OAGD Native Example"
run/main_scene="res://main.tscn"
[display]
window/size/viewport_width=1152
window/size/viewport_height=720
[rendering]
renderer/rendering_method="gl_compatibility"
environment/defaults/default_clear_color=Color(0.08,0.13,0.2,1)
''',encoding='utf-8')
        (root/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n[node name="Example" type="Node3D"]\nscript = ExtResource("1")\n',encoding='utf-8')
        content=root
    else:
        (root/'OAGDExamples.uproject').write_text(json.dumps({'FileVersion':3,'EngineAssociation':'5.8',
            'Modules':[{'Name':'OAGDExamples','Type':'Runtime','LoadingPhase':'Default'}],
            'Plugins':[{'Name':'OAGDCore','Enabled':True},{'Name':'PythonScriptPlugin','Enabled':True},{'Name':'EditorScriptingUtilities','Enabled':True}]},indent=2),encoding='utf-8')
        config=root/'Config';config.mkdir(exist_ok=True)
        (config/'DefaultEngine.ini').write_text('''[/Script/EngineSettings.GameMapsSettings]
GlobalDefaultGameMode=/Script/OAGDExamples.ExampleGame
GameDefaultMap=/Game/Example
EditorStartupMap=/Game/Example
[/Script/Engine.RendererSettings]
r.DynamicGlobalIlluminationMethod=0
r.ReflectionMethod=0
r.Shadow.Virtual.Enable=0
[/Script/Engine.UserInterfaceSettings]
bAllowHighDPIInGameMode=True
''',encoding='utf-8')
        (config/'DefaultInput.ini').write_text('''[/Script/Engine.InputSettings]
+AxisMappings=(AxisName="Forward",Scale=1.000000,Key=W)
+AxisMappings=(AxisName="Forward",Scale=-1.000000,Key=S)
+AxisMappings=(AxisName="Right",Scale=1.000000,Key=D)
+AxisMappings=(AxisName="Right",Scale=-1.000000,Key=A)
+AxisMappings=(AxisName="LookX",Scale=1.000000,Key=MouseX)
+AxisMappings=(AxisName="LookY",Scale=1.000000,Key=MouseY)
bCaptureMouseOnLaunch=False
''',encoding='utf-8')
        (config/'DefaultGame.ini').write_text('''[/Script/UnrealEd.ProjectPackagingSettings]
+DirectoriesToAlwaysStageAsNonUFS=(Path="generated")
+DirectoriesToAlwaysStageAsNonUFS=(Path="OAGDData")
''',encoding='utf-8')
        content=root/'Content';content.mkdir(exist_ok=True)
    scenario_path=content/'scenario.json' if engine=='godot' else content/'OAGDData/scenario.json'
    scenario_path.parent.mkdir(parents=True,exist_ok=True)
    scenario_path.write_text(json.dumps({'scenario':scenario}),encoding='utf-8')
    if scenario in ('input','state','feedback','interaction','navigation','scene','static'):
        profile=root/'input-profile.json' if engine=='godot' else content/'OAGDData/input-profile.json'
        input_id=scenario+'-example-'+uuid.uuid4().hex
        input_data=json.loads((ROOT/'templates/runtime_input/input-profile.json').read_text(encoding='utf-8'))
        input_data['id']=input_id
        profile.write_text(json.dumps(input_data,indent=2),encoding='utf-8')
        if engine=='godot':
            settings=root/'project.godot'
            settings.write_text(settings.read_text(encoding='utf-8').replace('OAGD Native Example',input_id),encoding='utf-8')
    if scenario in ('state','feedback') and engine=='unreal':
        with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:
            out.write('+MapsToCook=(FilePath="/Game/Example")\n+MapsToCook=(FilePath="/Game/Room_a")\n+MapsToCook=(FilePath="/Game/Room_b")\n+MapsToCook=(FilePath="/Game/InvalidRoom")\n')
    if scenario=='feedback':
        from templates.runtime_feedback.generate_audio import generate as generate_audio
        audio_root=root/'audio' if engine=='godot' else content/'OAGDData/audio'
        generate_audio(audio_root)
        config_path=root/'feedback-profile.json' if engine=='godot' else content/'OAGDData/feedback-profile.json'
        shutil.copy2(ROOT/'templates/runtime_feedback/feedback-profile.json',config_path)
        if engine=='godot':
            preset=root/'export_presets.cfg'
            preset.write_text(preset.read_text(encoding='utf-8').replace('input-profile.json,scenario.json','input-profile.json,scenario.json,feedback-profile.json'),encoding='utf-8')
        else:
            with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:
                out.write('+DirectoriesToAlwaysCook=(Path="/Game/Feedback")\n')
    if scenario=='interaction':
        config_path=root/'interaction-profile.json' if engine=='godot' else content/'OAGDData/interaction-profile.json'
        shutil.copy2(ROOT/'templates/runtime_interaction/interaction-profile.json',config_path)
        if engine=='godot':
            preset=root/'export_presets.cfg'
            preset.write_text(preset.read_text(encoding='utf-8').replace('input-profile.json,scenario.json','input-profile.json,scenario.json,interaction-profile.json'),encoding='utf-8')
        else:
            with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:
                out.write('+MapsToCook=(FilePath="/Game/Example")\n+DirectoriesToAlwaysCook=(Path="/Game/Interaction")\n')
    if scenario=='navigation':
        config_path=root/'navigation-profile.json' if engine=='godot' else content/'OAGDData/navigation-profile.json'
        shutil.copy2(ROOT/'templates/runtime_navigation/navigation-profile.json',config_path)
        if engine=='godot':
            preset=root/'export_presets.cfg'
            preset.write_text(preset.read_text(encoding='utf-8').replace('input-profile.json,scenario.json','input-profile.json,scenario.json,navigation-profile.json'),encoding='utf-8')
        else:
            with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:
                out.write('+MapsToCook=(FilePath="/Game/Example")\n+DirectoriesToAlwaysCook=(Path="/Game/Navigation")\n')
            with (root/'Config/DefaultEngine.ini').open('a',encoding='utf-8') as out:
                out.write('[/Script/NavigationSystem.RecastNavMesh]\nRuntimeGeneration=Dynamic\nAgentRadius=40.0\nAgentHeight=180.0\nCellHeight=10.0\nbForceRebuildOnLoad=True\n[/Script/NavigationSystem.NavigationSystemV1]\nbAutoCreateNavigationData=True\n')
    if scenario in ('scene','static'):
        scene=generate(scene_spec,content/'generated/scene')
        if engine=='godot':
            preset=root/'export_presets.cfg'
            preset.write_text(preset.read_text(encoding='utf-8').replace('input-profile.json,scenario.json','input-profile.json,scenario.json,generated/scene/*.json'),encoding='utf-8')
        else:
            agent=scene['navigation']['agent']
            with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:
                out.write('+MapsToCook=(FilePath="/Game/Example")\n+DirectoriesToAlwaysCook=(Path="/Game/Scene")\n')
            with (root/'Config/DefaultEngine.ini').open('a',encoding='utf-8') as out:
                out.write('[/Script/NavigationSystem.RecastNavMesh]\nRuntimeGeneration=Dynamic\nAgentRadius='+str(agent['navigation_radius_m']*100)+'\nAgentHeight='+str(agent['navigation_height_m']*100)+'\nAgentMaxSlope='+str(agent['max_slope_degrees'])+'\nAgentMaxStepHeight='+str(agent['max_step_m']*100)+'\nCellSize=10.0\nCellHeight=10.0\nbForceRebuildOnLoad=True\n[/Script/NavigationSystem.NavigationSystemV1]\nbAutoCreateNavigationData=True\n')
                out.write('!SupportedAgents=ClearArray\n+SupportedAgents=(Name="SceneAgent",AgentRadius='+str(agent['navigation_radius_m']*100)+',AgentHeight='+str(agent['navigation_height_m']*100)+',AgentStepHeight='+str(agent['max_step_m']*100)+',NavDataClass="/Script/NavigationSystem.RecastNavMesh")\n[/Script/NavigationSystem.RecastNavMesh]\n')
                for resolution in range(3):out.write('NavMeshResolutionParams['+str(resolution)+']=(CellSize=10.0,CellHeight=5.0,AgentMaxStepHeight='+str(agent['max_step_m']*100)+')\n')
    for name in (() if scenario in ('input','state','feedback','interaction','navigation','scene','static') else ('parts','terrain')):
        spec=json.loads((ROOT/'templates/procedural'/f'{name}.json').read_text())
        generate(spec,content/'generated'/name)
    if scenario=='static':
        from templates.runtime_static.setup import setup
        setup(root,content,engine,ROOT)
        if engine=='godot':
            preset=root/'export_presets.cfg';preset.write_text(preset.read_text(encoding='utf-8').replace('generated/scene/*.json','generated/scene/*.json,generated/static/*.json'),encoding='utf-8')
        else:
            with (root/'Config/DefaultGame.ini').open('a',encoding='utf-8') as out:out.write('+DirectoriesToAlwaysCook=(Path="/Game/Static")\n')
    data=install(root,engine,ue_root)
    (root/'README.md').write_text(f'''# OAGD {scenario} validation project

Project-owned game rules are in {'main.gd' if engine=='godot' else 'Source/OAGDExamples/ExampleGame.cpp'}.
Optional components are copied into this project. See {LOCK} for installation details. Copying or editing this game never changes another game.

WASD move, Space jump, E attack/interact, R restart, hold RMB to orbit.
Training: approach the yellow target and hit it three times. Puzzle: collect the key,
open the door, walk to the exit. Falling off the ground loses; R retries.
These are greybox engineering cases, not finished games or animation-quality demos.

Godot: open project.godot; use --headless --path PROJECT -- --self-test for automated physics checks.
UE 5.8: build OAGDExamplesEditor, run the create_map.py editor script once, then open Example.
Use UnrealEditor.exe PROJECT.uproject /Game/Example -game -OAGDSelfTest -unattended -windowed -ResX=1152 -ResY=720 for automated checks.
UE reports to Saved/validation.json; Godot to validation.json. Inspect failures and process logs.
''',encoding='utf-8')
    if scenario=='input':
        (root/'README.md').write_text('''# input and pause example

Project-owned UI and rules: main.gd (Godot) or Source/OAGDExamples/ExampleGame.cpp (UE).
Shared input components are pinned project copies. No animation plugin is required.
Start/resume, move with WASD or left stick; Space/South increments the action counter.
Escape/Start opens the menu. Arrows/D-pad navigate; Enter/South confirms.
Select a binding to capture a new key/button; Escape cancels. Conflicts are rejected.
Restore defaults and preferences affect only this example's input profile.
Native self-test: Godot -- --self-test --report=ABSOLUTE_JSON;
UE -OAGDSelfTest -InputReport=ABSOLUTE_JSON after building and running create_map.py.
Reports distinguish simulated native events from human or physical-device testing.
See runtime_components/INPUT.md in the toolkit for configuration and integration.
''',encoding='utf-8')
    if scenario=='state':
        (root/'README.md').write_text('''# local state example

Project-owned state, UI and tests: main.gd or Source/OAGDExamples/ExampleGame.cpp.
WASD moves; Space toggles the room door; Escape opens the menu. Save/continue slot 1,
set/respawn checkpoint, switch native room A/B, and cycle FPS/camera settings.
Godot: open project.godot. UE 5.8: build OAGDExamplesEditor, execute create_map.py,
open /Game/Example. Cook includes /Game/Room_a and /Game/Room_b.
Use runtime_validation.py for fresh isolated exercise + separate-process resume.
Manual saves: Godot user://state; UE Saved/OAGDState/<input-profile-id>.
Keep the generated identity stable when distributing updates to this SAME game.
Each new example has a different identity. No animation plugin is required.
See runtime_components/STATE.md for contract, failure recovery and limitations.
''',encoding='utf-8')
    if scenario=='feedback':
        (root/'README.md').write_text('# general feedback example\n\nWASD move, Space commits door toggle and its feedback. Esc opens menu.\nAction and zone controls are in the menu; entering/leaving the zone also follows actual player position.\nGodot: import project before running; UE 5.8: build editor, execute create_map.py to import WAV and save maps/material.\nNative cues are generated from an original calibration recipe, not final game audio or VFX.\nShared component owns instances; project owns event mapping and assets. No animation plugin required.\nSee runtime_components/FEEDBACK.md for limits and lifecycle integration.\n',encoding='utf-8')
    if scenario=='interaction':
        (root/'README.md').write_text('# interaction example\n\nWASD moves and faces; hold Space / gamepad South to interact, release to cancel. Esc opens a focused pause menu.\nSelect Face key / Face door to set aim without moving. Pick up the key then hold to open the door.\nThe game owns conditions and commits; generic components own selection, checks, requests and cancellation.\nGodot: open project.godot. UE 5.8: build editor then run create_map.py before opening /Game/Example.\nUse runtime_validation.py --visual for software input and native consumer tests. This is not human playtesting.\nSee runtime_components/INTERACTION.md. Each project owns a pinned component and configuration copy.\n',encoding='utf-8')
    if scenario=='navigation':
        (root/'README.md').write_text('# navigation example\n\nWASD moves the yellow target. Space starts the blue NPC patrol; Esc pauses. Buttons toggle a physics blocker or reset the NPC.\nGodot bakes static geometry on startup. UE 5.8: compile editor, execute create_map.py, then open /Game/Example; runtime native navigation builds from saved geometry and bounds.\nProject-owned behavior and patrol_points are editable independently of navigation components. No animation plugin required.\nSee runtime_components/NAVIGATION.md for requests, steering adapter, limits and evidence.\n',encoding='utf-8')
    if scenario in ('scene','static'):
        (root/'README.md').write_text('# scene traversal example\n\nGenerated rooms, ports and sampled cubic paths use generated/scene/spec.json.\nChoose a route, then Run. Each project owns its spec and pinned components.\nThe inspector reports actual native navigation and motor results for the configured capsule.\nUE 5.8: build editor, run create_map.py to persist generated collision and bounds; rebuild in a new project after spec changes.\nSee runtime_components/SCENE.md. These are engineering grayboxes, not human playtest acceptance.\n',encoding='utf-8')
    if scenario=='static':
        (root/'README.md').write_text('# static replacement example\n\nRead runtime_components/STATIC_ASSETS.md in the toolkit. Godot: import the project, execute build_assets.gd once, then run main.tscn. UE 5.8: build editor, execute create_map.py once, then run /Game/Example.\nProject owns source GLB, frozen mapping, native resources and original grayboxes. Collision policy is explicit. Existing destinations are not overwritten.\nDefault native validation has 64 checks, plus editor preparation and rollback checks. These are engineering cases, not final art or human playtest acceptance.\n',encoding='utf-8')
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('create','install','status'))
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--engine',choices=('godot','unreal'))
    parser.add_argument('--scenario',choices=('training','puzzle','input','state','feedback','interaction','navigation','scene','static'),default='training')
    parser.add_argument('--ue-root',type=Path)
    parser.add_argument('--scene-spec',type=Path,help='Project-owned scene specification for --scenario scene')
    args=parser.parse_args()
    try:
        if args.action=='status': result=status(args.project)
        elif not args.engine: raise ValueError('--engine is required')
        elif args.action=='install': result=install(args.project,args.engine,args.ue_root)
        else: result=create(args.project,args.engine,args.scenario,args.ue_root,args.scene_spec)
        print(json.dumps(result,indent=2))
        return int(bool(result.get('missing') or result.get('changed')))
    except (ValueError,OSError,KeyError) as error:
        print(json.dumps({'error':str(error)}));return 1

if __name__=='__main__': raise SystemExit(main())

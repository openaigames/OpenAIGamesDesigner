#!/usr/bin/env python3
"""Create an isolated playable motion example from a verified motion revision.
Projects receive pinned copies; existing projects and source animations are never overwritten.
"""
import argparse, json, shutil, math, hashlib, os, re, uuid
from pathlib import Path
import motion_workflow as motion
import runtime_components
import motion_root
import motion_constraints
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.5.0'
LOCK='.openaigame/motion-playback.json'
OBSERVATION_ROLES=('dst_root','dst_foot_L','dst_foot_R','dst_hand_R','dst_upperarm_R','dst_forearm_R','dst_spine','dst_head','dst_upperarm_L','dst_forearm_L','dst_hand_L')

def observation_bones(definitions):
    bones=definitions.get('observation_bones',{name:name for name in OBSERVATION_ROLES})
    if not isinstance(bones,dict) or set(bones)!=set(OBSERVATION_ROLES):
        raise ValueError('Observation mapping requires every example role explicitly')
    if any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+',n) for n in bones.values()):
        raise ValueError('Observation bone names must be safe nonempty names')
    if len({n.lower() for n in bones.values()})!=len(bones):
        raise ValueError('Observation roles must refer to distinct native bones')
    return bones

def example_settings(definitions):
    bones=observation_bones(definitions)
    motion_root.settings(definitions)
    motion_constraints.settings(definitions)
    speeds=definitions.get('movement_speeds_mps',{'walk':1.0,'run':2.5})
    if not isinstance(speeds,dict) or set(speeds)!={'walk','run'}:raise ValueError('Explicit walk/run speeds required')
    for k,v in speeds.items():motion.number(v,k+' speed',.01,20)
    settings=['WalkSpeedMps='+str(speeds['walk']),'RunSpeedMps='+str(speeds['run'])]
    locomotion=locomotion_settings(definitions)
    settings+=['LocomotionEnabled='+str(bool(locomotion)).lower()]
    turning=turning_settings(definitions)
    settings+=['TurningEnabled='+str(bool(turning)).lower()]
    settings+=['LayersEnabled='+str(bool(layer_settings(definitions))).lower()]
    if locomotion:
        settings += [key+'='+str(locomotion[field]) for key,field in
                     [('AccelerationMps2','acceleration_mps2'),('DecelerationMps2','deceleration_mps2'),('TurnSpeedDegS','turn_speed_deg_s')]]
    extra=definitions.get('turn_observation_bones',{})
    if turning and (not isinstance(extra,dict) or set(extra)!={'dst_hips','dst_thigh_L','dst_thigh_R','dst_shin_L','dst_shin_R'}):
        raise ValueError('Turn review requires explicit hips and both leg chains')
    if any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+',v) for v in extra.values()):raise ValueError('Unsafe turn observation bone')
    return '\n'.join(settings+['+ObservedBones='+k+'='+v for k,v in {**bones,**extra}.items()])+'\n'

def turning_settings(definitions):
    row=definitions.get('turning')
    if row is None:return None
    if not definitions.get('locomotion') or row!={'mode':'step_turn_v1','trigger_deg':30,'settle_s':.2,'recover_s':.2}:
        raise ValueError('Turning requires the explicit step_turn_v1 policy')
    clips={c['id']:c for c in definitions['clips']}
    for side in ('l','r'):
        for angle in (45,90,180):
            c=clips.get(f'turn_{side}_{angle}',{})
            if c.get('loop') is not False or c.get('markers') or abs(c.get('duration_s',0)-(.4+angle/45*.6))>1e-6:
                raise ValueError('Missing matching non-looping step turn assets')
    return row

def locomotion_settings(definitions):
    """Opt-in project policy; old bindings keep their discrete graph unchanged."""
    row=definitions.get('locomotion')
    if row is None:return None
    fields={'mode','acceleration_mps2','deceleration_mps2','turn_speed_deg_s','transition_s','contact_phase'}
    if not isinstance(row,dict) or set(row)!=fields or row['mode']!='speed_phase':
        raise ValueError('Locomotion requires explicit speed_phase policy and all settings')
    for key,low,high in [('acceleration_mps2',.1,30),('deceleration_mps2',.1,30),('turn_speed_deg_s',30,720),('transition_s',.05,.5)]:
        motion.number(row[key],key,low,high)
    speeds=definitions.get('movement_speeds_mps',{'walk':1.,'run':2.5})
    if not .01<=speeds['walk']<speeds['run']<=20:raise ValueError('Locomotion requires 0 < walk speed < run speed')
    phases=row['contact_phase']
    if not isinstance(phases,dict) or set(phases)!={'L','R'}:raise ValueError('Explicit shared L/R contact phases required')
    for side,window in phases.items():
        if not isinstance(window,list) or len(window)!=2:raise ValueError('Contact phase requires [start,end]')
        for v in window:motion.number(v,side+' contact phase',0,1)
        if not 0<window[0]<window[1]<1:raise ValueError('Interior ordered contact phases required')
    if max(phases['L'][0],phases['R'][0])<min(phases['L'][1],phases['R'][1]):raise ValueError('L/R stance interiors must not overlap')
    clips={c['id']:c for c in definitions.get('clips',[])}
    if 'locomotion' in clips:raise ValueError('locomotion is reserved for the generated graph')
    for name in ('idle','walk','run'):
        c=clips.get(name,{})
        if c.get('loop') is not True or c.get('markers') or not math.isfinite(c.get('duration_s',0)) or c.get('duration_s',0)<=0:
            raise ValueError('Locomotion requires looping idle/walk/run without markers')
    return dict(row)

def check_locomotion_phases(definitions,spec):
    row=locomotion_settings(definitions)
    if not row:return
    bindings={c['id']:c for c in definitions['clips']};clips={c['id']:c for c in spec['clips']}
    bones=observation_bones(definitions)
    for name in ('walk','run'):
        binding=bindings[name];clip=clips[binding['clip']];duration=binding['duration_s']
        for side,(lo,hi) in row['contact_phase'].items():
            rules=[c for c in clip.get('repairs',{}).get('contacts',[]) if c.get('chain',[])[-1:]==[bones['dst_foot_'+side]]]
            if not any((c['start_s']+c.get('blend_s',0))/duration<=lo+1e-6 and (c['end_s']-c.get('blend_s',0))/duration>=hi-1e-6 for c in rules):
                raise ValueError('Unverified shared contact phase: '+name+' '+side+'; calibrate aligned cycles before blending')

def safe_name(value):
    return isinstance(value,str) and bool(value) and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value)

def layer_settings(definitions):
    if any(type(c.get('layer_only',False)) is not bool for c in definitions.get('clips',[])):raise ValueError('Explicit layer_only bool required')
    row=definitions.get('layers')
    if row is None:
        if any(c.get('layer_only') for c in definitions.get('clips',[])):raise ValueError('Layer-only clips require explicit layers')
        return None
    fields={'mode','upper_root','clips','fade_in_s','fade_out_s','replace_s','event_policy'}
    if not isinstance(row,dict) or set(row)!=fields or row['mode']!='upper_full_v1' or row['event_policy']!='current_visible':
        raise ValueError('Explicit upper_full_v1 layers with current_visible events required')
    if row['upper_root']!=observation_bones(definitions)['dst_spine']:raise ValueError('Upper layer must start at calibrated spine; native import checks its descendants')
    for name in ('fade_in_s','fade_out_s','replace_s'):motion.number(row[name],name,.04,1.)
    ids=row['clips']
    if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):raise ValueError('Unique layer clip IDs required')
    clips={c['id']:c for c in definitions.get('clips',[])}
    if definitions.get('default_action','action') in ids:raise ValueError('Default base action cannot be layer-only')
    if set(ids)!={c['id'] for c in clips.values() if c.get('layer_only') is True}:raise ValueError('Explicit layer-only bindings must match layer clips')
    for name in ids:
        if name in {'idle','walk','run','jump','fall','land','action','action_v2','locomotion'} or name.startswith('turn_'):raise ValueError('Base actions cannot be layer-only')
        c=clips[name];events=c.get('markers',[])
        if not math.isfinite(c.get('duration_s',0)) or c['duration_s']<=0:raise ValueError('Layer clip duration required')
        if events!=sorted(events,key=lambda e:e['at_s']):raise ValueError('Layer markers must be time ordered')
        names=set()
        for e in events:
            if not re.fullmatch(r'[a-z][a-z0-9_]*',e.get('name','')) or e['name'] in names:raise ValueError('Unique safe marker names required')
            motion.number(e['at_s'],'layer marker',0,c['duration_s'])
            if c['loop'] and e['at_s']>=c['duration_s']:raise ValueError('Loop seam uses time zero, not duplicate end marker')
            names.add(e['name'])
    return dict(row)


def profile_settings(revision):
    """Project-owned runtime settings from the exact processed character profile."""
    revision=Path(revision);spec=motion.read(revision/'job.json')['spec'];profile=spec.get('character_profile')
    if not profile:return None
    if profile['coordinates']['target']['forward']!='-Y':
        raise ValueError('This playable template needs target anatomical -Y; normalize an export copy')
    observed={role:profile['roles'][role.removeprefix('dst_')]['target'] for role in OBSERVATION_ROLES}
    speeds={}
    for name in ('walk','run'):
        clips=[c for c in spec['clips'] if c['id']==name]
        if not clips:continue
        rules=clips[0].get('repairs',{}).get('contacts',[])
        velocities=[r.get('controller_velocity_mps',[0,0,0]) for r in rules]
        if not velocities:continue
        v=velocities[0]
        if abs(v[0])>1e-8 or abs(v[2])>1e-8 or v[1]>=0 or any(math.dist(v,w)>1e-8 for w in velocities):
            raise ValueError('Playable contact profile requires one forward controller speed per clip')
        speeds[name]=-v[1]
    return {'observation_bones':observed,'root_bone':profile['roles']['root']['target'],
            'contact_speeds_mps':speeds,'profile':spec['profile_dependency']}

def checked_bindings(revision,definitions):
    revision=Path(revision).resolve()
    result=motion.verify(revision)
    if not result['ok']:raise ValueError(str(result['failures']))
    report=motion.read(revision/'report.json')
    if definitions.get('schema')!='oagd.playback/1' or not safe_name(definitions.get('revision')):raise ValueError('Explicit playback schema and safe revision required')
    root_policy=motion_root.settings(definitions)
    if motion_constraints.settings(definitions) and any(definitions.get(k) for k in ('root_motion','layers','turning')):
        raise ValueError('Combined example policies require explicit project integration; contacts example uses base playback')
    if not root_policy and (report['root_motion']['owner']!='controller' or report['root_motion']['translation']!='in_place'):raise ValueError('Explicit root policy required for animation-owned motion')
    available={r['id']:r for r in report['clips']};seen=set()
    observed=observation_bones(definitions);example_settings(definitions)
    check_locomotion_phases(definitions,motion.read(revision/'job.json')['spec'])
    if turning_settings(definitions):
        turns=motion.read(revision/'turns.json')
        if not report.get('turn_authoring') or turns.get('schema')!='oagd.turns/1':raise ValueError('Verified turn authoring manifest required')
        expected={f'turn_{side}_{angle}' for side in ('l','r') for angle in (45,90,180)}
        if {c['id'] for c in turns['clips']}!=expected or len(turns['clips'])!=6:raise ValueError('All six authored turns required')
        for c in turns['clips']:
            named_angle=int(c['id'].split('_')[-1])*(-1 if '_l_' in c['id'] else 1)
            if c['angle_deg']!=named_angle or c['lead_s']!=.2 or c['step_s']!=.6 or c['tail_s']!=.2 or c['steps']!=abs(c['angle_deg'])//45:
                raise ValueError('Turn yaw schedule differs from native controller')
        profile=motion.read(revision/'job.json')['spec']['character_profile']
        if definitions['turn_observation_bones']!={k:profile['roles'][k.removeprefix('dst_')]['target'] for k in definitions['turn_observation_bones']}:
            raise ValueError('Turn observation differs from calibrated profile')
    # Legacy revisions do not need a profile. New profiles have one authoritative map/speed.
    if report.get('profile'):
        settings=profile_settings(revision)
        if observed!=settings['observation_bones'] or definitions.get('root_bone')!=settings['root_bone']:
            raise ValueError('Playback bone mapping differs from processed character profile')
        speeds=definitions.get('movement_speeds_mps',{'walk':1.,'run':2.5})
        if any(abs(speeds[k]-v)>1e-6 for k,v in settings['contact_speeds_mps'].items()):
            raise ValueError('Playback speed differs from contact repair coordinate frame')
    for row in definitions['clips']:
        ident=row['id'];clip=available.get(row['clip'])
        if not isinstance(ident,str) or not re.fullmatch(r'[a-z][a-z0-9_]*',ident) or ident in seen or not clip:raise ValueError('Unique lowercase binding IDs and existing clips required')
        seen.add(ident)
        rooted=row.get('motion_owner')=='animation'
        if rooted:
            source_policy=report.get('root_motion_by_clip',{}).get(row['clip'],report['root_motion'])
            if not root_policy or row.get('in_place') is not False or source_policy['owner']!='animation' or source_policy['translation']!='scaled':raise ValueError('Conflicting root movement ownership')
        elif row.get('motion_owner')!='controller' or row.get('in_place') is not True:raise ValueError('Conflicting movement ownership')
        if type(row['loop']) is not bool:raise ValueError('Explicit loop bool required')
        if not math.isfinite(row['duration_s']) or abs(row['duration_s']-clip['duration_s'])>1e-5:raise ValueError('Binding duration differs from processed clip')
        markers=set()
        for event in row.get('markers',[]):
            if row.get('layer_only'):continue # validated separately; never selected by the base player
            if row['loop'] or not re.fullmatch(r'[a-z][a-z0-9_]*',event['name']) or event['name'] in markers or not math.isfinite(event['at_s']) or not 0<event['at_s']<row['duration_s']:raise ValueError('Unique lowercase interior markers on non-looping clips required')
            markers.add(event['name'])
        # Endpoint displacement alone misses out-and-back motion: check every frame.
        frames=motion.read(revision/(row['clip']+'-capture.json'))['after'];root=report['root_motion']['bone']
        motion_constraints.check_capture(definitions,frames)
        if row.get('layer_only') and row['loop']:
            first,last=frames[0]['bones'],frames[-1]['bones']
            for name,pose in first.items():
                dot=abs(sum(a*b for a,b in zip(pose['q'],last[name]['q'])))
                if math.dist(pose['p'],last[name]['p'])>.001 or 2*math.acos(min(1,dot))>math.radians(.1):raise ValueError('Layer loop requires matching endpoint poses')
        if observed['dst_root']!=root:raise ValueError('Observed root differs from processed root')
        if any(name not in f['bones'] for f in frames for name in observed.values()):raise ValueError('Observed bone missing from processed capture')
        motion_root.check_track(frames,root,rooted)
        if clip['fps'] not in (30,60):raise ValueError('This playback example uses 30/60 fps assets')
    required={'idle','walk','run','jump','fall','land','action','action_v2'}
    if definitions.get('constraints',{}).get('grip'):required|={'hold','carry'}
    if root_policy:
        required|={'dash','roll'}
        if any(c['id'] in ('dash','roll') and c['motion_owner']!='animation' for c in definitions['clips']):raise ValueError('Root example needs animation-owned dash and roll')
    if not required.issubset(seen):raise ValueError('Example needs '+str(sorted(required)))
    if definitions.get('default_action','action') not in seen:raise ValueError('Default action missing')
    return report

def create(project,engine,revision,bindings,ue_root=None):
    project=Path(project).resolve();revision=Path(revision).resolve();definitions=motion.read(bindings)
    report=checked_bindings(revision,definitions)
    definitions['source_directory']='motion' if engine=='godot' else 'SourceMotion'
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.tscn',definitions.get('character_scene','character.tscn')):raise ValueError('Unsafe character scene name')
    if not re.fullmatch(r'/Game/Playback[A-Za-z0-9_]*',definitions.get('unreal_root','/Game/Playback')):raise ValueError('Unsafe native revision path')
    runtime_components.engine_version(engine,ue_root)
    if project.exists():raise ValueError('Choose a new project directory; migration is explicit')
    template=ROOT/'templates/motion_playback'/engine
    shutil.copytree(template,project)
    if engine=='godot':
        (project/'project.godot').write_text('''config_version=5
[application]
config/name="OAGD Playable Motion"
run/main_scene="res://main.tscn"
[display]
window/size/viewport_width=1152
window/size/viewport_height=720
[rendering]
renderer/rendering_method="gl_compatibility"
''',encoding='utf-8')
        (project/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n[node name="MotionExample" type="Node3D"]\nscript = ExtResource("1")\n')
        assets=project/'motion';extension='.glb';destination=project/'addons/oagd_playback'
        (project/'bindings.json').write_text(json.dumps(definitions,indent=2))
    else:
        (project/'MotionPlay.uproject').write_text(json.dumps({'FileVersion':3,'EngineAssociation':'5.8','Modules':[{'Name':'MotionPlay','Type':'Runtime','LoadingPhase':'Default'}],
            'Plugins':[{'Name':n,'Enabled':True} for n in ('OAGDCore','OAGDPlayback','PythonScriptPlugin','EditorScriptingUtilities')]},indent=2))
        config=project/'Config';config.mkdir(exist_ok=True)
        (config/'DefaultEngine.ini').write_text('''[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Game/Playback/Example
EditorStartupMap=/Game/Playback/Example
GlobalDefaultGameMode=/Script/MotionPlay.MotionGame
[/Script/Engine.RendererSettings]
r.DynamicGlobalIlluminationMethod=0
r.ReflectionMethod=0
r.Shadow.Virtual.Enable=0
r.DefaultFeature.AutoExposure=False
[/Script/Engine.UserInterfaceSettings]
bAllowHighDPIInGameMode=True

[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
!D3D12TargetedShaderFormats=ClearArray
+D3D12TargetedShaderFormats=PCD3D_SM6
'''.replace('/Game/Playback',definitions.get('unreal_root','/Game/Playback')))
        (config/'DefaultInput.ini').write_text('''[/Script/Engine.InputSettings]
+AxisMappings=(AxisName="Forward",Scale=1.0,Key=W)
+AxisMappings=(AxisName="Forward",Scale=-1.0,Key=S)
+AxisMappings=(AxisName="Right",Scale=1.0,Key=D)
+AxisMappings=(AxisName="Right",Scale=-1.0,Key=A)
bCaptureMouseOnLaunch=False
''')
        (config/'DefaultGame.ini').write_text('''[/Script/UnrealEd.ProjectPackagingSettings]
+MapsToCook=(FilePath="/Game/Playback/Example")
+DirectoriesToAlwaysCook=(Path="/Game/Playback")
+DirectoriesToAlwaysCook=(Path="/Engine/BasicShapes")
bUsePakFile=True
'''.replace('/Game/Playback',definitions.get('unreal_root','/Game/Playback'))+'\n[OAGDPlayback]\nRevisionRoot='+definitions.get('unreal_root','/Game/Playback')+'\n'+example_settings(definitions))
        assets=project/'SourceMotion';extension='.fbx';destination=project/'Plugins'
        (project/'bindings.json').write_text(json.dumps(definitions,indent=2))
    if definitions.get('root_motion'):
        if engine=='godot':
            (project/'main.gd').write_bytes((project/'root_main.gd').read_bytes())
        else:
            for ini in ('DefaultEngine.ini',):
                path=project/'Config'/ini;path.write_text(path.read_text().replace('/Script/MotionPlay.MotionGame','/Script/MotionPlay.RootGame')+'\n[SystemSettings]\nr.MotionBlurQuality=0\nr.DefaultFeature.MotionBlur=0\n')
    if definitions.get('constraints'):
        if engine=='godot':(project/'main.gd').write_bytes((project/'constraints_main.gd').read_bytes())
        else:
            path=project/'Config/DefaultEngine.ini';path.write_text(path.read_text().replace('/Script/MotionPlay.MotionGame','/Script/MotionPlay.ConstraintsGame')+'\n[SystemSettings]\nr.MotionBlurQuality=0\nr.DefaultFeature.MotionBlur=0\n')
    assets.mkdir()
    for row in definitions['clips']:shutil.copy2(revision/(row['clip']+extension),assets/(row['clip']+extension))
    if report.get('turn_authoring'):shutil.copy2(revision/'turns.json',assets/'turns.json')
    runtime_components.install(project,engine,ue_root)
    shutil.copytree(ROOT/'adapters/engines/motion_playback'/engine,destination,dirs_exist_ok=True)
    files={p.relative_to(project).as_posix():motion.digest(p) for p in project.rglob('*') if p.is_file()}
    data={'schema':'oagd.playback-install/1','version':VERSION,'engine':engine,'revision':definitions['revision'],'source_revision':str(revision),
          'source_report_sha256':motion.digest(revision/'report.json'),'files':files,'ownership':'project-owned copies; toolkit updates never mutate this project'}
    motion.write(project/LOCK,data)
    return data

def status(project):
    project=Path(project).resolve();data=motion.read(project/LOCK);missing=[];changed=[]
    for name,sha in data['files'].items():
        p=(project/name).resolve()
        if not p.is_relative_to(project):raise ValueError('Unsafe manifest path')
        if not p.is_file():missing.append(name)
        elif motion.digest(p)!=sha:changed.append(name)
    return {**data,'missing':missing,'changed':changed}

def stage(project,revision,bindings):
    project=Path(project).resolve();revision=Path(revision).resolve();definitions=motion.read(bindings)
    checked_bindings(revision,definitions);lock=motion.read(project/LOCK);engine=lock['engine']
    if bool(definitions.get('root_motion'))!=bool(motion.read(project/'bindings.json').get('root_motion')):
        raise ValueError('Movement mode migration requires an explicit project consumer change; use a new root example or keep the current mode')
    if bool(definitions.get('constraints'))!=bool(motion.read(project/'bindings.json').get('constraints')):
        raise ValueError('Constraint consumer migration requires an explicit project change')
    pending=project/'bindings.pending.json'
    if pending.exists():raise ValueError('A staged revision already exists; finish or explicitly preserve/resolve it first')
    ident=definitions['revision'];folder=project/('motion' if engine=='godot' else 'SourceMotion')/ident
    if folder.exists():raise ValueError('Revision source directory already exists')
    definitions['source_directory']=folder.relative_to(project).as_posix()
    definitions['character_scene']='character_'+ident+'.tscn'
    definitions['unreal_root']='/Game/Playback_'+ident.replace('-','_')
    definitions['source_report_sha256']=motion.digest(revision/'report.json')
    ext='.glb' if engine=='godot' else '.fbx'
    folder.mkdir(parents=True)
    for row in definitions['clips']:shutil.copy2(revision/(row['clip']+ext),folder/(row['clip']+ext))
    if definitions.get('turning'):shutil.copy2(revision/'turns.json',folder/'turns.json')
    definitions['source_hashes']={p.relative_to(project).as_posix():motion.digest(p) for p in folder.iterdir() if p.is_file()}
    motion.write(pending,definitions)
    return {'staged':ident,'binding':str(pending),'active_changed':False,'next':'run native prepare script, then activate'}

def activate(project):
    project=Path(project).resolve();pending=project/'bindings.pending.json';definitions=motion.read(pending);engine=motion.read(project/LOCK)['engine']
    if not safe_name(definitions.get('revision')):raise ValueError('Unsafe revision')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.tscn',definitions.get('character_scene','')):raise ValueError('Unsafe scene')
    if not re.fullmatch(r'/Game/Playback[A-Za-z0-9_]*',definitions.get('unreal_root','')):raise ValueError('Unsafe native path')
    for relative,sha in definitions.get('source_hashes',{}).items():
        p=runtime_components.safe(project,relative)
        if motion.digest(p)!=sha:raise ValueError('Staged source changed')
    report_path=project/(definitions['character_scene']+'.import-report.json' if engine=='godot' else definitions['unreal_root'].rsplit('/',1)[-1]+'-import-report.json')
    report=motion.read(report_path)
    if not report['ok'] or report.get('binding_sha256')!=motion.digest(pending):raise ValueError('Current successful native import evidence required')
    native={definitions['character_scene']:report['scene_sha256']} if engine=='godot' else report['native_files']
    for relative,sha in native.items():
        if motion.digest(runtime_components.safe(project,relative))!=sha:raise ValueError('Native output changed after import')
    # Validate and stage every replacement before changing any live selection.
    changes={'bindings.json':pending.read_bytes()}
    if engine=='unreal':
        root=definitions['unreal_root'];config=project/'Config/DefaultEngine.ini';text=config.read_text()
        text=re.sub(r'(?m)^(GameDefaultMap|EditorStartupMap)=.*$',lambda m:m.group(1)+'='+root+'/Example',text)
        changes['Config/DefaultEngine.ini']=text.encode('utf-8')
        config=project/'Config/DefaultGame.ini';text=config.read_text()
        text=re.sub(r'(?ms)^\[OAGDPlayback\]\n.*?(?=^\[|\Z)','',text)
        text=re.sub(r'(?m)^\+MapsToCook=.*$', '+MapsToCook=(FilePath="'+root+'/Example")',text)
        text=re.sub(r'(?m)^\+DirectoriesToAlwaysCook=\(Path="/Game/Playback[^\n]*$', '+DirectoriesToAlwaysCook=(Path="'+root+'")',text)
        changes['Config/DefaultGame.ini']=(text+'\n[OAGDPlayback]\nRevisionRoot='+root+'\n'+example_settings(definitions)).encode('utf-8')
    backup=project/'.openaigame/playback-history'/definitions['revision']
    if backup.exists():backup=backup.with_name(backup.name+'-retry-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True,exist_ok=False)
    originals={name:(project/name).read_bytes() for name in changes}
    for name,data in originals.items():
        target=backup/'before'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    for index,(name,data) in enumerate(changes.items()):(backup/('new-'+str(index))).write_bytes(data)
    applied=[]
    try:
        for index,name in enumerate(changes):
            os.replace(backup/('new-'+str(index)),project/name);applied.append(name)
    except BaseException:
        for name in reversed(applied):(project/name).write_bytes(originals[name])
        motion.write(backup/'activation.json',{'revision':definitions['revision'],'state':'rolled_back','pending_preserved':True})
        raise
    pending.unlink()
    motion.write(backup/'activation.json',{'revision':definitions['revision'],'import_report':str(report_path),'binding_sha256':motion.digest(project/'bindings.json'),'runtime_validation':'not_run'})
    return {'active':definitions['revision'],'backup':str(backup),'runtime_validation':'not_run'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['create','status','stage','activate']);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--engine',choices=['godot','unreal']);p.add_argument('--revision',type=Path);p.add_argument('--bindings',type=Path);p.add_argument('--ue-root',type=Path)
    a=p.parse_args()
    try:
        if a.command=='status':result=status(a.project)
        elif a.command=='stage':result=stage(a.project,a.revision,a.bindings)
        elif a.command=='activate':result=activate(a.project)
        else:result=create(a.project,a.engine,a.revision,a.bindings,a.ue_root)
        print(json.dumps(result,indent=2));raise SystemExit(int(bool(result.get('missing') or result.get('changed'))))
    except (ValueError,KeyError,TypeError,OSError) as error:p.exit(2,str(error)+'\n')

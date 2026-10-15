#!/usr/bin/env python3
"""Run a generated native example and verify a fresh structured result, not log text."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid
import array
import math
import sys
import wave


def inspect_audio(path):
    """Signal evidence only; this cannot establish listening quality."""
    with wave.open(str(path), 'rb') as stream:
        if stream.getsampwidth()!=2 or stream.getcomptype()!='NONE':
            raise ValueError('Expected native PCM16 recording')
        channels=stream.getnchannels();rate=stream.getframerate();frames=stream.getnframes()
        values=array.array('h',stream.readframes(frames))
    if sys.byteorder!='little':values.byteswap()
    if not values or rate<=0:raise ValueError('Empty native recording')
    peak=max(abs(v) for v in values)/32768
    rms=math.sqrt(sum(v*v for v in values)/len(values))/32768
    return {'seconds':frames/rate,'channels':channels,'sample_rate':rate,'peak':peak,'rms':rms,
            'non_silent':rms>0.00001,'clipped_samples':sum(abs(v)>=32767 for v in values),
            'listening_acceptance':'not_performed'}


def run_feedback(project,engine,exe,evidence,visual,timeout):
    report=evidence/'feedback.json';saves=evidence/'saves';saves.mkdir()
    if engine=='godot':
        # Fresh copies need native WAV/script imports before their first game run.
        command=[str(exe),'--headless','--editor','--path',str(project),'--quit']
        with (evidence/'import.log').open('wb') as out:
            imported=subprocess.run(command,cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
        if imported:raise ValueError('Godot import failed: '+str(evidence/'import.log'))
        command=[str(exe),'--path',str(project)]
        if not visual:command+=['--headless']
        command+=['--','--self-test','--report='+str(report),'--save-root='+str(saves)]
    else:
        projects=list(project.glob('*.uproject'))
        if len(projects)!=1:raise ValueError('Expected one .uproject')
        command=[str(exe),str(projects[0]),'/Game/Example','-game','-OAGDSelfTest',
                 '-FeedbackReport='+str(report),'-StateRoot='+str(saves),'-unattended','-AudioMixer',
                 '-ini:Engine:[Audio]:UnfocusedVolumeMultiplier=1.0','-RenderOffScreen',
                 '-windowed','-ResX=1152','-ResY=720','-stdout','-FullStdOutLogOutput',
                 '-abslog='+str(evidence/'engine.log')]
        if not visual:command+=['-nullrhi']
    start=time.monotonic()
    with (evidence/'process.log').open('wb') as out:
        try:code=subprocess.run(command,cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:code=124
    result=json.loads(report.read_text(encoding='utf-8-sig')) if report.is_file() else None
    audio=None;audio_error=None
    try:audio=inspect_audio(Path(str(report)+'.wav'))
    except (OSError,ValueError,wave.Error,EOFError) as error:audio_error=str(error)
    passed=code==0 and isinstance(result,dict) and result.get('failures')==[] and len(result.get('checks',[]))>=33
    if passed and engine=='unreal':passed=result.get('engine','').startswith('5.8.')
    passed=bool(passed and audio and audio['non_silent'] and audio['clipped_samples']==0)
    record={'passed':passed,'command':command,'exit_code':code,'seconds':round(time.monotonic()-start,3),
            'result':result,'audio':audio,'audio_error':audio_error,'rendered':visual,'evidence':str(evidence)}
    (evidence/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def run_state(project,engine,exe,evidence,visual,timeout):
    """Two real processes share only the isolated journal, never in-memory state."""
    saves=evidence/'saves';saves.mkdir()
    runs=[]
    for phase in ('exercise','resume'):
        report=evidence/(phase+'.json')
        if engine=='godot':
            command=[str(exe),'--path',str(project)]
            if not visual:command+=['--headless']
            command+=['--fixed-fps','60','--','--self-test','--state-phase='+phase,'--save-root='+str(saves),'--report='+str(report)]
        else:
            projects=list(project.glob('*.uproject'))
            if len(projects)!=1:raise ValueError('Expected one .uproject')
            command=[str(exe),str(projects[0]),'/Game/Example','-game','-OAGDSelfTest',
                     '-StatePhase='+phase,'-StateRoot='+str(saves),'-StateReport='+str(report),
                     '-unattended','-windowed','-ResX=1152','-ResY=720','-stdout','-FullStdOutLogOutput',
                     '-UseFixedTimeStep','-FPS=60','-abslog='+str(evidence/(phase+'-engine.log'))]
            if not visual:command+=['-nullrhi']
        start=time.monotonic()
        with (evidence/(phase+'-process.log')).open('wb') as out:
            try:code=subprocess.run(command,cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
        result=json.loads(report.read_text(encoding='utf-8-sig')) if report.is_file() else None
        passed=code==0 and isinstance(result,dict) and result.get('phase')==phase and result.get('failures')==[] and len(result.get('checks',[]))>=(8 if phase=='resume' else 28)
        if passed and engine=='unreal':passed=result.get('engine','').startswith('5.8.')
        runs.append({'phase':phase,'command':command,'exit_code':code,'seconds':round(time.monotonic()-start,3),'passed':passed,'result':result})
        if not passed:break
    record={'passed':len(runs)==2 and all(r['passed'] for r in runs),'runs':runs,'evidence':str(evidence),'save_root':str(saves)}
    (evidence/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def run(project,engine,executable,visual=False,timeout=180):
    project=Path(project).resolve();exe=Path(executable).resolve()
    if not exe.is_file():raise ValueError('Engine executable does not exist')
    evidence=project/'.openaigame/runtime-validation'/uuid.uuid4().hex
    evidence.mkdir(parents=True)
    report=project/('validation.json' if engine=='godot' else 'Saved/validation.json')
    scenario_file=project/('scenario.json' if engine=='godot' else 'Content/OAGDData/scenario.json')
    scenario=json.loads(scenario_file.read_text(encoding='utf-8')).get('scenario') if scenario_file.is_file() else None
    if scenario=='state':return run_state(project,engine,exe,evidence,visual,timeout)
    if scenario=='feedback':return run_feedback(project,engine,exe,evidence,visual,timeout)
    input_case=scenario=='input'
    scene_case=scenario in ('scene','static')
    navigation_case=scenario=='navigation'
    interaction_case=scenario=='interaction'
    if interaction_case or navigation_case or scene_case:
        report=evidence/('scene.json' if scene_case else ('navigation.json' if navigation_case else 'interaction.json'))
        if engine=='godot':
            with (evidence/'import.log').open('wb') as out:
                imported=subprocess.run([str(exe),'--headless','--editor','--path',str(project),'--quit'],cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
            if imported:raise ValueError('Godot import failed: '+str(evidence/'import.log'))
            if scenario=='static' and not (project/'static_scene.tscn').exists():
                with (evidence/'static-build.log').open('wb') as out:
                    built=subprocess.run([str(exe),'--headless','--path',str(project),'--script','res://build_assets.gd'],cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
                if built or not (project/'static_scene.tscn').exists():raise ValueError('Static asset preparation failed')
    # Archive stale output so a failed launch can never reuse a previous success.
    if report.exists():report.rename(evidence/'previous-result.json')
    if engine=='godot':
        command=[str(exe),'--path',str(project)]
        if not visual:command+=['--headless']
        if input_case:command+=['--fixed-fps','60']
        command+=['--','--self-test']
        if input_case or interaction_case or navigation_case or scene_case:command+=['--report='+str(report)]
    else:
        projects=list(project.glob('*.uproject'))
        if len(projects)!=1:raise ValueError('Expected one .uproject')
        command=[str(exe),str(projects[0]),'/Game/Example','-game','-OAGDSelfTest','-unattended','-windowed','-ResX=1152','-ResY=720','-nosplash','-stdout','-FullStdOutLogOutput','-abslog='+str(evidence/'engine.log')]
        if not visual:command+=['-nullrhi']
        if input_case:command+=['-InputReport='+str(report),'-UseFixedTimeStep','-FPS=60']
        if interaction_case:command+=['-InteractionReport='+str(report),'-RenderOffScreen']
        if navigation_case:command+=['-NavigationReport='+str(report),'-RenderOffScreen']
        if scene_case:command+=['-SceneReport='+str(report),'-RenderOffScreen']
    start=time.monotonic()
    with (evidence/'process.log').open('wb') as out:
        try:code=subprocess.run(command,cwd=project,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:code=124
    result=json.loads(report.read_text(encoding='utf-8-sig')) if report.is_file() else None
    scene_expected=None
    if scene_case:
        scene_path=project/('generated/scene/scene.json' if engine=='godot' else 'Content/generated/scene/scene.json')
        scene_expected=json.loads(scene_path.read_text(encoding='utf-8'))
    expected_count=(8+sum(6 if q['expected_reachable'] else 4 for q in scene_expected['navigation']['queries'])) if scene_case else (43 if navigation_case else (49 if interaction_case else (24 if input_case else 12)))
    if scenario=='static':
        plan_path=project/('generated/static/plan.json' if engine=='godot' else 'Content/generated/static/plan.json')
        expected_count+=8*len(json.loads(plan_path.read_text(encoding='utf-8'))['replacements'])
    passed=code==0 and isinstance(result,dict) and isinstance(result.get('checks'),list) and len(result['checks'])>=expected_count and result.get('failures')==[]
    if passed and scene_case:
        passed=result.get('spec_sha256')==scene_expected['spec_sha256'] and result.get('agent')==scene_expected['navigation']['agent'] and [c.get('id') for c in result.get('cases',[])]==[q['id'] for q in scene_expected['navigation']['queries']]
    if passed and engine=='unreal' and not result.get('engine','').startswith('5.8.'):
        passed=False
    record={'command':command,'exit_code':code,'seconds':round(time.monotonic()-start,3),
            'passed':passed,'result':result,'evidence':str(evidence)}
    (evidence/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--engine',required=True,choices=('godot','unreal'))
    parser.add_argument('--executable',required=True,type=Path)
    parser.add_argument('--visual',action='store_true')
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    try:
        result=run(args.project,args.engine,args.executable,args.visual,args.timeout)
        print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
    except (OSError,ValueError) as error:print(json.dumps({'error':str(error)}));return 1

if __name__=='__main__':raise SystemExit(main())

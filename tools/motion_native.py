#!/usr/bin/env python3
"""Prepare native import/capture jobs and audit actual engine samples of a motion revision."""
import argparse
import json
import math
from pathlib import Path
from motion_workflow import read, write, digest, verify, number


def clip_record(revision,clip):
    revision=Path(revision).resolve();check=verify(revision)
    if not check['ok']:raise ValueError('; '.join(check['failures']))
    report=read(revision/'report.json');rows=[r for r in report['clips'] if r['id']==clip]
    if len(rows)!=1:raise ValueError('Clip not in this revision')
    return revision,report,rows[0]


def prepare(revision,clip,engine,output,destination=None):
    revision,report,row=clip_record(revision,clip);output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    job={'fps':row['fps'],'frames':row['frames']}
    if engine=='godot':
        job.update(glb=str(revision/(clip+'.glb')),sha256=digest(revision/(clip+'.glb')),
                   scene=str(output/(clip+'.tscn')),report=str(output/'capture.json'))
    else:
        if not destination or not destination.startswith('/Game/') or '..' in destination:raise ValueError('New /Game/ destination required')
        if int(row['fps'])!=row['fps']:raise ValueError('UE FbxFactory adapter requires an integer sample rate')
        job.update(fbx=str(revision/(clip+'.fbx')),sha256=digest(revision/(clip+'.fbx')),name=clip,
                   destination=destination,report=str(output/'import.json'))
    write(output/'job.json',job)
    return {'ok':True,'job':str(output/'job.json'),'engine':engine,'action':'run_engine_adapter','quality':'not_checked'}


def capture_job(import_record,revision,clip,output):
    revision,report,row=clip_record(revision,clip);imported=read(import_record)
    if not imported.get('ok') or imported.get('source_sha256')!=digest(revision/(clip+'.fbx')):raise ValueError('Wrong or failed native import')
    for path,expected in imported['native_dependencies'].items():
        if not Path(path).is_file() or digest(path)!=expected:raise ValueError('Native import changed: '+path)
    job={'mesh':imported['mesh'],'animation':imported['animation'],'fps':row['fps'],'frames':row['frames'],
         'report':str(Path(output).resolve().with_name('capture.json'))}
    with Path(output).open('x',encoding='utf-8') as stream:json.dump(job,stream,indent=2)
    return {'ok':True,'job':str(Path(output).resolve()),'action':'run_native_sampling_plugin'}


def multiply(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inverse(q):return [-q[0],-q[1],-q[2],q[3]]
def rotation_error(a,b):
    denom=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    if denom<1e-8:raise ValueError('Invalid sampled quaternion')
    return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b)))/denom)))


def audit(revision,clip,capture_path,import_record=None,position_tolerance=.002,rotation_tolerance=.2):
    revision,report,row=clip_record(revision,clip);capture=read(capture_path);failures=[]
    number(position_tolerance,'position tolerance',1e-6,.1);number(rotation_tolerance,'rotation tolerance',.001,10)
    engine=capture['engine'];source=read(revision/(clip+'-capture.json'))['after'];native=capture['frames']
    if not capture.get('ok') or len(source)!=len(native):raise ValueError('Incomplete native capture')
    if abs(capture['length_s']-row['duration_s'])>1e-4:failures.append('Animation duration changed on import')
    if report['root_motion']['bone'] not in capture.get('root_bones',[]):failures.append('Declared root is not a native skeleton root')
    if engine=='godot':
        if not capture.get('skinned_meshes'):failures.append('No actual skinned meshes')
        if capture.get('source_sha256')!=digest(revision/(clip+'.glb')):failures.append('Capture does not match revision GLB')
        point=lambda p:[p[0],p[2],-p[1]]
        delta=lambda q:[q[0],q[2],-q[1],q[3]]
        units=1
    elif engine=='unreal':
        if not str(capture.get('engine_version','')).startswith('5.8.'):failures.append('Unverified UE version')
        if import_record is None:raise ValueError('Unreal audit needs native import record')
        imported=read(import_record)
        if not imported.get('ok') or imported.get('source_sha256')!=digest(revision/(clip+'.fbx')):failures.append('Native import source differs')
        for k in ('mesh','animation'):
            if capture.get(k)!=imported[k]:failures.append('Wrong native '+k+' consumer')
        if not imported.get('native_dependencies'):failures.append('Native asset hashes missing')
        for path,sha in imported.get('native_dependencies',{}).items():
            if not Path(path).is_file() or digest(path)!=sha:failures.append('Native asset changed: '+path)
        # Blender FBX (-Y forward / Z up), UE FbxFactory default scene conversion.
        point=lambda p:[p[0]*100,-p[1]*100,p[2]*100]
        delta=lambda q:[-q[0],q[1],-q[2],q[3]]
        units=100
    else:raise ValueError('Unsupported engine capture')
    max_p=0;max_q=0;worst=None
    for expected,actual in zip(source,native):
        if abs(expected['t']-actual['t'])>1e-5:raise ValueError('Mismatched sample times')
        if 'animation_time' in actual and abs(actual['t']-actual['animation_time'])>1e-4:failures.append('Engine did not seek to requested time')
        for name,bone in expected['bones'].items():
            observed=actual['bones'].get(name)
            if observed is None:raise ValueError('Native bone missing: '+name)
            values=observed['p']+observed['q']
            if len(observed['p'])!=3 or len(observed['q'])!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in values):raise ValueError('Invalid native pose')
            error=math.dist(point(bone['p']),observed['p'])/units
            if error>max_p:max_p=error;worst={'bone':name,'t':actual['t']}
            # Importers may change constant bone-axis conventions. Compare actual
            # global rotational motion relative to frame 0, which cancels those conventions.
            expected_delta=delta(multiply(bone['q'],inverse(source[0]['bones'][name]['q'])))
            actual_delta=multiply(observed['q'],inverse(native[0]['bones'][name]['q']))
            max_q=max(max_q,rotation_error(expected_delta,actual_delta))
    if max_p>position_tolerance:failures.append('Native position residual exceeds tolerance')
    if max_q>rotation_tolerance:failures.append('Native rotation delta residual exceeds tolerance')
    spec=read(revision/'job.json')['spec'];clip_spec=next(c for c in spec['clips'] if c['id']==clip);contacts=[]
    for rule in clip_spec.get('repairs',{}).get('contacts',[]):
        bone=rule['chain'][-1];rows=[f for f in native if rule['start_s']-1e-6<=f['t']<=rule['end_s']+1e-6]
        if len(rows)<2:raise ValueError('Contact window has insufficient engine samples')
        velocity=point(rule.get('controller_velocity_mps',[0,0,0]))
        drift=max(math.dist([v+velocity[j]*(f['t']-rows[0]['t']) for j,v in enumerate(f['bones'][bone]['p'])],rows[0]['bones'][bone]['p'])/units for f in rows)
        contacts.append({'bone':bone,'samples':len(rows),'max_drift_m':drift,'controller_velocity_mps':rule.get('controller_velocity_mps',[0,0,0])})
        if drift>spec['tolerances']['contact_m']:failures.append('Native contact drift exceeds declared tolerance')
    return {'ok':not failures,'engine':engine,'engine_version':capture['engine_version'],'frames':len(native),
            'bones_compared':len(source[0]['bones']),'max_position_error_m':max_p,'max_rotation_delta_error_deg':max_q,
            'worst_position':worst,'contacts':contacts,'failures':failures,
            'tolerances':{'position_m':position_tolerance,'rotation_delta_deg':rotation_tolerance},
            'capture_sha256':digest(capture_path),'revision_report_sha256':digest(revision/'report.json'),
            'quality':'technical_roundtrip_only; skin deformation, artistic quality and gameplay need separate review'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for action in ('prepare','capture-job','audit'):
        cmd=sub.add_parser(action)
        cmd.add_argument('--revision',type=Path,required=True);cmd.add_argument('--clip',required=True);cmd.add_argument('--output',type=Path,required=True)
        if action=='prepare':cmd.add_argument('--engine',choices=['godot','unreal'],required=True);cmd.add_argument('--destination')
        else:
            cmd.add_argument('--import-record',type=Path,required=action=='capture-job')
            if action=='audit':cmd.add_argument('--capture',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.command=='prepare':result=prepare(a.revision,a.clip,a.engine,a.output,a.destination)
        elif a.command=='capture-job':result=capture_job(a.import_record,a.revision,a.clip,a.output)
        else:
            result=audit(a.revision,a.clip,a.capture,a.import_record)
            with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ok'] else 2
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())

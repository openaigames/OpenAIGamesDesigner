#!/usr/bin/env python3
"""Inspect rigs or produce a new retargeted/repaired animation revision in Blender."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

VERSION = '0.2.0'
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def number(value, name, lower=None, upper=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if lower is not None and value < lower or upper is not None and value > upper:
        raise ValueError(name + ' out of range')
    return value


def validate(spec, base):
    """Validate intent and immutable source identity before launching a DCC process."""
    if spec.get('schema') != 'oagd.motion/1':
        raise ValueError('Expected oagd.motion/1')
    from motion_profile import resolve
    result = resolve(json.loads(json.dumps(spec, allow_nan=False)), base)
    for role in ('source', 'target'):
        row = result[role]
        path = (Path(base) / row['file']).resolve()
        if path.suffix.lower() not in ('.blend', '.fbx', '.glb') or not path.is_file():
            raise ValueError(role + ': expected existing .blend/.fbx/.glb')
        if not row.get('armature') or digest(path) != row.get('sha256'):
            raise ValueError(role + ': explicit armature and matching sha256 required')
        row['file'] = str(path)
    mapping = result['mapping']
    if not isinstance(mapping, dict) or not mapping or not all(isinstance(k, str) and k and isinstance(v, str) and v for k,v in mapping.items()):
        raise ValueError('mapping is target bone -> source bone; names must be explicit')
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('Mapping is not one-to-one')
    q = result['alignment_xyzw']
    if len(q) != 4 or abs(sum(number(v,'alignment')**2 for v in q)-1) > 1e-4:
        raise ValueError('alignment_xyzw must be a unit quaternion')
    root = result['root_motion']
    if root.get('owner') not in ('animation', 'controller') or root.get('translation') not in ('scaled', 'in_place'):
        raise ValueError('Explicit root motion owner and translation policy required')
    if root['owner'] == 'controller' and root['translation'] != 'in_place':
        raise ValueError('Controller-owned clip must be in_place; no double movement')
    if root.get('bone') not in mapping:
        raise ValueError('Root bone must be mapped')
    extra=root.get('translation_bones',[])
    if not isinstance(extra,list) or len(extra)!=len(set(extra)) or any(b not in mapping or b==root['bone'] for b in extra):
        raise ValueError('translation_bones must explicitly name unique mapped non-root bones')
    number(root['scale'], 'root scale', .001, 1000)
    ids = set()
    for clip in result['clips']:
        ident = clip['id']
        if not isinstance(ident, str) or not ident or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in ident) or ident in ids:
            raise ValueError('Unique safe clip IDs required')
        ids.add(ident)
        if not clip.get('action'):
            raise ValueError('Explicit source Action required')
        fps = number(clip['fps'], 'fps', 1, 240)
        for key in ('start_frame','end_frame'):
            if type(clip[key]) is not int: raise ValueError('Integer frame range required')
        count = clip['end_frame']-clip['start_frame']+1
        if count < 3 or count > 100000: raise ValueError('Clip frame count must be 3..100000')
        duration = (count-1)/fps
        offsets=clip.get('target_translation_offsets_m',{})
        if not isinstance(offsets,dict) or any(b not in extra for b in offsets):
            raise ValueError('Target calibration offsets require permitted translation bones')
        for vector in offsets.values():
            if not isinstance(vector,list) or len(vector)!=3:raise ValueError('Target calibration needs a 3D metre vector')
            for v in vector:number(v,'target calibration offset',-.5,.5)
        repairs = clip.get('repairs', {})
        if set(repairs)-{'rotation_spikes','loop','contacts'}:
            raise ValueError('Unknown repair; clothing and arbitrary smoothing are not supported')
        if 'rotation_spikes' in repairs:
            r = repairs['rotation_spikes']
            if not r['bones'] or any(b not in mapping for b in r['bones']): raise ValueError('Explicit mapped spike bones required')
            number(r['threshold_deg'],'spike threshold',1,180)
            number(r['neighbor_deg'],'spike neighbor agreement',0,r['threshold_deg']/2)
        if 'loop' in repairs:
            r = repairs['loop']
            if not r['bones'] or any(b not in mapping or b == root['bone'] for b in r['bones']):
                raise ValueError('Loop repair needs explicit mapped non-root bones')
            number(r['blend_s'],'loop blend',1/fps,duration)
        for r in repairs.get('contacts', []):
            if len(r['chain']) != 3 or len(set(r['chain'])) != 3: raise ValueError('Contact requires three distinct chain bones')
            if any(b not in mapping for b in r['chain']): raise ValueError('Contact bones must be mapped')
            number(r['start_s'],'contact start',0,duration)
            number(r['end_s'],'contact end',r['start_s']+1/fps,duration)
            number(r['blend_s'],'contact blend',1/fps,duration)
            if r['start_s'] < r['blend_s']-1e-6 or r['end_s']+r['blend_s'] > duration+1e-6:
                raise ValueError('Contact requires transition frames outside its declared support window')
            if r.get('anchor') != 'first_sample': raise ValueError('Contact anchor must be first_sample')
            if len(r['pole']) != 3 or sum(number(v,'pole')**2 for v in r['pole']) < 1e-8: raise ValueError('Nonzero explicit pole direction required')
            number(r['max_correction_m'],'max contact correction',0,10)
            number(r.get('max_joint_rotation_deg',60),'max joint rotation',1,180)
            velocity=r.get('controller_velocity_mps',[0,0,0])
            if not isinstance(velocity,list) or len(velocity)!=3:
                raise ValueError('Contact controller_velocity_mps must have three components')
            for v in velocity:number(v,'contact controller velocity',-20,20)
            if any(velocity) and (root['owner']!='controller' or root['translation']!='in_place' or abs(velocity[2])>1e-8):
                raise ValueError('Moving contact frame requires horizontal controller-owned in_place motion')
        contacts = repairs.get('contacts', [])
        for i,a in enumerate(contacts):
            for b in contacts[i+1:]:
                if set(a['chain']) & set(b['chain']) and max(a['start_s']-a['blend_s'],b['start_s']-b['blend_s']) <= min(a['end_s']+a['blend_s'],b['end_s']+b['blend_s']):
                    raise ValueError('Overlapping corrections on the same bone chain')
    if not ids: raise ValueError('At least one clip required')
    number(result['tolerances']['contact_m'],'contact tolerance',1e-6,.5)
    return result


def suggest(source, target, source_name, target_name):
    import re
    def select(doc,name):
        rows=[r for r in doc['rigs'] if r['name']==name]
        if len(rows)!=1:raise ValueError('Choose an inventory armature explicitly')
        return rows[0]
    aliases={'pelvis':'hips','hip':'hips','upperleg':'thigh','lowerleg':'shin','calf':'shin','lowerarm':'forearm','arm':'upperarm'}
    def key(name):
        n=name.rsplit(':',1)[-1].lower()
        n=re.sub(r'^(src|dst|mixamorig)[_.-]?', '',n)
        n=re.sub(r'[^a-z0-9]','',n)
        n=n.replace('left','l').replace('right','r')
        for old,new in aliases.items():
            if n==old or n in (old+'l',old+'r'):return new+n[len(old):]
        return n
    src=select(source,source_name);dst=select(target,target_name);index={}
    for b in src['bones']:index.setdefault(key(b['name']),[]).append(b['name'])
    mapping={};ambiguous=[];unmatched=[]
    for b in dst['bones']:
        matches=index.get(key(b['name']),[])
        if len(matches)==1 and matches[0] not in mapping.values():mapping[b['name']]=matches[0]
        elif matches:ambiguous.append(b['name'])
        else:unmatched.append(b['name'])
    return {'schema':'oagd.mapping-draft/1','status':'requires_mapping_and_reference_pose_review',
            'source_sha256':source['sha256'],'target_sha256':target['sha256'],'mapping':mapping,
            'ambiguous':ambiguous,'unmatched':unmatched,'basis':'name aliases only; topology checked by process'}


def launch(blender, output, job, timeout=1200):
    output = Path(output).resolve()
    # A completed or failed revision is immutable; choose another output to retry.
    output.mkdir(parents=True, exist_ok=False)
    write(output/'job.json',job)
    worker = ROOT/'adapters/processing/motion_blender.py'
    command = [str(Path(blender).resolve()),'--background','--factory-startup','--disable-autoexec','-t','2',
               '--python-exit-code','2','--python',str(worker),'--',str(output/'job.json')]
    write(output/'execution.json',{'command':command,'tool_version':VERSION,'worker_sha256':digest(worker)})
    with (output/'blender.log').open('w',encoding='utf-8') as log:
        try:
            process = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            code = process.returncode
        except subprocess.TimeoutExpired: code = 124
    report = output/'report.json'
    if code or not report.is_file():
        raise ValueError('Blender failed (exit '+str(code)+'); see '+str(output/'blender.log'))
    result = read(report)
    if not result.get('ok'): raise ValueError('Motion revision failed its checks: '+str(report))
    return result


def verify(output):
    output=Path(output).resolve();report=read(output/'report.json')
    failures=[]
    for path,expected in report.get('dependencies',{}).items():
        dependency=Path(path)
        if not dependency.is_absolute():
            dependency=(output/dependency).resolve()
            if not dependency.is_relative_to(output):
                failures.append('Unsafe relative dependency: '+path)
                continue
        if not dependency.is_file() or digest(dependency)!=expected: failures.append('Source changed: '+path)
    for name,expected in report.get('artifacts',{}).items():
        p=(output/name).resolve()
        if not p.is_relative_to(output) or not p.is_file() or digest(p)!=expected:failures.append('Artifact changed: '+name)
    if report.get('handoff',{}).get('schema')=='oagd.motion-handoff/1':
        # Playback reads this effective spec. Bind it to the preserved, hashed
        # original job even when the caller uses verify directly, not check.
        original_path='provenance/original-job.json'
        if original_path not in report.get('dependencies',{}):
            failures.append('Missing handoff job dependency')
        else:
            try:
                received=read(output/'job.json');original=read(output/original_path)
                if received.get('mode')!='received' or received.get('original_mode')!=original.get('mode') or received.get('spec')!=original.get('spec'):
                    failures.append('Received motion metadata changed')
            except (OSError,ValueError,TypeError):
                failures.append('Invalid received motion metadata')
    if not report.get('ok') or not report.get('artifacts'): failures.append('No completed processing evidence')
    return {'ok':not failures,'failures':failures,'quality':'requires_visual_review','engine_validation':'separate_native_capture_required'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for action in ('inspect','process'):
        cmd=sub.add_parser(action);cmd.add_argument('--blender',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
        cmd.add_argument('--input' if action=='inspect' else '--spec',type=Path,required=True)
    cmd=sub.add_parser('verify');cmd.add_argument('--output',type=Path,required=True)
    cmd=sub.add_parser('validate');cmd.add_argument('--spec',type=Path,required=True)
    cmd=sub.add_parser('suggest')
    for name in ('source_inventory','target_inventory','output'):cmd.add_argument('--'+name.replace('_','-'),required=True,type=Path)
    for name in ('source_armature','target_armature'):cmd.add_argument('--'+name.replace('_','-'),required=True)
    a=p.parse_args()
    try:
        if a.command=='suggest':
            result=suggest(read(a.source_inventory),read(a.target_inventory),a.source_armature,a.target_armature)
            with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        elif a.command=='validate':
            spec=validate(read(a.spec),a.spec.resolve().parent)
            result={'ok':True,'profile':spec.get('profile_dependency'),'mapped_bones':len(spec['mapping']),
                    'clips':[c['id'] for c in spec['clips']],'scope':'contract and dependency hashes only; actual rig diagnostics require process'}
        elif a.command=='verify': result=verify(a.output)
        elif a.command=='inspect':
            path=a.input.resolve()
            if path.suffix.lower() not in ('.blend','.fbx','.glb') or not path.is_file():raise ValueError('Expected .blend/.fbx/.glb')
            result=launch(a.blender,a.output,{'mode':'inspect','file':str(path),'sha256':digest(path)})
        else:
            spec=validate(read(a.spec),a.spec.resolve().parent)
            if any(a.output.resolve()==Path(spec[r]['file']).parent or Path(spec[r]['file']).is_relative_to(a.output.resolve()) for r in ('source','target')):
                raise ValueError('Output must be separate from input assets')
            result=launch(a.blender,a.output,{'mode':'process','spec':spec,'spec_file':str(a.spec.resolve()),'spec_sha256':digest(a.spec)})
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get('ok') else 2
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())

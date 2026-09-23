"""Engine-neutral JSON shape/value checks; operation vocabularies belong to drivers."""
import math
from pathlib import Path


def validate(request, engine, fields, required, action_fields, top_fields):
    if not isinstance(request, dict) or request.get('mode') not in {'edit','inspect','playback'}:
        raise ValueError('Request mode must be edit, inspect or playback')
    if request.get('engine') != engine:
        raise ValueError('Request engine must match the selected project engine')
    if set(request) - top_fields:
        raise ValueError('Unknown request fields: ' + str(set(request) - top_fields))
    if request['mode'] != 'edit' and request.get('operations'):
        raise ValueError('Only edit mode accepts operations')
    if request['mode'] != 'playback' and any(k in request for k in ['actions','seconds','capture_interval','max_p95_ms']):
        raise ValueError('Playback fields cannot be silently ignored')
    operations=request.get('operations', [])
    if not isinstance(operations,list): raise ValueError('operations must be an array')
    for op in operations:
        if not isinstance(op,dict) or op.get('op') not in fields:
            raise ValueError('Unsupported operation: ' + str(op))
        if set(op)-fields[op['op']]: raise ValueError('Unknown operation fields: '+str(set(op)-fields[op['op']]))
        for key in required.get(op['op'], []):
            if not op.get(key): raise ValueError(op['op']+' requires '+key)
        for key in ['position','rotation','scale']:
            if key in op: vector(op[key])
    if request['mode']=='playback':
        if not request.get('scene'): raise ValueError('Playback requires an explicit saved scene')
        for key in ['seconds','capture_interval','max_p95_ms']:
            n=request.get(key,0)
            if type(n) not in (int,float) or not math.isfinite(n) or n<0:
                raise ValueError('Playback limits must be finite nonnegative numbers')
        if not 0<request.get('seconds',0)<=120 or request.get('capture_interval',0)>120:
            raise ValueError('Playback duration/capture interval outside supported range')
        actions=request.get('actions',[])
        if not isinstance(actions,list): raise ValueError('actions must be an array')
        for a in actions:
            if (not isinstance(a,dict) or a.get('op') not in action_fields or not a.get('target')
                    or type(a.get('at')) not in (int,float) or not 0<=a['at']<request['seconds']):
                raise ValueError('Invalid timed gameplay action')
            if set(a)-action_fields[a['op']]: raise ValueError('Unknown gameplay action fields')
            if 'position' in a: vector(a['position'])


def vector(value):
    if not isinstance(value,list) or len(value)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in value):
        raise ValueError('Transform requires three finite numbers')


def playback_result(session, request, read):
    data=read(session/'playback.json')
    if (data.get('request_id')!=request['request_id'] or data.get('success') is not True
            or data.get('frames',0)<1 or data.get('actions_completed')!=len(request.get('actions',[]))):
        raise ValueError('Playback completion/evidence missing')
    frames=list((session/'frames').glob('*.png'))
    if request.get('capture_interval',0)>0 and not frames:
        raise ValueError('Recording requested but no frame files produced')
    if len(frames)!=data.get('captures',0) or any(f.stat().st_size==0 for f in frames):
        raise ValueError('Recording completion count does not match nonempty frame files')
    return data

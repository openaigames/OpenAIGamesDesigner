#!/usr/bin/env python3
"""Versioned runtime/spatial observations; no inference of missing engine facts."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
from record_io import identifier, local, read_json, write_json, now, snapshot_files, changed_files


def finite(value, label, minimum=None):
    if type(value) not in (int,float) or not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError('Invalid finite value: ' + label)


def vector(values, size, label):
    if not isinstance(values,list) or len(values) != size:
        raise ValueError('Invalid vector dimensions: ' + label)
    for value in values:
        finite(value,label)


def validate_capture(data):
    from validate_records import contract
    errors = contract('observation',data)
    if errors:
        raise ValueError('; '.join(errors))
    objects = {row['id'] for row in data['objects']}
    if len(objects) != len(data['objects']):
        raise ValueError('Duplicate observed object.')
    clocks = {row['id']:row for row in data['clocks']}
    if len(clocks) != len(data['clocks']):
        raise ValueError('Duplicate observation clock.')
    ids, last = set(), {}
    for row in data['events']:
        if row['id'] in ids or row['object'] not in objects or row['clock'] not in clocks:
            raise ValueError('Duplicate event or unknown object/clock.')
        finite(row['time'],'event time',0)
        if row['time'] < last.get(row['clock'],0):
            raise ValueError('Events must be ordered within each clock.')
        last[row['clock']] = row['time']
        ids.add(row['id'])
    for curve in data.get('curves',[]):
        if curve['object'] not in objects or curve['clock'] not in clocks:
            raise ValueError('Curve names an unknown object or clock.')
        previous = -1
        for sample in curve['samples']:
            vector(sample,2,'curve sample [time,value]')
            if sample[0] < 0 or sample[0] < previous:
                raise ValueError('Curve times must be nonnegative and ordered.')
            previous = sample[0]
    for parameter in data.get('parameters',[]):
        if parameter['object'] not in objects:
            raise ValueError('Parameter names an unknown object.')
        if type(parameter['value']) in (int,float):finite(parameter['value'],'parameter value')
    for media in data.get('media',[]):
        if media['clock'] not in clocks:
            raise ValueError('Media clock is missing.')
        previous = (-1,-1)
        for anchor in media['anchors']:
            vector(anchor,2,'media anchor [clock time, media seconds]')
            if anchor[0] < 0 or anchor[1] < 0 or anchor[0] <= previous[0] or anchor[1] <= previous[1]:
                raise ValueError('Media anchors must be strictly increasing; paused segments need separate mappings.')
            previous = anchor
    space = data.get('space')
    if space:
        dimensions = space['dimensions']
        for item in space['objects']:
            if item['id'] not in objects:
                raise ValueError('Spatial object is not declared.')
            vector(item['position'],dimensions,'object position')
            if 'bounds' in item:
                bounds = item['bounds']
                if not isinstance(bounds,list) or len(bounds) != 2:
                    raise ValueError('Bounds need minimum and maximum vectors.')
                vector(bounds[0],dimensions,'bounds minimum')
                vector(bounds[1],dimensions,'bounds maximum')
                if any(a>b for a,b in zip(*bounds)):
                    raise ValueError('Reversed object bounds.')
            for vertex in item.get('vertices',[]):
                vector(vertex,dimensions,'geometry vertex')
            for edge in item.get('edges',[]):
                if any(i>=len(item.get('vertices',[])) for i in edge):raise ValueError('Geometry edge references a missing vertex')
        for query in space.get('queries',[]):
            if query['object'] not in objects or query['clock'] not in clocks:raise ValueError('Spatial query names unknown object/clock')
            finite(query['time'],'spatial query time',0)
            for key in ['start','end']+(['point','normal'] if query['blocked'] else []):
                vector(query[key],dimensions,'query '+key)
        for route in space.get('routes',[]):
            if route['object'] not in objects or route['clock'] not in clocks:
                raise ValueError('Route names an unknown object or clock.')
            previous = -1
            for sample in route['samples']:
                vector(sample,dimensions+1,'route sample [time, position...]')
                if sample[0] < 0 or sample[0] < previous:
                    raise ValueError('Route samples must have ordered nonnegative time.')
                previous = sample[0]
    return data


def register(root, capture, observation_id, dependencies=None):
    identifier(observation_id)
    source = local(root,capture)
    data = validate_capture(read_json(source))
    files = [capture]
    if data['context'].get('run_ref'):
        files.append(data['context']['run_ref'])
    files.extend(m['path'] for m in data.get('media',[]))
    record = {'schema_version':1,'id':observation_id,'created_at':now(),'capture':capture,
              'dependencies':snapshot_files(root,list(dict.fromkeys(files + (dependencies or [])))),
              'data':data}
    path = local(root,'.openaigame/observations/'+observation_id+'.json')
    write_json(path,record,create=True)
    return record


def read(root, observation_id):
    record = read_json(local(root,'.openaigame/observations/'+identifier(observation_id)+'.json'))
    if not isinstance(record,dict) or record.get('schema_version') != 1 or record.get('id') != observation_id:
        raise ValueError('Unsupported observation record.')
    validate_capture(record['data'])
    from validate_records import contract
    errors=contract('observation-record',record)
    if errors:raise ValueError('; '.join(errors))
    if record['capture'] not in record['dependencies'] or any(m['path'] not in record['dependencies'] for m in record['data'].get('media',[])):
        raise ValueError('Observation lacks source/media version identity.')
    changes = changed_files(root,record['dependencies'])
    if record['capture'] not in changes and read_json(local(root,record['capture']))!=record['data']:
        raise ValueError('Stored observation differs from its unchanged source capture.')
    return {**record,'status':'stale' if changes else 'current','changed':changes}


def snapshots(root):
    rows, invalid = [], []
    for path in sorted(local(root,'.openaigame/observations').glob('*.json')):
        try:
            record = read(root,path.stem)
            data = record['data']
            rows.append({'id':record['id'],'status':record['status'],'changed':record['changed'],
                         'context':data['context'],'objects':data['objects'],'events':len(data['events']),
                         'space':bool(data.get('space')),'media':len(data.get('media',[])),
                         'limitations':data['limitations']})
        except (OSError,ValueError,KeyError,TypeError) as error:
            invalid.append({'path':path.relative_to(Path(root).resolve()).as_posix(),'error':str(error)})
    return {'observations':rows,'invalid':invalid}


def elapsed(data, start_id, end_id):
    """Only subtract measured times in the same clock. No guessed alignment."""
    events = {event['id']:event for event in validate_capture(data)['events']}
    start, end = events[start_id], events[end_id]
    if start['clock'] != end['clock']:
        raise ValueError('Cannot subtract different clocks without a measured mapping.')
    clock = next(c for c in data['clocks'] if c['id'] == start['clock'])
    duration = end['time'] - start['time']
    if duration < 0:
        raise ValueError('End precedes start.')
    return {'seconds':duration * (0.001 if clock['unit'] == 'milliseconds' else 1),
            'clock':clock['id'],'scope':clock['description'],
            'start':start_id,'end':end_id,'hardware_latency':'not_measured'}


def parameter_comparison(data, parameter_id):
    rows = [p for p in validate_capture(data).get('parameters',[]) if p['id'] == parameter_id]
    if not rows:
        raise ValueError('Parameter was not observed.')
    # Keep authored and measured values distinct; no computed "best" value.
    return {'id':parameter_id,'values':rows,'runtime_observed':any(p['provenance']=='runtime_readback' for p in rows)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    sub=parser.add_subparsers(dest='action',required=True)
    add=sub.add_parser('register')
    add.add_argument('--capture',required=True)
    add.add_argument('--id',required=True)
    add.add_argument('--dependency',action='append',default=[])
    show=sub.add_parser('show');show.add_argument('--id',required=True)
    sub.add_parser('list')
    duration=sub.add_parser('elapsed')
    duration.add_argument('--id',required=True);duration.add_argument('--start',required=True);duration.add_argument('--end',required=True)
    args=parser.parse_args(argv)
    try:
        root=args.project.resolve()
        if not root.is_dir():raise ValueError('Project directory does not exist.')
        if args.action=='register':result=register(root,args.capture,args.id,args.dependency)
        elif args.action=='list':result=snapshots(root)
        else:
            result=read(root,args.id)
            if args.action=='elapsed':
                if result['status']!='current':raise ValueError('Observation is stale; use its original version or recapture.')
                result=elapsed(result['data'],args.start,args.end)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(str(error),file=sys.stderr);return 2


if __name__=='__main__':
    raise SystemExit(main())

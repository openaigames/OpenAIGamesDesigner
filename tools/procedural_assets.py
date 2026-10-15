#!/usr/bin/env python3
"""Generate or merge a new static scene revision; never overwrite a hand-edited scene."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.processing.procedural_worker import write, glb


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def merge(baseline, generated, current):
    """Three-way merge at stable object boundaries. Deletions are also edits."""
    for scene in (baseline,generated,current):
        if scene.get('schema_version')!=1 or scene.get('coordinates')!='RH_Y_UP_METRES_CCW':
            raise ValueError('Incompatible scene format')
        ids=[m['id'] for m in scene['meshes']]
        if len(ids)!=len(set(ids)): raise ValueError('Duplicate object IDs')
    base={m['id']:m for m in baseline['meshes']}
    new={m['id']:m for m in generated['meshes']}
    local={m['id']:m for m in current['meshes']}
    result=copy.deepcopy(current);merged={};conflicts=[];preserved=[]
    for name in sorted(base.keys()|new.keys()|local.keys()):
        before,after,edited=base.get(name),new.get(name),local.get(name)
        if edited==before: chosen=after
        elif after==before or after==edited: chosen=edited;preserved.append(name)
        else: conflicts.append(name);continue
        if chosen is not None: merged[name]=chosen
    if conflicts: raise ValueError('Manual and generated edits conflict: '+', '.join(conflicts))
    result['meshes']=list(merged.values())
    result['revision']={'baseline':fingerprint(baseline),'generated':fingerprint(generated),
                        'current':fingerprint(current),'preserved_local_ids':preserved}
    result.pop('spec_sha256',None) # Merged contents no longer correspond to a single source spec.
    result.pop('navigation',None) # A hand edit can invalidate topology, slopes and clearance.
    result['validation']={'objects':len(merged),'triangles':sum(len(m['indices'])//3 for m in merged.values()),
                          'quality':'not_checked','note':'Merged object content; review in the target engine.'}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    build=sub.add_parser('build');build.add_argument('--spec',required=True,type=Path);build.add_argument('--output',required=True,type=Path)
    update=sub.add_parser('merge')
    for name in ('baseline','generated','current','output'):update.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    try:
        read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
        if a.action=='build': result=write(read(a.spec),a.output)
        else:
            result=merge(read(a.baseline),read(a.generated),read(a.current))
            if a.output.exists():raise ValueError('Merged output must use a new directory')
            a.output.mkdir(parents=True)
            (a.output/'scene.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
            (a.output/'scene.glb').write_bytes(glb(result))
        print(json.dumps({'output':str(a.output.resolve()),'validation':result['validation']}));return 0
    except (ValueError,OSError,KeyError,TypeError) as error: print(json.dumps({'error':str(error)}));return 1

if __name__=='__main__':raise SystemExit(main())

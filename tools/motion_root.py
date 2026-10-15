#!/usr/bin/env python3
"""Compose verified planar root clips with an existing in-place character revision."""
import argparse, copy, math, shutil
from pathlib import Path
import motion_workflow as motion

POLICY={'mode':'planar_v1','vertical':'physics','rotation':'controller','transition_s':0.0}

def settings(definitions):
    row=definitions.get('root_motion')
    if row is None:return None
    if row!=POLICY or type(row.get('transition_s')) not in (int,float) or any(k in definitions for k in ('layers','turning','locomotion')):
        raise ValueError('planar_v1 requires explicit physics height, controller rotation, immediate transitions and an unlayered graph')
    clips=definitions.get('clips',[])
    rooted=[c for c in clips if c.get('motion_owner')=='animation']
    if not rooted:raise ValueError('Root mode needs at least one animation-owned clip')
    for c in rooted:
        if c.get('in_place') is not False or c.get('loop') is not False or c.get('layer_only',False):
            raise ValueError('Root clips must be nonlooping, nonlayered and not in-place')
    return row

def check_track(frames,root,rooted):
    if not frames:raise ValueError('Missing root capture')
    p0=frames[0]['bones'][root]['p'];q0=frames[0]['bones'][root]['q']
    travelled=0.0;previous=p0
    for frame in frames:
        pose=frame['bones'][root];p=pose['p'];q=pose['q']
        if len(p)!=3 or len(q)!=4 or not all(math.isfinite(v) for v in [*p,*q]):raise ValueError('Invalid root sample')
        if abs(sum(v*v for v in q)-1)>1e-4:raise ValueError('Invalid root quaternion')
        if abs(sum(a*b for a,b in zip(q,q0)))<1-1e-7:raise ValueError('planar_v1 requires stationary root rotation')
        if (abs(p[2]-p0[2]) if rooted else math.dist(p,p0))>1e-5:raise ValueError('Vertical root motion is unsupported' if rooted else 'Root track is not in place')
        travelled+=math.dist(p,previous);previous=p
    if rooted and travelled<.001:raise ValueError('Animation-owned clip has no root displacement')

def compose(base,rooted,output):
    base=Path(base).resolve();rooted=Path(rooted).resolve();output=Path(output).resolve()
    if output.exists() or output.is_relative_to(base) or output.is_relative_to(rooted):raise ValueError('Choose a new collection directory outside both inputs')
    for source in (base,rooted):
        result=motion.verify(source)
        if not result['ok']:raise ValueError(str(result['failures']))
    a=motion.read(base/'report.json');b=motion.read(rooted/'report.json')
    if a['root_motion']['owner']!='controller' or b['root_motion']['owner']!='animation' or b['root_motion']['translation']!='scaled':raise ValueError('Expected in-place base and animation-owned rooted revision')
    if a['root_motion']['bone']!=b['root_motion']['bone']:raise ValueError('Root bone differs')
    # Full evaluated rest hierarchy must agree, not just shared display names.
    ar=motion.read(base/'target-rig.json');br=motion.read(rooted/'target-rig.json')
    if ar['bones']!=br['bones']:raise ValueError('Target rest skeleton differs')
    ids={c['id'] for c in a['clips']}
    if ids.intersection(c['id'] for c in b['clips']):raise ValueError('Clip ID collision')
    for c in b['clips']:check_track(motion.read(rooted/(c['id']+'-capture.json'))['after'],b['root_motion']['bone'],True)
    shutil.copytree(base,output)
    report=copy.deepcopy(a);report['root_motion_by_clip']={c['id']:b['root_motion'] for c in b['clips']}
    for name,sha in b['artifacts'].items():
        if any(name.startswith(c['id']+'.') or name.startswith(c['id']+'-') for c in b['clips']):
            shutil.copy2(rooted/name,output/name);report['artifacts'][name]=sha
    # Preserve dependencies as absolute resolved inputs until handoff packs them.
    deps={str((base/p).resolve()):sha for p,sha in a.get('dependencies',{}).items()}
    deps.update({str((rooted/p).resolve()):sha for p,sha in b.get('dependencies',{}).items()})
    for folder in (base,rooted):
        for name in ('report.json','job.json'):deps[str(folder/name)]=motion.digest(folder/name)
    report.pop('handoff',None);report['dependencies']=deps;report['clips']+=b['clips']
    report['root_collection']={'schema':'oagd.root-collection/1','base':str(base),'rooted':str(rooted)}
    job=motion.read(base/'job.json');job['mode']='root_compose';job['spec']['clips']+=motion.read(rooted/'job.json')['spec']['clips']
    motion.write(output/'job.json',job)
    report['dependencies'][str(output/'job.json')]=motion.digest(output/'job.json')
    motion.write(output/'report.json',report)
    return motion.verify(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--rooted',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:print(compose(a.base,a.rooted,a.output))
    except (ValueError,KeyError,OSError) as e:p.exit(2,str(e)+'\n')

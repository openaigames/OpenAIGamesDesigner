"""Author a separate, reproducible turn revision from a calibrated idle pose.

Controller owns yaw and translation. This is flat-ground stepping authoring,
not runtime IK, automatic motion capture, or arbitrary-skeleton retargeting.
"""
import argparse, json, subprocess, shutil, sys, os
from pathlib import Path
import motion_workflow as motion

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0'

def plan(base):
    base = Path(base).resolve()
    if not motion.verify(base)['ok']: raise ValueError('Verified base revision required')
    job = motion.read(base/'job.json'); profile = job['spec'].get('character_profile')
    if not profile or profile['coordinates']['target']['forward'] != '-Y':
        raise ValueError('Calibrated -Y forward character profile required')
    roles = {k:v['target'] for k,v in profile['roles'].items()}
    for side in ('L','R'):
        for name in ('thigh','shin','foot'):
            if name+'_'+side not in roles: raise ValueError('Explicit leg chains required')
    clips=[]
    for angle in (-180,-90,-45,45,90,180):
        steps=abs(angle)//45; duration=.4+steps*.6
        clips.append({'id':f'turn_{"r" if angle>0 else "l"}_{abs(angle)}',
                      'angle_deg':angle,'steps':steps,'duration_s':duration,'fps':60,
                      'lead_s':.2,'step_s':.6,'tail_s':.2})
    return {'schema':'oagd.turn-authoring/1','base':str(base),'roles':roles,
            'clips':clips,'lift_m':.075,'method':'alternating authored steps; fixed planted ankle position and orientation in controller world frame'}

def create(base,output,blender):
    spec=plan(base);out=Path(output).resolve()
    if out.exists():raise ValueError('Choose a new immutable turn revision directory')
    out.mkdir(parents=True);motion.write(out/'turn-job.json',spec)
    worker=ROOT/'adapters/processing/motion_turns_blender.py'
    shutil.copy2(worker,out/'author-worker.py')
    env=os.environ.copy();temp=out/'temp';temp.mkdir();env['TMP']=env['TEMP']=str(temp)
    with (out/'process.log').open('w',encoding='utf8') as log:
        result=subprocess.run([str(blender),'--background','--factory-startup','--python',str(worker),'--',str(out/'turn-job.json')],env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode or not (out/'turn-report.json').exists():raise ValueError('Authoring failed; see '+str(out/'process.log'))
    authored=motion.read(out/'turn-report.json')
    if not authored['ok']:raise ValueError('Evaluated turn authoring checks failed')
    base=Path(spec['base']);report=motion.read(base/'report.json');job=motion.read(base/'job.json')
    # Preserve the base clips and their provenance verbatim; append separately
    # authored clips with an explicit generator and independent evaluated capture.
    for name in report['artifacts']:shutil.copy2(base/name,out/name)
    for clip in authored['clips']:
        report['clips'].append(clip)
        job['spec']['clips'].append({'id':clip['id'],'action':clip['id'],'fps':60,'start_frame':1,'end_frame':clip['frames']})
    report['artifacts'].update(authored['artifacts'])
    report['dependencies'].update({str(base/'report.json'):motion.digest(base/'report.json'),str(out/'author-worker.py'):motion.digest(out/'author-worker.py'),str(out/'turn-job.json'):motion.digest(out/'turn-job.json')})
    report['turn_authoring']={'tool_version':VERSION,'base_revision':str(base),'manifest':'turns.json','quality':'requires native review; procedural technical motion'}
    report['artifacts']['turns.json']=motion.digest(out/'turns.json')
    report['artifacts']['turn-report.json']=motion.digest(out/'turn-report.json')
    motion.write(out/'job.json',job);motion.write(out/'report.json',report)
    return motion.verify(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--blender',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(create(a.base,a.output,a.blender)));raise SystemExit(0)
    except (ValueError,OSError,KeyError) as e:p.exit(2,str(e)+'\n')

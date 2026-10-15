"""Exercise installed quality CLI behavior with reproducible, explicitly synthetic cases."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tools'), str(ROOT/'tests')]
from test_asset_quality import picture, plan_fixture, reviewed
from adapters.assets import quality as q
from PIL import Image, ImageOps


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,default=ROOT,help='Source root or separately installed runtime to exercise')
    args=parser.parse_args()
    runtime=args.runtime.resolve()
    if not (runtime/'tools/asset_quality.py').is_file():parser.error('runtime must contain tools/asset_quality.py')
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    (output/'cli-logs').mkdir()
    env=dict(os.environ, PYTHONUTF8='1',PYTHONIOENCODING='utf-8',LOCALAPPDATA=str(output/'profile'))
    for key in ('TRIPO_API_KEY','HUNYUAN3D_API_KEY','TENCENTCLOUD_SECRET_ID','TENCENTCLOUD_SECRET_KEY',
                'TENCENTCLOUD_TOKEN','ARK_API_KEY','ELEVENLABS_API_KEY','PYTHONPATH'):
        env.pop(key,None)
    calls=[];cases=[]
    def call(root,argv,expected=0):
        guard=("import sys,runpy,socket;deny=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('Network forbidden'));"
               "socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny;"
               "script=sys.argv.pop(1);sys.path.insert(0,str(__import__('pathlib').Path(script).parent));"
               "sys.argv[0]=script;runpy.run_path(script,run_name='__main__')")
        command=[sys.executable,'-B','-X','utf8','-c',guard,str(runtime/'tools/asset_quality.py'),'--project',str(root),*argv]
        run=subprocess.run(command,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
        q.write(output/'cli-logs'/f'{len(calls)+1:03d}.json',{'command':command,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
        calls.append({'args':argv,'expected':expected,'exit':run.returncode})
        if run.returncode!=expected:raise AssertionError(run.stdout+run.stderr)
        return json.loads(run.stdout)
    for name in ('crate','scale_drift','missing_rear','mirror_pending','mirror_confirmed','symmetry_explained',
                 'perspective','cropped','occluded_landmark','side_iou','missing_door_opening','optional_wear',
                 'corrupt_image','stale_reference','unknown_citation'):
        root=output/name;root.mkdir()
        picture(root,'front.png');picture(root,'back.png',color='blue')
        plan=plan_fixture();plan['asset_id']=name
        expected='pass'
        if name=='scale_drift':
            picture(root,'back.png',box=(30,80,170,175),color='blue');expected='fail'
        elif name=='missing_rear':
            plan['views'].pop();plan['checks']=[];expected='needs_review'
        elif name.startswith('mirror'):
            with Image.open(root/'front.png') as original:ImageOps.mirror(original).save(root/'back.png')
            expected='fail' if name=='mirror_confirmed' else 'needs_review'
        elif name=='symmetry_explained':
            # Deliberately symmetric solid silhouette, viewed from opposite sides.
            from PIL import ImageDraw
            original=Image.new('RGBA',(200,200),(0,0,0,0))
            ImageDraw.Draw(original).rectangle((30,25,170,175),fill='red')
            original.save(root/'front.png');original.save(root/'back.png')
        elif name=='perspective':
            plan['views'][1]['projection']='perspective';expected='needs_review'
        elif name=='cropped':
            picture(root,'back.png',box=(0,25,170,175),color='blue');expected='needs_review'
        elif name=='occluded_landmark':
            plan['checks'][0].update(metric='landmark_height',landmark='handle',tolerance=0.02)
            for v in plan['views']:v['landmarks']={'handle':{'x':0.5,'y':0.4,'visibility':'occluded'}}
            expected='needs_review'
        elif name=='side_iou':
            plan['checks'][0].update(metric='silhouette_iou',tolerance=0.9);expected='needs_review'
        elif name=='optional_wear':
            plan['criteria'].append({'id':'wear','dimension':'style','priority':'preference','description':'Preferred light wear'})
        elif name=='missing_door_opening':
            plan['criteria'][0]['description']='Door must contain an open passage, not a solid panel';expected='fail'
        elif name=='corrupt_image':
            (root/'back.png').write_bytes(b'corrupt')
        q.write(root/'plan.json',plan)
        collected=call(root,['collect','--plan','plan.json','--output','evidence'],2 if name=='corrupt_image' else 0)
        if name=='corrupt_image':
            cases.append({'name':name,'status':'invalid image rejected'});continue
        evidence=q.read(root,'evidence/evidence.json');review=reviewed(evidence)
        if name.startswith('mirror'):
            review['findings'][0].update(status='confirmed' if name=='mirror_confirmed' else 'unknown',
                                        reason='Synthetic mirror defect fixture; not an art approval')
        if name=='missing_door_opening':
            review['criteria'][0].update(status='fail',score=0,observed='Synthetic solid rectangle has no opening',
                regions=[{'evidence':'front','x':0.2,'y':0.2,'width':0.6,'height':0.6}])
        if name=='optional_wear':review['criteria'][1].update(status='fail',score=1)
        if name=='unknown_citation':review['criteria'][0]['evidence']=['missing']
        q.write(root/'review.json',review)
        code=2 if name=='unknown_citation' else 0 if expected=='pass' else 1
        result=call(root,['assess','--evidence','evidence/evidence.json','--review','review.json','--output','assessment'],code)
        if name=='unknown_citation':
            cases.append({'name':name,'status':'invalid citation rejected'});continue
        if result['status']!=expected:raise AssertionError((name,result,expected))
        call(root,['check','--report','assessment/quality.json'],code)
        if name=='stale_reference':
            picture(root,'back.png',color='green')
            call(root,['check','--report','assessment/quality.json'],2)
        cases.append({'name':name,'status':result['status'],'expected':expected})
    q.write(output/'result.json',{'synthetic_cases':cases,'cli_calls':len(calls),'calls':calls,
        'network':'Python socket connections denied in CLI subprocesses',
        'visual_approval':'Fixture judgments only; no production art approval', 'status':'pass'})
    print(json.dumps({'status':'pass','cases':len(cases),'cli_calls':len(calls)}))


if __name__=='__main__':main()

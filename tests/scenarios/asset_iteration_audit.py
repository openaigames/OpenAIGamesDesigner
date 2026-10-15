"""Offline CLI scenarios with explicit synthetic results; no provider generation."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'tests')]
from test_asset_iteration import IterationTests
from adapters.assets import quality as q


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,default=ROOT,help='Source root or separately installed runtime to exercise')
    args=parser.parse_args();runtime=args.runtime.resolve()
    if not (runtime/'tools/asset_iterate.py').is_file():parser.error('runtime must contain tools/asset_iterate.py')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    (output/'logs').mkdir()
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',LOCALAPPDATA=str(output/'profile'))
    for key in ('TRIPO_API_KEY','HUNYUAN3D_API_KEY','TENCENTCLOUD_SECRET_ID','TENCENTCLOUD_SECRET_KEY',
                'TENCENTCLOUD_TOKEN','ARK_API_KEY','ELEVENLABS_API_KEY','PYTHONPATH'):
        env.pop(key,None)
    guard=("import sys,runpy,socket;deny=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('Network forbidden'));"
           "socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny;"
           "script=sys.argv.pop(1);sys.path.insert(0,str(__import__('pathlib').Path(script).parent));"
           "sys.argv[0]=script;runpy.run_path(script,run_name='__main__')")
    calls=[];cases=[]
    def call(root,args,expected=0,tool='asset_iterate.py'):
        command=[sys.executable,'-B','-X','utf8','-c',guard,str(runtime/'tools'/tool),'--project',str(root),*args]
        run=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=90)
        q.write(output/'logs'/f'{len(calls)+1:03d}.json',{'command':command,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
        calls.append({'tool':tool,'args':args,'expected':expected,'exit':run.returncode})
        if run.returncode!=expected:raise AssertionError(run.stdout+run.stderr)
        return json.loads(run.stdout)
    for name in ('text_model','image_reference','unsupported_prompt','missing_reference_review','regression',
                 'uncertainty','postprocess','accept','identical_result','stale_review','two_stalls','speech_text','same_payload','model_parameter'):
        case=IterationTests();case.case_root=output/name;case.preserve_artifacts=True;case.setUp()
        try:
            root=case.root
            if name in ('image_reference','unsupported_prompt','missing_reference_review','same_payload'):
                base=case.baseline('tripo','image_to_model')
            elif name=='speech_text':base=case.baseline('elevenlabs')
            elif name in ('text_model','model_parameter'):base=case.baseline('tripo')
            else:base=case.baseline()
            call(root,['draft','--report',base,'--output','draft'])
            plan=case.decision();expected=0
            if name in ('image_reference','missing_reference_review'):
                plan=case.reference_changes()
                if name=='missing_reference_review':plan['changes'].pop();expected=2
            elif name in ('unsupported_prompt','speech_text'):expected=2
            elif name=='same_payload':
                route=deepcopy(case.inputs['routes'][0]);route['evidence']='Different wording, same uploaded input.'
                plan['changes'][0].update(kind='route',value=route);expected=2
            elif name=='model_parameter':
                plan['changes'][0].update(kind='parameter',value={'key':'face_limit','value':2000})
            elif name=='uncertainty':
                base=case.quality('unknown','initial/preparation.json','unknown');plan=case.decision(base)
                plan.update(action='collect_evidence',changes=[],tasks=[{'issues':['criterion:shape'],
                    'operation':'Capture the obscured corners','expected':'All silhouette corners can be inspected'}]);expected=1
            elif name=='postprocess':
                plan.update(action='postprocess',changes=[],tasks=[{'issues':['criterion:shape'],
                    'operation':'Straighten the panel in the source asset','expected':'Rectangular silhouette with red material preserved'}]);expected=1
            elif name=='accept':
                base=case.quality('good','initial/preparation.json','pass');plan=case.decision(base)
                plan.update(action='accept',targets=[],changes=[])
            q.write(root/'decision.json',plan)
            result=call(root,['prepare','--plan','decision.json','--output','round1'],expected)
            if expected==2:
                cases.append({'name':name,'status':'invalid correction rejected'});continue
            call(root,['check','--iteration','round1/iteration.json'],expected)
            if plan['action']!='regenerate':
                assert not(root/'round1/prepared/request.json').exists()
                cases.append({'name':name,'status':result['status']});continue
            request=q.read(root,'round1/prepared/request.json')
            provider=q.read(root,'round1/iteration.json')['provider']
            job=call(root,['submit','--provider',provider,'--request','round1/prepared/request.json'],tool='asset_workflow.py')
            assert job['status']=='queued' and not job['attempts'] and job['request']['iteration']==request['iteration']
            if name=='stale_review':
                (root/'base.png').write_bytes(b'changed after iteration')
                call(root,['check','--iteration','round1/iteration.json'],2)
                cases.append({'name':name,'status':'stale evidence rejected'});continue
            after=case.after(color='fail' if name=='regression' else 'pass',shape='fail' if name=='two_stalls' else 'pass',
                             source='base.png' if name=='identical_result' else None)
            expected=1 if name in ('regression','identical_result','two_stalls') else 0
            result=call(root,['compare','--iteration','round1/iteration.json','--report',after,'--output','comparison1'],expected)
            call(root,['check','--comparison','comparison1/comparison.json'],expected)
            if name=='two_stalls':
                plan=case.decision(after,'comparison1/comparison.json');plan['changes'][0]['value']='Make the corner edges straight without changing color.'
                q.write(root/'decision2.json',plan)
                call(root,['prepare','--plan','decision2.json','--output','round2'])
                after2=case.after('candidate2',shape='fail',round_name='round2')
                result=call(root,['compare','--iteration','round2/iteration.json','--report',after2,'--output','comparison2'],1)
                assert result['recommendation']=='stop'
                plan=case.decision(after2,'comparison2/comparison.json');q.write(root/'decision3.json',plan)
                call(root,['prepare','--plan','decision3.json','--output','round3'],2)
            cases.append({'name':name,'status':result['status'],'recommendation':result['recommendation']})
        finally:case.doCleanups()
    q.write(output/'result.json',{'status':'pass','cases':cases,'cli_calls':len(calls),'calls':calls,
        'network':'Socket connections denied in CLI subprocesses','execution':'Generation jobs queued only',
        'quality':'Synthetic result images and explicit fixture judgments; no cloud model quality claim'})
    print(json.dumps({'status':'pass','cases':len(cases),'cli_calls':len(calls)}))


if __name__=='__main__':main()

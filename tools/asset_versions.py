#!/usr/bin/env python3
"""Save asset revisions, select an existing revision, or record native tool outputs."""
import argparse,json,sys
from pathlib import Path
import asset_workflow
from workbench import asset_versions as versions
from game_workflow import atomic_json

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,required=True)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('list')
    sub.add_parser('link-job').add_argument('--job',required=True)
    for name in ('apply','record-native'):
        sub.add_parser(name).add_argument('--request',required=True)
    args=parser.parse_args();root=args.project.resolve()
    try:
        if args.action=='list':result=versions.snapshot(root)
        elif args.action=='link-job':
            path,job=asset_workflow.read_job(root,args.job);asset_workflow.register_version(root,path,job);result=job
        else:
            spec=json.loads(versions.safe(root,args.request).read_text('utf-8-sig'))
            if args.action=='apply':result=versions.mutate(root,spec)
            else:
                request={'parameters':{'prompt':spec.get('prompt','')},'inputs':spec.get('inputs',[])}
                if spec.get('lineage'):request['lineage']=spec['lineage']
                if spec.get('art_record'):request['art_record']=spec['art_record']
                job=asset_workflow.read_job(root,spec['job'])[1] if spec.get('job') else asset_workflow.new_job(root,'image',request,{'mode':'host'})
                if job['provider']!='image' or job['status']!='queued':raise ValueError('请选择待执行的内置生图任务')
                for entry in job['request']['inputs']:
                    path=versions.safe(root,entry['snapshot'])
                    if not path.is_file() or versions.digest(path)!=entry['sha256']:raise ValueError('实际输入快照已变化，不能登记为该次生成结果')
                if spec.get('output_sets') is not None:job['output_sets']=spec['output_sets']
                job['artifacts']=asset_workflow.artifacts(root,root,{'artifacts':[{'path':p} for p in spec['outputs']]},job)
                job.update(status='registered',execution_source=versions.text(spec['tool'],'制作工具',100))
                job['notes'].append('已登记宿主工具的实际输出')
                atomic_json(asset_workflow.location(root,job['job_id'])/'job.json',job)
                asset_workflow.register_version(root,asset_workflow.location(root,job['job_id'])/'job.json',job)
                if job.get('version_registration_error'):raise ValueError(job['version_registration_error'])
                if job.get('art_registration_error'):raise ValueError(job['art_registration_error'])
                result={**job['asset_version'],'job':job['job_id']}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if any(result.get(k) for k in ('art_registration_error','version_registration_error','artRegistrationError')) else 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())

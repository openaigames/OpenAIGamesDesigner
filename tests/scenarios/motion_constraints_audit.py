"""Audit actual evaluated native bone/prop readback, independently of either solver."""
import json,math,sys,argparse
from pathlib import Path

def audit(report,bindings):
 d=json.loads(Path(report).read_text());b=json.loads(Path(bindings).read_text())['constraints'];checks=[];metrics={}
 def check(name,ok,detail=None):checks.append({'name':name,'ok':bool(ok),'detail':detail})
 rows=d['frames'];cases={n:[r for r in rows if r['case'].lower()==n] for n in {r['case'].lower() for r in rows}}
 check('22 native scenarios',len(cases)==22,sorted(cases))
 def values(x):
  if isinstance(x,dict):
   for v in x.values():yield from values(v)
  elif isinstance(x,list):
   for v in x:yield from values(v)
  elif isinstance(x,(int,float)):yield x
 check('finite observations',all(math.isfinite(n) for n in values(rows)))
 for name,rs in cases.items():
  check(name+' sampled to completion',len(rs)>40 and rs[-1]['t']>=2.19)
  check(name+' bounded envelopes',all(all(0<=w<=1.00001 for w in r['weights']) and 0<=r['grip_weight']<=1.00001 and abs(r['pelvis'])<=b['feet']['max_pelvis_m']+.001 for r in rs))
 # Limb lengths are observed after source animation, pelvis, IK and native import.
 for chain in [b['feet']['left'],b['feet']['right'],b['grip']['offhand']]:
  for a,z in zip(chain,chain[1:]):
   lengths=[math.dist(r['bones'][a],r['bones'][z]) for r in rows]
   check('no stretch '+a,max(lengths)-min(lengths)<.0006,[min(lengths),max(lengths)])
 feet_errors=[]
 for case in ('flat','slope','step_up','step_down','feet_only'):
  for i,side in enumerate(('left','right')):
   chain=b['feet'][side];rs=[r for r in cases[case] if r['t']>.4 and r['weights'][i]>.999 and r['feet_status'][i]=='contact']
   check(case+' '+side+' actual contact samples',len(rs)>30)
   errors=[math.dist(r['bones'][chain[2]],r['goals'][i]) for r in rs];feet_errors+=errors
   check(case+' '+side+' ankle reaches terrain goal',bool(errors) and max(errors)<.002,max(errors,default=None))
   knees=[sum((r['bones'][chain[1]][j]-r['bones'][chain[0]][j])*r['forward'][j] for j in range(3)) for r in rs]
   check(case+' '+side+' knee remains forward',bool(knees) and min(knees)>-.005,min(knees,default=None))
 check('step has two actual foot heights',max(abs(r['bones'][b['feet']['left'][2]][2]-r['bones'][b['feet']['right'][2]][2]) for r in cases['step_up'])>.08)
 check('pelvis compensates descent',min(r['pelvis'] for r in cases['step_down'])<-.07)
 for name,status in [('no_ground','no_ground'),('steep','slope_limit'),('high_step','step_limit'),('foot_reach','unreachable')]:
  check(name+' explicit fallback',any(status in r['feet_status'] for r in cases[name]))
  check(name+' rejected limb releases',any(r['t']>.7 and any(r['feet_status'][i]==status and r['weights'][i]<.001 for i in range(2)) for r in cases[name]))
 air=cases['air_land'];check('native jump',max(r['actor'][2] for r in air)-min(r['actor'][2] for r in air)>.4)
 check('air release',any(r['t']>.65 and r['feet_status']==['airborne','airborne'] and max(r['weights'])<.001 for r in air))
 check('landing recovery',all(r['feet_status']==['contact','contact'] and min(r['weights'])>.999 for r in air if r['t']>1.8))
 check('left swing releases independently',any(r['weights'][0]<.001 and r['weights'][1]>.999 for r in cases['swing']))
 hand=b['grip']['offhand'][2];grip_errors=[]
 for case in ('two_hand','carry','turn','switch','regrab','grip_only'):
  rs=[r for r in cases[case] if r['grip_weight']>.999 and r['grip_status']=='contact'];errors=[math.dist(r['bones'][hand],r['support']) for r in rs];grip_errors+=errors
  check(case+' actual support samples',len(rs)>10)
  check(case+' support error',bool(errors) and max(errors)<.003,max(errors,default=None))
 for case in ('single_hand','feet_only'):check(case+' no support influence',all(r['grip_weight']==0 for r in cases[case]))
 check('grip-only leaves feet disabled',all(max(r['weights'])==0 and r['feet_status']==['disabled','disabled'] for r in cases['grip_only']))
 for case in ('two_hand','carry','turn','switch'):
  check(case+' contact window opens and closes',any(0<r['grip_weight']<1 for r in cases[case]) and all(r['grip_weight']<.001 for r in cases[case] if r['t']>2.0))
 for case in ('cancel','drop'):
  rs=[r for r in cases[case] if r['t']>1.15];check(case+' releases',all(not r['holding'] and r['grip_weight']==0 for r in rs));check(case+' prop stays at release transform',max(math.dist(r['prop'],rs[0]['prop']) for r in rs)<.0001)
 check('destroyed target reported',any(r['grip_status']=='missing_target' for r in cases['lost_target']))
 check('destroyed target clears constraint',all(not r['holding'] and r['grip_weight']==0 for r in cases['lost_target'] if r['t']>1.2))
 check('unreachable support falls back',all(r['grip_weight']==0 and r['grip_status']=='unreachable' for r in cases['unreachable'] if .7<r['t']<1.7))
 check('carry actually moves',math.dist(cases['carry'][-1]['actor'],cases['carry'][0]['actor'])>.5)
 check('turn actually rotates',sum(cases['turn'][-1]['forward'][i]*cases['turn'][0]['forward'][i] for i in range(3))<.1)
 check('switch uses actual native carry clock',any(r['state'].lower()=='carry' and r['clock']>.2 for r in cases['switch']))
 negatives=[e for e in d['events'] if e['kind'] in ('config_rejected','missing_request_rejected')]
 check('five native invalid requests rejected',len(negatives)==5 and all(e['ok'] for e in negatives))
 metrics={'max_foot_error_m':max(feet_errors,default=None),'max_support_error_m':max(grip_errors,default=None),'frames':len(rows),'cases':len(cases),'engine':d['engine']}
 return {'ok':all(c['ok'] for c in checks),'checks':checks,'metrics':metrics,'scope':'native evaluated bones and actual prop; visual review recorded separately'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('bindings');p.add_argument('--output');a=p.parse_args();r=audit(a.report,a.bindings)
 if a.output:Path(a.output).write_text(json.dumps(r,indent=2))
 print(json.dumps({'ok':r['ok'],'checks':len(r['checks']),'metrics':r['metrics'],'failures':[c for c in r['checks'] if not c['ok']]},indent=2));sys.exit(not r['ok'])

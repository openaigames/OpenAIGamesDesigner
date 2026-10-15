#!/usr/bin/env python3
"""Audit actual native root-motion reports; never manufactures runtime samples."""
import argparse,collections,copy,json,math
from pathlib import Path
CASES=('dash','roll','diagonal','wall','wall_diagonal','slow','fast','variable','pause','cancel','reentry','restart','controller_takeover','root_takeover')
def audit(report):
 # UE FName is case-insensitive; cooked name pools can preserve another casing.
 # Normalize identity in a copy only. Raw evidence and all measurements remain unchanged.
 report=copy.deepcopy(report)
 for event in report['events']:
  for key in ('action','name'):
   if key in event:event[key]=event[key].lower()
 for frame in report['frames']:
  frame['state']=frame['state'].lower()
  assert len({k.lower() for k in frame['bones']})==len(frame['bones'])
  frame['bones']={(k[:-1]+k[-1].upper() if k.lower().endswith(('_l','_r')) else k.lower()):v for k,v in frame['bones'].items()}
 groups=collections.defaultdict(list)
 for f in report['frames']:groups[f['case']].append(f)
 checks=[];metrics={}
 def check(name,ok,actual=None):checks.append({'name':name,'ok':bool(ok),'actual':actual})
 check('all_14_cases',set(groups)==set(CASES))
 for name in CASES:
  f=groups[name]
  if not f:continue
  ev=[e for e in report['events'] if e['case']==name]
  end=f[-1]['actor'];extracted=[sum(x['requested'][i] for x in f) for i in range(3)]
  metrics[name]={'final_m':end,'extracted_m':extracted,'frames':len(f)}
  check(name+'/requests_accepted',all(e['ok'] for e in ev if e['kind']=='request') and any(e['kind']=='request' for e in ev))
  check(name+'/native_extraction',math.hypot(*extracted[:2])>.1,extracted)
  check(name+'/grounded_planar',max(abs(x['actor'][2]) for x in f)<.055)
  check(name+'/root_locked_to_actor',max(math.dist(x['bones']['dst_root'][:2],x['actor'][:2]) for x in f)<.012)
  check(name+'/no_negative_forward_step',min(x['actual'][0] for x in f)>-.004)
  check(name+'/released_owner',not f[-1]['active'] and f[-1]['state']=='idle')
  markers=[e for e in ev if e['kind']=='marker'];keys=[(e['run'],e['name']) for e in markers]
  check(name+'/markers_once',len(keys)==len(set(keys)))
  check(name+'/marker_count',len(markers)==(0 if name=='cancel' else 1),len(markers))
  completed=[e for e in ev if e['kind']=='ended' and e['action'] in ('dash','roll') and e['name']=='completed']
  check(name+'/completed_count',len(completed)==(0 if name=='cancel' else 1),len(completed))
  if name in ('dash','roll','diagonal','slow','fast','variable','pause'):
   distance=2 if name=='roll' else 2.4
   target=[distance,0] if name!='diagonal' else [distance/math.sqrt(2)]*2
   check(name+'/distance_from_authored_track',math.dist(end[:2],target)<.012,end[:2])
   check(name+'/no_controller_double_motion',math.dist(end[:2],extracted[:2])<.012)
  if name not in ('controller_takeover','root_takeover'):
   idle=[x for x in f if x['t']>2.3]
   check(name+'/no_residual_after_end',math.dist(idle[0]['actor'][:2],idle[-1]['actor'][:2])<.003)
 for name in ('wall','wall_diagonal'):
  f=groups[name];end=f[-1]['actor'];check(name+'/capsule_wall_clearance',1.23<end[0]<1.253,end[0])
  check(name+'/blocked_distance_discarded',metrics[name]['extracted_m'][0]-end[0]>.3)
  off=[x for x in f if x['t']>1.7];check(name+'/wall_removed_no_catchup',math.dist(off[0]['actor'][:2],off[-1]['actor'][:2])<.003)
 check('wall_diagonal/native_slide',abs(groups['wall_diagonal'][-1]['actor'][1]-2.4/math.sqrt(2))<.012)
 paused=[x for x in groups['pause'] if .58<x['t']<.94]
 check('pause/clock_and_position_frozen',len(paused)>5 and max(x['clock'] for x in paused)-min(x['clock'] for x in paused)<1e-5 and math.dist(paused[0]['actor'][:2],paused[-1]['actor'][:2])<.003)
 cancelled=[x for x in groups['cancel'] if x['t']>.65]
 check('cancel/no_drift',math.dist(cancelled[0]['actor'][:2],cancelled[-1]['actor'][:2])<.003)
 partial=groups['cancel'][-1]['actor'][0]
 for name in ('reentry','restart'):check(name+'/starts_new_delta_without_rewind',abs(groups[name][-1]['actor'][0]-partial-2.4)<.015)
 check('controller_takeover/real_controller_movement',abs(groups['controller_takeover'][-1]['actor'][0]-2.9)<.045)
 check('root_takeover/no_controller_inertia',2.5<groups['root_takeover'][-1]['actor'][0]<2.65)
 strike=min((x for x in groups['dash'] if x['active']),key=lambda x:abs(x['clock']-.6))
 forward=strike['bones']['dst_hand_R'][0]-strike['bones']['dst_upperarm_R'][0]
 check('dash/hand_in_front_of_shoulder',forward>.15,forward)
 return {'ok':all(c['ok'] for c in checks),'checks':checks,'failures':[c for c in checks if not c['ok']],'metrics':metrics,'scope':'14 scripted native cases; no human playtest or final animation quality approval'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=audit(json.loads(a.report.read_text(encoding='utf-8-sig')))
 if a.output:a.output.write_text(json.dumps(r,indent=2),encoding='utf8')
 print(json.dumps({'ok':r['ok'],'checks':len(r['checks']),'failures':r['failures']},indent=2));raise SystemExit(not r['ok'])

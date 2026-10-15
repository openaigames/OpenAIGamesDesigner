"""Native external-clip replacement audit; reads immutable runtime captures."""
from pathlib import Path
import json,math,collections,sys
from motion_layers_audit import canonical,sub,dot,norm,cross,dist,qangle

def audit(path,baseline,source_revision,bindings):
 path,baseline,source_revision,bindings=map(Path,(path,baseline,source_revision,bindings))
 d=canonical(json.loads(path.read_text()));base=canonical(json.loads(baseline.read_text()));binding=json.loads(bindings.read_text());rows={c['id']:c for c in binding['clips']};frames=d['frames'];checks=[]
 def check(name,ok,measured):checks.append({'name':name,'ok':bool(ok),'measured':measured})
 check('native sequence completes',len(frames)>300 and frames[-1]['t']>=12.39,{'frames':len(frames),'time':frames[-1]['t']})
 check('independent baseline follows identical sample schedule',len(frames)==len(base['frames']) and all(abs(f['t']-g['t'])<1e-5 for f,g in zip(frames,base['frames'])),{'baseline_frames':len(base['frames'])})
 check('no native clock disagreement',not d['layer_faults'],d['layer_faults'])
 up=[0,1,0] if d['engine']=='godot' else [0,0,1]
 def local(f,bone):
  v=sub(f['bones'][bone]['p'],f['bones']['dst_root']['p']);fw=f['forward'];right=cross(fw,up) if d['engine']=='godot' else cross(up,fw)
  return [dot(v,right),dot(v,up),dot(v,fw)]
 lower=['dst_root','dst_hips','dst_thigh_L','dst_thigh_R','dst_shin_L','dst_shin_R','dst_foot_L','dst_foot_R']
 mask_p=[];mask_q=[];upper_effect=[];lower_effect=[];full_error=[];details=[];rotation_samples=[]
 source=json.loads((source_revision/'external_gait-capture.json').read_text())['after'];spec=json.loads((source_revision/'job.json').read_text())['spec'];roles=spec['character_profile']['roles'];root=roles['root']['target'];reference=None
 def sample(t,name):
  a=min(int(t*30+1e-5),len(source)-1);z=min(a+1,len(source)-1);alpha=max(0,min(1,t*30-a));p0=sub(source[a]['bones'][name]['p'],source[a]['bones'][root]['p']);p1=sub(source[z]['bones'][name]['p'],source[z]['bones'][root]['p']);p=[x+(y-x)*alpha for x,y in zip(p0,p1)]
  q0=source[a]['bones'][name]['q'];q1=source[z]['bones'][name]['q'];sgn=1 if dot(q0,q1)>=0 else -1;q=[(1-alpha)*x+alpha*y*sgn for x,y in zip(q0,q1)];q=[v/norm(q) for v in q]
  return [-p[0],p[2],-p[1]],q
 for i,f in enumerate(frames):
  g=base['frames'][i] if i<len(base['frames']) else None;s=f['layers'];u=s['upper'];v=s['full']
  if g and v['weight']<1e-6:
   for role in lower:mask_p.append(dist(local(f,role),local(g,role)));mask_q.append(qangle(f['bones'][role]['q'],g['bones'][role]['q']))
   if u['active'] and f['speed_mps']>.1:upper_effect.append(dist(local(f,'dst_hand_R'),local(g,'dst_hand_R')))
  if v['active'] and v['action']=='full_external' and v['weight']>.99999 and abs(v['mix']-v['bank'])<1e-5:
   expected={role:sample(v['position_s'],roles[role.removeprefix('dst_')]['target']) for role in f['bones'] if role!='dst_root'}
   for role,(pos,q) in expected.items():
    error=dist(local(f,role),pos);full_error.append(error)
    if error>.002:details.append({'t':f['t'],'position_s':v['position_s'],'role':role,'error_m':error})
   if reference is None:reference=(f,expected)
   else:
    rf,re=reference
    for role,(pos,q) in expected.items():rotation_samples.append(abs(qangle(f['bones'][role]['q'],rf['bones'][role]['q'])-qangle(q,re[role][1])))
   if g:lower_effect.append(max(dist(local(f,role),local(g,role)) for role in lower))
 check('new full clip agrees with DCC position',bool(full_error) and max(full_error)<.002,{'samples':len(full_error),'max_error_m':max(full_error,default=None),'failures':sorted(details,key=lambda r:r['error_m'],reverse=True)[:8]})
 check('bone rotation change magnitude agrees with DCC',bool(rotation_samples) and max(rotation_samples)<.2,{'samples':len(rotation_samples),'max_error_deg':max(rotation_samples,default=None),'scope':'Coordinate-invariant relative angle magnitude; does not alone prove rotation axis or skin quality'})
 check('upper mask preserves lower body',bool(mask_p) and max(mask_p)<.0001 and max(mask_q)<.02,{'max_position_m':max(mask_p,default=None),'max_rotation_deg':max(mask_q,default=None)})
 check('second source changes arms while moving and full-body legs',upper_effect and max(upper_effect)>.02 and lower_effect and max(lower_effect)>.01,{'moving_upper_samples':len(upper_effect),'max_hand_m':max(upper_effect,default=None),'max_leg_m':max(lower_effect,default=None)})
 requests={(r['channel'],r['run']):r for r in d['layer_requests'] if r['op']=='play' and r['accepted']};events=collections.defaultdict(list)
 for e in d['layer_events']:events[e['channel'],e['run']].append(e)
 errors=[]
 for key,r in requests.items():
  ev=events[key];ends=[e for e in ev if e['kind']=='ended'];marks=[e for e in ev if e['kind']=='marker']
  if len(ends)!=1:errors.append([key,'end count',len(ends)]);continue
  expected=[e['name'] for e in rows[r['action']]['markers'] if e['at_s']<=ends[0]['total_s']+1e-5]
  if [e['name'] for e in marks]!=expected or ev[-1]['kind']!='ended':errors.append([key,'marker interval/order'])
  for e in marks:
   marker=next(m for m in rows[r['action']]['markers'] if m['name']==e['name'])
   if abs(e['at_s']-marker['at_s'])>1e-5:errors.append([key,'wrong event timestamp'])
 check('accepted actions have ordered once-only events',len(requests)==4 and set(events)==set(requests) and not errors,{'accepted_runs':len(requests),'failures':errors})
 cancelled=[e for e in d['layer_events'] if e['kind']=='ended' and e['name']=='cancelled']
 check('cancellation stops events and clears weight',len(cancelled)==1 and all(not frames[-1]['layers'][c]['active'] and frames[-1]['layers'][c]['weight']<1e-6 for c in ('upper','full')),{'cancelled':len(cancelled),'last':frames[-1]['layers']})
 check('second-source alias is the actual requested resource',rows['full_external']['clip']=='external_gait' and abs(rows['full_external']['duration_s']-1.9)<1e-6 and all(r['action']=='full_external' for r in requests.values()),rows['full_external'])
 if d.get('variable_fps'):check('variable physical steps actually occur',all(any(abs(f['dt']-v)<.001 for f in frames) for v in (1/30,1/60)),sorted(set(round(f['dt'],5) for f in frames)))
 result={'ok':all(c['ok'] for c in checks),'checks':checks,'failures':[c['name'] for c in checks if not c['ok']],'source':str(path),'baseline':str(baseline),'scope':'Second source natural native playback and masking; no contact/loop claim or final art/human approval'}
 path.with_name('audit.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
 result=audit(*sys.argv[1:5]);print(json.dumps({'ok':result['ok'],'checks':len(result['checks']),'failures':result['failures']}));raise SystemExit(0 if result['ok'] else 1)

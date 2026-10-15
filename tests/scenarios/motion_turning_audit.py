"""Audit native evaluated legs, all declared turn contacts and control recovery."""
from pathlib import Path
import json,math,sys
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(v):return math.sqrt(dot(v,v))
def dist(a,b):return norm(sub(a,b))
def angle(a,b):return math.degrees(math.acos(max(-1,min(1,dot(a,b)/max(1e-12,norm(a)*norm(b))))))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def audit(path):
 d=json.loads(path.read_text());frames=d['frames'];up=[0,1,0] if d['engine']=='godot' else [0,0,1]
 for f in frames:f['bones']={k[:-1]+k[-1].upper() if k.endswith(('_l','_r')) else k:v for k,v in f['bones'].items()}
 checks=[]
 def check(name,ok,data):checks.append({'name':name,'ok':bool(ok),'measured':data})
 def local(f,n):
  p=sub(f['bones'][n]['p'],f['actor']);fw=f['forward'];return [dot(p,cross(fw,up)),dot(p,up),dot(p,fw)]
 segments=[];active={};knees=[];turns=[];last=None;pause=0.;maxstep=0.;maxyaw=0.;maxmove=0.;steady=[];lococontacts=[];locoseg={}
 def close(segment,kind):
  if len(segment)<2:return
  values=[dist(f['p'],segment[0]['p']) for f in segment];q=segment[0]['q'];rotation=max(math.degrees(2*math.acos(min(1,abs(dot(f['q'],q))))) for f in segment)
  entry={'start':segment[0]['t'],'end':segment[-1]['t'],'drift_m':max(values),'rotation_deg':rotation,'kind':kind}
  (segments if kind.startswith('turn_') else lococontacts).append(entry)
 for i,f in enumerate(frames):
  prev=frames[i-1] if i else f;dt=f['t']-prev['t'];reset=prev['t']<37<=f['t']+1e-5
  if i and not reset:
   maxstep=max(maxstep,max(dist(local(f,n),local(prev,n))/max(dt*30,1e-8) for n in f['bones']))
   maxyaw=max(maxyaw,angle(f['forward'],prev['forward'])/dt)
   if f['paused'] and prev['paused']:pause=max(pause,dist(f['actor'],prev['actor']),*(dist(f['bones'][n]['p'],prev['bones'][n]['p']) for n in f['bones']))
  if f['state'].startswith('turn_'):
   if last!=f['state']:turns.append({'clip':f['state'],'start':f['t'],'forward_start':prev['forward']})
   turns[-1].update(end=f['t'],forward_end=f['forward'],max_position=f['position_s'])
   maxmove=max(maxmove,f['speed_mps'])
   steps=int(f['state'].split('_')[-1])//45;u=(f['position_s']-.2)/.6;step=math.floor(u);phase=u-step;lead='R' if '_r_' in f['state'] else 'L'
   for side in ('L','R'):
    lo,hi=(.1,.45) if side==lead else (.55,.9)
    planted=u<0 or u>=steps or not lo<phase<hi
    # The lead-in is included: all planted contacts are measured, including blends.
    key=(f['state'],side)
    if planted:active.setdefault(key,[]).append({'t':f['t'],**f['bones']['dst_foot_'+side]})
    elif key in active:close(active.pop(key),f['state'])
  else:
   for key,s in active.items():close(s,key[0])
   active={}
  if f['state']=='locomotion' and not f['paused'] and f['floor'] and f['transition_age_s']>=.2:
   phase=f['clip_times']['walk']%1
   for side,lo,hi in [('L',1/6,1/3),('R',2/3,5/6)]:
    if lo<=phase<=hi:locoseg.setdefault(side,[]).append({'t':f['t'],**f['bones']['dst_foot_'+side]})
    elif side in locoseg:close(locoseg.pop(side),'start_stop_walk_run')
  else:
   for s in locoseg.values():close(s,'start_stop_walk_run')
   locoseg={}
  for side in ('L','R'):
   if 'dst_shin_'+side not in f['bones']:continue
   hip=local(f,'dst_thigh_'+side);knee=local(f,'dst_shin_'+side);foot=local(f,'dst_foot_'+side)
   bend=180-angle(sub(hip,knee),sub(foot,knee));axis=sub(foot,hip);v=sub(knee,hip);projected=sub(v,[x*dot(v,axis)/dot(axis,axis) for x in axis]);knees.append({'t':f['t'],'bend_deg':bend,'forward_m':projected[2]})
  last=f['state']
 for key,s in active.items():close(s,key[0])
 for s in locoseg.values():close(s,'start_stop_walk_run')
 check('complete 40 second native run',frames[-1]['t']>=39.99 and len(frames)>1000,{'seconds':frames[-1]['t'],'frames':len(frames)})
 check('both left and right 45/90 plus reversal consumed',{'turn_l_45','turn_r_45','turn_l_90','turn_r_90'}.issubset({t['clip'] for t in turns}) and any('180' in t['clip'] for t in turns),[t['clip'] for t in turns])
 maxdrift=max((s['drift_m'] for s in segments),default=1e9);maxrot=max((s['rotation_deg'] for s in segments),default=1e9)
 check('all planted turn windows including entry blend',len(segments)>30 and maxdrift<.01,{'segments':len(segments),'max_drift_m':maxdrift,'budget_m':.01})
 check('planted foot orientation',maxrot<3,{'max_deg':maxrot,'budget_deg':3})
 check('turn has stopped translation',maxmove<.006,maxmove)
 check('moving/start/stop stance remains bounded',bool(lococontacts) and max(s['drift_m'] for s in lococontacts)<.035,{'segments':len(lococontacts),'max_m':max((s['drift_m'] for s in lococontacts),default=None)})
 check('no pose discontinuity',maxstep<.12,{'max_m_per_30hz':maxstep,'budget':.12})
 check('bounded yaw',maxyaw<242,maxyaw)
 check('whole character pause',sum(f['paused'] for f in frames)>=10 and pause<1e-5,pause)
 check('knees observed without backward bend',len(knees)>2000 and min((k['forward_m'] for k in knees),default=-1)>-.005,{'samples':len(knees),'min_forward_m':min((k['forward_m'] for k in knees),default=None),'max_bend_deg':max((k['bend_deg'] for k in knees),default=None)})
 check('no unintended airborne state',all(f['floor'] for f in frames if f['t']>.2),True)
 check('turning recovers to travel after queued input',any(f['t']>32 and f['t']<34 and f['speed_mps']>.1 for f in frames),max(f['speed_mps'] for f in frames if 32<f['t']<34))
 check('gesture events and reset unaffected',d['marker_count']==2 and d['completed_runs']==2 and d['generation']==1,{'markers':d['marker_count'],'completed':d['completed_runs'],'generation':d['generation']})
 gesture=[]
 for f in frames:
  if 38.55<f['t']<38.75:gesture.append((local(f,'dst_forearm_R')[2]-local(f,'dst_upperarm_R')[2],local(f,'dst_hand_R')[2]-local(f,'dst_upperarm_R')[2]))
 check('independent forward shoulder elbow wrist',bool(gesture) and min(v[0] for v in gesture)>.05 and min(v[1] for v in gesture)>.12,gesture)
 if d.get('variable_fps'):check('30 and 60 Hz actually sampled',all(any(abs(f['dt']-step)<.001 for f in frames) for step in (1/30,1/60)),sorted(set(round(f['dt'],5) for f in frames)))
 result={'ok':all(c['ok'] for c in checks),'checks':checks,'turns':turns,'turn_contacts':segments,'locomotion_contacts':lococontacts,'failures':[c['name'] for c in checks if not c['ok']],'source':str(path),'scope':'native evaluated pose/feet; scripted controller input, no human artistic acceptance'}
 path.with_name('audit.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':
 r=audit(Path(sys.argv[1]));print(json.dumps({k:v for k,v in r.items() if k not in ('turn_contacts','locomotion_contacts','turns')},indent=2));sys.exit(0 if r['ok'] else 1)

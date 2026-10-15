"""Independent audit of native evaluated bones; no expected pose generator."""
import json,sys,math,statistics
from pathlib import Path
W=Path(__file__).resolve().parent
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(v):return math.sqrt(dot(v,v))
def dist(a,b):return norm(sub(a,b))
def yawdiff(a,b):return math.degrees(math.acos(max(-1,min(1,dot(a,b)))))
def audit(path):
 d=json.loads(path.read_text());frames=d['frames'];up=[0,1,0] if d['engine']=='godot' else [0,0,1];vertical=1 if d['engine']=='godot' else 2
 for f in frames:f['bones']={(k[:-1]+k[-1].upper() if k.endswith(('_l','_r')) else k):v for k,v in f['bones'].items()}
 def local(f,name):
  p=sub(f['bones'][name]['p'],f['actor']);fw=f['forward'];right=[fw[1]*up[2]-fw[2]*up[1],fw[2]*up[0]-fw[0]*up[2],fw[0]*up[1]-fw[1]*up[0]]
  return [dot(p,right),dot(p,up),dot(p,fw)]
 failures=[];checks=[]
 def check(name,ok,measured):
  checks.append({'name':name,'ok':bool(ok),'measured':measured})
  if not ok:failures.append(name)
 check('complete native timeline',frames[-1]['t']>=22 and len(frames)>600,{'duration':frames[-1]['t'],'samples':len(frames)})
 check('native values finite',all(math.isfinite(v) for f in frames for b in f['bones'].values() for v in b['p']+b['q']),True)
 phase=[];samples=[];groups={k:[] for k in ('steady_walk','steady_run','steady_blend','start_stop','speed_change','turn')};active={}
 maximum_step=(0,None);maximum_turn=0;paused_drift=0;pause_samples=0
 def finish_contact(segment):
  if len(segment)<2:return
  # Classify the entire uninterrupted stance interior. Never reset an anchor
  # simply because acceleration changes halfway through the contact window.
  categories={f['category'] for f in segment}
  category=next((c for c in ('turn','start_stop','speed_change') if c in categories),segment[0]['category'])
  groups[category].append(segment)
 for i,f in enumerate(frames):
  if i==0:continue
  prev=frames[i-1];dt=f['t']-prev['t'];reset=prev['t']<19.3<=f['t']+.00001
  if not reset:
   maximum_turn=max(maximum_turn,yawdiff(f['forward'],prev['forward'])/dt)
   for b in f['bones']:
    step=dist(local(f,b),local(prev,b))/(dt*30)
    if step>maximum_step[0]:maximum_step=(step,{'time':f['t'],'bone':b,'state':f['state']})
  if f['paused'] and prev['paused']:
   pause_samples+=1;paused_drift=max(paused_drift,dist(f['actor'],prev['actor']),*(dist(f['bones'][b]['p'],prev['bones'][b]['p']) for b in f['bones']))
  if f['state']=='locomotion' and not f['paused'] and f['speed_mps']>.02:
   w=f['clip_times']['walk'];r=f['clip_times']['run']/.6;e=abs(w-r)%1;phase.append(min(e,1-e))
  speedchange=abs(f['speed_mps']-prev['speed_mps'])/dt;turn=yawdiff(f['forward'],prev['forward'])/dt
  if f['state']!='locomotion' or not f['floor'] or f['paused'] or f['transition_age_s']<.2 or reset:
   for segment in active.values():finish_contact(segment)
   active={};continue
  phasevalue=f['clip_times']['walk']%1
  for side,lo,hi in [('L',1/6,1/3),('R',2/3,5/6)]:
   category='turn' if turn>5 else 'start_stop' if f['move_weight']<.999 else 'speed_change' if speedchange>.02 else 'steady_walk' if f['run_weight']<.001 else 'steady_run' if f['run_weight']>.999 else 'steady_blend'
   if side in active and not lo<=phasevalue<=hi:finish_contact(active.pop(side))
   if lo<=phasevalue<=hi:active.setdefault(side,[]).append({'t':f['t'],'p':f['bones']['dst_foot_'+side]['p'],'phase':phasevalue,'category':category})
 for segment in active.values():finish_contact(segment)
 contacts={}
 for category,segments in groups.items():
  values=[{'start':s[0]['t'],'end':s[-1]['t'],'drift_m':max(dist(f['p'],s[0]['p']) for f in s),'duration_s':s[-1]['t']-s[0]['t']} for s in segments]
  contacts[category]={'segments':values,'max_drift_m':max((v['drift_m'] for v in values),default=None)}
 check('walk and run native phase agreement',bool(phase) and max(phase)<.0001,max(phase,default=None))
 check('pose continuity per 30 Hz equivalent',maximum_step[0]<.12,{'max_step_m':maximum_step[0],'at':maximum_step[1],'budget_m':.12})
 check('bounded project turn speed',maximum_turn<242,maximum_turn)
 check('whole pose and actor pause',pause_samples>=10 and paused_drift<.00001,{'samples':pause_samples,'max_drift_m':paused_drift})
 for name,budget in [('steady_walk',.003),('steady_run',.003),('steady_blend',.008),('start_stop',.08),('speed_change',.08),('turn',.20)]:
  c=contacts[name];check('contact '+name,c['max_drift_m'] is not None and c['max_drift_m']<budget,{'max_drift_m':c['max_drift_m'],'budget_m':budget,'segments':len(c['segments'])})
 states={f['state'] for f in frames};check('jump fall land and gesture consumed',{'jump','fall','land','action_v2'}.issubset(states),sorted(states))
 check('only requested jump becomes airborne',not any(not f['floor'] and not 11.5<f['t']<12.8 and f['t']>.2 for f in frames),[f['t'] for f in frames if not f['floor'] and not 11.5<f['t']<12.8 and f['t']>.2][:4])
 check('gesture and cancellation events',d['marker_count']==2 and d['completed_runs']==2,{'markers':d['marker_count'],'completed':d['completed_runs']})
 reentry=[f['position_s'] for f in frames if 17.45<f['t']<17.64 and f['state']=='action_v2']
 check('same action really restarts during fade-out',len(reentry)>=3 and max(reentry)<.3 and max(reentry)-min(reentry)>.05,reentry)
 check('session restart',d['generation']==1,d['generation'])
 directions=[]
 for f in frames:
  if 20.55<f['t']<20.75:
   shoulder=local(f,'dst_upperarm_R');elbow=local(f,'dst_forearm_R');wrist=local(f,'dst_hand_R')
   directions.append({'elbow_forward_m':elbow[2]-shoulder[2],'wrist_forward_m':wrist[2]-shoulder[2]})
 check('independent anatomical forward gesture',bool(directions) and min(x['elbow_forward_m'] for x in directions)>.05 and min(x['wrist_forward_m'] for x in directions)>.12,directions)
 if d.get('variable_fps'):check('both frame steps actually observed',any(abs(f['dt']-1/30)<.001 for f in frames) and any(abs(f['dt']-1/60)<.001 for f in frames),sorted(set(round(f['dt'],5) for f in frames)))
 result={'ok':not failures,'failures':failures,'checks':checks,'contacts':contacts,'source':str(path),'method':'world-space evaluated ankle drift during shared authored stance interiors; transition categories separate; no runtime foot IK; pose positions expressed in actual actor forward frame','limits':'scripted control, no human acceptance; turning feet are not fixed pivots'}
 path.with_name('audit.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':
 r=audit(Path(sys.argv[1]));print(json.dumps({k:v for k,v in r.items() if k!='contacts'},indent=2));sys.exit(0 if r['ok'] else 1)

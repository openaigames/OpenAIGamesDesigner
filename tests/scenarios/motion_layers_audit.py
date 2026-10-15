"""Independent audit of native layer events, baseline poses and full-body source capture.

No engine or event stream is simulated here. Input must be recorded native output.
"""
import json,math,sys,hashlib,collections
from pathlib import Path

def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(v):return math.sqrt(dot(v,v))
def dist(a,b):return norm(sub(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def qangle(a,b):return math.degrees(2*math.acos(min(1,abs(dot(a,b))/max(1e-20,norm(a)*norm(b)))))
def canonical(report):
 for f in report['frames']:
  f['bones']={k[:-1]+k[-1].upper() if k.endswith(('_l','_r')) else k:v for k,v in f['bones'].items()}
  # UE serializes these FName control identifiers using its name-table casing,
  # which differs between editor and packaged builds. Normalize identifiers
  # only; retain every recorded pose, clock, action and marker unchanged.
  if report['engine']=='unreal' and 'layers' in f:
   layers={k.lower():v for k,v in f['layers'].items()}
   if len(layers)!=len(f['layers']):raise ValueError('Duplicate layer channel after FName normalization')
   f['layers']=layers
 if report['engine']=='unreal':
  for row in report.get('layer_requests',[])+report.get('layer_events',[]):
   if 'channel' in row:row['channel']=row['channel'].lower()
   if 'op' in row:row['op']=row['op'].lower()
   if 'reason' in row:row['reason']=row['reason'].lower()
 return report

def audit(path,baseline,revision,bindings):
 path,baseline,revision,bindings=map(Path,(path,baseline,revision,bindings))
 d=canonical(json.loads(path.read_text()));base=canonical(json.loads(baseline.read_text()));b=json.loads(bindings.read_text());rows={c['id']:c for c in b['clips']};frames=d['frames'];events=d['layer_events'];requests=d['layer_requests'];checks=[]
 def check(name,ok,data):checks.append({'name':name,'ok':bool(ok),'measured':data})
 check('completed native run',frames[-1]['t']>=39.99 and len(frames)>1000,{'frames':len(frames),'seconds':frames[-1]['t']})
 check('actual clocks agree',not d['layer_faults'],d['layer_faults'])
 check('baseline is a matching independent native run',d['engine']==base['engine'] and not base['layer_events'] and len(frames)==len(base['frames']) and all(abs(x['t']-y['t'])<1e-5 for x,y in zip(frames,base['frames'])),{'baseline':str(baseline),'frames':len(base['frames'])})
 # Every accepted logical run must finish exactly once. An idempotent request is not a new run.
 runs={(r['channel'],r['run']):r for r in reversed(requests) if r['op']=='play' and r['accepted']}
 grouped=collections.defaultdict(list)
 for e in events:grouped[(e['channel'],e['run'])].append(e)
 problems=[];marker_count=0
 for key,req in runs.items():
  emitted=grouped[key];ends=[e for e in emitted if e['kind']=='ended'];marks=[e for e in emitted if e['kind']=='marker'];row=rows[req['action']]
  if len(ends)!=1:problems.append([key,'end count',len(ends)]);continue
  end=ends[0];duration=row['duration_s'];limit=end['total_s']
  if end['name']=='callback_cancelled':limit=min(limit,.65)
  expected=[(cycle,m['name']) for cycle in range(int((limit+1e-5)/duration)+1 if row['loop'] else 1) for m in row['markers'] if cycle*duration+m['at_s']<=limit+1e-5]
  actual=[(e['cycle'],e['name']) for e in marks];marker_count+=len(marks)
  if actual!=expected:problems.append([key,'marker intervals',expected,actual])
  if emitted[-1]['kind']!='ended' or any(e['action']!=req['action'] or e['weight']<=.001 for e in marks):problems.append([key,'inactive or invisible event'])
  if any(x['t']>y['t']+1e-6 for x,y in zip(emitted,emitted[1:])):problems.append([key,'unordered'])
 check('ordered once-only events from actual native intervals',bool(runs) and not problems and set(grouped)==set(runs),{'runs':len(runs),'markers':marker_count,'failures':problems})
 reasons={r.get('reason') for r in requests if r['op']=='play' and not r['accepted']}
 check('priority, busy banks, full override and project movement guards exercised',{'priority','transition_busy','full_override','project_motion'}<=reasons,sorted(reasons))
 endings=collections.Counter(e['name'] for e in events if e['kind']=='ended')
 check('all cancellation and completion paths exercised',{'completed','cancelled','interrupted','overridden','reset','weight_zero','callback_cancelled'}<=set(endings),dict(endings))
 pause=0.;hold=0.;lower_p=[];lower_q=[];upper_diff=[];full_lower=[];maxstep=0.;reset_times=[14,28,34];forward=[];base_motion=0
 up=[0,1,0] if d['engine']=='godot' else [0,0,1]
 def local(f,name):
  p=sub(f['bones'][name]['p'],f['bones']['dst_root']['p']);fw=f['forward'];right=cross(fw,up) if d['engine']=='godot' else cross(up,fw)
  return [dot(p,right),dot(p,up),dot(p,fw)]
 lower=['dst_root','dst_hips','dst_thigh_L','dst_thigh_R','dst_shin_L','dst_shin_R','dst_foot_L','dst_foot_R']
 for i,f in enumerate(frames):
  g=base['frames'][i] if i<len(base['frames']) else None;s=f['layers'];u=s['upper'];v=s['full'];prev=frames[i-1] if i else f
  if g and v['weight']<1e-6:
   for k in lower:lower_p.append(dist(local(f,k),local(g,k)));lower_q.append(qangle(f['bones'][k]['q'],g['bones'][k]['q']))
   if u['weight']>.1:upper_diff.append(dist(local(f,'dst_hand_R'),local(g,'dst_hand_R')))
  if g and v['action']=='full_tuck' and v['weight']>.999:
   full_lower.append(max(dist(local(f,k),local(g,k)) for k in lower))
  if u['active'] and f['state']=='locomotion' and f['speed_mps']>.1:base_motion+=1
  if i and f['paused'] and prev['paused']:
   pause=max(pause,dist(f['actor'],prev['actor']),*(dist(f['bones'][k]['p'],prev['bones'][k]['p']) for k in f['bones']))
  if i and u['active'] and u['rate']==0 and prev['layers']['upper']['rate']==0:hold=max(hold,abs(u['total_s']-prev['layers']['upper']['total_s']))
  reset=any(prev['t']<t+1e-4<=f['t']+1e-4 for t in reset_times)
  if i and not reset and f['dt']<.1 and prev['layers']['upper']['run']==u['run']:
   maxstep=max(maxstep,max(dist(local(f,k),local(prev,k)) for k in f['bones'])/(f['dt']*30))
  if u['action']=='upper_wave' and u['weight']>.999 and .5<u['position_s']<.7 and v['weight']<1e-6:
   shoulder=local(f,'dst_upperarm_R');forward.append([local(f,'dst_forearm_R')[2]-shoulder[2],local(f,'dst_hand_R')[2]-shoulder[2]])
 check('upper mask preserves every lower-body sample',bool(lower_p) and max(lower_p)<.0001 and max(lower_q)<.02,{'samples':len(lower_p),'max_position_m':max(lower_p,default=None),'max_rotation_deg':max(lower_q,default=None)})
 check('upper pose visibly changes while base moves',base_motion>100 and upper_diff and max(upper_diff)>.1,{'moving_samples':base_motion,'max_hand_difference_m':max(upper_diff,default=0)})
 check('full mask actually changes legs',full_lower and max(full_lower)>.01,{'samples':len(full_lower),'max_lower_difference_m':max(full_lower,default=0)})
 check('pause and zero layer rate hold their respective clocks',sum(f['paused'] for f in frames)>5 and pause<1e-5 and hold<1e-7,{'paused_pose_drift_m':pause,'zero_rate_clock_drift_s':hold})
 check('gesture elbow and wrist face forward',bool(forward) and min(v[0] for v in forward)>.04 and min(v[1] for v in forward)>.1,{'samples':len(forward),'min_elbow_m':min((v[0] for v in forward),default=None),'min_wrist_m':min((v[1] for v in forward),default=None)})
 # Compare two requests of the same clip at the same native phase. Half weight
 # must produce an intermediate pose, rather than just reporting a changed value.
 half=[(i,f) for i,f in enumerate(frames) if 29<f['t']<30 and .45<f['layers']['upper']['position_s']<.7]
 whole=[(i,f) for i,f in enumerate(frames) if 35<f['t']<36 and .4<f['layers']['upper']['position_s']<.75]
 ratios=[]
 for i,f in half:
  if not whole:break
  j,g=min(whole,key=lambda x:abs(x[1]['layers']['upper']['position_s']-f['layers']['upper']['position_s']))
  small=dist(local(f,'dst_hand_R'),local(base['frames'][i],'dst_hand_R'));large=dist(local(g,'dst_hand_R'),local(base['frames'][j],'dst_hand_R'))
  if large>.1:ratios.append(small/large)
 check('partial weight actually blends the evaluated hand pose',bool(ratios) and min(ratios)>.35 and max(ratios)<.75,{'samples':len(ratios),'min_ratio':min(ratios,default=None),'max_ratio':max(ratios,default=None),'method':'matched native phase, same gesture at 0.5 vs 1.0, subtract independent base pose'})
 check('native weights bounded and settled after actions',all(0<=s[k]['weight']<=1.00001 and 0<=s[k]['mix']<=1.00001 for f in frames for s in [f['layers']] for k in ('upper','full')) and all(not frames[-1]['layers'][k]['active'] and frames[-1]['layers'][k]['weight']<1e-6 for k in ('upper','full')),{'last':frames[-1]['layers'],'max_step_m_per_30hz':maxstep})
 # Full-weight unmasked native pose must agree with the source at the observed sequence time.
 source_errors=[];source_detail=[];captures={};cache={};roles=json.loads((revision/'job.json').read_text())['spec']['character_profile']['roles']
 for f in frames:
  s=f['layers']['full']
  if not s['action'] or s['weight']<.99999 or abs(s['mix']-s['bank'])>1e-5:continue
  name=rows[s['action']]['clip'];t=s['position_s']
  # An ended/cancelled layer keeps fading while its bank continues: only active samples have a current observed time.
  if not s['active']:continue
  if name not in cache:
   file=revision/(name+'-capture.json');cache[name]=json.loads(file.read_text())['after'];captures[file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
  clip=cache[name];a=min(int(t*30+1e-5),len(clip)-1);z=min(a+1,len(clip)-1);alpha=max(0,min(1,t*30-a));root=roles['root']['target']
  for role in f['bones']:
   if role=='dst_root':continue
   name2=roles[role.removeprefix('dst_')]['target'];p0=sub(clip[a]['bones'][name2]['p'],clip[a]['bones'][root]['p']);p1=sub(clip[z]['bones'][name2]['p'],clip[z]['bones'][root]['p']);p=[x+(y-x)*alpha for x,y in zip(p0,p1)];expected=[-p[0],p[2],-p[1]];error=dist(local(f,role),expected);source_errors.append(error)
   if error>.002:source_detail.append({'t':f['t'],'role':role,'action':s['action'],'error_m':error})
 check('full native pose agrees with Blender capture',bool(source_errors) and max(source_errors)<.002,{'samples':len(source_errors),'max_error_m':max(source_errors,default=None),'failures':sorted(source_detail,key=lambda x:x['error_m'],reverse=True)[:5],'captures':captures})
 if d.get('variable_fps'):check('both 30 and 60 Hz really sampled',all(any(abs(f['dt']-v)<.001 for f in frames) for v in (1/30,1/60)),sorted(set(round(f['dt'],5) for f in frames)))
 if 'hitch' in d['scenario']:
  bursts=collections.Counter((e['t'],e['channel'],e['run']) for e in events if e['kind']=='marker')
  check('one native evaluation crosses multiple loop boundaries',max(bursts.values())>=6,{'max_markers_in_frame':max(bursts.values())})
 result={'ok':all(c['ok'] for c in checks),'checks':checks,'failures':[c['name'] for c in checks if not c['ok']],'source':str(path),'baseline':str(baseline),'scope':'Technical native layers, scripted input; no human play or final artistic certification'}
 path.with_name('audit.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
 r=audit(*sys.argv[1:5]);print(json.dumps({'ok':r['ok'],'checks':len(r['checks']),'failures':r['failures']},indent=2));sys.exit(0 if r['ok'] else 1)

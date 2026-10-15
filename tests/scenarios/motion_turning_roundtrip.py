"""Independent source/import comparison during native, unblended turn playback."""
import sys,json,math,hashlib
from pathlib import Path
from motion_turning_audit import sub,dot,dist,cross
def check(path,revision):
 d=json.loads(path.read_text());rev=Path(revision);profile=json.loads((rev/'job.json').read_text())['spec']['character_profile'];roles=profile['roles'];cache={};errors=[];details=[];captures={}
 for f in d['frames']:
  name=f['state'];t=f['position_s']
  if not name.startswith('turn_') or t<.2:continue
  if name not in cache:
   file=rev/(name+'-capture.json');cache[name]=json.loads(file.read_text())['after'];captures[file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
  clip=cache[name];i=min(int(t*60+1e-5),len(clip)-1);j=min(i+1,len(clip)-1);alpha=max(0,min(1,t*60-i))
  bones={k[:-1]+k[-1].upper() if k.endswith(('_l','_r')) else k:v for k,v in f['bones'].items()}
  up=[0,1,0] if d['engine']=='godot' else [0,0,1];fw=f['forward'];right=cross(fw,up) if d['engine']=='godot' else cross(up,fw)
  for role,bone in bones.items():
   if role=='dst_root':continue
   source=roles[role.removeprefix('dst_')]['target'];root=roles['root']['target']
   a=sub(clip[i]['bones'][source]['p'],clip[i]['bones'][root]['p']);b=sub(clip[j]['bones'][source]['p'],clip[j]['bones'][root]['p']);p=[x+(y-x)*alpha for x,y in zip(a,b)];expected=[-p[0],p[2],-p[1]]
   actual=sub(bone['p'],bones['dst_root']['p']);actual=[dot(actual,right),dot(actual,up),dot(actual,fw)];error=dist(actual,expected);errors.append(error)
   if error>.002:details.append({'t':f['t'],'clip':name,'role':role,'error_m':error,'actual':actual,'source':expected})
 result={'ok':bool(errors) and max(errors)<.002,'max_bone_error_m':max(errors,default=None),'samples':len(errors),'failures':sorted(details,key=lambda x:x['error_m'],reverse=True)[:5],'source_captures':captures,'method':'actual native bone positions relative to stationary root, anatomical forward/right/up; compared with Blender evaluated baked capture at observed native sequence time, after entry blend; 2 mm budget'}
 path.with_name('roundtrip.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':print(json.dumps(check(Path(sys.argv[1]),Path(sys.argv[2])),indent=2))

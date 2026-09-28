"""Portable animation evidence tools. No third-party Python packages required.

The analyzer flags geometric/timing risks; it never approves subjective animation quality.
"""
from pathlib import Path
import argparse, bisect, copy, hashlib, html, json, math, re, sys

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def local(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('Manifest path escapes workspace: ' + str(relative))
    return p

def add(a,b): return [x+y for x,y in zip(a,b)]
def sub(a,b): return [x-y for x,y in zip(a,b)]
def mul(a,s): return [x*s for x in a]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def distance(a,b): return norm(sub(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rotate(q,v):
    u=q[:3];return add(v,add(mul(cross(u,v),2*q[3]),mul(cross(u,cross(u,v)),2)))
def point(transform,v): return add(transform['p'],rotate(transform['q'],[a*b for a,b in zip(v,transform['s'])]))
def qangle(a,b): return math.degrees(2*math.acos(min(1,abs(dot(a,b)))))

def asset_paths(m):
    paths=list(m.get('evidence_dependencies',[]))
    paths.extend(c['fbx'] for c in m['clips'])
    return sorted(set(paths))

def asset_snapshot(m,root):
    return {p:digest(local(root,p)) if local(root,p).is_file() else None for p in asset_paths(m)}

def segment_distance(p1,q1,p2,q2):
    # Closest points on finite segments; includes crossing and degenerate segments.
    d1=sub(q1,p1);d2=sub(q2,p2);r=sub(p1,p2);a=dot(d1,d1);e=dot(d2,d2);f=dot(d2,r)
    clamp=lambda x:max(0,min(1,x))
    if a<=1e-12 and e<=1e-12:return distance(p1,p2)
    if a<=1e-12:s=0;t=clamp(f/e)
    else:
        c=dot(d1,r)
        if e<=1e-12:t=0;s=clamp(-c/a)
        else:
            b=dot(d1,d2);den=a*e-b*b;s=clamp((b*f-c*e)/den) if den>1e-12 else 0
            t=(b*s+f)/e
            if t<0:t=0;s=clamp(-c/a)
            elif t>1:t=1;s=clamp((b-c)/a)
    return distance(add(p1,mul(d1,s)),add(p2,mul(d2,t)))

def validate_capture(c):
    if c.get('schema')=='animlab.capture/2':
        from pipeline_v2 import validate_capture as validate_v2
        return validate_v2(c)
    if c.get('schema')!='animlab.capture/1':raise ValueError('Unsupported capture schema')
    names=[b['name'] for b in c['bones']]
    if len(names)!=len(set(names)) or not names:raise ValueError('Invalid bone identifiers')
    for i,b in enumerate(c['bones']):
        if not -1<=b['parent']<i:raise ValueError('Bones must be in parent-before-child order')
    ids=set()
    for clip in c['clips']:
        if clip['id'] in ids:raise ValueError('Duplicate clip')
        ids.add(clip['id'])
        if len(clip['frames'])<2:raise ValueError('Insufficient samples: '+clip['id'])
        previous=-1
        for f in clip['frames']:
            if not math.isfinite(f['t']) or f['t']<=previous:raise ValueError('Non-monotonic sample clock')
            previous=f['t']
            if len(f['pose'])!=len(names):raise ValueError('Bone count mismatch')
            for t in f['pose']+[f['weapon']]:
                if len(t['p'])!=3 or len(t['q'])!=4 or len(t['s'])!=3:raise ValueError('Malformed transform')
                if not all(math.isfinite(v) for k in ['p','q','s'] for v in t[k]):raise ValueError('Non-finite pose')
                if abs(norm(t['q'])-1)>.015:raise ValueError('Non-unit quaternion')
    return names

def validate_manifest(m, root=None):
    if m.get('schema')=='animlab.manifest/2':
        from pipeline_v2 import validate as validate_v2
        return validate_v2(m,root)
    if m.get('schema')!='animlab.manifest/1':raise ValueError('Unsupported manifest schema')
    if m.get('space',{}).get('units')!='cm':raise ValueError('This adapter expects canonical centimeters')
    if m['root_motion_owner'] not in ('character','animation'):raise ValueError('Choose exactly one root motion owner')
    ids=[]
    for c in m['clips']:
        if not re.fullmatch(r'[a-z][a-z0-9_]*',c['id']):raise ValueError('Unsafe clip identifier')
        ids.append(c['id'])
        if c['fps']<=0 or c['duration_s']<=0:raise ValueError('Invalid timing')
        if not 0<=c['timing']['contact_s']<=c['duration_s']:raise ValueError('Contact outside clip')
        if c['weapon'] not in m['weapons']:raise ValueError('Unknown weapon')
        for e in c.get('weapon_events',[]):
            if e['weapon'] not in m['weapons'] or not 0<=e['t']<=c['duration_s']:raise ValueError('Invalid weapon event')
        if root:local(root,c['fbx'])
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate clip ids')
    for w in m['weapons'].values():
        if len(w['binding']['q'])!=4 or abs(norm(w['binding']['q'])-1)>.015:raise ValueError('Invalid binding quaternion')
    return m

def init_workspace(root, capture_path):
    root=Path(root).resolve();capture_path=Path(capture_path).resolve();c=read(capture_path);validate_capture(c)
    if (root/'manifest.json').exists():raise ValueError('Manifest exists; create a new revision instead of overwriting edits')
    rig=read(root/'source/rig.json');clips=[]
    for clip in c['clips']:
        item={k:copy.deepcopy(v) for k,v in clip.items() if k!='frames'}
        item['duration_s']=clip['frames'][-1]['t']
        item['fbx']='exports/'+clip['id']+'.fbx';item['ue_asset']='/Game/AnimationLab/Clips/'+clip['id']+'.'+clip['id']
        item['foot_contacts']=[];item['stance_in']='needs_review';item['stance_out']='needs_review'
        events=[]
        for f in clip['frames']:
            w=f.get('weapon_id',clip['weapon'])
            if not events or events[-1]['weapon']!=w:events.append({'t':f['t'],'weapon':w})
        item['weapon_events']=events;clips.append(item)
    m={'schema':'animlab.manifest/1','revision':'baseline-r1','space':c['space'],'rig':rig,
       'root_motion_owner':'character','baseline_capture':str(capture_path.relative_to(root).as_posix()),
       'weapons':c['weapons'],'clips':clips,
       'tolerances':{'grip_cm':3,'hand_step_cm':18,'contact_gap_cm':8,'roundtrip_position_cm':1,'roundtrip_rotation_deg':2,'floor_penetration_cm':3,'foot_slide_cm':3},
       'tolerance_status':'Initial diagnostic values; calibrate to rig, contact markers and intended motion before approval.',
       'body_proxies':[{'id':'torso','a':'pelvis','b':'spine_05','radius_cm':15},{'id':'head','a':'head','b':'head','radius_cm':11}],
       'provenance':{'baseline_sha256':digest(capture_path),'reference_fbx_sha256':digest(root/rig['reference_fbx'])}}
    m['evidence_dependencies']=[rig['reference_fbx'],'source/AnimationLab.blend']+['unreal/Content/'+x['ue_asset'].split('.')[0].removeprefix('/Game/')+'.uasset' for x in clips]
    validate_manifest(m,root);write(root/'manifest.json',m)
    review={'schema':'animlab.review/1','manifest_sha256':digest(root/'manifest.json'),'report_sha256':None,'reviewer':None,'clips':{x['id']:{'decision':'needs_review','evidence':[],'waivers':[],'notes':'Watch normal speed and slow motion from front, side, gameplay view; confirm source, grip, feet, transition and contact.'} for x in clips}}
    write(root/'review.json',review)
    return {'manifest':str(root/'manifest.json'),'clips':len(clips),'status':'baseline_not_approved'}

def analyze(manifest_path,capture_path,report_path,compare_path=None):
    if read(manifest_path).get('schema')=='animlab.manifest/2':
        from pipeline_v2 import analyze as analyze_v2
        return analyze_v2(manifest_path,capture_path,report_path,compare_path)
    mp=Path(manifest_path).resolve();m=validate_manifest(read(mp),mp.parent);data=read(capture_path);names=validate_capture(data);ix={n:i for i,n in enumerate(names)}
    baseline=read(compare_path) if compare_path else None
    if baseline:validate_capture(baseline)
    old={c['id']:c for c in baseline['clips']} if baseline else {}
    if baseline and [b['name'] for b in baseline['bones']]!=names:raise ValueError('Roundtrip skeleton ordering mismatch')
    settings=m['tolerances'];specs={c['id']:c for c in m['clips']};rows=[];issues=[]
    if {c['id'] for c in data['clips']}!=set(specs):raise ValueError('Capture clip set differs from manifest')
    if baseline and set(old)!=set(specs):raise ValueError('Comparison clip set differs from manifest')
    for c in data['clips']:
        spec=specs[c['id']];fs=c['frames'];metrics={'right_grip_cm':0,'left_grip_cm':None,'hand_step_cm':0,'proxy_overlap_frames':0,'contact_gap_cm':None,'foot_slide_cm':None,'root_travel_cm':0}
        collision_times=[];tips=[];worst={};source_frame=fs[0]
        for j,f in enumerate(fs):
            w=m['weapons'][f.get('weapon_id',c['weapon'])];wp=f['weapon'];a=point(wp,w['segment_a']);b=point(wp,w['segment_b']);tips.append(b)
            for side,bone in [('right','hand_r'),('left','hand_l')]:
                if side in w['grips'] and bone in ix:
                    key=side+'_grip_cm';d=distance(point(wp,w['grips'][side]),f['pose'][ix[bone]]['p'])
                    if d>(metrics[key] or 0):metrics[key]=d;worst[key]=f['t']
            overlaps=False
            for proxy in m['body_proxies']:
                if proxy['a'] in ix and proxy['b'] in ix:
                    body_a=f['pose'][ix[proxy['a']]]['p'];body_b=f['pose'][ix[proxy['b']]]['p']
                    if segment_distance(a,b,body_a,body_b)<w['radius_cm']+proxy['radius_cm']:overlaps=True
            if overlaps:collision_times.append(f['t'])
            if j:
                jump=max(distance(f['pose'][ix[n]]['p'],fs[j-1]['pose'][ix[n]]['p']) for n in ['hand_r','hand_l'] if n in ix)
                if jump>metrics['hand_step_cm']:metrics['hand_step_cm']=jump;worst['hand_step_cm']=f['t']
            if 'root' in ix:metrics['root_travel_cm']=max(metrics['root_travel_cm'],distance(f['pose'][ix['root']]['p'],source_frame['pose'][ix['root']]['p']))
        metrics['proxy_overlap_frames']=len(collision_times)
        contact=min(range(len(fs)),key=lambda j:abs(fs[j]['t']-spec['timing']['contact_s']))
        f=fs[contact];w=m['weapons'][f.get('weapon_id',c['weapon'])];reach=spec['test_distance_cm']
        metrics['contact_gap_cm']=max(0,segment_distance(point(f['weapon'],w['segment_a']),point(f['weapon'],w['segment_b']),[reach,0,50],[reach,0,160])-35-w['radius_cm'])
        metrics['contact_sample_s']=f['t']
        speeds=[distance(tips[j],tips[j-1])/(fs[j]['t']-fs[j-1]['t']) for j in range(1,len(fs))]
        metrics['tip_peak_speed_cm_s']=max(speeds);metrics['tip_peak_time_s']=fs[1+speeds.index(max(speeds))]['t']
        metrics['contact_to_peak_s']=spec['timing']['contact_s']-metrics['tip_peak_time_s']
        for window in spec.get('foot_contacts',[]):
            selected=[f for f in fs if window['start_s']<=f['t']<=window['end_s']]
            if selected and window['bone'] in ix:
                positions=[f['pose'][ix[window['bone']]]['p'][:2]+[0] for f in selected]
                metrics['foot_slide_cm']=max(metrics['foot_slide_cm'] or 0,max(distance(positions[0],p) for p in positions))
        def flag(code,reason,time=None):
            issues.append({'id':c['id']+':'+code,'clip':c['id'],'code':code,'reason':reason,'time_s':time,'classification':'requires_inspection'})
        for side in ['right','left']:
            key=side+'_grip_cm'
            if metrics[key] is not None and metrics[key]>settings['grip_cm']:flag(key,'Hand origin differs from declared grip marker',worst.get(key))
        if collision_times:flag('proxy_intersection','Weapon/body proxy overlap. Confirm actual mesh intersection in Blender; this is not a mesh collision verdict.',collision_times[0])
        if metrics['hand_step_cm']>settings['hand_step_cm']:flag('pose_jump','Large adjacent sample hand displacement; inspect phase/transition',worst.get('hand_step_cm'))
        if metrics['contact_gap_cm']>settings['contact_gap_cm']:flag('contact_gap','Declared hit reach exceeds weapon contact with the reference target at the event',f['t'])
        if metrics['foot_slide_cm'] is not None and metrics['foot_slide_cm']>settings['foot_slide_cm']:flag('foot_slide','Foot moved during an authored planted interval')
        if c['id'] in old:
            target=old[c['id']]['frames'];ts=[x['t'] for x in target];pos_error=angle_error=weapon_error=0
            if abs(fs[0]['t']-ts[0])>.0001 or abs(fs[-1]['t']-ts[-1])>.0001:raise ValueError('Roundtrip start/end coverage mismatch')
            for f in fs:
                k=bisect.bisect_left(ts,f['t']);choices=[max(0,k-1),min(k,len(ts)-1)];ref=target[min(choices,key=lambda i:abs(ts[i]-f['t']))]
                if abs(ref['t']-f['t'])>1/60+.0001:raise ValueError('Roundtrip time coverage mismatch')
                pos_error=max(pos_error,max(distance(a['p'],b['p']) for a,b in zip(f['pose'],ref['pose'])))
                angle_error=max(angle_error,max(qangle(a['q'],b['q']) for a,b in zip(f['pose'],ref['pose'])))
                weapon_error=max(weapon_error,distance(f['weapon']['p'],ref['weapon']['p']))
            metrics['roundtrip_position_cm']=pos_error;metrics['roundtrip_rotation_deg']=angle_error
            metrics['roundtrip_weapon_cm']=weapon_error
            if pos_error>settings['roundtrip_position_cm'] or angle_error>settings['roundtrip_rotation_deg']:flag('roundtrip_drift','FBX/engine pose differs from runtime source; inspect scale, hierarchy, rest pose or sampling')
            if weapon_error>settings['roundtrip_position_cm']:flag('roundtrip_weapon_drift','Weapon attachment differs between source and engine')
        rows.append({'id':c['id'],'metrics':metrics,'status':'needs_review','foot_contact_status':'sampled' if spec.get('foot_contacts') else 'not_measured_no_authored_contact_intervals'})
    report={'schema':'animlab.audit/1','manifest_sha256':digest(mp),'capture_sha256':digest(capture_path),'capture_path':str(Path(capture_path).resolve()),'stage':data.get('stage'),
            'comparison_sha256':digest(compare_path) if compare_path else None,'comparison_path':str(Path(compare_path).resolve()) if compare_path else None,'asset_sha256':asset_snapshot(m,mp.parent),'clips':rows,'issues':issues,'animation_quality':'not_approved','limitations':['Proxy overlap is a screening signal, not proof of skin/weapon mesh intersection.','Foot sliding is not evaluated without authored contact intervals.','Geometric contact and timing do not establish subjective impact feel.','Capture is sampled; thin fast intersections between samples may be missed.']}
    write(report_path,report);render_report(report,Path(report_path).with_suffix('.html'))
    return {'report':str(report_path),'clips':len(rows),'issues':len(issues),'status':'needs_review'}

def render_report(r,path):
    esc=lambda x:html.escape(str(x))
    if r.get('schema')=='animlab.audit/2':
        body=''.join('<h2>'+esc(c['id'])+'</h2><table>'+''.join('<tr><td>'+esc(k)+'</td><td>'+esc(v)+'</td></tr>' for k,v in {**c['checks'],**c['metrics']}.items())+'</table>' for c in r['clips'])
        body+='<h2>需要定位的实际样本</h2>'+''.join('<p>'+esc(i['id'])+' · '+esc(i['time_s'])+' s · '+esc(i['reason'])+'</p>' for i in r['issues'])
        path.write_text('<!doctype html><meta charset="utf-8"><title>Animation evidence</title><style>body{font:16px system-ui;margin:40px;max-width:1000px}td{padding:8px;border-bottom:1px solid #ccd}p{line-height:1.6}</style><h1>'+esc(r['mode'])+' 动画诊断</h1><p>自动指标用于定位；实际蒙皮、手指、连续性和打击感仍需播放评审。</p>'+body,encoding='utf-8')
        return
    rows=''.join('<tr><td>'+esc(c['id'])+'</td>'+''.join('<td>'+('—' if c['metrics'].get(k) is None else f"{c['metrics'][k]:.2f}")+'</td>' for k in ['right_grip_cm','left_grip_cm','contact_gap_cm','hand_step_cm','proxy_overlap_frames','roundtrip_position_cm'])+'</tr>' for c in r['clips'])
    issues=''.join('<li><strong>'+esc(i['id'])+'</strong> · '+esc(i['time_s'])+' s<br>'+esc(i['reason'])+'</li>' for i in r['issues'])
    doc='''<!doctype html><meta charset="utf-8"><title>Animation Lab · 动作诊断</title><style>body{background:#121820;color:#e9eff6;font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px}h1{font-size:32px}p{line-height:1.8;color:#b5c7d8}.tag{color:#ffc570}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:12px;border-bottom:1px solid #34414f;text-align:left}th{color:#85cde6}li{margin:20px 0;line-height:1.7}code{overflow-wrap:anywhere}</style><h1>Animation Lab / 动作诊断</h1><p class="tag">待返修 / 待观察。自动指标不等于动画品质通过。</p><p>握持误差、目标接触间隙、逐帧跳变用于定位检查时点。代理碰撞需要在真实蒙皮和武器模型上确认。单位：厘米；代理重叠列为采样帧数。</p><table><thead><tr><th>动作</th><th>右手误差</th><th>左手误差</th><th>目标间隙</th><th>最大手部帧跳</th><th>代理重叠</th><th>回传误差</th></tr></thead><tbody>'''+rows+'</tbody></table><h2>检查定位</h2><ul>'+issues+'</ul><p>没有声明脚部着地窗口的动作，不给出脚滑通过结论。未做真人打击感评价。</p><p>Manifest SHA-256: <code>'+esc(r['manifest_sha256'])+'</code></p>'
    path.write_text(doc,encoding='utf-8')

def gate(manifest_path,report_path,review_path,out_path):
    if read(manifest_path).get('schema')=='animlab.manifest/2':
        from pipeline_v2 import gate as gate_v2
        return gate_v2(manifest_path,report_path,review_path,out_path)
    mp=Path(manifest_path).resolve();m=validate_manifest(read(mp),mp.parent);r=read(report_path);v=read(review_path);reasons=[]
    current=digest(mp)
    if r.get('manifest_sha256')!=current or v.get('manifest_sha256')!=current:reasons.append('Manifest changed or review is stale')
    if v.get('report_sha256')!=digest(report_path):reasons.append('Review does not identify this audit revision')
    capture=Path(r.get('capture_path',''))
    if not capture.is_file() or digest(capture)!=r.get('capture_sha256'):reasons.append('Capture evidence changed or missing')
    if r.get('stage')!='unreal_roundtrip' or not r.get('comparison_sha256'):reasons.append('Actual roundtrip comparison is required')
    comparison=Path(r.get('comparison_path') or '')
    if not comparison.is_file() or digest(comparison)!=r.get('comparison_sha256'):reasons.append('Source comparison changed or missing')
    assets=asset_snapshot(m,mp.parent)
    if not m.get('evidence_dependencies'):reasons.append('Source blend and engine assets must be declared as evidence dependencies')
    if assets!=r.get('asset_sha256') or any(v is None for v in assets.values()):reasons.append('Source/export/engine asset evidence changed or missing')
    if not v.get('reviewer'):reasons.append('No reviewer identity')
    reported={x['id'] for x in r.get('clips',[])}
    for c in m['clips']:
        review=v.get('clips',{}).get(c['id'],{})
        if c.get('role')=='baseline':reasons.append(c['id']+': baseline is not a release candidate')
        if c['id'] not in reported or review.get('decision')!='accepted':reasons.append(c['id']+': review incomplete')
        evidence=review.get('evidence',[])
        if not evidence or any(not local(mp.parent,p).is_file() for p in evidence):reasons.append(c['id']+': playback evidence missing')
        elif any(review.get('evidence_sha256',{}).get(p)!=digest(local(mp.parent,p)) for p in evidence):reasons.append(c['id']+': playback evidence changed or unversioned')
        waivers={x['issue_id'] for x in review.get('waivers',[]) if x.get('reason')}
        for issue in r.get('issues',[]):
            if issue['clip']==c['id'] and issue['id'] not in waivers:reasons.append(issue['id']+': unresolved')
    result={'schema':'animlab.handoff/1','eligible':not reasons,'reasons':reasons,'manifest_sha256':current,'report_sha256':digest(report_path),'review_sha256':digest(review_path),'binding_plan':m['clips'] if not reasons else [],'does_not_install_into_game':True}
    write(out_path,result);return result

def apply_binding(manifest_path,draft_path,out_path):
    m=read(manifest_path);d=read(draft_path)
    if m.get('schema')=='animlab.manifest/2':raise ValueError('Use an explicit new /2 attachment revision; legacy binding draft has no parent/source identity')
    if d.get('schema')!='animlab.binding-draft/1' or d['weapon'] not in m['weapons']:raise ValueError('Invalid binding draft')
    if d.get('source_manifest')!=m:raise ValueError('Binding draft is stale or belongs to another manifest')
    if Path(out_path).resolve()==Path(manifest_path).resolve():raise ValueError('Write a new manifest revision, preserving the baseline')
    m['weapons'][d['weapon']]['binding']=d['binding'];m['revision']+='-binding-edit';validate_manifest(m);write(out_path,m)
    return {'manifest':str(out_path),'status':'binding_changed_reaudit_required'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    q=sp.add_parser('init');q.add_argument('--workspace',required=True);q.add_argument('--capture',required=True)
    q=sp.add_parser('validate');q.add_argument('--manifest',required=True)
    q=sp.add_parser('audit');q.add_argument('--manifest',required=True);q.add_argument('--capture',required=True);q.add_argument('--out',required=True);q.add_argument('--compare')
    q=sp.add_parser('gate');q.add_argument('--manifest',required=True);q.add_argument('--report',required=True);q.add_argument('--review',required=True);q.add_argument('--out',required=True)
    q=sp.add_parser('apply-binding');q.add_argument('--manifest',required=True);q.add_argument('--draft',required=True);q.add_argument('--out',required=True)
    q=sp.add_parser('migrate-v1');q.add_argument('--manifest',required=True);q.add_argument('--plan',required=True);q.add_argument('--out',required=True)
    a=p.parse_args(argv)
    try:
        if a.command=='init':result=init_workspace(a.workspace,a.capture)
        elif a.command=='validate':validate_manifest(read(a.manifest),Path(a.manifest).resolve().parent);result={'valid':True}
        elif a.command=='audit':result=analyze(a.manifest,a.capture,a.out,a.compare)
        elif a.command=='migrate-v1':
            from pipeline_v2 import migrate
            result=migrate(a.manifest,a.plan,a.out)
        elif a.command=='gate':
            result=gate(a.manifest,a.report,a.review,a.out);print(json.dumps(result,ensure_ascii=False));return 0 if result['eligible'] else 2
        else:result=apply_binding(a.manifest,a.draft,a.out)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,KeyError,TypeError,OSError,IndexError) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())

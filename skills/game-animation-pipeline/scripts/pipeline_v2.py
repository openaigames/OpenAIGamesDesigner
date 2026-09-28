"""Explicit animation modes and measured binding diagnostics; called by anim_pipeline.

No rig aliases, guessed sockets, fabricated hit events or implied art approval.
Legacy /1 remains readable and retains its original strict external roundtrip gate.
"""
from pathlib import Path
import bisect
import copy
import math
import anim_pipeline as core

MODES = {
    'external': {'source_export', 'engine_import', 'runtime_consumer'},
    'native_reuse': {'native_source', 'binding_readback', 'runtime_consumer'},
    'local_change': {'before_config', 'after_config', 'runtime_consumer'},
}


def finite(value, name, minimum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError('Invalid '+name)


def transform(value):
    for key, count in [('p',3),('q',4),('s',3)]:
        if not isinstance(value.get(key),list) or len(value[key]) != count: raise ValueError('Malformed transform '+key)
        for v in value[key]: finite(v,key)
    if abs(core.norm(value['q'])-1) > .015: raise ValueError('Non-unit quaternion')
    if any(v<=0 for v in value['s']): raise ValueError('Positive diagnostic transform scale required')


def window(value, duration):
    if not isinstance(value,list) or len(value)!=2: raise ValueError('Interval needs [start,end] seconds')
    for v in value: finite(v,'interval',0)
    if value[0]>value[1] or value[1]>duration: raise ValueError('Interval outside clip')


def validate(m, root=None):
    if m.get('schema')!='animlab.manifest/2' or m.get('mode') not in MODES: raise ValueError('Unsupported animation mode')
    if m.get('space',{}).get('units')!='cm' or not m['space'].get('axes'): raise ValueError('Declare canonical cm and axes')
    if m.get('root_motion_owner') not in ('character','animation'): raise ValueError('Declare single root motion owner')
    if not m.get('mode_basis',{}).get('reason') or not m['mode_basis'].get('source_type'): raise ValueError('Mode requires actual source basis')
    if m['mode_basis']['source_type'] not in {'external':'dcc_export','native_reuse':'engine_native','local_change':'existing_consumer'}[m['mode']].split():
        raise ValueError('Mode differs from declared source type; preserve failures when changing scope')
    deps=m.get('evidence_dependencies',{})
    if not isinstance(deps,dict) or not MODES[m['mode']]<=set(deps): raise ValueError('Missing mode evidence roles')
    for role, paths in deps.items():
        if not isinstance(paths,list) or not paths or any(not isinstance(p,str) or not p for p in paths):raise ValueError('Evidence role requires actual file paths: '+role)
        if root:
            for p in paths:core.local(root,p)
    for name, w in m.get('weapons',{}).items():
        a=w.get('attachment',{})
        if a.get('kind') not in ('bone','socket','component') or not a.get('parent') or not a.get('source'):raise ValueError('Explicit attachment with source required: '+name)
        transform(a['relative'])
        for label, grip in w.get('grips',{}).items():
            if not grip.get('bone'):raise ValueError('Grip marker must name actual bone: '+label)
            transform(grip['hand_marker']);transform(grip['weapon_marker'])
    ids=set()
    for c in m.get('clips',[]):
        if not isinstance(c.get('id'),str) or not c['id'] or c['id'] in ids:raise ValueError('Unique clip id required')
        ids.add(c['id']);finite(c['duration_s'],'duration',.0001)
        if not c.get('source_ref'):raise ValueError('Clip requires source_ref')
        if m['mode']=='external' and not c.get('fbx'):raise ValueError('External mode still requires actual export')
        weapon=c.get('weapon')
        if weapon is not None and weapon not in m.get('weapons',{}):raise ValueError('Unknown weapon')
        for grip, windows in c.get('grip_intervals',{}).items():
            if not weapon or grip not in m['weapons'][weapon].get('grips',{}):raise ValueError('Unknown grip interval')
            for pair in windows:window(pair,c['duration_s'])
        for contact in c.get('foot_contacts',[]):
            if not contact.get('bone'):raise ValueError('Foot contact needs actual bone')
            window([contact['start_s'],contact['end_s']],c['duration_s'])
        if c.get('contact'):
            contact=c['contact'];finite(contact['time_s'],'contact time',0)
            if contact['time_s']>c['duration_s']:raise ValueError('Contact outside clip')
            if not contact.get('bone') or not contact.get('target_marker'):raise ValueError('Contact needs observed bone and target marker')
    if not ids:raise ValueError('At least one scoped clip required')
    for name, tolerance in m.get('tolerances',{}).items():finite(tolerance,'tolerance '+name,0)
    needed={'binding_position_cm','binding_rotation_deg','grip_position_cm','grip_rotation_deg','comparison_position_cm','comparison_rotation_deg','sample_time_s','foot_slide_cm','contact_gap_cm'}
    if not needed<=set(m.get('tolerances',{})) or not m.get('tolerance_basis'):raise ValueError('Declare project diagnostic tolerances and basis')
    return m


def validate_capture(data):
    if data.get('schema')!='animlab.capture/2':raise ValueError('Explicit /2 capture required; old evidence is not auto-upgraded')
    context=data.get('context',{})
    if any(not context.get(k) for k in ('engine_version','execution_ref','method','sampling')) or not isinstance(context.get('conditions'),list):raise ValueError('Capture needs actual engine/execution/method/sampling/conditions')
    names=[]
    for i,bone in enumerate(data['bones']):
        if bone['name'] in names or not -1<=bone['parent']<i:raise ValueError('Unique parent-before-child skeleton required')
        names.append(bone['name'])
    if not names:raise ValueError('Actual skeleton required')
    ids=set()
    for clip in data['clips']:
        if clip['id'] in ids:raise ValueError('Duplicate capture clip')
        ids.add(clip['id']);last=-1
        if len(clip['frames'])<2:raise ValueError('Insufficient actual samples')
        for frame in clip['frames']:
            finite(frame['t'],'frame time',0)
            if frame['t']<=last or len(frame['pose'])!=len(names):raise ValueError('Pose clock or bone count mismatch')
            last=frame['t']
            for t in frame['pose']:transform(t)
            if frame.get('weapon') is not None:transform(frame['weapon'])
            if frame.get('attachment') is not None:
                a=frame['attachment']
                if type(a.get('exists')) is not bool or a.get('kind') not in ('bone','socket','component') or not a.get('parent'):raise ValueError('Capture actual attachment identity/existence')
                if a['exists']:transform(a['relative'])
            for t in frame.get('markers',{}).values():transform(t)
    return names


def qmul(a,b):
    return [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],
            a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
            a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],
            a[3]*b[3]-sum(a[i]*b[i] for i in range(3))]


def marker(parent, offset):
    return {'p':core.point(parent,offset['p']),'q':qmul(parent['q'],offset['q']), 's':[a*b for a,b in zip(parent['s'],offset['s'])]}


def assets(m,root):
    paths=set(p for files in m['evidence_dependencies'].values() for p in files)
    paths.update(c['fbx'] for c in m['clips'] if c.get('fbx'))
    return {p:core.digest(core.local(root,p)) if core.local(root,p).is_file() else None for p in sorted(paths)}


def analyze(manifest_path,capture_path,report_path,compare_path=None):
    mp=Path(manifest_path).resolve();m=validate(core.read(mp),mp.parent)
    capture=core.read(capture_path);names=validate_capture(capture);index={n:i for i,n in enumerate(names)}
    baseline=core.read(compare_path) if compare_path else None
    if baseline and validate_capture(baseline)!=names:raise ValueError('Comparison skeleton identity/order differs')
    specs={c['id']:c for c in m['clips']};old={c['id']:c for c in baseline['clips']} if baseline else {}
    if {c['id'] for c in capture['clips']}!=set(specs) or (baseline and set(old)!=set(specs)):raise ValueError('Capture clip scope differs')
    tolerance=m['tolerances'];issues=[];rows=[]
    for clip in capture['clips']:
        c=specs[clip['id']];frames=clip['frames'];metrics={};checks={};times={}
        def flag(code,reason,time=None):
            if not any(i['id']==c['id']+':'+code for i in issues):
                issues.append({'id':c['id']+':'+code,'clip':c['id'],'code':code,'reason':reason,'time_s':time,'classification':'requires_inspection'})
        def peak(key,value,time):
            if key not in metrics or value>metrics[key]:metrics[key]=value;times[key]=time
        if abs(frames[0]['t'])>tolerance['sample_time_s'] or abs(frames[-1]['t']-c['duration_s'])>tolerance['sample_time_s']:flag('coverage','Capture does not cover declared clip duration')
        weapon=m.get('weapons',{}).get(c.get('weapon'))
        checks['binding']='sampled' if weapon else 'not_applicable_unarmed'
        checks['contact']='sampled' if c.get('contact') else 'not_applicable_no_declared_contact'
        checks['feet']='sampled' if c.get('foot_contacts') else 'not_measured_no_planted_intervals'
        if weapon:
            expected=weapon['attachment']
            for frame in frames:
                a=frame.get('attachment');wp=frame.get('weapon');t=frame['t']
                if not a or not a.get('exists') or wp is None:flag('missing_binding','Actual weapon/attachment missing or unresolved',t);continue
                if (a['parent'],a['kind'])!=(expected['parent'],expected['kind']):flag('attachment_identity','Runtime parent/type differs from explicit binding',t)
                peak('binding_position_cm',core.distance(a['relative']['p'],expected['relative']['p']),t)
                peak('binding_rotation_deg',core.qangle(a['relative']['q'],expected['relative']['q']),t)
                if any(abs(x-y)>.0001 for x,y in zip(a['relative']['s'],expected['relative']['s'])):flag('binding_scale','Runtime attachment scale differs',t)
                for label,grip in weapon.get('grips',{}).items():
                    intervals=c.get('grip_intervals',{}).get(label)
                    checks['grip:'+label]='sampled_in_declared_intervals' if intervals else 'not_measured_no_grip_intervals'
                    if not intervals or not any(start<=t<=end for start,end in intervals):continue
                    if grip['bone'] not in index:flag('missing_grip:'+label,'Actual grip bone not in capture',t);continue
                    hand=marker(frame['pose'][index[grip['bone']]],grip['hand_marker']);handle=marker(wp,grip['weapon_marker'])
                    peak(label+':grip_position_cm',core.distance(hand['p'],handle['p']),t)
                    peak(label+':grip_rotation_deg',core.qangle(hand['q'],handle['q']),t)
            for label,intervals in c.get('grip_intervals',{}).items():
                for start,end in intervals:
                    if not any(start<=f['t']<=end for f in frames):flag('grip_coverage:'+label,'Declared grip interval has no actual sample',start)
        for contact in c.get('foot_contacts',[]):
            bone=contact['bone'];chosen=[f for f in frames if contact['start_s']<=f['t']<=contact['end_s']]
            if bone not in index or len(chosen)<2:flag('foot_coverage:'+bone,'Planted interval lacks bone or samples');continue
            origin=chosen[0]['pose'][index[bone]]['p']
            for f in chosen:peak('foot_slide_cm',core.distance(origin,f['pose'][index[bone]]['p']),f['t'])
        if c.get('contact'):
            contact=c['contact'];f=min(frames,key=lambda f:abs(f['t']-contact['time_s']))
            if abs(f['t']-contact['time_s'])>tolerance['sample_time_s'] or contact['bone'] not in index or contact['target_marker'] not in f.get('markers',{}):flag('contact_unmeasured','Contact lacks actual aligned target/bone sample',contact['time_s'])
            else:peak('contact_gap_cm',core.distance(f['pose'][index[contact['bone']]]['p'],f['markers'][contact['target_marker']]['p']),f['t'])
        if baseline:
            previous=old[c['id']]['frames'];ts=[f['t'] for f in previous]
            for f in frames:
                k=bisect.bisect_left(ts,f['t']);ref=previous[min([max(0,k-1),min(k,len(ts)-1)],key=lambda n:abs(ts[n]-f['t']))]
                if abs(ref['t']-f['t'])>tolerance['sample_time_s']:flag('comparison_coverage','No aligned baseline sample',f['t']);continue
                peak('comparison_position_cm',max(core.distance(a['p'],b['p']) for a,b in zip(f['pose'],ref['pose'])),f['t'])
                peak('comparison_rotation_deg',max(core.qangle(a['q'],b['q']) for a,b in zip(f['pose'],ref['pose'])),f['t'])
                if f.get('weapon') is not None and ref.get('weapon') is not None:
                    peak('comparison_weapon_position_cm',core.distance(f['weapon']['p'],ref['weapon']['p']),f['t'])
                    peak('comparison_weapon_rotation_deg',core.qangle(f['weapon']['q'],ref['weapon']['q']),f['t'])
        for key,value in metrics.items():
            standard=key.split(':')[-1].replace('comparison_weapon_','comparison_')
            # Local changes may intentionally differ from baseline; remain explicit findings to review.
            if standard in tolerance and value>tolerance[standard]:flag(key,'Measured value exceeds declared diagnostic tolerance',times[key])
        rows.append({'id':c['id'],'metrics':metrics,'checks':checks,'status':'needs_review'})
    dependencies=assets(m,mp.parent)
    context_refs=[capture['context']['execution_ref']]+([baseline['context']['execution_ref']] if baseline else [])
    for p in context_refs:dependencies[p]=core.digest(core.local(mp.parent,p)) if core.local(mp.parent,p).is_file() else None
    report={'schema':'animlab.audit/2','mode':m['mode'],'manifest_sha256':core.digest(mp),
            'capture_path':str(Path(capture_path).resolve()),'capture_sha256':core.digest(capture_path),'stage':capture.get('stage'),
            'comparison_path':str(Path(compare_path).resolve()) if compare_path else None,'comparison_sha256':core.digest(compare_path) if compare_path else None,
            'asset_sha256':dependencies,'clips':rows,'issues':issues,'animation_quality':'not_approved',
            'limitations':['Marker position/direction do not establish finger contact or mesh quality.',
                'No declaration means not measured/not applicable, never automatic approval.',
                'Sampled poses cannot prove continuous collisions or subjective impact.']}
    core.write(report_path,report);core.render_report(report,Path(report_path).with_suffix('.html'))
    return {'report':str(report_path),'issues':len(issues),'mode':m['mode'],'status':'needs_review'}


def gate(manifest_path,report_path,review_path,out_path):
    mp=Path(manifest_path).resolve();m=validate(core.read(mp),mp.parent);r=core.read(report_path);v=core.read(review_path);reasons=[]
    if r.get('schema')!='animlab.audit/2' or v.get('schema')!='animlab.review/2':reasons.append('Version 2 actual audit and fresh review required')
    if r.get('mode')!=m['mode']:reasons.append('Mode changed since audit')
    for record in (r,v):
        if record.get('manifest_sha256')!=core.digest(mp):reasons.append('Manifest/review stale')
    if v.get('report_sha256')!=core.digest(report_path):reasons.append('Review identifies another audit')
    for key in ['capture']+(['comparison'] if m['mode'] in ('external','local_change') else []):
        path=Path(r.get(key+'_path') or '')
        if not path.is_file() or core.digest(path)!=r.get(key+'_sha256'):reasons.append(key+' missing/changed')
    if m['mode']=='external' and r.get('stage')!='unreal_roundtrip':reasons.append('External mode requires actual unreal_roundtrip')
    if m['mode']!='external' and r.get('stage')!='runtime_consumer':reasons.append('Actual current consumer capture required')
    current=assets(m,mp.parent)
    if any(v is None or r.get('asset_sha256',{}).get(p)!=v for p,v in current.items()):reasons.append('Source/consumer dependencies missing or changed')
    for p,sha in r.get('asset_sha256',{}).items():
        path=core.local(mp.parent,p)
        if sha is None or not path.is_file() or core.digest(path)!=sha:reasons.append('Audit dependency changed: '+p)
    if not v.get('reviewer'):reasons.append('Actual reviewer required')
    for c in m['clips']:
        review=v.get('clips',{}).get(c['id'],{})
        if c.get('role')=='baseline' or review.get('decision')!='accepted':reasons.append(c['id']+': incomplete review')
        files=review.get('evidence',[])
        if not files:reasons.append(c['id']+': actual playback evidence missing')
        for p in files:
            path=core.local(mp.parent,p)
            if not path.is_file() or core.digest(path)!=review.get('evidence_sha256',{}).get(p):reasons.append(c['id']+': playback stale')
        waivers={item['issue_id'] for item in review.get('waivers',[]) if item.get('reason')}
        for issue in r.get('issues',[]):
            if issue['clip']==c['id'] and issue['id'] not in waivers:reasons.append(issue['id']+': unresolved')
        if not any(row['id']==c['id'] for row in r.get('clips',[])):reasons.append(c['id']+': not audited')
    result={'schema':'animlab.handoff/2','eligible':not reasons,'reasons':reasons,'mode':m['mode'],
        'manifest_sha256':core.digest(mp),'report_sha256':core.digest(report_path),'review_sha256':core.digest(review_path),
        'binding_plan':m['clips'] if not reasons else [],'does_not_install_into_game':True}
    core.write(out_path,result);return result


def migrate(source,plan,out):
    """Explicit author plan, preserving /1 source and all old failed evidence."""
    src=Path(source).resolve();target=Path(out).resolve();old=core.read(src);new=core.read(plan)
    if old.get('schema')!='animlab.manifest/1' or target==src or target.exists():raise ValueError('Migration preserves source; new destination required')
    validate(new,target.parent)
    if new['mode']!='external' or {c['id'] for c in old['clips']}!={c['id'] for c in new['clips']}:raise ValueError('Migration retains external scope; a new task is needed to change mode')
    new['migration']={'source':str(src),'sha256':core.digest(src),'previous_reviews':'historical_not_transferred','status':'reaudit_required'}
    core.write(target,new)
    core.write(target.with_suffix('.review.json'),{'schema':'animlab.review/2','manifest_sha256':core.digest(target),'report_sha256':None,'reviewer':None,
        'clips':{c['id']:{'decision':'needs_review','evidence':[],'waivers':[]} for c in new['clips']}})
    return {'manifest':str(target),'status':'reaudit_required'}

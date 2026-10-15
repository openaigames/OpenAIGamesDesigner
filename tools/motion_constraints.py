"""Optional terrain feet and prop grip contracts. Values never enable a gameplay policy implicitly."""
import math
import motion_workflow as motion

def vector(value, size, label):
    if not isinstance(value,list) or len(value)!=size: raise ValueError(label+' requires '+str(size)+' numbers')
    for n in value: motion.number(n,label,-10000,10000)
    return value

def settings(definitions):
    row=definitions.get('constraints')
    if row is None: return None
    if not isinstance(row,dict) or set(row)-{'mode','feet','grip'} or row.get('mode')!='contacts_v1' or not ('feet' in row or 'grip' in row):
        raise ValueError('contacts_v1 requires feet and/or grip')
    def chain(names):
        if not isinstance(names,list) or len(names)!=3 or len(set(names))!=3 or any(not isinstance(n,str) or not n for n in names):raise ValueError('Three distinct chain bones required')
    feet=row.get('feet')
    if feet is not None:
        keys={'pelvis','left','right','sole_offset_m','probe_up_m','probe_down_m','max_step_m','max_slope_deg','max_pelvis_m','blend_s','knee_pole'}
        if not isinstance(feet,dict) or set(feet)!=keys or not isinstance(feet['pelvis'],str) or not feet['pelvis']:raise ValueError('Explicit feet settings required')
        chain(feet['left']);chain(feet['right'])
        if len(set([feet['pelvis'],*feet['left'],*feet['right']]))!=7:raise ValueError('Disjoint feet and pelvis required')
        for k,lo,hi in [('sole_offset_m',0,.2),('probe_up_m',.01,1),('probe_down_m',.01,1),('max_step_m',.01,.4),('max_slope_deg',1,60),('max_pelvis_m',0,.3),('blend_s',.02,1)]:motion.number(feet[k],k,lo,hi)
        if feet['max_step_m']>min(feet['probe_up_m'],feet['probe_down_m']):raise ValueError('Probe must cover step range')
        if math.dist(vector(feet['knee_pole'],3,'knee pole'),[0,0,0])<.1:raise ValueError('Nonzero knee pole required')
    grip=row.get('grip')
    if grip is not None:
        if not isinstance(grip,dict) or set(grip)!={'main_hand','offhand','blend_s','elbow_pole','sockets'} or not isinstance(grip['main_hand'],str) or not grip['main_hand']:raise ValueError('Explicit grip settings required')
        chain(grip['offhand'])
        if grip['main_hand'] in grip['offhand']:raise ValueError('Main and support hands must differ')
        motion.number(grip['blend_s'],'grip blend',.02,1)
        if math.dist(vector(grip['elbow_pole'],3,'elbow pole'),[0,0,0])<.1:raise ValueError('Nonzero elbow pole required')
        if set(grip['sockets'])!={'godot','unreal'}:raise ValueError('Calibrated native sockets required for both imports')
        for engine,sockets in grip['sockets'].items():
            if set(sockets)!={'main','support'}:raise ValueError('Main and support socket transforms required')
            for socket in sockets.values():
                if set(socket)!={'position','rotation_xyzw'}:raise ValueError('Socket position/quaternion required')
                vector(socket['position'],3,'socket position')
                q=vector(socket['rotation_xyzw'],4,'socket quaternion')
                if abs(sum(x*x for x in q)-1)>.001:raise ValueError('Normalized socket quaternion required')
    return row

def check_capture(definitions, frames):
    row=settings(definitions)
    if not row:return
    names=[]
    if 'feet' in row:names += [row['feet']['pelvis'],*row['feet']['left'],*row['feet']['right']]
    if 'grip' in row:names += [row['grip']['main_hand'],*row['grip']['offhand']]
    if any(n not in f['bones'] for f in frames for n in names):raise ValueError('Constraint bone missing from processed capture')

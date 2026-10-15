"""Blender worker: author flat-ground step turns on the actual calibrated skin."""
import bpy,sys,json,math,copy
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
import motion_blender as m

def smooth(x):
    x=max(0,min(1,x));return x*x*(3-2*x)

def yaw_fraction(t,c):
    u=(t-c['lead_s'])/c['step_s'];i=max(0,min(c['steps'],math.floor(u)))
    return (i+smooth((u-i-.1)/.8))/c['steps'] if 0<=u<c['steps'] else (0 if u<0 else 1)

def solve(rest,frame,root,chain,goal,foot_q,pole):
    upper,lower,foot=chain;p=m.fk(rest,frame['local'],root,frame['translation'],frame['offsets'])
    hip=p[upper].translation;knee=p[lower].translation;ankle=p[foot].translation
    a=(knee-hip).length;b=(ankle-knee).length;d=goal-hip;distance=d.length
    if not abs(a-b)+1e-5<distance<a+b-1e-5:raise ValueError('Unreachable turn step '+foot)
    axis=d.normalized();bend=pole-axis*pole.dot(axis)
    along=(a*a-b*b+distance*distance)/(2*distance)
    target=hip+axis*along+bend.normalized()*math.sqrt(max(0,a*a-along*along))
    m.set_world_rotation(rest,frame['local'],p,upper,(knee-hip).rotation_difference(target-hip)@p[upper].to_quaternion())
    p=m.fk(rest,frame['local'],root,frame['translation'],frame['offsets']);knee=p[lower].translation
    m.set_world_rotation(rest,frame['local'],p,lower,(p[foot].translation-knee).rotation_difference(goal-knee)@p[lower].to_quaternion())
    p=m.fk(rest,frame['local'],root,frame['translation'],frame['offsets']);m.set_world_rotation(rest,frame['local'],p,foot,foot_q)

def main():
    path=Path(sys.argv[sys.argv.index('--')+1]);out=path.parent;s=json.loads(path.read_text());base=Path(s['base']);roles=s['roles'];clips=[];artifacts={};manifest={'schema':'oagd.turns/1','clips':[],'root_owner':'controller','positive_yaw':'right','coordinates':'Blender metres +Z up -Y forward'}
    for c in s['clips']:
        m.load(base/'idle.blend');rig=m.rig_named(json.loads((base/'target-rig.json').read_text())['armature']);rest=m.rest_data(rig);root=roles['root'];bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
        poses={n:rig.matrix_world@rig.pose.bones[n].matrix for n in rest};original={'local':{},'offsets':{},'translation':Vector((0,0,0))}
        for n,b in rest.items():
            parent=b['parent'];basis=poses[parent]@rest[parent]['m'].inverted()@b['m'] if parent else b['m'];delta=basis.inverted()@poses[n]
            original['local'][n]=delta.to_quaternion();original['offsets'][n]=delta.translation
        feet={side:poses[roles['foot_'+side]].copy() for side in ('L','R')};frames=[];contacts={side:[] for side in ('L','R')}
        # Anatomical -Y forward has right = -X. A right turn is therefore
        # negative Blender Z yaw, unlike UE's positive right-handed screen yaw.
        angle=-math.radians(c['angle_deg']);lead='R' if c['angle_deg']>0 else 'L'
        for k in range(round(c['duration_s']*60)+1):
            t=k/60;f=copy.deepcopy(original);yaw=angle*yaw_fraction(t,c);unrotate=Quaternion((0,0,1),-yaw);u=(t-.2)/.6
            for side in ('L','R'):
                progress=0.;lift=0.;planted=True
                if u>=c['steps']:progress=c['steps']
                elif u>=0:
                    step=math.floor(u);phase=u-step;lo,hi=(.1,.45) if side==lead else (.55,.9)
                    fraction=smooth((phase-lo)/(hi-lo));progress=step+fraction;planted=not lo<phase<hi
                    lift=s['lift_m']*math.sin(math.pi*fraction)
                foot_yaw=angle*progress/c['steps'];q=Quaternion((0,0,1),foot_yaw)
                goal=unrotate@(q@feet[side].translation+Vector((0,0,lift)))
                # Knee bend tracks the moving foot, avoiding an abrupt pole flip.
                pole=Quaternion((0,0,1),(foot_yaw-yaw)*.5)@Vector((0,-1,0))
                solve(rest,f,root,[roles[x+'_'+side] for x in ('thigh','shin','foot')],goal,unrotate@q@feet[side].to_quaternion(),pole)
                contacts[side].append(planted)
            frames.append(f)
        # Exact idle endpoints, including its authored knee bend direction.
        # Interior solutions approach the same pose; continuity is audited below.
        clip={'id':c['id'],'fps':60,'start_frame':1,'end_frame':len(frames)}
        m.bake(rig,rest,frames,root,c['id'],60);capture=m.evaluated_capture(rig,rest,clip)
        windows=[];maxdrift=0.;maxstep=0.;minfloor=1e9
        for side,flags in contacts.items():
            start=None
            for k,flag in enumerate(flags+[False]):
                if flag and start is None:start=k
                if not flag and start is not None:
                    if k-start>=3:
                        points=[Quaternion((0,0,1),angle*yaw_fraction(j/60,c))@Vector(capture[j]['bones'][roles['foot_'+side]]['p']) for j in range(start,k)]
                        drift=max((v-points[0]).length for v in points);maxdrift=max(maxdrift,drift)
                        windows.append({'side':side,'start_s':start/60,'end_s':(k-1)/60,'max_drift_m':drift})
                    start=None
        for k,f in enumerate(capture):
            if k:maxstep=max(maxstep,max((Vector(f['bones'][n]['p'])-Vector(capture[k-1]['bones'][n]['p'])).length for n in rest))
            bpy.context.scene.frame_set(k+1);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
            for obj in bpy.context.scene.objects:
                if obj.type=='MESH':
                    ev=obj.evaluated_get(dg);mesh=ev.to_mesh();minfloor=min(minfloor,min((ev.matrix_world@v.co).z for v in mesh.vertices));ev.to_mesh_clear()
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
        for mesh in meshes:mesh.select_set(True)
        bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/(c['id']+'.blend')));m.export_glb(out/(c['id']+'.glb'),60);m.export_fbx(rig,meshes,out/(c['id']+'.fbx'))
        m.write(out/(c['id']+'-capture.json'),{'schema':'oagd.motion-capture/1','method':'new procedural turn authoring; evaluated Blender skin rig, no retarget repairs','coordinates':'RH_Z_UP_METRES','after':capture,'before':capture})
        failures=[]
        if maxdrift>.0005:failures.append('planted ankle drift')
        if maxstep>.08:failures.append('pose discontinuity')
        if minfloor<-.005:failures.append('skin below ground')
        clips.append({**c,'frames':len(frames),'failures':failures,'authoring':'new flat-ground turn from calibrated idle; base rig/weights unchanged','max_planted_drift_m':maxdrift,'max_bone_step_m':maxstep,'min_skin_z_m':minfloor})
        manifest['clips'].append({**c,'contacts':windows})
        for ext in ('.blend','.glb','.fbx','-capture.json'):artifacts[c['id']+ext]=m.sha(out/(c['id']+ext))
    m.write(out/'turns.json',manifest);m.write(out/'turn-report.json',{'ok':not any(c['failures'] for c in clips),'clips':clips,'artifacts':artifacts,'method':'actual evaluated Blender bones and mesh vertices; controller yaw applied only for declared world-contact diagnostics'})

if __name__=='__main__':main()

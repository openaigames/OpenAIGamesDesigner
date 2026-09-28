"""Read-only sampling INSIDE UE; driven by the existing Playback lifecycle.

Runtime events require a project-owned UFunction returning JSON. Bounds are
engine bounds, never a substitute for a collision/nav/line-of-sight query.
"""
import json
import math
import time
import unreal
from spatial_worker import collision_objects,ray_queries


def xyz(value):
    return [value.x, value.y, value.z]


def transform(value):
    return {'position':xyz(value.translation), 'scale':xyz(value.scale3d),
            'rotation_xyzw':[value.rotation.x,value.rotation.y,value.rotation.z,value.rotation.w]}


def serial(value, depth=0):
    if depth > 6:
        raise ValueError('Native value exceeds observation nesting limit')
    if value is None or isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        if not math.isfinite(value):raise ValueError('Non-finite native value')
        return value
    if isinstance(value,unreal.Object):return {'asset':value.get_path_name()}
    if isinstance(value,unreal.Vector):return xyz(value)
    if isinstance(value,unreal.Rotator):return [value.pitch,value.yaw,value.roll]
    if isinstance(value,unreal.Transform):return transform(value)
    if isinstance(value,(list,tuple,unreal.Array)):
        return [serial(v,depth+1) for v in value]
    if isinstance(value,dict):return {str(k):serial(v,depth+1) for k,v in value.items()}
    # Unsupported native structs retain their type/text. They cannot be edited
    # or treated as a numeric readback through this representation.
    return {'native_type':type(value).__name__,'text':str(value),'editable':False}


def component_detail(component, markers=()):
    detail={'name':component.get_name(),'path':component.get_path_name(),
            'class':component.get_class().get_path_name(),'references':{},'unavailable':[]}
    names={str(p) for p in ['static_mesh','skeletal_mesh_asset','anim_class','animation_data']}
    for key in sorted(names):
        try:detail['references'][key]=serial(component.get_editor_property(key))
        except Exception:pass  # A non-mesh component need not expose mesh properties.
    if isinstance(component,unreal.SceneComponent):
        parent=component.get_attach_parent()
        socket=str(component.get_attach_socket_name())
        detail.update(parent=parent.get_path_name() if parent else None,attachment=socket,
                      world=transform(component.get_world_transform()),
                      relative=transform(component.get_relative_transform()))
        if parent and socket not in ('None',''):
            detail['attachment_exists']=bool(parent.does_socket_exist(socket))
        if isinstance(component,unreal.SkeletalMeshComponent):
            detail['markers']={}
            for name in markers:
                exists=component.does_socket_exist(name)
                index=component.get_bone_index(name)
                detail['markers'][name]={'exists':bool(exists),'kind':'bone' if index>=0 else 'socket' if exists else 'missing'}
                if exists:detail['markers'][name]['world']=transform(component.get_socket_transform(name,unreal.RelativeTransformSpace.RTS_WORLD))
            mesh=component.get_editor_property('skeletal_mesh_asset')
            if mesh:
                try:detail['references']['skeleton']=serial(mesh.get_editor_property('skeleton'))
                except Exception as error:detail['unavailable'].append('skeleton: '+str(error))
            try:
                animation=component.get_editor_property('animation_data')
                detail['single_node_animation']={key:serial(animation.get_editor_property(key))
                    for key in ['anim_to_play','saved_play_rate','saved_position','saved_looping']}
            except Exception as error:detail['unavailable'].append('single_node_animation: '+str(error))
    try:detail['creation_method']=str(component.get_editor_property('creation_method'))
    except Exception:detail['unavailable'].append('creation_method not exposed')
    return detail


def actor_detail(actor, markers=()):
    return {'label':actor.get_actor_label(),'path':actor.get_path_name(),
            'class':actor.get_class().get_path_name(),'transform':transform(actor.get_actor_transform()),
            'components':[component_detail(c,markers) for c in actor.get_components_by_class(unreal.ActorComponent)]}


def attached_detail(actor, markers=()):
    # Author demos often spawn a separate weapon Actor in BeginPlay. Reading
    # only the character's own components would incorrectly report no weapon.
    children=actor.get_attached_actors(reset_array=True,recursively_include_attached_actors=True)
    if len(children)>256:raise ValueError('Attached actor observation exceeds 256; narrow the subject')
    return [actor_detail(child,markers) for child in children]


class Observer:
    def __init__(self, request, find_actor):
        self.request=request
        self.options=request['observe']
        self.find_actor=find_actor
        self.objects={}
        self.events={}
        self.routes={}
        self.parameters=[]
        self.curves={}
        self.bindings=[]
        self.space=[]
        self.cost=0.0
        self.samples=0
        self.last=None
        self.truncated=False
        self.missing=[]
        self.media=[]
        self.queries=[]
        self.pose_sampler=None
        if self.options.get('animation_capture'):
            from pose_worker import PoseSampler
            self.pose_sampler=PoseSampler(request,find_actor)

    def sample(self,world,world_time):
        if self.last is not None and world_time-self.last<self.options.get('interval',0.05):return
        if self.samples>=self.options.get('max_samples',2400):
            self.truncated=True
            return
        begin=time.perf_counter()
        self.last=world_time
        self.samples+=1
        bindings=[]
        space=[]
        for spec in self.options['actors']:
            actor=self.find_actor(spec['target'],world)
            oid=spec['id']
            self.objects[oid]={'id':oid,'label':actor.get_actor_label(),'source':actor.get_path_name(),'kind':spec.get('kind','actor')}
            position=xyz(actor.get_actor_location())
            self.routes.setdefault(oid,{'id':oid+'-movement','object':oid,'clock':'game',
                'measurement':'actual_movement','samples':[],'conditions':'PIE actor location sampled from Slate; see automated actions'})['samples'].append([world_time,*position])
            spatial={'id':oid,'position':position,'kind':spec.get('kind','actor'),'measurement':'engine_geometry','collision':'unknown'}
            cameras=actor.get_components_by_class(unreal.CameraComponent)
            if cameras:
                camera=cameras[0]
                spatial['projection']={key:serial(camera.get_editor_property(key)) for key in ['field_of_view','aspect_ratio','ortho_width']}
                spatial['projection']['world']=transform(camera.get_world_transform())
            else:
                bounds,extent=actor.get_actor_bounds(False,True)
                spatial['bounds']=[[a-b for a,b in zip(xyz(bounds),xyz(extent))],[a+b for a,b in zip(xyz(bounds),xyz(extent))]]
            space.append(spatial)
            for shape in collision_objects(actor,oid):
                self.objects[shape['id']]={'id':shape['id'],'label':shape['id'],'source':shape['geometry_source'],'kind':shape['kind']}
                space.append(shape)
            if self.options.get('bindings',True):
                detail=actor_detail(actor,spec.get('markers',[]))
                if spec.get('attached_actors'):detail['attached_actors']=attached_detail(actor,spec.get('markers',[]))
                bindings.append({'id':oid,'time':world_time,**detail})
            for prop in spec.get('properties',[]):
                target=actor
                if prop.get('component'):
                    matches=[c for c in actor.get_components_by_class(unreal.ActorComponent) if c.get_name()==prop['component']]
                    if len(matches)!=1:raise ValueError('Observed component must resolve exactly once: '+prop['component'])
                    target=matches[0]
                value=serial(target.get_editor_property(prop['property']))
                if type(value) not in (int,float,bool,str):raise ValueError('Observed parameter requires a scalar property: '+prop['property'])
                source=target.get_path_name()+'::'+prop['property']
                row={'id':prop['id'],'object':oid,'value':value,'unit':prop['unit'],
                     'provenance':'runtime_readback','source':source,'conditions':'PIE get_editor_property at game time '+str(world_time)}
                self.parameters=[p for p in self.parameters if (p['id'],p['object'])!=(row['id'],oid)]+[row]
                if type(value) in (int,float):
                    key=oid+':'+prop['id']
                    self.curves.setdefault(key,{'id':key,'object':oid,'clock':'game','unit':prop['unit'],
                        'measurement':'measured','samples':[]})['samples'].append([world_time,value])
            if spec.get('event_exporter'):
                # The project supplies a documented read-only UFunction. The
                # tool never interprets a generic state change as a gameplay hit.
                raw=actor.call_method(spec['event_exporter'],())
                if not isinstance(raw,str) or len(raw)>1048576:raise ValueError('Event exporter must return <=1 MiB JSON string')
                rows=json.loads(raw)
                if not isinstance(rows,list) or len(rows)>10000:raise ValueError('Exporter must return a bounded event list')
                for event in rows:
                    if not isinstance(event,dict) or set(event)-{'id','time','event','data'} or not all(k in event for k in ('id','time','event')):
                        raise ValueError('Invalid project event shape')
                    if not isinstance(event['id'],str) or not isinstance(event['event'],str) or type(event['time']) not in (int,float) or not math.isfinite(event['time']) or event['time']<0:
                        raise ValueError('Invalid project event value')
                    key=oid+':'+event['id']
                    row={**event,'id':key,'object':oid,'clock':'game'}
                    if key in self.events and self.events[key]!=row:raise ValueError('Project event ID was reused with different content')
                    self.events[key]=row
                    if len(self.events)>10000:raise ValueError('Observation event limit exceeded')
        self.bindings.append({'time':world_time,'actors':bindings})
        self.space=space
        self.queries.extend(ray_queries(world,self.options.get('queries',[]),self.find_actor,world_time))
        if self.pose_sampler:self.pose_sampler.sample(world,world_time)
        self.cost+=time.perf_counter()-begin

    def capture(self,project,engine_version):
        limitations=['Bounds are broad geometry. Shape outlines and explicit ray samples are labeled; unprobed terrain/navigation/visibility remain unknown.',
            'Direct timed actions are component calls/teleports, not human or hardware input latency.',
            'Only explicitly exported events are gameplay facts; unobserved events/actions may still exist.',
            'Screenshot sequence has no audio; Slate sampling and screenshots affect frame time.']
        if self.truncated:limitations.append('Sample limit reached; remaining playback is not observed.')
        return {'schema_version':1,'context':{'engine':'unreal','engine_version':engine_version,'project':str(project),
            'build':self.request['request_id'],'run_ref':'runs/'+self.request['request_id']+'/session.json',
            'input_mode':'component_call' if self.request.get('actions') else 'none',
            'method':'PIE world-time/property/component sampling via existing engine session',
            'conditions':self.options.get('conditions',[])+['PIE','Slate tick sampling'],
            'sampling_overhead':'observer %.3f ms total / %d samples; screenshot cost excluded'%(self.cost*1000,self.samples)},
            'objects':list(self.objects.values()),'clocks':[{'id':'game','unit':'seconds','description':'PIE GetTimeSeconds; affected by world time dilation; not wall clock'}],
            'events':sorted(self.events.values(),key=lambda e:e['time']),'curves':list(self.curves.values()),
            'parameters':self.parameters,'media':self.media,
            'space':{'dimensions':3,'unit':'cm','axes':'UE +X forward, +Y right, +Z up','objects':self.space,'routes':list(self.routes.values()),'queries':self.queries},
            'limitations':limitations+self.missing}

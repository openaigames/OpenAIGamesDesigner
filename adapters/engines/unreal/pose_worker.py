"""Actual PIE skeletal poses and explicit weapon binding, within shared Playback."""
import unreal

def measured(value):
    return {'p':[value.translation.x,value.translation.y,value.translation.z],
            'q':[value.rotation.x,value.rotation.y,value.rotation.z,value.rotation.w],
            's':[value.scale3d.x,value.scale3d.y,value.scale3d.z]}

class PoseSampler:
    def __init__(self,request,find_actor):
        self.request=request;self.spec=request['observe']['animation_capture'];self.find_actor=find_actor
        self.first=None;self.frames=[];self.bones=None;self.consumer=None

    def sample(self,world,world_time):
        if self.first is None:self.first=world_time
        elapsed=world_time-self.first-self.spec.get('start',0)
        if elapsed<0 or elapsed>self.spec['duration']:return
        actor=self.find_actor(self.spec['target'],world)
        matches=[c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()==self.spec['component']]
        if len(matches)!=1:raise ValueError('Animation capture requires one explicit runtime skeletal component')
        component=matches[0];count=component.get_num_bones()
        if not 1<=count<=512:raise ValueError('Runtime skeleton must have 1..512 bones')
        names=[str(component.get_bone_name(i)) for i in range(count)]
        bones=[{'name':name,'parent':component.get_bone_index(component.get_parent_bone(name))} for name in names]
        if self.bones is not None and bones!=self.bones:raise ValueError('Runtime skeleton changed during capture')
        self.bones=bones
        mesh=component.get_editor_property('skeletal_mesh_asset')
        self.consumer={'actor':actor.get_path_name(),'component':component.get_path_name(),'mesh':mesh.get_path_name(),
                       'skeleton':mesh.get_editor_property('skeleton').get_path_name()}
        frame={'t':elapsed,'world_time':world_time,'pose':[measured(component.get_socket_transform(name,unreal.RelativeTransformSpace.RTS_WORLD)) for name in names]}
        try:
            single=component.get_single_node_instance()
            if single:frame['native_animation_time']=single.get_current_time()
        except Exception:pass  # AnimBP/montage phase is not guessed from clip names.
        selector=self.spec.get('weapon')
        if selector:
            actors=[actor]+list(actor.get_attached_actors(reset_array=True,recursively_include_attached_actors=True))
            candidates=[]
            for owner in actors:
                for c in owner.get_components_by_class(unreal.SceneComponent):
                    if c.get_attach_parent()!=component:continue
                    if selector.get('component') and c.get_name()!=selector['component']:continue
                    try:asset=c.get_editor_property('static_mesh')
                    except Exception:continue
                    if asset and asset.get_path_name()==selector['mesh_asset']:candidates.append(c)
            if len(candidates)>1:raise ValueError('Weapon selector is ambiguous; add explicit component name')
            expected=selector['attachment'];exists=bool(candidates)
            frame['attachment']={'parent':expected,'kind':selector['kind'],'exists':False}
            if exists:
                weapon=candidates[0];actual=str(weapon.get_attach_socket_name())
                kind='bone' if component.get_bone_index(actual)>=0 else 'socket' if component.does_socket_exist(actual) else 'component' if actual in ('None','') else selector['kind']
                frame['weapon']=measured(weapon.get_world_transform())
                frame['attachment']={'parent':actual if actual not in ('None','') else component.get_name(),'kind':kind,
                    'exists':actual in ('None','') or bool(component.does_socket_exist(actual)),
                    'relative':measured(weapon.get_relative_transform()),'component':weapon.get_path_name()}
        self.frames.append(frame)

    def capture(self,version):
        if len(self.frames)<2:raise ValueError('Requested animation observation window has fewer than two samples')
        return {'schema':'animlab.capture/2','stage':self.spec.get('stage','runtime_consumer'),
            'context':{'engine_version':version,'execution_ref':'runs/'+self.request['request_id']+'/session.json',
                'method':'Read-only actual PIE component world poses; no animation reset or interpolation',
                'sampling':'Slate world-time samples at requested observation interval; actual timestamps retained',
                'conditions':self.request['observe'].get('conditions',[])+['Window time is relative to first observed PIE sample; native phase is recorded when available'],
                'space':{'units':'cm','axes':'Unreal world +X forward +Y right +Z up'},'consumer':self.consumer},
            'bones':self.bones,'clips':[{'id':self.spec['clip'],'frames':self.frames}]}

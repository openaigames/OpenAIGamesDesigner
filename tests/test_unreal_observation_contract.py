"""Observation options must be explicit and reject silent mutations/omissions."""
from copy import deepcopy
import unittest
from adapters.engines.unreal.production import validate_request


class UnrealObservationContractTests(unittest.TestCase):
    def request(self):
        return {'engine':'unreal','mode':'playback','scene':'/Game/Map','seconds':3,
                'observe':{'actors':[{'id':'hero','target':'Hero','event_exporter':'ExportObservationEvents',
                    'markers':['weapon_r'],'properties':[{'id':'speed','property':'speed','unit':'cm/s'}]}]}}

    def test_project_exporter_is_explicit_and_readonly_source_preview_rejects_actions(self):
        request=self.request();request['readonly_preview']=True
        validate_request(request)
        request['actions']=[{'op':'method','at':0,'target':'Hero','method':'Attack'}]
        with self.assertRaises(ValueError):validate_request(request)

    def test_non_playback_options_limits_and_duplicate_ids_rejected(self):
        base=self.request()
        for modify in [lambda r:r.update(mode='inspect'),lambda r:r['observe'].update(interval=float('nan')),
                       lambda r:r['observe'].update(max_samples=0),lambda r:r['observe']['actors'].append(deepcopy(r['observe']['actors'][0])),
                       lambda r:r['observe'].update(unimplemented=True)]:
            request=deepcopy(base);modify(request)
            with self.assertRaises(ValueError):validate_request(request)

    def test_native_window_camera_and_probe_budgets(self):
        request=self.request();request['readonly_preview']=True
        request['observation_camera']={'position':[100,0,200],'rotation':[-20,180,0],'field_of_view':60}
        request['observe']['animation_capture']={'target':'Hero','component':'Mesh','clip':'idle','start':.5,'duration':2}
        validate_request(request)
        for change in [lambda r:r.update(camera_target='Camera'),
            lambda r:r['observation_camera'].update(field_of_view=0),
            lambda r:r['observe']['animation_capture'].update(duration=4),
            lambda r:r['observe']['animation_capture'].pop('duration'),
            lambda r:r['observe']['animation_capture'].update(weapon={'mesh_asset':'/Game/Sword'})]:
            value=deepcopy(request);change(value)
            with self.assertRaises(ValueError):validate_request(value)
        request=self.request();request['seconds']=60
        request['observe'].update(interval=.01,queries=[{'id':str(i),'object':'hero','start':[0,0,0],'end':[100,0,0],'purpose':'real ray'} for i in range(32)])
        with self.assertRaisesRegex(ValueError,'50000'):validate_request(request)

    def test_capture_cannot_reuse_other_session_or_wrong_component(self):
        from adapters.engines.unreal.production import validate_pose_result
        request=self.request();request['request_id']='S1'
        request['observe']['animation_capture']={'target':'Hero','component':'Mesh','clip':'idle','duration':1}
        capture={'schema':'animlab.capture/2','stage':'runtime_consumer','context':{'execution_ref':'runs/S1/session.json','consumer':{'component':'Actor.Mesh'}},
            'bones':[{'name':'root','parent':-1}],'clips':[{'id':'idle','frames':[{'t':0,'pose':[{}]},{'t':1,'pose':[{}]}]}]}
        validate_pose_result(capture,request)
        capture['context']['execution_ref']='runs/old/session.json'
        with self.assertRaisesRegex(ValueError,'another session'):validate_pose_result(capture,request)


if __name__=='__main__':unittest.main()

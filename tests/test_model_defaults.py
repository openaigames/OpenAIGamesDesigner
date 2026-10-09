"""Quality-first defaults reach queued requests, approval and outgoing payloads.

All generation/network calls are mocked; no credentials or paid generation.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import asset_workflow as workflow
from adapters.assets import model_defaults as defaults, elevenlabs, ark, tripo
from adapters.assets import hunyuan_inputs, generation_capabilities, generation_approval, api_common, http_io


class ModelDefaultsTests(unittest.TestCase):
    def test_new_job_pins_model_for_each_supported_product_without_network(self):
        cases=[('tripo',{'prompt':'crate'},'model_version','v3.1-20260211'),
               ('hunyuan3d',{'Prompt':'木箱'},'Model','3.1'),
               ('seedream',{'prompt':'crate'},'model','doubao-seedream-5-0-pro-260628'),
               ('seedance',{'prompt':'crate'},'model','doubao-seedance-2-5-260628'),
               ('elevenlabs',{'kind':'speech','voice_id':'testvoice','text':'Mission start.'},'model_id','eleven_v4'),
               ('elevenlabs',{'kind':'music','music_length_ms':5000,'text':'Victory sting'},'model_id','music_v2_5'),
               ('elevenlabs',{'kind':'sound_effect','duration_seconds':1,'text':'Click'},'model_id','eleven_text_to_sound_v2')]
        with tempfile.TemporaryDirectory() as folder, patch.object(http_io,'open_url',side_effect=AssertionError('Unexpected network')):
            for provider,params,field,model in cases:
                with self.subTest(provider=provider,kind=params.get('kind')):
                    request={'parameters':params,'inputs':[]};before=copy.deepcopy(request)
                    job=workflow.new_job(Path(folder),provider,request,{'mode':'api'})
                    saved=workflow.read_job(Path(folder),job['job_id'])[1]
                    self.assertEqual(saved['request']['parameters'][field],model)
                    self.assertEqual(request,before)
                    self.assertEqual(saved['status'],'queued')

    def test_explicit_legacy_choices_survive_new_jobs_and_payloads(self):
        request={'parameters':{'kind':'speech','voice_id':'testvoice','text':'Ready.','model_id':'eleven_v3'},'inputs':[]}
        with tempfile.TemporaryDirectory() as folder:
            job=workflow.new_job(Path(folder),'elevenlabs',request,{'mode':'api'})
            self.assertEqual(job['request']['parameters']['model_id'],'eleven_v3')
        self.assertEqual(elevenlabs.payload(request)[1]['model_id'],'eleven_v3')
        p=hunyuan_inputs.build_payload({'parameters':{'Model':'3.0','Prompt':'crate'},'inputs':[]})
        self.assertEqual(p['Model'],'3.0')

    def test_speech_and_music_models_reach_correct_wire_endpoints(self):
        cases=[({'kind':'speech','voice_id':'testvoice','text':'Mission start.'},'/text-to-speech/testvoice','eleven_v4'),
               ({'kind':'music','music_length_ms':5000,'text':'Instrumental'},'/music','music_v2_5'),
               ({'kind':'sound_effect','duration_seconds':1,'text':'Click'},'/sound-generation','eleven_text_to_sound_v2')]
        for params,endpoint,model in cases:
            path,body=elevenlabs.payload({'parameters':params,'inputs':[]})
            self.assertEqual((path,body['model_id']),(endpoint,model))

    def test_tripo_submits_h31_and_preserves_explicit_older_model(self):
        with patch.object(api_common,'credential',return_value='fixture'):
            client=tripo.Client({})
        for version in (None,'v3.0-20250812'):
            request={'parameters':{'prompt':'crate'},'inputs':[]}
            if version:request['parameters']['model_version']=version
            with patch.object(client,'call',return_value={'task_id':'test-task'}) as call:
                client.submit(request)
            body=call.call_args.args[1]
            self.assertEqual(body['model_version'],version or 'v3.1-20260211')
            self.assertEqual(body['type'],'text_to_model')

    def test_tripo_image_view_endpoint_gets_no_fictitious_model_parameter(self):
        request={'parameters':{'type':'generate_multiview_image'},'inputs':[{'path':'front.png','view':'front'}]}
        prepared=defaults.prepare('tripo',request)
        self.assertEqual(prepared,request)
        api_common.validate_request('tripo',prepared,{'mode':'api'})

    def test_hunyuan_defaults_match_wire_and_capability_display(self):
        request={'parameters':{'Prompt':'crate'},'inputs':[]}
        self.assertEqual(hunyuan_inputs.build_payload(request)['Model'],'3.1')
        self.assertEqual(generation_capabilities.describe('hunyuan3d',request)['model'],'3.1')
        self.assertEqual(generation_capabilities.describe('tripo',{'parameters':{'prompt':'crate'}})['model'],'v3.1-20260211')

    def test_incompatible_hunyuan_modes_do_not_silently_downgrade(self):
        with self.assertRaises(ValueError):
            hunyuan_inputs.build_payload({'parameters':{'Prompt':'crate','GenerateType':'LowPoly'},'inputs':[]})
        explicit={'parameters':{'Prompt':'crate','Model':'3.0','GenerateType':'LowPoly'},'inputs':[]}
        self.assertEqual(hunyuan_inputs.build_payload(explicit)['Model'],'3.0')

    def test_historical_unpinned_tasks_are_not_relabelled_as_current_flagships(self):
        old={'parameters':{'Prompt':'crate','GenerateType':'LowPoly'},'inputs':[]}
        info=generation_capabilities.describe('hunyuan3d',old,historical=True)
        self.assertIn('3.0',info['model'])
        info=generation_capabilities.describe('tripo',{'parameters':{'prompt':'crate'}},historical=True)
        self.assertNotIn('v3.1',info['model'])
        pinned={'parameters':{'Prompt':'crate','Model':'3.1'},'inputs':[]}
        self.assertEqual(generation_capabilities.describe('hunyuan3d',pinned,historical=True)['model'],'3.1')

    def test_ark_defaults_reach_payload_and_reference_constraints_still_apply(self):
        self.assertEqual(ark.payload('seedream',{'parameters':{'prompt':'crate'}})['model'],'doubao-seedream-5-0-pro-260628')
        self.assertEqual(ark.payload('seedance',{'parameters':{'prompt':'crate'}})['model'],'doubao-seedance-2-5-260628')
        with self.assertRaises(ValueError):
            ark.validate_request('seedance',{'parameters':{'prompt':'crate'},'inputs':['front.png']})

    def test_approval_binds_resolved_model_and_pinned_jobs_do_not_drift(self):
        source={'parameters':{'kind':'speech','text':'Ready.','voice_id':'testvoice'},'inputs':[]}
        pinned=defaults.prepare('elevenlabs',source)
        with patch.object(api_common,'credential',return_value='synthetic'):
            def identity(request):return generation_approval.identity(ROOT,'Afixture','elevenlabs',{'mode':'api'},request)
            before=identity(source);pinned_before=identity(pinned)
            self.assertEqual(before,pinned_before)
            with patch.dict(defaults.ELEVENLABS,{'speech':'future-test-model'}):
                self.assertNotEqual(identity(source),before)
                self.assertEqual(identity(pinned),pinned_before)

    def test_host_and_custom_command_routes_do_not_receive_invented_parameters(self):
        request={'parameters':{'prompt':'crate'},'inputs':[]}
        for provider,settings in [('image',{'mode':'host'}),('audio',{'command':['tool']}),('blender',{}),('hunyuan3d',{'command':['custom']})]:
            self.assertEqual(defaults.prepare(provider,request,settings),request)


if __name__=='__main__':unittest.main()

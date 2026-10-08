"""Ark contracts, shared credentials and controlled delivery; never calls a paid API."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import asset_workflow
from adapters.assets import ark, ark_worker as worker, credential_store as store, api_common, generation_approval as approval, http_io

PNG=b'\x89PNG\r\n\x1a\n'+b'\0'*28
MP4=b'\0\0\0\x18ftypisom'+b'\0'*24

class Response(io.BytesIO):
    pass

class ArkTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.settings={'mode':'api','api_key_env':'ARK_API_KEY','poll_seconds':1}
        for context in (patch.dict(os.environ,{'ARK_API_KEY':'synthetic-ark-key'}),patch.object(store,'store_path',return_value=self.root/'profile/keys.json')):
            context.start();self.addCleanup(context.stop)

    def request(self,provider):
        return ark.prepare(provider,{'parameters':{'prompt':'test asset'},'inputs':[],
                                     '_approval':{'project':str(self.root),'job_id':'Aexample'}})

    def output(self,name):
        folder=self.root/name;folder.mkdir();out=folder/'output';out.mkdir();return out,folder/'result.json'

    def authorize(self,provider,request):
        approval.approve(approval.identity(str(self.root),'Aexample',provider,self.settings,request))

    def test_shared_encrypted_storage_and_removal(self):
        if not store.available():self.skipTest('Windows DPAPI only')
        with patch.dict(os.environ,{'ARK_API_KEY':''}):
            store.save('seedream','synthetic-shared-ark-key')
            self.assertNotIn(b'synthetic-shared-ark-key',store.store_path().read_bytes())
            status=store.status()
            self.assertTrue(status['providers']['seedance']['saved'])
            self.assertEqual(store.default_settings('seedream'),store.default_settings('seedance'))
            self.assertNotIn('synthetic-shared-ark-key',json.dumps(status))
            store.save('seedance','synthetic-replacement-key')
            self.assertEqual(store.get('ARK_API_KEY'),'synthetic-replacement-key')
            store.remove('seedream')
            self.assertFalse(store.status()['providers']['seedance']['saved'])
        self.assertEqual(api_common.credential(self.settings,'api_key_env','ARK_API_KEY'),'synthetic-ark-key')
        self.assertTrue(api_common.doctor('seedance',self.settings)['ready_to_attempt'])

    def test_model_contracts_reject_invalid_parameters_before_creating_job(self):
        cases=[('seedream',{'size':'4K'}),('seedream',{'size':[]} ),('seedream',{'model':'https://other.example'}),
               ('seedream',{'api_key':'secret'}),('seedance',{'duration':31}),('seedance',{'duration':True}),
               ('seedance',{'duration':5.5}),('seedance',{'callback_url':'https://example.com'}),
               ('seedance',{'generate_audio':'true'}),('seedance',{'resolution':'8k'}),('seedance',{'ratio':'wide'})]
        for provider,params in cases:
            with self.subTest(provider=provider,params=params),self.assertRaises(ValueError):
                asset_workflow.new_job(self.root,provider,{'parameters':{'prompt':'asset',**params}},self.settings)
        self.assertFalse((self.root/'.openaigame').exists())

    def test_payloads_and_reference_snapshot(self):
        image=self.root/'reference.png';image.write_bytes(PNG)
        job=asset_workflow.new_job(self.root,'seedream',{'parameters':{'prompt':'alter image'},'inputs':['reference.png']},self.settings)
        request=copy.deepcopy(job['request'])
        request['inputs'][0]['snapshot']=str(self.root/request['inputs'][0]['snapshot'])
        body=ark.payload('seedream',request)
        self.assertEqual(body['response_format'],'url');self.assertFalse(body['stream'])
        self.assertNotIn('sequential_image_generation',body)
        self.assertTrue(body['image'].startswith('data:image/png;base64,'))
        self.assertNotIn('inputs',body)
        video=self.request('seedance');video['parameters']['ratio']='adaptive';video['inputs']=request['inputs']
        self.assertEqual(ark.payload('seedance',video)['content'][1]['role'],'first_frame')
        video['parameters']['ratio']='16:9'
        with self.assertRaises(ValueError):ark.payload('seedance',video)
        Path(request['inputs'][0]['snapshot']).write_bytes(PNG+b'changed')
        with self.assertRaises(ValueError):ark.payload('seedream',request)

    def test_request_fingerprints_bind_model_duration_and_provider(self):
        request=self.request('seedance')
        first=approval.identity(str(self.root),'Aexample','seedance',self.settings,request)
        request['parameters']['duration']=6
        second=approval.identity(str(self.root),'Aexample','seedance',self.settings,request)
        self.assertNotEqual(first,second)
        third=approval.identity(str(self.root),'Aexample','seedream',self.settings,request)
        self.assertNotEqual(second,third)
        with patch.dict(os.environ,{'ARK_API_KEY':'synthetic-new-key'}):
            self.assertNotEqual(second,approval.identity(str(self.root),'Aexample','seedance',self.settings,request))

    def test_transport_routes_and_no_key_in_body(self):
        payload=ark.payload('seedream',self.request('seedream'))
        with patch.object(http_io,'open_url',return_value=Response(json.dumps({'data':[{'url':'https://cdn.example/img'}]}).encode())) as call:
            self.assertEqual(ark.Client(self.settings).image(payload),'https://cdn.example/img')
            args=call.call_args.args
            self.assertEqual(args[0],ark.BASE+'/images/generations')
            self.assertEqual(args[2]['Authorization'],'Bearer synthetic-ark-key')
            self.assertNotIn(b'synthetic-ark-key',args[1]);self.assertEqual(call.call_args.kwargs['timeout'],300)
        with patch.object(http_io,'json_request',return_value={'id':'cgt-test'}) as call:
            self.assertEqual(ark.Client(self.settings).submit_video({'content':[]}),'cgt-test')
            self.assertEqual(call.call_args.args[0],ark.BASE+'/contents/generations/tasks')
        with patch.object(http_io,'json_request',return_value={'id':'wrong'}),self.assertRaises(ValueError):
            ark.Client(self.settings).query_video('cgt-test')

    def test_one_image_download_and_result(self):
        request=self.request('seedream');self.authorize('seedream',request);out,result=self.output('image')
        def download(url,path,limit):path.write_bytes(PNG)
        with patch.object(ark.Client,'image',return_value='https://cdn.example/image?signature=private') as generate,patch.object(http_io,'download',side_effect=download):
            worker.run('seedream',self.settings,request,out,result)
            generate.assert_called_once()
            with self.assertRaises(ValueError):worker.run('seedream',self.settings,request,out,result)
        data=json.loads(result.read_text());self.assertEqual(data['artifacts'],[{'path':'image.png'}])
        self.assertEqual(data['observations']['quality_validation'],'not_checked')
        self.assertNotIn('signature',result.read_text()+result.with_name('remote.json').read_text())

    def test_unapproved_and_lost_image_response_never_resubmit(self):
        request=self.request('seedream');out,result=self.output('unapproved')
        with patch.object(ark.Client,'image') as generate,self.assertRaises(ValueError):worker.run('seedream',self.settings,request,out,result)
        generate.assert_not_called()
        self.authorize('seedream',request)
        with patch.object(ark.Client,'image',side_effect=ValueError('lost response')) as generate,self.assertRaises(ValueError):
            worker.run('seedream',self.settings,request,out,result)
        self.assertEqual(json.loads(result.with_name('remote.json').read_text())['status'],'submitting')
        out2,result2=self.output('second-attempt')
        with patch.object(ark.Client,'image') as again,self.assertRaises(ValueError):worker.run('seedream',self.settings,request,out2,result2)
        again.assert_not_called()

    def test_video_polling_and_resume_without_new_submission(self):
        request=self.request('seedance');self.authorize('seedance',request);out,result=self.output('video')
        reports=[{'id':'cgt-task','status':'queued'},{'id':'cgt-task','status':'succeeded','content':{'video_url':'https://cdn.example/video'},'duration':5}]
        def download(url,path,limit):path.write_bytes(MP4)
        with patch.object(ark.Client,'submit_video',return_value='cgt-task') as submit,patch.object(ark.Client,'query_video',side_effect=reports),patch.object(worker.time,'sleep'),patch.object(http_io,'download',side_effect=download):
            worker.run('seedance',self.settings,request,out,result)
            submit.assert_called_once()
        self.assertEqual(json.loads(result.read_text())['provider_job_id'],'cgt-task')
        request['provider_job_id']='cgt-task';out,result=self.output('resume')
        with patch.object(ark.Client,'submit_video') as submit,patch.object(ark.Client,'query_video',return_value=reports[-1]),patch.object(http_io,'download',side_effect=download),patch.object(approval,'require') as consume:
            worker.run('seedance',self.settings,request,out,result)
        submit.assert_not_called();consume.assert_not_called()

    def test_video_stops_retain_id_and_reject_error_downloads(self):
        request=self.request('seedance');request['provider_job_id']='cgt-existing'
        for status in ('failed','expired','cancelled','unknown'):
            out,result=self.output(status)
            with patch.object(ark.Client,'query_video',return_value={'status':status}),patch.object(http_io,'download') as download,self.assertRaises(ValueError):
                worker.run('seedance',self.settings,request,out,result)
            download.assert_not_called();self.assertEqual(json.loads(result.with_name('remote.json').read_text())['provider_job_id'],'cgt-existing')
        out,result=self.output('invalid-content')
        with patch.object(ark.Client,'query_video',return_value={'status':'succeeded','content':{'video_url':'https://cdn.example'}}),patch.object(http_io,'download',side_effect=lambda u,p,m:p.write_text('<html>error</html>')),self.assertRaises(ValueError):
            worker.run('seedance',self.settings,request,out,result)
        self.assertFalse(result.exists())

    def test_cli_blocks_synchronous_resume_and_unapproved_run(self):
        for provider in ('seedream','seedance'):
            job=asset_workflow.new_job(self.root,provider,{'parameters':{'prompt':'asset'}},self.settings)
            with patch.object(asset_workflow.subprocess,'Popen') as run,self.assertRaises(ValueError):
                asset_workflow.execute_job(self.root,job['job_id'],1)
            run.assert_not_called()
            if provider=='seedream':
                with self.assertRaises(ValueError):asset_workflow.execute_job(self.root,job['job_id'],1,resume=True)

if __name__=='__main__':unittest.main()

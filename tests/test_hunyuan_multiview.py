"""Offline end-to-end contracts: snapshots, wire fields, review and one-use consent."""
import base64
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import uuid
import shutil
import threading
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import asset_workflow as workflow
import project_workbench as wb
from adapters.assets import hunyuan_inputs as hi, hunyuan_api, api_common, api_worker, generation_approval, credential_store
from workbench import asset_versions

def png(width=256,height=256,color=0):
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
    pixels=b''.join(b'\0'+bytes([color,20,30])*width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')

class MultiViewTests(unittest.TestCase):
    def setUp(self):
        self.root=(ROOT/'dist'/('multiview-test-'+uuid.uuid4().hex)).resolve()
        self.root.mkdir(parents=True)
        def cleanup():
            if self.root.parent != (ROOT/'dist').resolve():raise ValueError('Test cleanup escaped its workspace')
            shutil.rmtree(self.root)
        self.addCleanup(cleanup)
        self.settings={'mode':'api','auth':'api_key'}
        for i,view in enumerate(('front','left','back')):(self.root/(view+'.png')).write_bytes(png(color=i*20))
        self.request={'parameters':{'Model':'3.1','EnablePBR':True,'FaceCount':1000000,'GenerateType':'Normal'},
                      'inputs':[{'path':v+'.png','view':v} for v in ('front','left','back')],
                      'brief':'本地说明，长袖，全指手套。'}
        # Never inherit the developer's account preferences or credential store.
        ctx=patch.dict(os.environ,{'HUNYUAN3D_API_KEY':'synthetic-test-key',
                                   'LOCALAPPDATA':str(self.root/'test-user')})
        ctx.start();self.addCleanup(ctx.stop)

    def queued(self):return workflow.new_job(self.root,'hunyuan3d',self.request,self.settings)

    def test_saved_multiview_job_passes_schema_on_reload(self):
        created=self.queued()
        _,loaded=workflow.read_job(self.root,created['job_id'])
        self.assertEqual(loaded['request'],created['request'])
        self.assertEqual(hi.build_payload(self.wire(loaded)),hi.build_payload(self.wire(created)))
        self.request['brief']='x'*12001
        with self.assertRaisesRegex(ValueError,'brief'):self.queued()

    def test_model_version_uses_mesh_primary_and_preserves_companions(self):
        job=self.queued()
        (self.root/'result.glb').write_bytes(b'fixture for file identity; not a rendered mesh')
        (self.root/'result.zip').write_bytes(b'fixture archive')
        paths=['result.zip','front.png','result.glb']
        job['status']='succeeded'
        job['artifacts']=[{'path':p,'sha256':hashlib.sha256((self.root/p).read_bytes()).hexdigest()} for p in paths]
        result=asset_versions.complete_job(self.root,job)
        group=asset_versions.load(self.root)['groups'][result['group']]
        self.assertEqual(group['kind'],'model')
        self.assertEqual(group['versions'][0]['files'][0]['sourcePath'],'result.glb')
        self.assertEqual({x['sourcePath'] for x in group['versions'][0]['files']},set(paths))
        job['request']['lineage']={'group':result['group'],'parent':None,'references':[],'note':'second model'}
        job['job_id']='AnewFixtureJob'
        asset_versions.complete_job(self.root,job)
        self.assertEqual(len(asset_versions.load(self.root)['groups'][result['group']]['versions']),2)

    def wire(self,job):
        req=copy.deepcopy(job['request'])
        for item in req['inputs']:item['snapshot']=str(self.root/item['snapshot'])
        return req

    def test_three_images_arrive_under_official_fields_for_both_auth_routes(self):
        job=self.queued();request=self.wire(job)
        for settings in (self.settings,{'mode':'api','auth':'tc3','region':'ap-guangzhou'}):
            with patch.dict(os.environ,{'TENCENTCLOUD_SECRET_ID':'synthetic-id','TENCENTCLOUD_SECRET_KEY':'synthetic-key'}):client=hunyuan_api.Client(settings)
            with patch.object(client,'call',return_value={'JobId':'fixture-1'}) as call:
                self.assertEqual(client.submit(request),'fixture-1')
            action,payload=call.call_args.args
            self.assertEqual(action,'SubmitHunyuanTo3DProJob')
            self.assertEqual(set(payload),{'Model','EnablePBR','FaceCount','GenerateType','ImageBase64','MultiViewImages'})
            self.assertEqual(base64.b64decode(payload['ImageBase64']),(self.root/'front.png').read_bytes())
            self.assertEqual([x['ViewType'] for x in payload['MultiViewImages']],['left','back'])
            for entry,view in zip(payload['MultiViewImages'],['left','back']):self.assertEqual(base64.b64decode(entry['ViewImageBase64']),(self.root/(view+'.png')).read_bytes())

    def test_retry_preserves_views_brief_and_immutable_snapshots(self):
        job=self.queued();old=self.wire(job)
        (self.root/'left.png').write_bytes(png(color=250))
        retry=workflow.new_job(self.root,'hunyuan3d',job['request'],self.settings,retry_of=job['job_id'])
        self.assertEqual(retry['request']['brief'],job['request']['brief'])
        self.assertEqual([i['view'] for i in retry['request']['inputs']],['front','left','back'])
        self.assertEqual(hi.build_payload(old),hi.build_payload(self.wire(retry)))

    def test_changed_view_and_brief_invalidate_approval_identity(self):
        job=self.queued();req=job['request']
        def fp(r):return generation_approval.identity(self.root,job['job_id'],'hunyuan3d',self.settings,r)
        before=fp(req);changed=copy.deepcopy(req);changed['inputs'][1]['view']='right'
        self.assertNotEqual(before,fp(changed))
        changed=copy.deepcopy(req);changed['brief']='另一份本地说明'
        self.assertNotEqual(before,fp(changed))

    def test_legacy_single_front_and_text_still_work(self):
        self.request={'parameters':{'Model':'3.1'},'inputs':['front.png']}
        job=self.queued();payload=hi.build_payload(self.wire(job))
        self.assertIn('ImageBase64',payload);self.assertNotIn('MultiViewImages',payload)
        self.assertEqual(hi.build_payload({'parameters':{'Prompt':'木箱'},'inputs':[]}),{'Prompt':'木箱'})

    def test_front_is_selected_by_label_not_array_position(self):
        self.request['inputs'].reverse()
        payload=hi.build_payload(self.wire(self.queued()))
        self.assertEqual(base64.b64decode(payload['ImageBase64']),(self.root/'front.png').read_bytes())

    def test_invalid_directions_and_duplicates_do_not_create_jobs(self):
        for rows in ([{'path':'left.png','view':'left'}],
                     [{'path':'front.png','view':'front'},{'path':'left.png','view':'front'}],
                     ['front.png','back.png'],
                     [{'path':'front.png','view':'front'},{'path':'front.png','view':'left'}],
                     [{'path':'front.png','view':'front'},{'path':'left.png','view':'unknown'}]):
            self.request['inputs']=rows
            with self.assertRaises(ValueError):self.queued()
        self.assertFalse((self.root/'.openaigame/asset-jobs').exists())

    def test_prompt_image_conflict_is_not_silently_dropped(self):
        self.request['parameters']['Prompt']='写实长袖角色'
        with self.assertRaisesRegex(ValueError,'Prompt'):self.queued()
        self.assertFalse((self.root/'.openaigame/asset-jobs').exists())

    def test_model_version_and_face_count_limits(self):
        for key,value in [('FaceCount',True),('FaceCount',1500001),('FaceCount',2999),('Model','4.0'),('GenerateType','LowPoly')]:
            req=copy.deepcopy(self.request);req['parameters'][key]=value
            with self.assertRaises(ValueError):hi.validate(req)
        req=copy.deepcopy(self.request);req['parameters']['Model']='3.0';req['inputs'][1]['view']='top'
        with self.assertRaises(ValueError):hi.validate(req)

    def test_snapshot_tampering_stops_wire_payload(self):
        req=self.wire(self.queued());Path(req['inputs'][1]['snapshot']).write_bytes(png(color=100))
        with self.assertRaisesRegex(ValueError,'changed'):hi.build_payload(req)

    def test_image_headers_bounds_and_total_budget(self):
        for data in (b'fake-png',png(128,256)):
            (self.root/'left.png').write_bytes(data)
            with self.assertRaises(ValueError):self.queued()
        (self.root/'left.png').write_bytes(png(color=20))
        with patch.object(hi,'MAX_ENCODED',100):
            with self.assertRaisesRegex(ValueError,'Base64'):self.queued()

    def test_paths_cannot_escape_project(self):
        self.request['inputs'][0]['path']='../outside.png'
        with self.assertRaises(ValueError):self.queued()

    def test_review_preserves_labels_and_unsent_brief(self):
        job=self.queued();summary=wb.job_summary(self.root,job)
        self.assertEqual([i['view'] for i in summary['inputs']],['front','left','back'])
        self.assertFalse(summary['transmission']['prompt_sent'])
        self.assertFalse(summary['transmission']['brief_sent'])
        self.assertEqual(summary['brief'],self.request['brief'])
        self.assertEqual(len(summary['transmission']['images']),3)

    def test_worker_invalid_input_does_not_consume_approval_or_call_provider(self):
        job=self.queued();req=self.wire(job);req['_approval']={'project':str(self.root),'job_id':job['job_id']}
        Path(req['inputs'][0]['snapshot']).write_bytes(b'bad')
        with patch.object(generation_approval,'require') as approve,patch.object(hunyuan_api.Client,'call') as call:
            with self.assertRaises(ValueError):api_worker.run('hunyuan3d',self.settings,req,self.root,self.root/'result.json')
            approve.assert_not_called();call.assert_not_called()

    def test_worker_records_three_view_receipt_without_base64_or_secrets(self):
        job=self.queued();req=self.wire(job);req['_approval']={'project':str(self.root),'job_id':job['job_id']}
        result=self.root/'result.json'
        with patch.object(generation_approval,'require') as approval,patch.object(hunyuan_api.Client,'call',return_value={'JobId':'fixture-77'}) as call,patch.object(hunyuan_api.Client,'query',return_value={'status':'DONE','done':True,'pending':False,'files':[],'credit_consumed':None}),patch.object(api_worker.hunyuan3d,'validate'):
            api_worker.run('hunyuan3d',self.settings,req,self.root,result)
        self.assertEqual(len(call.call_args.args[1]['MultiViewImages']),2)
        self.assertTrue(approval.call_args.kwargs['consume'])
        report=json.loads((self.root/'transmission.json').read_text('utf-8'))
        self.assertEqual(report['status'],'accepted');self.assertEqual(len(report['images']),3)
        self.assertNotIn('synthetic-test-key',json.dumps(report));self.assertNotIn('iVBOR',json.dumps(report))

    def test_http_form_to_review_keeps_three_images(self):
        server=wb.WorkbenchServer(self.root)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
        self.addCleanup(conn.close)
        headers={'Origin':server.origin,'Content-Type':'application/json','X-Workbench-Connect':'1'}
        conn.request('POST','/session','{}',headers);r=conn.getresponse();cookie=r.getheader('Set-Cookie').split(';')[0];r.read()
        conn.request('GET','/api/session',headers={'Cookie':cookie});r=conn.getresponse();session=json.loads(r.read())
        headers.update(Cookie=cookie,**{'X-CSRF-Token':session['csrf']})
        form={'provider':'hunyuan3d','prompt':'长袖角色（仅本地说明）','hunyuan':{'mode':'image','parameters':self.request['parameters']},'inputs':self.request['inputs']}
        conn.request('POST','/api/jobs',json.dumps(form),headers);r=conn.getresponse();body=r.read()
        self.assertEqual(r.status,201,body)
        summary=json.loads(body)['job'];self.assertEqual(summary['transmission']['mode'],'multiview')
        self.assertEqual(len(summary['inputs']),3);self.assertNotIn('Prompt',summary['parameters'])
        self.assertEqual(summary['brief'],form['prompt'])

if __name__=='__main__':unittest.main(verbosity=2)

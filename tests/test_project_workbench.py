"""Project scope, Art Direction authority and real settings/approval integration."""
import hashlib, http.client, json, os, shutil, struct, subprocess, sys, threading, unittest, uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import project_workbench as wb
import package_skills, check_installation
from workbench import art_registry as registry, asset_browser as browser
from adapters.assets import credential_store, generation_approval


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=(ROOT/'dist'/('workbench-test-'+uuid.uuid4().hex)).resolve();self.temp.mkdir(parents=True)
        def cleanup():
            assert self.temp.is_relative_to(ROOT)
            shutil.rmtree(self.temp)
        self.addCleanup(cleanup)
        self.root=self.temp/'游戏 A';self.root.mkdir();self.other=self.temp/'游戏 B';self.other.mkdir()
        (self.root/'Audio').mkdir();(self.root/'VFX').mkdir()
        self.paths=['Audio/click.ogg','VFX/spark.vfx.json']
        (self.root/self.paths[0]).write_bytes(b'actual-audio');(self.root/self.paths[1]).write_text('{}')
        self.doc=self.root/'Art Direction.md';self.doc.write_bytes('# 游戏 A · 美术方向\r\n\r\n保留旧清单和美术方向。\r\n'.encode())
        self.initial=self.doc.read_bytes()
        contexts=[patch.object(credential_store,'store_path',return_value=self.temp/'profile/credentials.json'),patch.dict(os.environ,{'TRIPO_API_KEY':'synthetic-workbench-key','HUNYUAN3D_API_KEY':''})]
        for context in contexts:context.start();self.addCleanup(context.stop)
        self.server=wb.WorkbenchServer(self.root);thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def stop():self.server.shutdown();self.server.server_close();thread.join(3)
        self.addCleanup(stop);self.headers={};self.login()
    def request(self,path,body=None,headers=None,auth=True):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        base=dict(self.headers) if auth else {}
        if body is not None:base.update({'Origin':self.server.origin,'Content-Type':'application/json'})
        base.update(headers or {})
        c.request('GET' if body is None else 'POST',path,json.dumps(body).encode() if body is not None else None,base)
        r=c.getresponse();status=r.status;head=dict(r.getheaders());raw=r.read();c.close()
        value=json.loads(raw) if head.get('Content-Type','').startswith('application/json') else raw
        return status,head,value
    def login(self):
        status,headers,_=self.request('/session',{}, {'X-Workbench-Connect':'1','Sec-Fetch-Site':'same-origin'},auth=False)
        self.assertEqual(status,200);self.headers={'Cookie':headers['Set-Cookie'].split(';')[0],'X-CSRF-Token':self.server.csrf}
    def art(self,route,payload):
        return self.request('/api/art-'+route,{'project':'current','revision':registry.load(self.root)['revision'],**payload})
    def test_multiple_browsers_connect_from_the_same_plain_url(self):
        self.assertEqual(self.server.launch_url,self.server.origin+'/#assets')
        self.assertNotIn(self.server.launch_token,self.server.launch_url)
        first_browser=dict(self.headers)
        self.assertEqual(self.request('/api/assets',auth=False)[0],401)
        for metadata in ({'Sec-Fetch-Site':'same-origin'},{}):
            status,headers,result=self.request('/session',{}, {'X-Workbench-Connect':'1',**metadata},auth=False)
            self.assertEqual(status,200)
            self.assertEqual(result['connectionMode'],'local-browser')
            self.assertEqual(result['project'],str(self.root))
            self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
            second_browser={'Cookie':headers['Set-Cookie'].split(';')[0]}
            status,_,session=self.request('/api/session',headers=second_browser,auth=False)
            self.assertEqual(status,200);self.assertEqual(session['csrf'],self.server.csrf)
            self.assertEqual(self.request('/api/assets',headers=second_browser,auth=False)[0],200)
            self.assertEqual(self.request('/api/assets',headers=first_browser,auth=False)[0],200)
            self.assertEqual(self.request('/api/art-initialize',{},headers={**second_browser,'X-CSRF-Token':'bad'},auth=False)[0],403)
        self.assertEqual(self.doc.read_bytes(),self.initial)
    def test_connection_rejects_foreign_websites_and_simple_requests(self):
        for override in ({'Origin':'https://other.test'}, {'Origin':'null'}, {'Origin':''},
                         {'Host':'other.test'}, {'Sec-Fetch-Site':'cross-site'},
                         {'Sec-Fetch-Site':'same-site'}, {'X-Workbench-Connect':''}):
            status,headers,_=self.request('/session',{}, {'X-Workbench-Connect':'1',**override},auth=False)
            self.assertEqual(status,403,override);self.assertNotIn('Set-Cookie',headers)
        status,headers,_=self.request('/session',{}, {'X-Workbench-Connect':'1','Content-Type':'text/plain'},auth=False)
        self.assertEqual(status,400);self.assertNotIn('Set-Cookie',headers)
        self.assertEqual(self.request('/session',{'project':'other'}, {'X-Workbench-Connect':'1'},auth=False)[0],400)
        self.assertNotIn('Set-Cookie',self.request('/',auth=False)[1])
        self.assertEqual(self.request('/api/assets',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
    def test_scope_sessions_no_auto_writes_and_asset_ranges(self):
        self.assertEqual(self.request('/api/assets',auth=False)[0],401)
        self.assertEqual(self.request('/api/assets?project=other')[0],404)
        result=self.request('/api/assets')[2];self.assertEqual(result['artAudit']['counts']['unregistered'],2)
        self.assertEqual(self.doc.read_bytes(),self.initial)
        with patch.object(credential_store,'status',side_effect=ValueError('unreadable profile')):
            self.assertEqual(self.request('/api/session')[0],200)
            self.assertEqual(self.request('/api/assets')[0],200)
        self.assertEqual(self.request('/asset/current/Audio/click.ogg',headers={'Range':'bytes=0-3'})[2],b'actu')
        for path in ['/asset/current/../../secret.png','/asset/current/Art%20Direction.md','/asset/current/.openaigame/asset-providers.json']:
            self.assertEqual(self.request(path)[0],404,path)
        self.assertEqual(self.request('/api/art-initialize',{},headers={'Origin':'https://other.test'})[0],403)
        self.assertEqual(self.request('/api/art-initialize',{},headers={'X-CSRF-Token':'bad'})[0],403)
        self.assertEqual(self.request('/api/approve',{})[0],404)
    def test_registration_shared_tags_and_external_updates(self):
        self.assertEqual(self.request('/api/art-initialize',{})[0],200)
        self.assertTrue(self.doc.read_bytes().startswith(self.initial))
        self.assertEqual(self.art('register',{'paths':self.paths})[0],200)
        result=self.art('record',{'path':self.paths[0],'object':{'label':'机器人','tags':['主角']}})
        self.assertEqual(result[0],200,result);obj=result[2]['artObjects'][0]['id']
        self.assertEqual(self.art('record',{'path':self.paths[1],'objectId':obj})[0],200)
        self.assertTrue(all(a['tags']==['主角'] for a in browser.scan(self.root)['assets']))
        self.assertEqual(self.art('object',{'object':{'id':obj,'label':'机器人','tags':['主角','维修机器人']}})[0],200)
        self.doc.write_bytes(self.doc.read_bytes().replace('主角、维修机器人'.encode(),'主角、修理工'.encode()))
        self.assertTrue(all(a['tags']==['主角','修理工'] for a in browser.scan(self.root)['assets']))
        self.assertEqual((self.root/self.paths[0]).read_bytes(),b'actual-audio')
        self.assertFalse((self.other/'Art Direction.md').exists())
    def test_invalid_batch_conflicts_corruption_and_file_changes(self):
        registry.initialize(self.root);before=self.doc.read_bytes()
        self.assertEqual(self.art('register',{'paths':[self.paths[0],'../bad.ogg']})[0],400)
        self.assertEqual(before,self.doc.read_bytes())
        revision=registry.load(self.root)['revision'];self.doc.write_bytes(before+b'\nExternal edit\n')
        self.assertEqual(self.request('/api/art-register',{'paths':self.paths,'revision':revision})[0],409)
        self.art('register',{'paths':self.paths});(self.root/self.paths[0]).write_bytes(b'updated-audio');(self.root/self.paths[1]).unlink()
        counts=self.request('/api/art-audit')[2]['counts'];self.assertEqual(counts['missingFiles'],1);self.assertEqual(counts['changedFiles'],1)
        damaged='<!-- art-objects:start --> broken';self.doc.write_text(damaged)
        self.assertEqual(self.request('/api/art-initialize',{})[0],400);self.assertEqual(self.doc.read_text(),damaged)
    def test_custom_art_path_initialization_and_cli(self):
        (self.root/'.openaigame').mkdir();(self.root/'design').mkdir()
        (self.root/'.openaigame/workbench.json').write_text(json.dumps({'art_document':'design/art.md'}))
        code=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/asset_audit.py'),'--project',str(self.root),'--init-art','--register-missing'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(code.returncode,0,code.stderr+code.stdout)
        self.assertEqual(json.loads(code.stdout)['counts']['incomplete'],2)
        self.assertEqual(self.doc.read_bytes(),self.initial)
        self.assertEqual(self.request('/api/art-source')[2]['path'],'design/art.md')
    def test_hidden_registered_outputs_but_not_job_metadata(self):
        job=wb.asset_workflow.new_job(self.root,'tripo',{'parameters':{'prompt':'crate'},'inputs':[]},{'mode':'api'})
        folder=self.root/'.openaigame/asset-jobs'/job['job_id']/'attempt-1/output';folder.mkdir(parents=True)
        path=folder/'model.gltf';path.write_text('{"asset":{"version":"2.0"},"buffers":[{"uri":"data.bin","byteLength":4}]}')
        (folder/'data.bin').write_bytes(b'1234')
        relative=path.relative_to(self.root).as_posix()
        job['artifacts']=[{'schema_version':1,'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'source':{'job_id':job['job_id'],'provider':'tripo','provider_job_id':None},'quality_validation':'not_checked'}]
        wb.asset_workflow.atomic_json(wb.asset_workflow.location(self.root,job['job_id'])/'job.json',job)
        self.assertIn(relative,[a['path'] for a in browser.scan(self.root)['assets']])
        self.assertEqual(self.request('/asset/current/'+relative)[0],200)
        self.assertEqual(self.request('/asset/current/'+relative.rsplit('/',1)[0]+'/data.bin')[2],b'1234')
        self.assertEqual(self.request('/asset/current/.openaigame/asset-jobs/'+job['job_id']+'/job.json')[0],404)
        registry.initialize(self.root);self.assertEqual(self.art('register',{'paths':[relative]})[0],200)
    def test_real_job_records_review_and_fingerprint_bound_approval(self):
        with patch.object(wb.asset_workflow.subprocess,'Popen') as launch:
            status,_,result=self.request('/api/jobs',{'provider':'tripo','prompt':'crate'})
            self.assertEqual(status,201,result);job_id=result['job']['id'];launch.assert_not_called()
        self.assertEqual(self.request('/api/jobs')[2]['jobs'][0]['status'],'queued')
        review=self.request('/api/job-review?job='+job_id)[2];fingerprint=review['approval']['fingerprint']
        self.assertNotIn('synthetic-workbench-key',json.dumps(review))
        body={'job':job_id,'fingerprint':fingerprint,'accept_charge':False}
        self.assertEqual(self.request('/api/job-approve',body)[0],400)
        body['accept_charge']=True
        self.assertEqual(self.request('/api/job-approve',{**body,'fingerprint':'0'*64})[0],409)
        self.assertEqual(self.request('/api/job-approve',body)[0],200)
        generation_approval.require(fingerprint)
        self.assertEqual(wb.asset_workflow.read_job(self.root,job_id)[1]['status'],'queued')
        self.assertTrue(self.request('/api/job-review?job='+job_id)[2]['approval']['approved'])
    @unittest.skipUnless(os.name=='nt','Windows encrypted storage')
    def test_integrated_settings_never_echo_secrets(self):
        secret='workbench-synthetic-only'
        result=self.request('/api/save',{'provider':'hunyuan3d','key':secret})
        self.assertEqual(result[0],200,result);self.assertTrue(result[2]['providers']['hunyuan3d']['saved'])
        self.assertNotIn(secret,json.dumps(result[2]));self.assertNotIn(secret,credential_store.store_path().read_text())
        self.assertFalse((self.root/'credentials.json').exists())
    def test_bundle_contains_runnable_shared_workbench_without_samples(self):
        bundle=package_skills.package(self.temp/'bundle');runtime=bundle/'game-preproduction/runtime'
        result=check_installation.check(bundle);self.assertEqual(result['missing'],[]);self.assertEqual(result['changed'],[])
        for name in ('project_workbench.py','asset_audit.py'):
            run=subprocess.run([sys.executable,str(runtime/'tools'/name),'--help'],capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue((runtime/'tools/workbench/web/vendor/three/build/three.module.js').is_file())
        self.assertFalse((runtime/'tools/workbench/projects').exists())

    def preview_fixture(self):
        source='Meshes/hero.uasset';target='Previews/hero.glb';dependency='Meshes/material.uasset'
        (self.root/'Meshes').mkdir();(self.root/'Previews').mkdir()
        (self.root/source).write_bytes(b'engine mesh');(self.root/dependency).write_bytes(b'engine material')
        document={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],
                  'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
                  'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[0,0,0],'max':[1,1,0]}],
                  'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36}],'buffers':[{'byteLength':36}]}
        text=json.dumps(document).encode();text+=b' '*((-len(text))%4)
        vertices=struct.pack('<9f',0,0,0,1,0,0,0,1,0)
        glb=struct.pack('<4sII',b'glTF',2,28+len(text)+len(vertices))+struct.pack('<II',len(text),0x4E4F534A)+text+struct.pack('<II',len(vertices),0x004E4942)+vertices
        (self.root/target).write_bytes(glb)
        mapping={'version':1,'assets':{source:{'path':target,'source_sha256':registry.digest(self.root/source),
                 'sha256':registry.digest(self.root/target),'dependencies':{dependency:registry.digest(self.root/dependency)}}}}
        (self.root/'.asset-browser').mkdir();path=self.root/'.asset-browser/previews.json';path.write_text(json.dumps(mapping))
        return source,target,dependency,path,mapping

    def test_obj_is_previewable_and_mtl_dependency_is_served(self):
        (self.root/'mesh.obj').write_text('mtllib mesh.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        (self.root/'mesh.mtl').write_text('newmtl stone\nKd 0.5 0.5 0.5\n')
        row=next(a for a in self.request('/api/assets')[2]['assets'] if a['name']=='mesh.obj')
        self.assertEqual((row['kind'],row['preview']),('model','native'))
        self.assertEqual(self.request('/asset/current/mesh.mtl')[0],200)

    def test_engine_preview_keeps_original_identity_and_shared_tags(self):
        source,target,dependency,path,mapping=self.preview_fixture()
        self.art('register',{'paths':[]}) if '<!-- art-objects:' in self.doc.read_text() else registry.initialize(self.root)
        self.art('register',{'paths':[source,target]})
        self.art('record',{'path':source,'object':{'label':'Hero','tags':['主角']}})
        row=next(a for a in self.request('/api/assets')[2]['assets'] if a['path']==source)
        self.assertEqual(row['ext'],'UASSET');self.assertEqual(row['kind'],'model')
        self.assertEqual(row['preview'],'derived');self.assertEqual(row['tags'],['主角'])
        self.assertEqual(row['triangles'],1);self.assertEqual(row['previewUrl'],'/asset/current/'+target)
        self.assertEqual(self.request(row['previewUrl'])[2],(self.root/target).read_bytes())

    def test_stale_model_material_or_preview_is_not_shown_as_current(self):
        source,target,dependency,path,mapping=self.preview_fixture()
        for relative in [source,dependency,target]:
            with self.subTest(path=relative):
                file=self.root/relative;original=file.read_bytes();file.write_bytes(original+b'changed')
                row=next(a for a in browser.scan(self.root)['assets'] if a['path']==source)
                self.assertEqual(row['preview'],'unavailable');self.assertNotIn('previewUrl',row)
                self.assertIn('previewIssue',row);file.write_bytes(original)

    def test_invalid_preview_mapping_cannot_escape_project(self):
        source,target,dependency,path,mapping=self.preview_fixture()
        for relative in ['../outside.glb','.openaigame/credentials.glb','Meshes/missing.glb']:
            mapping['assets'][source]['path']=relative;path.write_text(json.dumps(mapping))
            row=next(a for a in browser.scan(self.root)['assets'] if a['path']==source)
            self.assertEqual(row['preview'],'unavailable');self.assertNotIn('previewPath',row)
        path.write_text('broken JSON')
        self.assertTrue(browser.scan(self.root)['previewMappingError'])

if __name__=='__main__':unittest.main()

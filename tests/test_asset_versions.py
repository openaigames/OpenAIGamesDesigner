"""Revision preservation, pinned inputs, native outputs and authenticated board operations."""
import base64,json,sys,subprocess,unittest,uuid,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from workbench import asset_versions as v,asset_browser,art_registry
import asset_workflow as jobs
import test_project_workbench as wt
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7ZkAAAAASUVORK5CYII=')

class VersionsTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'dist'/('test-versions-'+uuid.uuid4().hex);self.root.mkdir(parents=True)
        self.addCleanup(lambda:shutil.rmtree(self.root))
    def file(self,name,content=PNG):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);return name
    def create(self,name='a.png',**kw):
        self.file(name)
        return v.mutate(self.root,{'action':'create','title':'Hero concept','kind':'image','files':[name],**kw})
    def add(self,gid,name,**kw):
        self.file(name,PNG+name.encode())
        return v.mutate(self.root,{'action':'add','group':gid,'files':[name],**kw})
    def test_old_selection_branches_and_original_overwrite(self):
        a=self.create();b=self.add(a['group'],'b.png',parent=a['version'])
        self.file('a.png',b'original overwritten')
        v.mutate(self.root,{'action':'select','group':a['group'],'version':a['version'],'reason':'prefer original proportions'})
        c=self.add(a['group'],'c.png',parent=a['version'])
        g=v.snapshot(self.root)['groups'][0]
        self.assertEqual(g['selected'],a['version']);self.assertEqual(g['latest'],c['version'])
        self.assertEqual(g['versions'][2]['parent'],a['version']);self.assertEqual(len(g['versions']),3)
        self.assertEqual(v.file_path(self.root,g['versions'][0]['files'][0]['path']).read_bytes(),PNG)
        self.assertEqual(g['versions'][1]['id'],b['version']);self.assertTrue(all(x['intact'] for x in g['versions']))
    def test_reference_roles_and_dependency_change_warnings(self):
        base=self.create();palette=self.create('palette.png')
        self.add(base['group'],'new.png',parent=base['version'],references=[{'group':palette['group'],'version':palette['version'],'role':'palette only'}])
        newer=self.add(palette['group'],'blue.png')
        v.mutate(self.root,{'action':'select','group':palette['group'],'version':newer['version'],'reason':'blue palette'})
        changed=v.snapshot(self.root)['groups'][0]['versions'][1]
        self.assertEqual(changed['references'][0]['role'],'palette only');self.assertTrue(changed['warnings'])
    def test_companion_files_keep_relative_links_and_separate_deliverable_kinds(self):
        self.file('model/hero.gltf',b'{"images":[{"uri":"maps/color.png"}]}');self.file('model/maps/color.png')
        a=v.mutate(self.root,{'action':'create','kind':'model','title':'Hero model','files':['model/hero.gltf','model/maps/color.png']})
        files=v.snapshot(self.root)['groups'][0]['versions'][0]['files']
        self.assertEqual((self.root/files[0]['path']).parent.joinpath('maps/color.png').read_bytes(),PNG)
        self.file('concept.png')
        with self.assertRaisesRegex(ValueError,'不同类型'):v.mutate(self.root,{'action':'add','group':a['group'],'files':['concept.png']})
    def test_stale_revision_idempotency_and_archiving(self):
        a=self.create();payload={'action':'add','group':a['group'],'files':['a.png'],'note':'variant'}
        b=v.mutate(self.root,payload);retry=v.mutate(self.root,payload)
        self.assertEqual(b['version'],retry['version'])
        with self.assertRaises(art_registry.RevisionConflict):v.mutate(self.root,{**payload,'revision':0})
        v.mutate(self.root,{'action':'select','group':a['group'],'version':a['version'],'reason':'chosen'})
        with self.assertRaises(ValueError):v.mutate(self.root,{'action':'archive','group':a['group'],'version':a['version'],'archived':True})
        v.mutate(self.root,{'action':'archive','group':a['group'],'version':b['version'],'archived':True})
        self.assertEqual(v.snapshot(self.root)['groups'][0]['current'],a['version'])
        v.mutate(self.root,{'action':'select','group':a['group'],'version':b['version'],'reason':'restore alternative'})
        self.assertFalse(v.snapshot(self.root)['groups'][0]['versions'][1]['archived'])
    def test_tamper_path_and_copy_race_fail_closed(self):
        a=self.create();snap=v.snapshot(self.root)['groups'][0]['versions'][0];path=snap['files'][0]['path']
        (self.root/path).write_bytes(b'tampered')
        self.assertFalse(v.snapshot(self.root)['groups'][0]['versions'][0]['intact'])
        with self.assertRaises(ValueError):v.file_path(self.root,path)
        with self.assertRaises(ValueError):v.mutate(self.root,{'action':'select','group':a['group'],'version':a['version'],'reason':'x'})
        for relative in ('../escape.png','C:/escape.png','a/../escape','a\\x'):
            with self.assertRaises(ValueError):v.safe(self.root,relative)
        revision=v.load(self.root)['revision'];self.file('race.png')
        def changed(src,dst):Path(dst).write_bytes(b'raced')
        with patch.object(v.shutil,'copy2',side_effect=changed),self.assertRaises(ValueError):
            v.mutate(self.root,{'action':'add','group':a['group'],'files':['race.png']})
        self.assertEqual(v.load(self.root)['revision'],revision)
    def test_document_summary_preserves_prose_and_game_membership(self):
        art_registry.initialize(self.root)
        doc=art_registry.document_path(self.root);doc.write_text(doc.read_text('utf-8')+'\nKeep my game design.\n','utf-8')
        a=self.create('game/hero.png');b=self.add(a['group'],'concept-new.png')
        v.mutate(self.root,{'action':'select','group':a['group'],'version':b['version'],'reason':'next target'})
        report=asset_browser.scan(self.root);g=report['versions']['groups'][0]
        self.assertEqual(g['selected'],b['version']);self.assertEqual(g['versions'][0]['gameFiles'],['game/hero.png'])
        self.assertEqual((self.root/'game/hero.png').read_bytes(),PNG)
        self.assertIn('Keep my game design.',doc.read_text('utf-8'));self.assertEqual(doc.read_text('utf-8').count('<!-- asset-version-selections:start -->'),1)
    def test_job_pins_parent_bytes_and_native_never_executes_cloud(self):
        a=self.create();c={'group':a['group'],'parent':a['version'],'note':'smaller armor','references':[]}
        job=jobs.new_job(self.root,'image',{'parameters':{'prompt':'modify'},'lineage':c},{'mode':'host'})
        self.assertEqual(len(job['request']['inputs']),1)
        entry=job['request']['inputs'][0];self.assertEqual((self.root/entry['snapshot']).read_bytes(),PNG)
        self.file('a.png',b'changed');self.assertEqual((self.root/entry['snapshot']).read_bytes(),PNG)
        with patch.object(jobs.subprocess,'Popen') as popen,self.assertRaisesRegex(ValueError,'宿主生图'):
            jobs.execute_job(self.root,job['job_id'],10)
        popen.assert_not_called();self.assertFalse((jobs.location(self.root,job['job_id'])/'worker.lock').exists())
        paths=[self.file('ref'+str(n)+'.png') for n in range(5)]
        with self.assertRaisesRegex(ValueError,'五张'):jobs.new_job(self.root,'image',{'parameters':{},'inputs':paths,'lineage':c},{'mode':'host'})
    def test_native_cli_records_real_alternatives_and_idempotent_job_link(self):
        base=self.create();self.file('result1.png');self.file('result2.png',PNG+b'2')
        spec={'prompt':'two armor alternatives','tool':'fixture-native-tool','outputs':['result1.png','result2.png'],
              'lineage':{'group':base['group'],'parent':base['version'],'references':[]}}
        (self.root/'native.json').write_text(json.dumps(spec),'utf-8')
        run=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'tools/asset_versions.py'),'--project',str(self.root),'record-native','--request','native.json'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout);self.assertEqual(len(result['versions']),2)
        job=jobs.read_job(self.root,result['job'])[1];self.assertEqual(job['status'],'registered')
        self.assertEqual(job['execution_source'],'fixture-native-tool');self.assertFalse(job['attempts'])
        self.assertEqual(v.complete_job(self.root,job)['versions'],result['versions'])
        g=v.snapshot(self.root)['groups'][0];self.assertEqual(len(g['versions']),3);self.assertIsNone(g['selected'])
        self.assertEqual([x['parent'] for x in g['versions'][1:]],[base['version']]*2)
    def test_explicit_output_sets_keep_multiviews_together(self):
        paths=[self.file('front.png'),self.file('side.png'),self.file('variant.png')]
        job=jobs.new_job(self.root,'image',{'parameters':{'prompt':'views'}},{'mode':'host'})
        job['artifacts']=jobs.artifacts(self.root,self.root,{'artifacts':[{'path':p} for p in paths]},job)
        job.update(status='registered',output_sets=[paths[:2],paths[2:]])
        result=v.complete_job(self.root,job);self.assertEqual(len(result['versions']),2)
        self.assertEqual([len(x['files']) for x in v.snapshot(self.root)['groups'][0]['versions']],[2,1])
        job['output_sets']=[paths[:2],paths[1:]]
        with self.assertRaises(ValueError):v.complete_job(self.root,job)

class VersionApiTests(unittest.TestCase):
    setUp=wt.WorkbenchTests.setUp
    tearDown=wt.WorkbenchTests.tearDown
    request=wt.WorkbenchTests.request
    login=wt.WorkbenchTests.login
    def test_version_api_security_and_pinned_task_preview(self):
        (self.root/'hero.png').write_bytes(PNG)
        payload={'action':'create','title':'Hero','kind':'image','files':['hero.png']}
        self.assertEqual(self.request('/api/asset-versions',payload,auth=False)[0],401)
        status,_,created=self.request('/api/asset-versions',payload);self.assertEqual(status,200,created)
        report=self.request('/api/asset-versions')[2];saved=report['groups'][0]['versions'][0]
        url=saved['files'][0]['url'];self.assertEqual(self.request(url)[2],PNG)
        self.assertEqual(self.request(url,auth=False)[0],401)
        status,_,reply=self.request('/api/jobs',{'provider':'image','prompt':'modify hero','lineage':{'group':created['group'],'parent':created['version']}})
        self.assertEqual(status,201,reply);job=reply['job'];self.assertTrue(job['host']);self.assertEqual(len(job['inputs']),1)
        self.assertIsNone(self.request('/api/job-review?job='+job['id'])[2]['approval'])
        self.assertEqual(self.request(job['inputs'][0]['previewUrl'])[2],PNG)
        (self.root/saved['files'][0]['path']).write_bytes(b'tampered')
        self.assertEqual(self.request(url)[0],404)
        self.assertEqual(self.request('/api/asset-versions',{'action':'select','group':created['group'],'version':created['version'],'reason':'old'})[0],400)
        self.assertEqual(self.request('/api/asset-versions',dict(payload,revision=0))[0],409)

if __name__=='__main__':unittest.main()

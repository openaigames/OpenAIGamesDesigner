import base64
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

RUNTIME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RUNTIME/'tools'))
sys.path.insert(0,str(RUNTIME))
from workbench import asset_handoff as handoff, art_registry, asset_versions, asset_browser
from record_io import digest, project_lock
import asset_handoff as cli
import asset_workflow, asset_library, task_state, validate_records

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a2WQAAAAASUVORK5CYII=')


class AssetHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.write('art.png',PNG)
        self.write('actor.gd','extends Node\n')
        self.write('source.md','Test fixture provenance; not an actual game validation.\n')
        self.write('run.txt','Synthetic test evidence.\n')
        self.object={'id':'PLAYER','label':'Player','tags':['player']}

    def write(self,rel,value):
        path=self.root/rel;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value if isinstance(value,bytes) else value.encode())
        return path

    def manifest(self,rel='art.png'):
        return {'schema_version':1,'objects':[self.object], 'assets':[{
            'id':'ART1','path':rel,'sha256':digest(self.root/rel),'objectId':'PLAYER',
            'details':{'production':{'method':'authored','source':'Synthetic local fixture','license':'test only','evidence':['source.md']},
                       'selection':{'state':'adopted','basis':'Test fixture chosen explicitly'},
                       'integration':{'state':'imported','consumers':['actor.gd#ready'],'evidence':['run.txt']},
                       'verification':{'state':'passed','scope':'Synthetic record gate test','evidence':['run.txt']}}}]}

    def check(self,level='verified',rel='art.png'):
        return handoff.check(self.root,{'paths':[rel],'require':level})

    def test_apply_is_one_authority_and_idempotent(self):
        self.write('Art Direction.md','# Existing art\n\nKeep this authored direction.\n')
        manifest=self.manifest();handoff.apply(self.root,manifest)
        original=(self.root/'Art Direction.md').read_bytes()
        self.assertTrue(self.check()['ok'])
        handoff.apply(self.root,manifest)
        self.assertEqual((self.root/'Art Direction.md').read_bytes(),original)
        self.assertIn(b'Keep this authored direction.',original)
        self.assertFalse((self.root/'.openaigame/asset-records.json').exists())

    def test_replacement_drops_previous_engine_and_quality_claims(self):
        handoff.apply(self.root,self.manifest())
        self.write('art.png',PNG+b'changed')
        self.assertFalse(self.check()['ok'])
        manifest={'schema_version':1,'assets':[{'path':'art.png','sha256':digest(self.root/'art.png')}]}
        handoff.apply(self.root,manifest)
        self.assertTrue(self.check('recorded')['ok'])
        self.assertFalse(self.check('integrated')['ok'])
        self.assertFalse(self.check()['ok'])
        self.assertEqual(art_registry.load(self.root)['assets']['art.png']['id'],'ART1')

    def test_changed_consumer_invalidates_integration_and_verification(self):
        handoff.apply(self.root,self.manifest())
        self.write('actor.gd','extends Node3D\n')
        self.assertTrue(self.check('recorded')['ok'])
        self.assertFalse(self.check('integrated')['ok'])
        self.assertFalse(self.check()['ok'])

    def test_rebinding_consumer_does_not_inherit_old_verification(self):
        handoff.apply(self.root,self.manifest())
        self.write('second.gd','extends Node\n')
        manifest={'schema_version':1,'assets':[{'path':'art.png','sha256':digest(self.root/'art.png'),
            'details':{'integration':{'state':'imported','consumers':['second.gd'],'evidence':['run.txt']}}}]}
        handoff.apply(self.root,manifest)
        self.assertTrue(self.check('integrated')['ok'])
        self.assertFalse(self.check()['ok'])

    def test_invalid_batch_and_stale_revision_leave_authority_unchanged(self):
        handoff.apply(self.root,self.manifest())
        before=(self.root/'Art Direction.md').read_bytes()
        manifest=self.manifest();manifest['assets'].append({'path':'missing.png','sha256':'0'*64})
        with self.assertRaises(ValueError):handoff.apply(self.root,manifest)
        manifest=self.manifest();manifest['revision']='old'
        with self.assertRaises(ValueError):handoff.apply(self.root,manifest)
        self.assertEqual(before,(self.root/'Art Direction.md').read_bytes())

    def test_ids_are_stable_and_not_reassigned_to_copies(self):
        handoff.apply(self.root,self.manifest())
        manifest=self.manifest();manifest['assets'][0]['id']='CHANGED'
        with self.assertRaises(ValueError):handoff.apply(self.root,manifest)
        self.write('copy.png',PNG)
        with self.assertRaises(ValueError):handoff.apply(self.root,self.manifest('copy.png'))

    def test_legacy_mapping_uses_configured_authority_and_preserves_old_table(self):
        self.write('.openaigame/workbench.json',json.dumps({'art_document':'design/Assets.md'}))
        old='# Existing authority\n\n| Stable ID | File |\n| --- | --- |\n| ART1 | art.png |\n'
        self.write('design/Assets.md',old)
        manifest=self.manifest();manifest['assets'][0]['details']['legacyRef']='design/Assets.md#existing'
        handoff.apply(self.root,manifest)
        self.assertFalse((self.root/'Art Direction.md').exists())
        self.assertIn(old,(self.root/'design/Assets.md').read_text('utf8'))
        self.assertEqual(art_registry.load(self.root)['assets']['art.png']['id'],'ART1')
        row=next(a for a in asset_browser.scan(self.root)['assets'] if a['path']=='art.png')
        self.assertEqual(row['art']['objectId'],'PLAYER')

    def test_scope_does_not_require_unrelated_files_and_unknown_license_is_explicit(self):
        manifest=self.manifest();manifest['assets'][0]['details']['production']['license']='unknown'
        handoff.apply(self.root,manifest)
        self.write('unrelated.png',PNG)
        result=self.check('recorded')
        self.assertTrue(result['ok']);self.assertTrue(result['warnings'])
        manifest=self.manifest();manifest['assets'][0]['objectId']=''
        handoff.apply(self.root,manifest)
        self.assertFalse(self.check('recorded')['ok'])

    def test_move_preserves_id_and_derivation_has_separate_identity(self):
        handoff.apply(self.root,self.manifest())
        (self.root/'art.png').rename(self.root/'moved.png')
        handoff.apply(self.root,{'schema_version':1,'assets':[{'path':'moved.png','previousPath':'art.png','sha256':digest(self.root/'moved.png')}]})
        self.assertEqual(art_registry.load(self.root)['assets']['moved.png']['id'],'ART1')
        self.assertFalse(self.check('integrated','moved.png')['ok'])
        self.write('converted.png',PNG+b'derived')
        manifest=self.manifest('converted.png');row=manifest['assets'][0]
        row['id']='ART2';row['details']['production']['method']='converted';row['details']['derivedFrom']=['moved.png']
        handoff.apply(self.root,manifest)
        self.assertTrue(self.check(rel='converted.png')['ok'])
        self.assertEqual(len(art_registry.load(self.root)['assets']),2)

    def test_procedural_asset_has_real_code_entry(self):
        manifest=self.manifest('actor.gd');details=manifest['assets'][0]['details']
        details['production']['method']='procedural'
        details['integration']['state']='procedural'
        handoff.apply(self.root,manifest)
        self.assertTrue(self.check(rel='actor.gd')['ok'])

    def test_lock_and_existing_ui_write_preserve_production_metadata(self):
        handoff.apply(self.root,self.manifest())
        data=art_registry.load(self.root)
        with project_lock(self.root,'art-registry'):
            with self.assertRaises(ValueError):handoff.apply(self.root,self.manifest())
            with self.assertRaises(ValueError):art_registry.write(self.root,data,data['revision'])
        data['objects']['PLAYER']['tags'].append('ally')
        art_registry.write(self.root,data,data['revision'])
        self.assertTrue(self.check()['ok'])

    def test_job_external_results_auto_register_but_do_not_claim_import(self):
        context={'object':self.object,'source':'Fixture task','license':'test only'}
        job=asset_workflow.new_job(self.root,'image',{'parameters':{},'inputs':[],'art_record':context},{'mode':'host'})
        result=self.write('result.json',json.dumps({'artifacts':[{'path':'art.png'}]}))
        with redirect_stdout(io.StringIO()):
            code=asset_workflow.main(['--project',str(self.root),'register','--job',job['job_id'],'--result','result.json'])
        self.assertEqual(code,0)
        self.assertTrue(self.check('recorded')['ok'])
        self.assertFalse(self.check('integrated')['ok'])
        data=art_registry.load(self.root)
        detail=next(iter(data['lifecycle'].values()))
        self.assertEqual(detail['production']['method'],'existing')
        self.assertEqual(detail['selection']['state'],'candidate')

    def test_actual_local_worker_completion_registers_output(self):
        settings={'command':[sys.executable,'-B',str(RUNTIME/'tests/fixtures/local_asset_provider.py'),'{request}','{output}','{result}']}
        job=asset_workflow.new_job(self.root,'image',{'parameters':{},'inputs':[],
            'art_record':{'object':self.object,'license':'test only'}},settings)
        finished=asset_workflow.execute_job(self.root,job['job_id'],10)
        self.assertEqual(finished['status'],'succeeded')
        self.assertNotIn('art_registration_error',finished)
        rel=finished['artifacts'][0]['path']
        self.assertTrue(self.check('recorded',rel)['ok'])
        self.assertFalse(self.check('integrated',rel)['ok'])

    def test_registration_failure_preserves_output_and_can_repair_without_generation(self):
        job=asset_workflow.new_job(self.root,'image',{'parameters':{},'inputs':[],'art_record':{'object':self.object}},{'mode':'host'})
        self.write('result.json',json.dumps({'artifacts':[{'path':'art.png'}]}))
        self.write('Art Direction.md','<!-- art-objects:start -->\nbroken')
        with redirect_stdout(io.StringIO()):
            code=asset_workflow.main(['--project',str(self.root),'register','--job',job['job_id'],'--result','result.json'])
        self.assertEqual(code,1)
        _,saved=asset_workflow.read_job(self.root,job['job_id'])
        self.assertEqual(saved['status'],'registered');self.assertTrue(saved['art_registration_error'])
        self.assertEqual((self.root/'art.png').read_bytes(),PNG)
        self.write('Art Direction.md','# Fixed fixture\n')
        with patch.object(asset_workflow,'execute_job',side_effect=AssertionError('must not generate again')),redirect_stdout(io.StringIO()):
            code=asset_workflow.main(['--project',str(self.root),'sync-records','--job',job['job_id']])
        self.assertEqual(code,0);self.assertTrue(self.check('recorded')['ok'])

    def test_acquisition_and_reuse_auto_register(self):
        request={'title':'Fixture','source_url':'https://example.com/fixture','author':'fixture author','kind':'2d',
                 'license':{'name':'test','status':'unverified'},'files':[{'name':'art.png','local':'art.png'}],
                 'art_record':{'object':self.object}}
        first=asset_library.acquire(self.root,request)
        second=asset_library.acquire(self.root,request)
        self.assertTrue(second['reused'])
        self.assertEqual(first['asset_id'],second['asset_id'])
        self.assertTrue(self.check('recorded',first['files'][0]['path'])['ok'])
        self.assertFalse(self.check('integrated',first['files'][0]['path'])['ok'])

    def test_manual_versions_register_and_preserve_existing_known_records(self):
        handoff.apply(self.root,self.manifest())
        before=deepcopy(art_registry.load(self.root)['lifecycle'])
        result=asset_versions.mutate(self.root,{'action':'create','title':'fixture','kind':'image',
                                              'files':[{'path':'art.png','sha256':digest(self.root/'art.png')}]})
        self.assertNotIn('artRegistrationError',result)
        self.assertEqual(before,art_registry.load(self.root)['lifecycle'])
        self.assertTrue(self.check()['ok'])

    def test_cli_gate_returns_failure_before_registration_and_pass_after(self):
        scope=self.write('scope.json',json.dumps({'paths':['art.png'],'require':'integrated'}))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--project',str(self.root),'check','--scope',str(scope)]),1)
        handoff.apply(self.root,self.manifest())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--project',str(self.root),'check','--scope',str(scope)]),0)
            self.assertEqual(validate_records.main(['--project',str(self.root),'--asset-scope',str(scope)]),0)

    def test_task_close_requires_bound_asset_scope_and_rechecks_drift(self):
        task=task_state.create(self.root,{'id':'fixture','goal':'test gate','start_stage':1,'end_stage':1,
            'objects':[{'id':'PLAYER','title':'Player'}],'deliverables':['fixture'],
            'asset_scope':{'paths':['art.png'],'require':'verified'}})
        stage=task['stages'][0];stage.update(readiness='ready',outcome='supported')
        stage['reviews']={r['id']:{'result':'passed','reason':'fixture','observer':'test','evidence':['fixture']} for r in stage['requirements']}
        evidence=([{'objects':['PLAYER'],'source_type':'command','result':'passed'}],[])
        with patch.object(task_state,'evidence_status',return_value=evidence):
            self.assertFalse(task_state.status(self.root,task)['can_close'])
            with self.assertRaises(ValueError):task_state.apply_operation(self.root,task,{'action':'close','reason':'test'})
            handoff.apply(self.root,self.manifest())
            task_state.apply_operation(self.root,task,{'action':'close','reason':'test'})
            self.assertEqual(task['state'],'complete')
            self.write('actor.gd','changed')
            self.assertEqual(task_state.status(self.root,task)['effective_state'],'needs_revalidation')

    def test_paths_and_fabricated_evidence_are_rejected_without_registration(self):
        for mutate in (lambda r:r.update(path='../art.png'),
                       lambda r:r['details']['integration'].update(evidence=['missing.log']),
                       lambda r:r['details']['verification'].update(evidence=[])):
            manifest=self.manifest();mutate(manifest['assets'][0])
            with self.assertRaises(ValueError):handoff.apply(self.root,manifest)
        self.assertFalse((self.root/'Art Direction.md').exists())


if __name__=='__main__':
    unittest.main()

"""Protection boundaries and evidence checks, separate from real engine integration."""
from pathlib import Path
import sys
import tempfile
import os
import subprocess
import unittest
import json
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from adapters.engines import sessions as p
from adapters.engines.registry import production_driver
from adapters.engines.unity.production import helper_install
from validate_records import check_record


class ProductionContracts(unittest.TestCase):
    def test_published_requests_match_current_engine_contract(self):
        for engine in ('unity','unreal'):
            for path in (ROOT/'adapters/engines'/engine/'examples').glob('*.json'):
                with self.subTest(path=path.name, engine=engine):
                    production_driver(engine).validate_request(json.loads(path.read_text()))

    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.project=self.root/'game'; self.project.mkdir()
        self.session=self.root/'run'; self.session.mkdir()

    def record(self):
        (self.project/'old.txt').write_text('before')
        before=p.checkpoint(self.project,self.session/'before')
        (self.project/'old.txt').write_text('after')
        (self.project/'new.txt').write_text('new')
        record={'project':str(self.project),'status':'failed','before':before,'after':p.inventory(self.project)}
        p.write(self.session/'session.json',record)
        return record

    @patch.object(p,'ensure_idle')
    def test_restore_verifies_and_quarantines_new_files(self, idle):
        record=self.record()
        p.restore(self.project,self.session)
        self.assertEqual(p.inventory(self.project),record['before'])
        restored=p.read(self.session/'session.json')
        self.assertEqual((Path(restored['displaced'])/'new.txt').read_text(),'new')
        self.assertEqual((Path(restored['displaced'])/'old.txt').read_text(),'after')

    @patch.object(p,'ensure_idle')
    def test_later_edit_blocks_restore_without_partial_write(self, idle):
        self.record(); (self.project/'new.txt').write_text('user change')
        with self.assertRaisesRegex(ValueError,'changed since'): p.restore(self.project,self.session)
        self.assertEqual((self.project/'old.txt').read_text(),'after')

    @patch.object(p,'ensure_idle')
    def test_corrupt_checkpoint_rejected_before_restore(self, idle):
        self.record(); (self.session/'before/old.txt').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'corrupt'): p.restore(self.project,self.session)
        self.assertEqual((self.project/'old.txt').read_text(),'after')

    def test_wrong_project_restore_rejected(self):
        self.record(); other=self.root/'other'; other.mkdir()
        with self.assertRaisesRegex(ValueError,'another project'): p.restore(other,self.session)

    def test_running_session_cannot_restore(self):
        record=self.record(); record['status']='running'; p.write(self.session/'session.json',record)
        with self.assertRaisesRegex(ValueError,'Reconcile'): p.restore(self.project,self.session)

    def test_escape_rejected(self):
        for path in ['../other','.',str(self.root/'outside')]:
            with self.subTest(path=path),self.assertRaises(ValueError): p.inside(self.project,path)

    def test_helper_preserves_user_edits(self):
        helper_install(self.project)
        target=self.project/'Assets/Editor/OpenAIGamesDesigner/OAGDProduction.cs'
        target.write_text('// user changes')
        with self.assertRaisesRegex(ValueError,'user changes'): helper_install(self.project)
        self.assertEqual(target.read_text(),'// user changes')

    def test_helper_owned_upgrade(self):
        helper_install(self.project)
        target=self.project/'Assets/Editor/OpenAIGamesDesigner/OAGDProduction.cs'
        target.write_text('// earlier toolkit version')
        receipt=p.read(self.project/'.oagd-production-helpers.json')
        receipt['Editor/OpenAIGamesDesigner/OAGDProduction.cs']=p.digest(target)
        p.write(self.project/'.oagd-production-helpers.json',receipt)
        helper_install(self.project)
        self.assertEqual(target.read_bytes(),(ROOT/'adapters/engines/unity/OAGDProduction.cs').read_bytes())

    def test_later_dependency_conflict_does_not_partially_upgrade(self):
        helper_install(self.project)
        target=self.project/'Assets/Editor/OpenAIGamesDesigner/OAGDProduction.cs'
        target.write_text('// earlier toolkit version')
        receipt=p.read(self.project/'.oagd-production-helpers.json')
        receipt['Editor/OpenAIGamesDesigner/OAGDProduction.cs']=p.digest(target)
        p.write(self.project/'.oagd-production-helpers.json',receipt)
        shared=self.project/'Assets/Editor/OpenAIGamesDesigner/OAGDBuild.cs'
        shared.write_text('// user build helper')
        with self.assertRaisesRegex(ValueError,'user changes'): helper_install(self.project)
        self.assertEqual(target.read_text(),'// earlier toolkit version')
        self.assertEqual(shared.read_text(),'// user build helper')

    def test_identity_result_not_just_success_boolean(self):
        data={'success':True,'engine':'unity','request_id':'test','project':str(self.project),'version':'2022'}
        p.write(self.session/'result.json',data)
        self.assertTrue(p.native_result(self.session,self.project,'unity','test')['success'])
        for key,value in [('request_id','other'),('engine','unreal'),('project',str(self.root)),('version',''),('success',False)]:
            with self.subTest(key=key):
                bad={**data,key:value}; p.write(self.session/'result.json',bad)
                with self.assertRaises(ValueError): p.native_result(self.session,self.project,'unity','test')

    def test_inspect_rejects_writes_and_unknown_fields(self):
        for request in [dict(engine='unity',mode='inspect',operations=[{'op':'scene','path':'Assets/X.unity'}]),
                        dict(engine='unity',mode='inspect',actions=[]),dict(engine='unity',mode='inspect',mod='edit')]:
            with self.assertRaises(ValueError): production_driver('unity').validate_request(request)

    def test_playback_rejects_unbounded_or_wrong_engine_actions(self):
        base={'engine':'unreal','mode':'playback','scene':'/Game/Test','seconds':3}
        for changes in [{'seconds':float('nan')},{'seconds':300},{'actions':[{'op':'message','target':'A','at':1}]},
                        {'actions':[{'op':'position','target':'A','at':5}]}]:
            with self.assertRaises(ValueError): production_driver('unreal').validate_request({**base,**changes})

    def test_examples_validate(self):
        for engine in ['unity','unreal']:
            for path in (ROOT/'adapters/engines'/engine/'examples').glob('*.json'):
                production_driver(engine).validate_request(p.read(path))

    def test_engine_specific_fields_are_not_silently_accepted(self):
        source=self.root/'mesh.fbx'; source.touch()
        with self.assertRaisesRegex(ValueError,'Unknown operation fields'):
            production_driver('unity').validate_request({'engine':'unity','mode':'edit','operations':[
                {'op':'import','path':'Assets/Mesh.fbx','source':str(source),'skeletal':True}]})
        with self.assertRaisesRegex(ValueError,'Unknown operation fields'):
            production_driver('unreal').validate_request({'engine':'unreal','mode':'edit','operations':[
                {'op':'animation','target':'Hero','mesh':'/Game/Hero','controller':'Assets/Hero.controller'}]})

    def test_driver_native_launch_routes(self):
        config={'editor_executable':str(self.root/'UnrealEditor.exe'),'project_file':'Game.uproject'}
        (self.project/'Game.uproject').write_text('{}')
        request={'request_id':'test','mode':'inspect'}
        for engine, marker in [('unity','-executeMethod'),('unreal','-run=pythonscript')]:
            driver=production_driver(engine)
            with patch.object(p,'run') as run, patch.object(p,'native_result',return_value={'success':True}):
                driver.launch(config,self.project,self.session,request,30,{})
                argv=run.call_args.args[0]
                self.assertIn(marker,argv)
                self.assertNotIn('-run=pythonscript' if engine=='unity' else '-executeMethod',argv)

    def test_creation_belongs_to_selected_driver(self):
        from argparse import Namespace
        args=Namespace(editor=Path(sys.executable),name='Sample',brief='test',version='5.8',timeout=30)
        with patch.object(p,'run') as run:
            self.assertIsNone(production_driver('unity').create_project(args,self.root,self.project,self.session,{}))
            self.assertIn('-createProject',run.call_args.args[0])
        self.assertEqual(production_driver('unreal').create_project(args,self.root,self.project,self.session,{}),'Sample.uproject')
        self.assertTrue((self.project/'Sample.uproject').is_file())

    def test_selected_driver_rejects_other_engine_request(self):
        production_driver('unity').validate_request({'engine':'unity','mode':'inspect'})
        with self.assertRaises(ValueError):
            production_driver('unreal').validate_request({'engine':'unity','mode':'inspect'})

    def test_live_owner_blocks_recovery(self):
        with self.assertRaisesRegex(ValueError,'still alive'):
            p.ensure_stopped({'owner_pid':os.getpid()})

    def test_record_validation_detects_evidence_tampering(self):
        report=self.session/'result.json'; p.write(report,{'success':True})
        record={'schema_version':1,'project':str(self.project),'engine':'unity','status':'completed',
                'evidence_hashes':{'result.json':p.digest(report)}}
        self.assertEqual(check_record('engine-session',record,self.root,self.session/'session.json'),[])
        report.write_text('{}')
        self.assertTrue(check_record('engine-session',record,self.root,self.session/'session.json'))

    def test_timeout_stops_owned_process_and_preserves_other_process(self):
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        other=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],creationflags=flags)
        try:
            record={}
            with self.assertRaisesRegex(ValueError,'timed out'):
                p.run([sys.executable,'-c','import time; time.sleep(60)'],self.project,self.session/'process.log',.2,self.session,record)
            self.assertFalse(p.process_alive(record['pid']))
            self.assertIsNone(other.poll())
        finally:
            other.terminate(); other.wait(timeout=10)


if __name__=='__main__': unittest.main()

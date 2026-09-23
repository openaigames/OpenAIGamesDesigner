"""Cross-module recovery, evidence and command dispatch regression cases."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import engine_workflow as ew
import game_workflow as gw
import validate_records as vr
from adapters.engines import sessions as s
from adapters.engines.registry import production_driver


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.game = self.root / 'game'

    def setup_engine(self, engine):
        self.game.mkdir(exist_ok=True)
        config = {'schema_version':1, 'engine':engine, 'engine_root':'game', 'editor_executable':sys.executable}
        if engine == 'unity':
            (self.game/'Assets').mkdir(exist_ok=True)
            descriptor = self.game/'ProjectSettings/ProjectVersion.txt'
            descriptor.parent.mkdir(exist_ok=True)
            descriptor.write_text('m_EditorVersion: 2022.3.62f3c1\n')
        else:
            descriptor = self.game/'Test.uproject'
            descriptor.write_text('{"EngineAssociation":"5.8"}')
            config['project_file'] = descriptor.name
        s.write(self.root/'.openaigame/project.json', config)
        return descriptor

    def failed_session(self, engine):
        descriptor = self.setup_engine(engine)
        session = self.root/'runs/engine-broken'
        before = s.checkpoint(self.game, session/'before')
        descriptor.unlink()
        record = {'schema_version':1, 'engine':engine, 'project':str(self.game), 'status':'failed',
                  'before':before, 'after':s.inventory(self.game)}
        s.write(session/'session.json',record)
        return descriptor, session, record

    def test_restore_unity_with_missing_version_file(self):
        descriptor, session, _ = self.failed_session('unity')
        with patch.object(s,'ensure_idle'):
            self.assertEqual(ew.recover(self.root,session.name,True),session)
        self.assertTrue(descriptor.is_file())
        self.assertEqual(s.read(session/'session.json')['status'],'restored')
        self.assertIn('restored_engine_inspection',s.read(session/'session.json'))

    def test_restore_unreal_with_missing_project_descriptor(self):
        descriptor, session, _ = self.failed_session('unreal')
        with patch.object(s,'ensure_idle'):
            ew.recover(self.root,session.name,True)
        self.assertEqual(json.loads(descriptor.read_text())['EngineAssociation'],'5.8')

    def test_recovery_keeps_engine_identity_and_checkpoint_protection(self):
        descriptor, session, record = self.failed_session('unity')
        record['engine']='unreal'; s.write(session/'session.json',record)
        with self.assertRaisesRegex(ValueError,'engine'):
            ew.recover(self.root,session.name,True)
        record['engine']='unity'; s.write(session/'session.json',record)
        (session/'before/ProjectSettings/ProjectVersion.txt').write_text('corrupted')
        with patch.object(s,'ensure_idle'), self.assertRaisesRegex(ValueError,'corrupt'):
            ew.recover(self.root,session.name,True)
        self.assertFalse(descriptor.exists())

    def link_evidence(self, relative):
        self.game.mkdir(exist_ok=True)
        (self.game/'Test.uproject').write_text('{}')
        for name in ('Project Management.md','Risk & Assumption List.md'):
            (self.root/name).write_text(f'[engine](game/Test.uproject)\n[evidence]({relative})\n')

    def test_closeout_accepts_session_but_rejects_changed_evidence(self):
        relative='runs/engine-test/session.json'; self.link_evidence(relative)
        session=self.root/'runs/engine-test'
        s.write(session/'result.json',{'success':True})
        record={'schema_version':1,'project':str(self.game),'engine':'unreal','status':'completed',
                'evidence_hashes':{'result.json':s.digest(session/'result.json')}}
        s.write(session/'session.json',record)
        self.assertEqual(vr.closeout_errors(self.root),[])
        s.write(session/'result.json',{'success':False})
        self.assertTrue(vr.closeout_errors(self.root))

    def test_existing_and_explicit_report_roots(self):
        for relative in ('production/validation/check.md','custom/reports/check.md'):
            self.link_evidence(relative)
            path=self.root/relative; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Actual interrupted validation; quality remains unverified.')
            if relative.startswith('custom'):
                self.assertTrue(vr.closeout_errors(self.root))
                self.assertEqual(vr.closeout_errors(self.root,['custom/reports']),[])
            else:
                self.assertEqual(vr.closeout_errors(self.root),[])
        with self.assertRaises(ValueError): vr.closeout_errors(self.root,['../outside'])

    def create_with_fake_editor(self, fail=False):
        driver=production_driver('unity')
        def create(*args):
            if fail: raise ValueError('fixture creation failed')
            self.game.mkdir(exist_ok=True)
            (self.game/'Assets').mkdir()
            (self.game/'ProjectSettings').mkdir()
            (self.game/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 2022.3\n')
        def verify(*args):
            session=self.root/'runs/engine-verify'
            s.write(session/'session.json',{'schema_version':1,'project':str(self.game),'engine':'unity','status':'completed'})
            return session
        args=argparse.Namespace(project=self.root,engine='unity',editor=Path(sys.executable),name='Test',brief='test',version='',timeout=5)
        with patch.object(s,'ensure_idle'), patch.object(driver,'create_project',side_effect=create), patch.object(ew,'execute',side_effect=verify), contextlib.redirect_stdout(io.StringIO()):
            return ew.create(args)

    def test_creation_record_is_scanned_and_linked_verification_checked(self):
        session=self.create_with_fake_editor()
        record=s.read(session/'session.json')
        self.assertEqual(vr.check_record('engine-session',record,self.root,session/'session.json'),[])
        output=io.StringIO()
        with contextlib.redirect_stdout(output): code=vr.main(['--project',str(self.root)])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['records_checked'],3)
        (self.root/record['verification']).unlink()
        self.assertTrue(vr.check_record('engine-session',record,self.root,session/'session.json'))

    def test_failed_creation_is_valid_evidence_and_legacy_records_are_not_skipped(self):
        with self.assertRaisesRegex(ValueError,'fixture'): self.create_with_fake_editor(True)
        session=next((self.root/'runs').glob('create-*'))
        record=s.read(session/'session.json')
        self.assertEqual(vr.check_record('engine-session',record,self.root,session/'session.json'),[])
        del record['schema_version']; s.write(session/'session.json',record)
        output=io.StringIO()
        with contextlib.redirect_stdout(output): code=vr.main(['--project',str(self.root)])
        self.assertEqual(code,1)
        self.assertEqual(json.loads(output.getvalue())['records_checked'],1)

    def godot_override(self, action, report=None, output=False, returncode=0):
        self.game.mkdir(exist_ok=True)
        (self.game/'project.godot').write_text('[application]\nconfig/name="Fixture"')
        command=[sys.executable,'custom-tool.py','{project}','{run}','{output}']
        s.write(self.root/'.openaigame/project.json',{'schema_version':1,'engine':'godot','engine_root':'game',
                'godot_executable':sys.executable,'commands':{action:command}})
        calls=[]
        def execute(argv,cwd,log,timeout):
            calls.append(argv)
            if '--version' in argv:
                log.write_text('4.4.stable\n'); return 0,None
            log.write_text('custom execution\n')
            if report is not None: s.write(log.parent/'test-results.json',report)
            if output:
                destination=Path(argv[-1]); destination.mkdir(parents=True,exist_ok=True)
                (destination/'index.html').write_text('<html>actual fixture output</html>')
            return returncode,None
        with patch.object(gw,'execute',side_effect=execute), contextlib.redirect_stdout(io.StringIO()):
            code=gw.main(['run','--project',str(self.root),'--action',action])
        self.assertEqual(calls[-1][1],'custom-tool.py')
        self.assertNotIn('--headless',calls[-1])
        manifest=s.read(sorted((self.root/'runs').glob('*/manifest.json'))[-1])
        return code,manifest

    def test_godot_smoke_uses_custom_command_and_propagates_failure(self):
        code,record=self.godot_override('smoke',returncode=7)
        self.assertEqual(code,1)
        self.assertEqual(record['status'],'failed')
        self.assertEqual(record['commands'][-1]['exit_code'],7)

    def test_godot_custom_test_requires_real_report_without_native_marker(self):
        code,record=self.godot_override('test',{'tests':2,'failed':0,'errors':0})
        self.assertEqual(code,0)
        self.assertEqual(record['test_report']['tests'],2)

    def test_godot_custom_test_missing_report_fails(self):
        code,record=self.godot_override('test')
        self.assertEqual(code,1)
        self.assertEqual(record['status'],'failed')

    def test_godot_custom_export_without_preset_registers_output(self):
        code,record=self.godot_override('export',output=True)
        self.assertEqual(code,0)
        self.assertEqual(len(record['build_files']),1)

    def test_godot_custom_export_without_output_fails(self):
        code,record=self.godot_override('export')
        self.assertEqual(code,1)
        self.assertEqual(record['status'],'failed')

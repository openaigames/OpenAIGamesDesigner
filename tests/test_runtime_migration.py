import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import runtime_migration as m
import runtime_components as core

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.project=self.root/'project';self.project.mkdir();(self.project/'project.godot').write_text('config_version=5')
        self.sources={'addons/oagd/a.gd':b'old a','addons/oagd/b.gd':b'old b'}
        self.mock=patch.object(m,'sources',side_effect=lambda engine,package,toolkit=m.ROOT:dict(self.sources));self.mock.start()
        plan=m.plan(self.project,'godot',['core']);m.apply(self.project,plan,self.root/'install')
        (self.project/'game.gd').write_bytes(b'project game');(self.project/'save.json').write_bytes(b'project save')
    def tearDown(self):self.mock.stop();self.temp.cleanup()
    def content(self):return {p.relative_to(self.project).as_posix():p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
    def test_migration_preserves_customization_and_rollback_is_byte_exact(self):
        (self.project/'addons/oagd/a.gd').write_bytes(b'project a');before=self.content();self.sources['addons/oagd/b.gd']=b'new b'
        plan=m.plan(self.project,'godot',['core']);self.assertEqual(plan['preserved'],['addons/oagd/a.gd']);self.assertFalse(plan['conflicts'])
        m.apply(self.project,plan,self.root/'upgrade');self.assertEqual((self.project/'addons/oagd/a.gd').read_bytes(),b'project a');self.assertEqual((self.project/'addons/oagd/b.gd').read_bytes(),b'new b')
        self.assertEqual((self.project/'game.gd').read_bytes(),b'project game');m.rollback(self.project,self.root/'upgrade');self.assertEqual(before,self.content())
    def test_both_changed_conflict_leaves_every_file_untouched(self):
        (self.project/'addons/oagd/a.gd').write_bytes(b'project a');self.sources['addons/oagd/a.gd']=b'new a';before=self.content();plan=m.plan(self.project,'godot',['core'])
        self.assertEqual(plan['conflicts'],['addons/oagd/a.gd'])
        with self.assertRaisesRegex(ValueError,'Conflicts'):m.apply(self.project,plan,self.root/'conflict')
        self.assertEqual(before,self.content());self.assertFalse((self.root/'conflict').exists())
    def test_stale_project_and_stale_toolkit_plans_are_rejected(self):
        plan=m.plan(self.project,'godot',['core']);(self.project/'addons/oagd/b.gd').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Stale'):m.apply(self.project,plan,self.root/'stale')
        plan=m.plan(self.project,'godot',['core']);self.sources['addons/oagd/a.gd']=b'new'
        with self.assertRaisesRegex(ValueError,'Stale'):m.apply(self.project,plan,self.root/'stale-source')
    def test_rollback_refuses_new_project_edits_and_damaged_backup(self):
        self.sources['addons/oagd/b.gd']=b'new b';m.apply(self.project,m.plan(self.project,'godot',['core']),self.root/'upgrade')
        target=self.project/'addons/oagd/b.gd';target.write_bytes(b'later edit');before=self.content()
        with self.assertRaisesRegex(ValueError,'changed after'):m.rollback(self.project,self.root/'upgrade')
        self.assertEqual(before,self.content());target.write_bytes(b'new b');(self.root/'upgrade/0.before').write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError,'integrity'):m.rollback(self.project,self.root/'upgrade')
    def test_unowned_collision_and_deleted_local_customization(self):
        self.sources['addons/oagd/c.gd']=b'new c';(self.project/'addons/oagd/c.gd').write_bytes(b'unowned')
        self.assertIn('addons/oagd/c.gd',m.plan(self.project,'godot',['core'])['conflicts'])
        del self.sources['addons/oagd/c.gd'];(self.project/'addons/oagd/b.gd').unlink()
        plan=m.plan(self.project,'godot',['core']);self.assertIn('addons/oagd/b.gd',plan['preserved']);m.apply(self.project,plan,self.root/'preserve-delete');self.assertFalse((self.project/'addons/oagd/b.gd').exists())
    def test_removed_upstream_file_and_new_file_restore_on_rollback(self):
        before=self.content();del self.sources['addons/oagd/b.gd'];self.sources['addons/oagd/new.gd']=b'new'
        m.apply(self.project,m.plan(self.project,'godot',['core']),self.root/'remove-add');self.assertFalse((self.project/'addons/oagd/b.gd').exists());m.rollback(self.project,self.root/'remove-add');self.assertEqual(before,self.content())
    def test_paths_cannot_escape_project_or_backup(self):
        for path in ('../outside','C:/outside','addons/../../outside','..\\outside'):
            with self.subTest(path=path),self.assertRaises(ValueError):m.safe(self.project,path)
    def test_native_pin_updates_without_migrating_project_template(self):
        pin={'engine':'godot','component_version':'old','files':{p:m.sha(b) for p,b in self.sources.items()}}
        m.write(self.project/core.LOCK,pin);self.sources['addons/oagd/b.gd']=b'new b'
        m.apply(self.project,m.plan(self.project,'godot',['core']),self.root/'pin')
        self.assertEqual(core.status(self.project)['changed'],[]);self.assertEqual(core.status(self.project)['component_version'],core.VERSION)
    def test_catchable_write_failure_restores_prior_files(self):
        before=self.content();self.sources['addons/oagd/a.gd']=b'new a';self.sources['addons/oagd/b.gd']=b'new b';plan=m.plan(self.project,'godot',['core']);original=Path.replace
        def failing(path,target):
            if str(target).endswith('b.gd'):raise OSError('injected write failure')
            return original(path,target)
        with patch.object(Path,'replace',failing),self.assertRaisesRegex(OSError,'injected'):m.apply(self.project,plan,self.root/'failed')
        self.assertEqual(before,self.content());self.assertEqual(m.read(self.root/'failed/receipt.json')['state'],'reverted-on-error')

class PackageChoiceTests(unittest.TestCase):
    def test_unreal_packages_install_independently_and_rollback_in_reverse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';game.mkdir()
            project=game/'Game.uproject';project.write_text(json.dumps({'EngineAssociation':'5.8'}))
            original=project.read_bytes()
            m.apply(game,m.plan(game,'unreal',['core']),root/'core')
            self.assertTrue((game/'Plugins/OAGDCore/OAGDCore.uplugin').is_file())
            self.assertFalse((game/'Plugins/OAGDPlayback').exists())
            before={p.relative_to(game).as_posix():p.read_bytes() for p in game.rglob('*') if p.is_file()}
            m.apply(game,m.plan(game,'unreal',['playback']),root/'playback')
            self.assertTrue((game/'Plugins/OAGDPlayback/OAGDPlayback.uplugin').is_file())
            self.assertFalse((game/'Config').exists());self.assertEqual(project.read_bytes(),original)
            self.assertEqual(m.plan(game,'unreal',['core','playback'])['actions'],[])
            m.rollback(game,root/'playback')
            self.assertEqual(before,{p.relative_to(game).as_posix():p.read_bytes() for p in game.rglob('*') if p.is_file()})
            m.rollback(game,root/'core')
            self.assertEqual([project],[p for p in game.rglob('*') if p.is_file()])
    def test_playback_package_can_be_installed_without_core_or_game_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';game.mkdir();(game/'project.godot').write_text('config_version=5')
            before=(game/'project.godot').read_bytes();plan=m.plan(game,'godot',['playback']);m.apply(game,plan,root/'receipt')
            self.assertTrue((game/'addons/oagd_playback/oagd_playback.gd').is_file());self.assertFalse((game/'addons/oagd').exists());self.assertFalse((game/'bindings.json').exists())
            self.assertEqual((game/'project.godot').read_bytes(),before);self.assertEqual(m.plan(game,'godot',['playback'])['actions'],[])
            m.rollback(game,root/'receipt');self.assertFalse((game/'addons/oagd_playback/oagd_playback.gd').exists())
    def test_unreal_wrong_minor_version_is_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'Game.uproject').write_text(json.dumps({'EngineAssociation':'5.7'}))
            with self.assertRaisesRegex(ValueError,'5.8'):m.plan(root,'unreal',['core'])
            self.assertFalse((root/'Plugins').exists())

if __name__=='__main__':unittest.main()

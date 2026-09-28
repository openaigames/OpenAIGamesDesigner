"""Configured native content roots agree in scanning and role/action validation."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import content_roots
from workbench import asset_browser, character_bindings


class ContentRootTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def file(self,name,content=b'fixture'):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def config(self,engine='unreal',engine_root='.',**extra):
        self.file('.openaigame/project.json',json.dumps({'schema_version':1,'engine':engine,'engine_root':engine_root,**extra}).encode())

    def test_default_custom_and_root_native_layouts_match_bindings(self):
        for engine_root in ('game','NativeProject','.'):
            with self.subTest(root=engine_root):
                self.config(engine_root=engine_root)
                prefix=engine_root+'/' if engine_root!='.' else ''
                model=prefix+'Content/Hero.uasset'
                animation=prefix+'Content/Attack.uasset'
                dependencies={p:self.file(p) for p in (model,animation)}
                self.file('.asset-browser/characters.json',json.dumps({'version':1,'dependencies':dependencies,
                    'characters':[{'id':'hero','model':model,'actions':[{'label':'Attack','path':animation}]}]}).encode())
                result=asset_browser.scan(self.root)
                self.assertEqual(result['characters'][0]['actions'][0]['path'],animation)
                rows={r['path']:r for r in result['assets']}
                self.assertEqual(rows[model]['location'],'game')
                self.assertEqual(rows[animation]['location'],'game')

    def test_root_project_does_not_claim_sources_builds_or_project_documents(self):
        self.config()
        for name in ('Content/Hero.uasset','assets-source/Hero.fbx','design/layout.png','builds/Hero.fbx','previews/Hero.fbx'):
            self.file(name)
        self.assertTrue(content_roots.in_game('Content/Hero.uasset',self.root))
        for name in ('assets-source/Hero.fbx','design/layout.png','builds/Hero.fbx','previews/Hero.fbx'):
            self.assertFalse(content_roots.in_game(name,self.root),name)

    def test_godot_root_excludes_records_and_honors_explicit_content(self):
        self.config(engine='godot',content_roots=['resources'])
        self.assertTrue(content_roots.in_game('resources/hero.glb',self.root))
        self.assertFalse(content_roots.in_game('assets-source/hero.glb',self.root))
        self.config(engine='godot')
        self.assertFalse(content_roots.in_game('production/preview.png',self.root))
        self.assertTrue(content_roots.in_game('resources/hero.glb',self.root))

    def test_invalid_and_escaping_config_is_visible_not_silently_defaulted(self):
        self.config(engine_root='../another-project')
        outcome=content_roots.classify(self.root,'game/Hero.fbx')
        self.assertEqual(outcome['location'],'candidate')
        self.assertIn('无法确认',outcome['reason'])
        self.config(engine_root='game',content_roots=['sources'])
        self.assertEqual(content_roots.layout(self.root)['mode'],'invalid')

    def test_unity_and_unreal_plugin_content_and_exclusions(self):
        self.config(engine='unity',engine_root='UnityGame')
        self.assertTrue(content_roots.in_game('UnityGame/Assets/Hero.fbx',self.root))
        self.assertFalse(content_roots.in_game('UnityGame/Library/Hero.fbx',self.root))
        self.file('Plugins/Pack/Content/Hero.uasset')
        self.config(asset_exclude_roots=['Content/SourceCopies'])
        self.assertTrue(content_roots.in_game('Plugins/Pack/Content/Hero.uasset',self.root))
        self.assertFalse(content_roots.in_game('Content/SourceCopies/Hero.fbx',self.root))

    def test_custom_root_candidate_cannot_be_claimed_by_character_manifest(self):
        self.config(engine_root='Native')
        files={p:self.file(p) for p in ('Native/Content/Hero.uasset','sources/Attack.fbx')}
        self.file('.asset-browser/characters.json',json.dumps({'version':1,'dependencies':files,
            'characters':[{'id':'hero','model':'Native/Content/Hero.uasset','actions':[{'label':'Attack','path':'sources/Attack.fbx'}]}]}).encode())
        result=asset_browser.scan(self.root)
        self.assertEqual(result['characters'],[])
        self.assertTrue(result['characterBindingError'])

    def test_engine_checkpoints_and_generated_preview_history_are_not_candidates(self):
        self.config()
        for name in ['runs/session/before/Content/Hero.uasset','previews/engine/session/Hero.fbx','sources/Hero.fbx','Content/Hero.uasset']:
            self.file(name)
        self.assertEqual({a['path'] for a in asset_browser.scan(self.root)['assets']},{'sources/Hero.fbx','Content/Hero.uasset'})


if __name__=='__main__':
    unittest.main()

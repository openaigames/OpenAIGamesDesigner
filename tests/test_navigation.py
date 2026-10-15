import json
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import runtime_components as runtime

class NavigationExamplesTests(unittest.TestCase):
    def test_godot_independent_rules_configuration_and_component_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b'
            for p in (a,b):runtime.create(p,'godot','navigation')
            self.assertNotEqual(json.loads((a/'input-profile.json').read_text())['id'],json.loads((b/'input-profile.json').read_text())['id'])
            original=(b/'navigation-profile.json').read_bytes();(a/'navigation-profile.json').write_text('{"custom":true}')
            self.assertEqual(original,(b/'navigation-profile.json').read_bytes())
            self.assertTrue((a/'npc_behavior.gd').is_file())
            self.assertIn('navigation-profile.json',(a/'export_presets.cfg').read_text())
            self.assertFalse((a/'addons/oagd_playback').exists())
            self.assertEqual(runtime.status(a)['changed'],[])
            (a/'addons/oagd/oagd_navigation.gd').write_text('# project edits')
            with self.assertRaisesRegex(ValueError,'local edits'):runtime.install(a,'godot')

    def test_unreal_native_navigation_dependencies_and_cook_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);engine=root/'ue';version=engine/'Engine/Build';version.mkdir(parents=True)
            (version/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':8,'PatchVersion':2}))
            p=root/'game';runtime.create(p,'unreal','navigation',engine)
            self.assertIn('RuntimeGeneration=Dynamic',(p/'Config/DefaultEngine.ini').read_text())
            self.assertIn('/Game/Navigation',(p/'Config/DefaultGame.ini').read_text())
            self.assertIn('/Game/Example',(p/'Config/DefaultGame.ini').read_text())
            self.assertIn('NavigationSystem',(p/'Plugins/OAGDCore/Source/OAGDCore/OAGDCore.Build.cs').read_text())
            self.assertTrue((p/'Content/OAGDData/navigation-profile.json').is_file())
            self.assertTrue((p/'Plugins/OAGDCore/Source/OAGDCore/Public/OAGDNavigation.h').is_file())
            self.assertFalse((p/'Plugins/OAGDPlayback').exists())
            self.assertEqual(runtime.status(p)['changed'],[])

if __name__=='__main__':unittest.main()

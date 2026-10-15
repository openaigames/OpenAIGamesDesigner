import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import runtime_components as runtime

class InteractionExamplesTests(unittest.TestCase):
    def test_godot_generation_preserves_independent_configuration_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b';runtime.create(a,'godot','interaction');runtime.create(b,'godot','interaction')
            self.assertNotEqual(json.loads((a/'input-profile.json').read_text())['id'],json.loads((b/'input-profile.json').read_text())['id'])
            original=(b/'interaction-profile.json').read_bytes()
            (a/'interaction-profile.json').write_text('{"project_custom":true}')
            self.assertEqual((b/'interaction-profile.json').read_bytes(),original)
            self.assertIn('interaction-profile.json',(a/'export_presets.cfg').read_text())
            self.assertTrue((a/'addons/oagd/oagd_interaction.gd').is_file())
            self.assertTrue((a/'addons/oagd/oagd_interactable.gd').is_file())
            self.assertFalse((a/'addons/oagd_playback').exists())
            self.assertEqual(runtime.status(a)['changed'],[])

    def test_unreal_maps_and_visual_resources_are_declared_for_cooking(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'ue/Engine/Build';fake.mkdir(parents=True)
            (fake/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':8,'PatchVersion':2}))
            game=root/'game';runtime.create(game,'unreal','interaction',root/'ue')
            self.assertIn('/Game/Example',(game/'Config/DefaultGame.ini').read_text())
            self.assertIn('/Game/Interaction',(game/'Config/DefaultGame.ini').read_text())
            self.assertTrue((game/'Content/OAGDData/interaction-profile.json').is_file())
            self.assertTrue((game/'Plugins/OAGDCore/Source/OAGDCore/Public/OAGDInteraction.h').is_file())
            self.assertEqual(runtime.status(game)['changed'],[])
            self.assertFalse((game/'Plugins/OAGDPlayback').exists())
            # Installer may not overwrite a game's customized component.
            (game/'Plugins/OAGDCore/Source/OAGDCore/Public/OAGDInteraction.h').write_text('// game customization')
            with self.assertRaisesRegex(ValueError,'local edits'):runtime.install(game,'unreal',root/'ue')

if __name__=='__main__':unittest.main()

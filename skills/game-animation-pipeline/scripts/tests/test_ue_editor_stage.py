"""Check configuration before legacy editor helpers can create a map."""
from pathlib import Path
import os
import runpy
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'ue_editor_stage.py'


class BeforeMapCreation(Exception):
    pass


class LabModuleTests(unittest.TestCase):
    def run_stage(self, module, unreal):
        environment = {'ANIMLAB_WORKSPACE': str(SCRIPT.parent), 'ANIMLAB_STAGE': 'build-stage'}
        if module is not None:
            environment['ANIMLAB_MODULE'] = module
        with patch.dict(os.environ, environment, clear=True), patch.dict('sys.modules', {'unreal': unreal}):
            runpy.run_path(str(SCRIPT), run_name='test_editor_stage')

    def test_missing_module_fails_before_editor_access(self):
        unreal = Mock()
        with self.assertRaisesRegex(RuntimeError, 'ANIMLAB_MODULE'):
            self.run_stage(None, unreal)
        self.assertEqual(unreal.mock_calls, [])

    def test_invalid_module_path_fails_before_editor_access(self):
        unreal = Mock()
        with self.assertRaisesRegex(RuntimeError, 'ANIMLAB_MODULE'):
            self.run_stage('../Other.Module', unreal)
        self.assertEqual(unreal.mock_calls, [])

    def test_uncompiled_module_does_not_create_level(self):
        unreal = Mock()
        unreal.load_class.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'Compile and load'):
            self.run_stage('CustomLab', unreal)
        unreal.load_class.assert_called_once_with(None, '/Script/CustomLab.AnimationLabMode')
        unreal.get_editor_subsystem.assert_not_called()

    def test_custom_module_resolves_before_map_creation(self):
        unreal = Mock()
        unreal.get_editor_subsystem.side_effect = BeforeMapCreation()
        with self.assertRaises(BeforeMapCreation):
            self.run_stage('MyAnimationLab', unreal)
        unreal.load_class.assert_called_once_with(None, '/Script/MyAnimationLab.AnimationLabMode')
        unreal.EditorAssetLibrary.does_asset_exist.assert_not_called()


if __name__ == '__main__':
    unittest.main()

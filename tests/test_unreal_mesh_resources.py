"""Request protection tests. Native processing requires the separate UE fixture."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.engines.unreal.production import validate_request, worker_files
from adapters.engines.unreal import mesh_contract


class MeshRequests(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((ROOT/'adapters/engines/unreal/examples/mesh-configure.json').read_text())

    def invalid(self, recipe):
        with self.assertRaises(ValueError):
            validate_request(recipe)

    def test_published_examples(self):
        for name in ('mesh-audit', 'mesh-configure'):
            validate_request(json.loads((ROOT/f'adapters/engines/unreal/examples/{name}.json').read_text()))

    def test_source_and_path_are_distinct(self):
        self.recipe['operations'][0]['path'] = self.recipe['operations'][0]['source']
        self.invalid(self.recipe)

    def test_destination_is_game_package(self):
        for path in ['/Engine/Test', '/Game/A/../B', '/Game/X.X', '/Game//A', '/Game/A/']:
            recipe = copy.deepcopy(self.recipe)
            recipe['operations'][0]['path'] = path
            self.invalid(recipe)

    def test_levels_are_ordered_and_lod0_preserved(self):
        for key, value, index in [('percent_triangles', .8, 0), ('percent_triangles', .9, 2),
                                  ('screen_size', .4, 2), ('screen_size', -1, 2),
                                  ('percent_triangles', float('nan'), 1), ('screen_size', True, 1)]:
            recipe = copy.deepcopy(self.recipe)
            recipe['operations'][0]['lods'][index][key] = value
            self.invalid(recipe)

    def test_nanite_requires_platform_decision(self):
        del self.recipe['operations'][1]['platform_supports_nanite']
        self.invalid(self.recipe)

    def test_no_conflicting_strategies(self):
        self.recipe['operations'][1]['lods'] = self.recipe['operations'][0]['lods']
        self.invalid(self.recipe)

    def test_fallback_parameter_has_explicit_target(self):
        self.recipe['operations'][1]['nanite']['fallback_target'] = 'auto'
        self.invalid(self.recipe)

    def test_preserve_area_only_foliage(self):
        self.recipe['operations'][1]['nanite']['preserve_area'] = True
        self.invalid(self.recipe)
        self.recipe['operations'][1]['asset_role'] = 'foliage'
        validate_request(self.recipe)

    def test_collision_lod_exists(self):
        self.recipe['operations'][0]['lod_for_collision'] = 3
        self.invalid(self.recipe)

    def test_no_duplicate_destinations(self):
        self.recipe['operations'][1]['path'] = self.recipe['operations'][0]['path']
        self.invalid(self.recipe)

    def test_audit_does_not_mutate(self):
        self.recipe['mode'] = 'inspect'
        self.invalid(self.recipe)
        self.invalid({'engine': 'unreal', 'mode': 'edit', 'mesh_audit': {'paths': ['/Engine/BasicShapes/Sphere']}})

    def test_audit_scope_and_limits_explicit(self):
        for audit in ({}, {'include_scene': True}, {'paths': [{}]}, {'paths': ['/Game/A'], 'warning_limits': {'triangles': 0}},
                      {'paths': ['/Game/A', '/Game/A']}, {'paths': ['/Game/A'], 'delete': True}):
            self.invalid({'engine': 'unreal', 'mode': 'inspect', 'mesh_audit': audit})
        validate_request({'engine': 'unreal', 'mode': 'inspect', 'scene': '/Game/Map',
                          'mesh_audit': {'include_scene': True, 'warning_limits': {'triangles': 50000}}})

    def test_workers_in_evidence_manifest(self):
        names = {path.name for path in worker_files()}
        self.assertTrue({'mesh_contract.py', 'static_meshes.py'} <= names)

    def worker(self):
        fake = SimpleNamespace(EditorAssetLibrary=MagicMock())
        fake.EditorAssetLibrary.does_asset_exist.return_value = False
        spec = importlib.util.spec_from_file_location('test_mesh_worker', ROOT/'adapters/engines/unreal/static_meshes.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'unreal': fake, 'mesh_contract': mesh_contract}):
            spec.loader.exec_module(module)
        return module, fake

    def test_existing_asset_rejected_before_load_or_duplicate(self):
        worker, fake = self.worker()
        fake.EditorAssetLibrary.does_asset_exist.return_value = True
        load = MagicMock()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            worker.configure(self.recipe['operations'][0], load, lambda path: path)
        load.assert_not_called()
        fake.EditorAssetLibrary.duplicate_asset.assert_not_called()

    def test_nanite_unsupported_or_unknown_material_rejected_before_duplicate(self):
        worker, fake = self.worker()
        for supported in [False, None]:
            with patch.object(worker, 'inspect_mesh', return_value={'materials': [{'nanite_blend_supported': supported}]}):
                with self.assertRaisesRegex(ValueError, 'Opaque/Masked'):
                    worker.configure(self.recipe['operations'][1], MagicMock(), lambda path: path)
        fake.EditorAssetLibrary.duplicate_asset.assert_not_called()

    def test_existing_collision_lod_is_not_silently_clamped(self):
        worker, fake = self.worker()
        with patch.object(worker, 'inspect_mesh', return_value={'collision': {'lod': 7}}):
            with self.assertRaisesRegex(ValueError, 'collision LOD'):
                worker.configure(self.recipe['operations'][0], MagicMock(), lambda path: path)
        fake.EditorAssetLibrary.duplicate_asset.assert_not_called()


if __name__ == '__main__':
    unittest.main()

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from workbench import asset_browser, character_bindings


class CharacterBindingsTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'dist' / ('characters-test-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(self.root))

    def file(self, path, data=b'asset'):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def fixture(self):
        model, action = 'game/model.uasset', 'game/attack.uasset'
        deps = {p: self.file(p) for p in (model, action)}
        data = {'version': 1, 'dependencies': deps, 'characters': [{'id': 'hero', 'model': model,
                'role': 'player', 'title': 'Hero', 'actions': [{'label': 'Attack', 'path': action}]}]}
        self.file('.asset-browser/characters.json', json.dumps(data).encode())
        return data

    def test_location_is_folder_fact_without_registration_or_usage(self):
        for p in ('game/hero.fbx', 'Game/other.fbx', 'gameplay/hero.fbx', 'sources/game/hero.fbx'):
            self.file(p)
        rows = {a['path']: a for a in asset_browser.scan(self.root)['assets']}
        self.assertEqual(rows['game/hero.fbx']['location'], 'game')
        self.assertTrue(character_bindings.in_game('Game/other.fbx'))
        self.assertEqual(next(a['location'] for p,a in rows.items() if p.endswith('/other.fbx')), 'game')
        self.assertEqual(rows['gameplay/hero.fbx']['location'], 'candidate')
        self.assertEqual(rows['sources/game/hero.fbx']['location'], 'candidate')
        self.assertEqual(rows['game/hero.fbx']['usage']['status'], 'local')
        self.assertFalse((self.root / '.openaigame').exists())

    def test_explicit_character_actions_and_stale_binding(self):
        self.fixture()
        result = asset_browser.scan(self.root)
        self.assertEqual(result['characters'][0]['actions'][0]['label'], 'Attack')
        self.file('game/attack.uasset', b'new version')
        result = asset_browser.scan(self.root)
        self.assertEqual(result['characters'], [])
        self.assertIn('变化', result['characterBindingError'])
        self.assertEqual(len(result['assets']), 2)

    def test_candidates_cannot_be_claimed_as_bound_game_actions(self):
        data = self.fixture()
        data['dependencies']['outside.fbx'] = self.file('outside.fbx')
        data['characters'][0]['actions'][0]['path'] = 'outside.fbx'
        self.file('.asset-browser/characters.json', json.dumps(data).encode())
        result = asset_browser.scan(self.root)
        self.assertEqual(result['characters'], [])
        self.assertTrue(result['characterBindingError'])

    def test_no_dependency_or_escape_is_accepted(self):
        data = self.fixture()
        del data['dependencies']['game/attack.uasset']
        self.file('.asset-browser/characters.json', json.dumps(data).encode())
        self.assertFalse(asset_browser.scan(self.root)['characters'])
        data['dependencies']['../outside.fbx'] = 'invalid'
        self.file('.asset-browser/characters.json', json.dumps(data).encode())
        self.assertFalse(asset_browser.scan(self.root)['characters'])

    def test_fbx_preview_versions_and_no_duplicate_candidates(self):
        data = self.fixture()
        preview = 'previews/hero.fbx'
        hashed = self.file(preview, b'Kaydara FBX Binary  \x00\x1a\x00' + bytes(40))
        mapping = {'version': 1, 'assets': {'game/model.uasset': {'path': preview, 'sha256': hashed,
                    'source_sha256': data['dependencies']['game/model.uasset'], 'dependencies': {}}}}
        self.file('.asset-browser/previews.json', json.dumps(mapping).encode())
        rows = {a['path']: a for a in asset_browser.scan(self.root)['assets']}
        self.assertEqual(rows['game/model.uasset']['previewExt'], 'FBX')
        self.assertTrue(rows[preview]['previewCopy'])
        self.file(preview, b'changed')
        rows = {a['path']: a for a in asset_browser.scan(self.root)['assets']}
        self.assertEqual(rows['game/model.uasset']['preview'], 'unavailable')
        self.assertTrue(rows[preview]['previewCopy'])


if __name__ == '__main__':
    unittest.main()

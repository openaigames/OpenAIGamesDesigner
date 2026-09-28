"""Motion decisions stay tied to watched content and never become active game data."""
from __future__ import annotations

import http.client
import json
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import project_workbench as wb
from workbench import art_registry as registry, asset_browser, motion_review as review


def animation_fixture(root):
    """One triangle, three named clips (two duplicate names), external animation data."""
    model = root / 'actor.gltf'
    vertices = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    times = struct.pack('<2f', 0, 1)
    positions = struct.pack('<6f', 0, 0, 0, 0, 1, 0)
    (root / 'actor.bin').write_bytes(vertices + times + positions)
    document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                'nodes': [{'name': 'Actor', 'mesh': 0}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
                'buffers': [{'uri': 'actor.bin', 'byteLength': 68}],
                'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36},
                                {'buffer': 0, 'byteOffset': 36, 'byteLength': 8},
                                {'buffer': 0, 'byteOffset': 44, 'byteLength': 24}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]},
                              {'bufferView': 1, 'componentType': 5126, 'count': 2, 'type': 'SCALAR', 'min': [0], 'max': [1]},
                              {'bufferView': 2, 'componentType': 5126, 'count': 2, 'type': 'VEC3'}],
                'animations': [{'name': name, 'samplers': [{'input': 1, 'output': 2}],
                                'channels': [{'sampler': 0, 'target': {'node': 0, 'path': 'translation'}}]}
                               for name in ('Thrust', 'Thrust', 'Roar')]}
    model.write_text(json.dumps(document), encoding='utf-8')
    registry.initialize(root)
    art = registry.load(root)
    registry.register(root, art, asset_browser.scan(root)['assets'], ['actor.gltf'])
    registry.write(root, art, art['revision'])
    return model, document


class MotionReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='oagd-motion-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.model, self.document = animation_fixture(self.root)

    def payload(self, index=0, **choice):
        snapshot = review.snapshot(self.root)
        entry = next(e for e in snapshot['entries'] if e['clip_index'] == index)
        return {'revision': snapshot['revision'], 'asset_id': entry['asset_id'], 'clip_index': index,
                'fingerprint': entry['source']['fingerprint'],
                'choice': {'decision': 'keep', 'role': 'boss', 'semantic': 'thrust', 'mirror': False,
                           'root_motion': 'in_place', 'note': 'No knockdown', **choice}}

    def test_read_only_duplicate_names_history_and_candidate_export(self):
        original = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(len(review.snapshot(self.root)['entries']), 3)
        self.assertFalse((self.root / '.asset-browser').exists())
        review.save(self.root, self.payload())
        review.save(self.root, self.payload(1, decision='reject', note='Too agile'))
        review.save(self.root, self.payload(note='Heavy thrust; mirror right hand', mirror=True))
        snapshot = review.snapshot(self.root)
        self.assertEqual(snapshot['history_count'], 3)
        report = review.handoff(self.root)
        self.assertEqual(report['runtime_validation'], 'not_checked')
        self.assertEqual([r['clip_index'] for r in report['candidates']], [0])
        self.assertTrue(report['candidates'][0]['choice']['mirror'])
        self.assertEqual({e['decision'] for e in report['excluded']}, {'reject', 'pending'})
        self.assertEqual(report['excluded'][0]['review']['choice']['note'], 'Too agile')
        for name, data in original.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_dependency_change_reorder_missing_and_re_review(self):
        request = self.payload()
        review.save(self.root, request)
        binary = self.root / 'actor.bin'
        binary.write_bytes(binary.read_bytes() + b'changed')
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'], 'stale')
        self.assertEqual(review.handoff(self.root)['candidates'], [])
        request['revision'] = review.snapshot(self.root)['revision']
        with self.assertRaises(registry.RevisionConflict):
            review.save(self.root, request)
        review.save(self.root, self.payload())
        self.document['animations'].reverse()
        self.model.write_text(json.dumps(self.document))
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'], 'stale')
        binary.unlink()
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'], 'unavailable')
        self.assertEqual(review.handoff(self.root)['candidates'], [])
        self.assertEqual(review.load(self.root)[0]['history'][0]['clip_name'], 'Thrust')

    def test_concurrent_edit_and_invalid_payload_never_overwrite(self):
        old_request = self.payload()
        review.save(self.root, self.payload(note='Another browser'))
        path = self.root / '.asset-browser/motion-review.json'
        before = path.read_bytes()
        with self.assertRaises(registry.RevisionConflict):
            review.save(self.root, old_request)
        for choice in ({'mirror': 'yes'}, {'role': 'unassigned'}, {'semantic': ''}, {'decision': 'approved'}, {'note': 'x' * 2001}):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                review.save(self.root, self.payload(**choice))
        self.assertEqual(path.read_bytes(), before)
        path.write_bytes(b'')
        with self.assertRaises(ValueError):
            review.load(self.root)
        self.assertEqual(path.read_bytes(), b'')

    def test_no_remote_dependency_paths_symlinks_or_unregistered_saves(self):
        art = registry.load(self.root)
        art['assets'].clear()
        registry.write(self.root, art, art['revision'])
        self.assertEqual(review.snapshot(self.root)['entries'], [])
        for uri in ('https://example.invalid/actor.bin', '../outside.bin', '/tmp/file.bin', 'actor.bin?token=bad'):
            with self.subTest(uri=uri):
                self.document['buffers'][0]['uri'] = uri
                self.model.write_text(json.dumps(self.document))
                row = asset_browser.scan(self.root)['assets'][0]
                with self.assertRaises(ValueError):
                    review.source_version(self.root, row)
        (self.root / '.asset-browser').symlink_to(self.root / 'elsewhere', target_is_directory=True)
        with self.assertRaises(ValueError):
            review.load(self.root)

    def test_engine_preview_identity_and_dependency_invalidation(self):
        self.document['buffers'][0].pop('uri')
        raw = json.dumps(self.document).encode()
        raw += b' ' * (-len(raw) % 4)
        binary = (self.root / 'actor.bin').read_bytes()
        preview = self.root / 'preview.glb'
        preview.write_bytes(struct.pack('<4sII', b'glTF', 2, 28 + len(raw) + len(binary)) +
                            struct.pack('<II', len(raw), 0x4E4F534A) + raw +
                            struct.pack('<II', len(binary), 0x004E4942) + binary)
        source = self.root / 'actor.uasset';source.write_bytes(b'engine source')
        dependency = self.root / 'material.uasset';dependency.write_bytes(b'material')
        folder = self.root / '.asset-browser';folder.mkdir()
        mapping = {'version': 1, 'assets': {'actor.uasset': {'path': 'preview.glb',
                   'source_sha256': registry.digest(source), 'sha256': registry.digest(preview),
                   'dependencies': {'material.uasset': registry.digest(dependency)}}}}
        (folder / 'previews.json').write_text(json.dumps(mapping))
        art = registry.load(self.root)
        registry.register(self.root, art, asset_browser.scan(self.root)['assets'], ['actor.uasset'])
        registry.write(self.root, art, art['revision'])
        view = review.snapshot(self.root)
        entry = next(e for e in view['entries'] if e['path'] == 'actor.uasset')
        payload = self.payload()
        payload.update(asset_id=entry['asset_id'], fingerprint=entry['source']['fingerprint'])
        review.save(self.root, payload)
        self.assertEqual(review.handoff(self.root)['candidates'][0]['path'], 'actor.uasset')
        dependency.write_bytes(b'new material')
        self.assertEqual(review.handoff(self.root)['candidates'], [])
        self.assertEqual(next(e for e in review.snapshot(self.root)['entries'] if e['asset_id'] == entry['asset_id'])['state'], 'unavailable')

    def test_http_session_csrf_and_conflict_status(self):
        server = wb.WorkbenchServer(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        def stop():
            server.shutdown();server.server_close();thread.join(3)
        self.addCleanup(stop)
        def request(route, payload=None, authorized=True, csrf=True):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Origin': server.origin, 'Content-Type': 'application/json'}
            if authorized:headers['Cookie'] = server.cookie_name + '=' + server.session
            if csrf:headers['X-CSRF-Token'] = server.csrf
            connection.request('GET' if payload is None else 'POST', route,
                               None if payload is None else json.dumps(payload), headers)
            response = connection.getresponse();status = response.status
            data = json.loads(response.read());connection.close()
            return status, data
        self.assertEqual(request('/api/motion-review', authorized=False)[0], 401)
        self.assertEqual(request('/api/motion-handoff?project=other')[0], 404)
        payload = self.payload()
        self.assertEqual(request('/api/motion-review', payload, csrf=False)[0], 403)
        self.assertEqual(request('/api/motion-review', payload)[0], 200)
        self.assertEqual(request('/api/motion-review', payload)[0], 409)
        self.assertEqual(len(request('/api/motion-handoff')[1]['candidates']), 1)
        rows = request('/api/assets')[1]['assets']
        self.assertEqual(rows[0]['motionFingerprint'], payload['fingerprint'])


if __name__ == '__main__':
    unittest.main()

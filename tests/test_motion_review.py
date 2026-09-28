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
    return model, document



def context(role='boss', character=None, rig=None, use='general'):
    return {'character_id':character,'role':role,'use':use,'rig_path':rig}


class MotionReviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='oagd-motion-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.model,self.document=animation_fixture(self.root)

    def preview(self, path='actor.gltf', **ctx):
        return {'path':path,'context':context(**ctx)}

    def payload(self, index=0, preview=None, **choice):
        preview=preview or self.preview();view=review.describe(self.root,preview)
        return {'revision':view['revision'],'preview':preview,'clip_index':index,
                'fingerprint':view['source']['fingerprint'],'choice':{
                    'decision':'keep','role':preview['context']['role'],'semantic':'thrust',
                    'mirror':False,'root_motion':'in_place','note':'No knockdown',**choice}}

    def test_read_only_without_registration_duplicate_names_and_independent_roles(self):
        original={p.name:p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(len(review.describe(self.root,self.preview())['entries']),3)
        self.assertFalse((self.root/'.asset-browser').exists())
        review.save(self.root,self.payload())
        review.save(self.root,self.payload(1,decision='reject'))
        review.save(self.root,self.payload(preview=self.preview(role='player'),note='Player use'))
        review.save(self.root,self.payload(preview=self.preview(use='finisher'),note='Separate use'))
        report=review.handoff(self.root)
        self.assertEqual(len(report['candidates']),3)
        self.assertEqual({r['context']['role'] for r in report['candidates']},{'player','boss'})
        self.assertEqual(report['excluded'][0]['clip_index'],1)
        self.assertEqual(report['runtime_validation'],'not_checked')
        self.assertFalse((self.root/'Art Direction.md').exists())
        for name,data in original.items():self.assertEqual((self.root/name).read_bytes(),data)
        self.assertFalse((self.root/'game').exists())

    def test_dependency_change_reorder_missing_and_re_review(self):
        request=self.payload();review.save(self.root,request)
        binary=self.root/'actor.bin';binary.write_bytes(binary.read_bytes()+b'changed')
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'],'stale')
        self.assertFalse(review.handoff(self.root)['candidates'])
        request['revision']=review.load(self.root)[1]
        with self.assertRaises(registry.RevisionConflict):review.save(self.root,request)
        review.save(self.root,self.payload())
        self.document['animations'].reverse();self.model.write_text(json.dumps(self.document))
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'],'stale')
        binary.unlink()
        self.assertEqual(review.snapshot(self.root)['entries'][0]['state'],'unavailable')
        self.assertEqual(review.load(self.root)[0]['history'][0]['clip_name'],'Thrust')

    def test_concurrency_invalid_payload_corruption_and_hash_tampering(self):
        request=self.payload();review.save(self.root,request)
        path=self.root/'.asset-browser/motion-review.json';before=path.read_bytes()
        with self.assertRaises(registry.RevisionConflict):review.save(self.root,request)
        for choice in ({'mirror':'yes'},{'role':'unassigned'},{'semantic':''},{'decision':'approved'},{'note':'x'*2001}):
            with self.subTest(choice=choice),self.assertRaises(ValueError):review.save(self.root,self.payload(**choice))
        self.assertEqual(path.read_bytes(),before)
        for raw in (b'',b'{"schema_version":3,"history":[]}',b'broken'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):review.load(self.root)
            self.assertEqual(path.read_bytes(),raw)
        value=json.loads(before);value['history'][0]['source']['files']['actor.gltf']='a'*64
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'校验失败'):review.load(self.root)

    def test_external_dependency_boundaries(self):
        for uri in ('https://example.invalid/a.bin','../outside.bin','/tmp/file.bin','actor.bin?token=bad'):
            with self.subTest(uri=uri):
                self.document['buffers'][0]['uri']=uri;self.model.write_text(json.dumps(self.document))
                with self.assertRaises(ValueError):review.describe(self.root,self.preview())
        bad=self.preview();bad['context']['rig_path']='../../outside.fbx'
        with self.assertRaises(ValueError):review.describe(self.root,bad)

    def test_metadata_symlink_rejected(self):
        target=self.root/'elsewhere';target.mkdir()
        try:(self.root/'.asset-browser').symlink_to(target,target_is_directory=True)
        except OSError as error:
            if getattr(error,'winerror',None)!=1314:raise
            import subprocess
            result=subprocess.run(['cmd','/c','mklink','/J',str(self.root/'.asset-browser'),str(target)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(ValueError):review.load(self.root)

    def binding(self):
        import shutil
        game=self.root/'game';game.mkdir()
        for name in ('actor.gltf','actor.bin'):shutil.copy2(self.root/name,game/name)
        deps={'game/'+n:registry.digest(game/n) for n in ('actor.gltf','actor.bin')}
        characters=[{'id':role,'title':role,'role':role,'model':'game/actor.gltf',
                     'actions':[{'label':'Thrust','path':'game/actor.gltf'}],'dependencies':deps.copy()}
                    for role in ('player','boss')]
        path=self.root/'.asset-browser/characters.json';path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'version':1,'characters':characters}))
        return path,characters

    def test_character_context_and_per_character_binding_invalidation(self):
        path,characters=self.binding()
        for role in ('player','boss'):
            review.save(self.root,self.payload(preview=self.preview('game/actor.gltf',role=role,character=role)))
        self.assertEqual(len(review.handoff(self.root)['candidates']),2)
        characters[1]['title']='Renamed other character';path.write_text(json.dumps({'version':1,'characters':characters}))
        self.assertEqual(len(review.handoff(self.root)['candidates']),2)
        characters[1]['consumer']='new component';path.write_text(json.dumps({'version':1,'characters':characters}))
        self.assertEqual([r['context']['character_id'] for r in review.handoff(self.root)['candidates']],['player'])
        self.assertEqual(len(review.handoff(self.root,'player')['candidates']),1)
        bad=self.preview(character='player')
        with self.assertRaises(ValueError):review.describe(self.root,bad)

    def test_fbx_observation_and_temporary_rig_version(self):
        # Backend protocol fixture only. Actual FBX parsing is covered by the Blender/browser run.
        (self.root/'motion.fbx').write_bytes(b'FBX protocol fixture')
        (self.root/'rig.fbx').write_bytes(b'FBX rig protocol fixture')
        preview=self.preview('motion.fbx',rig='rig.fbx')
        first=review.describe(self.root,preview)
        self.assertEqual(first['entries'],[])
        preview['observation']={'fingerprint':first['source']['fingerprint'],
                                'clips':[{'name':'same','duration':1},{'name':'same','duration':2}]}
        review.save(self.root,self.payload(1,preview=preview))
        self.assertEqual(review.handoff(self.root)['candidates'][0]['clip_index'],1)
        self.assertEqual(review.handoff(self.root)['candidates'][0]['provenance'],'browser_fbx_observation')
        (self.root/'rig.fbx').write_bytes(b'changed')
        self.assertFalse(review.handoff(self.root)['candidates'])
        with self.assertRaises(registry.RevisionConflict):review.describe(self.root,preview)

    def test_native_preview_mapping(self):
        self.document['buffers'][0].pop('uri');raw=json.dumps(self.document).encode();raw+=b' '*(-len(raw)%4)
        binary=(self.root/'actor.bin').read_bytes();preview=self.root/'preview.glb'
        preview.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(raw)+len(binary))+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(binary),0x004E4942)+binary)
        source=self.root/'actor.uasset';source.write_bytes(b'engine source')
        dependency=self.root/'material.uasset';dependency.write_bytes(b'material')
        folder=self.root/'.asset-browser';folder.mkdir()
        mapping={'version':1,'assets':{'actor.uasset':{'path':'preview.glb','source_sha256':registry.digest(source),
                  'sha256':registry.digest(preview),'dependencies':{'material.uasset':registry.digest(dependency)}}}}
        (folder/'previews.json').write_text(json.dumps(mapping))
        review.save(self.root,self.payload(preview=self.preview('actor.uasset')))
        self.assertEqual(review.handoff(self.root)['candidates'][0]['path'],'actor.uasset')
        dependency.write_bytes(b'changed')
        self.assertFalse(review.handoff(self.root)['candidates'])

    def test_v1_migration_preserves_exact_backup_and_resource_context(self):
        source=review.source_version(self.root,asset_browser.scan(self.root)['assets'][0])
        legacy={'schema_version':1,'history':[{'asset_id':'old-art-id','path':'actor.gltf','clip_index':0,
            'clip_name':'Thrust','source':source,'choice':self.payload()['choice'],'reviewed_at':'old'}]}
        path=self.root/'.asset-browser/motion-review.json';path.parent.mkdir();raw=json.dumps(legacy).encode();path.write_bytes(raw)
        view=review.snapshot(self.root)
        self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(view['entries'][0]['state'],'stale')
        self.assertIsNone(view['entries'][0]['context']['character_id'])
        review.save(self.root,self.payload())
        backup=path.with_name('motion-review.v1.'+review._hash(raw)+'.json')
        self.assertEqual(backup.read_bytes(),raw)
        self.assertEqual(review.load(self.root)[0]['schema_version'],2)
        self.assertEqual(len(review.load(self.root)[0]['history']),2)
        self.assertEqual(len(review.handoff(self.root)['candidates']),1)

    def test_busy_writer_does_not_override(self):
        import record_io
        request=self.payload()
        with record_io.project_lock(self.root,'motion-review'):
            with self.assertRaisesRegex(ValueError,'writer'):review.save(self.root,request)
        self.assertFalse((self.root/'.asset-browser/motion-review.json').exists())

    def test_http_session_csrf_and_conflict_status(self):
        server=wb.WorkbenchServer(self.root);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def stop():server.shutdown();server.server_close();thread.join(3)
        self.addCleanup(stop)
        def request(route,payload=None,authorized=True,csrf=True):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            headers={'Origin':server.origin,'Content-Type':'application/json'}
            if authorized:headers['Cookie']=server.cookie_name+'='+server.session
            if csrf:headers['X-CSRF-Token']=server.csrf
            connection.request('GET' if payload is None else 'POST',route,None if payload is None else json.dumps(payload),headers)
            response=connection.getresponse();status=response.status;data=json.loads(response.read());connection.close();return status,data
        self.assertEqual(request('/api/motion-review',authorized=False)[0],401)
        self.assertEqual(request('/api/motion-handoff?project=other')[0],404)
        self.assertEqual(request('/api/motion-context',self.preview())[0],200)
        payload=self.payload()
        self.assertEqual(request('/api/motion-review',payload,csrf=False)[0],403)
        self.assertEqual(request('/api/motion-review',payload)[0],200)
        self.assertEqual(request('/api/motion-review',payload)[0],409)
        self.assertEqual(len(request('/api/motion-handoff')[1]['candidates']),1)
        self.assertEqual(request('/api/production')[0],200)
        self.assertEqual(request('/api/asset-review')[0],200)


if __name__=='__main__':unittest.main()

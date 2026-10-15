"""Static input boundaries, identity, dependency and old-pipeline compatibility."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import static_scene as scene
import static_assets
from templates.static_scene.make_fixtures import create


class StaticSceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = create(self.root/'source')
        self.path = self.assets/'door.gltf'
        self.doc = json.loads(self.path.read_text())

    def changed(self, edit):
        edit(self.doc)
        self.path.write_text(json.dumps(self.doc))
        return self.path

    def reject(self, edit):
        self.changed(edit)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            scene.prepare(self.path, self.root/'invalid')
        self.assertFalse((self.root/'invalid').exists())

    def test_hierarchy_instances_and_names(self):
        p = scene.prepare(self.path, self.root/'revision')
        self.assertEqual(len(p['nodes']), 7)
        self.assertEqual(len(p['meshes']), 4)
        self.assertEqual(p['nodes'][1]['name'], p['nodes'][2]['name'])
        self.assertEqual(p['nodes'][6]['parent'], 5)
        d, _, _, _ = scene.inspect(self.root/'revision/scene.glb')
        self.assertEqual(len(d['nodes']), 7)
        self.assertEqual(scene.read_plan(self.root/'revision'), p)

    def test_dependency_bytes_and_source_protection(self):
        before = {p: scene.sha(p) for p in self.assets.rglob('*') if p.is_file()}
        scene.prepare(self.path, self.root/'revision')
        _, _, original, _ = scene.read_source(self.path)
        _, _, frozen, _ = scene.read_source(self.root/'revision/scene.glb')
        self.assertEqual(sorted(scene.hashlib.sha256(b).hexdigest() for _, b in original), sorted(scene.hashlib.sha256(b).hexdigest() for _, b in frozen))
        self.assertTrue(all(scene.sha(p)==h for p,h in before.items()))

    def test_selection_keeps_ancestors(self):
        p = scene.prepare(self.path, self.root/'revision', [6])
        self.assertEqual([n['id'] for n in p['nodes']], [0, 4, 5, 6])

    def test_invalid_selection(self):
        for ids in ([], [99], [1,1], [True]):
            with self.assertRaises(ValueError): scene.inspect(self.path, ids)

    def test_cycle(self): self.reject(lambda d: d['nodes'][6].update(children=[0]))
    def test_multiple_parents(self): self.reject(lambda d: d['nodes'][2].update(children=[6]))
    def test_nonuniform_scale(self): self.reject(lambda d: d['nodes'][4].update(scale=[1,2,1]))
    def test_mirror_scale(self): self.reject(lambda d: d['nodes'][4].update(scale=[-1,1,1]))
    def test_nan_transform(self): self.reject(lambda d: d['nodes'][4].update(translation=[0,float('nan'),0]))
    def test_bad_quaternion(self): self.reject(lambda d: d['nodes'][4].update(rotation=[1,1,1,1]))
    def test_matrix_and_trs(self): self.reject(lambda d: d['nodes'][4].update(matrix=scene.IDENTITY))
    def test_shear(self):
        def edit(d):
            m=scene.IDENTITY.copy();m[4]=.4;d['nodes'][1]['matrix']=m
        self.reject(edit)
    def test_skin(self): self.reject(lambda d: d.update(skins=[{}]))
    def test_animation(self): self.reject(lambda d: d.update(animations=[{}]))
    def test_unknown_extension(self): self.reject(lambda d: d.update(extensionsUsed=['KHR_draco_mesh_compression']))
    def test_undeclared_nested_extension(self): self.reject(lambda d: d['nodes'][1].update(extensions={'UNKNOWN':{}}))
    def test_uv1(self): self.reject(lambda d: d['materials'][0]['normalTexture'].update(texCoord=1))
    def test_alpha(self): self.reject(lambda d: d['materials'][0].update(alphaMode='BLEND'))
    def test_ao(self): self.reject(lambda d: d['materials'][0].update(occlusionTexture={'index':2}))
    def test_missing_uv(self): self.reject(lambda d: d['meshes'][1]['primitives'][0]['attributes'].pop('TEXCOORD_0'))
    def test_remote_uri(self): self.reject(lambda d: d['images'][0].update(uri='https://example.test/a.png'))
    def test_data_uri(self): self.reject(lambda d: d['images'][0].update(uri='data:image/png;base64,AA=='))
    def test_escape_uri(self):
        (self.root/'outside.png').write_bytes((self.assets/'textures/color.png').read_bytes())
        self.reject(lambda d: d['images'][0].update(uri='../outside.png'))
    def test_percent_escape_uri(self): self.reject(lambda d: d['images'][0].update(uri='%2e%2e/outside.png'))
    def test_missing_dependency(self): self.reject(lambda d: d['images'][0].update(uri='absent.png'))
    def test_bad_buffer_range(self): self.reject(lambda d: d['bufferViews'][0].update(byteLength=999999999))
    def test_bad_accessor_range(self): self.reject(lambda d: d['accessors'][4].update(count=999999999))
    def test_invalid_indices(self):
        p=self.doc['meshes'][1]['primitives'][0];a=self.doc['accessors'][p['indices']];v=self.doc['bufferViews'][a['bufferView']]
        data=bytearray((self.assets/'geometry.bin').read_bytes());struct.pack_into('<H',data,v['byteOffset'],65535);(self.assets/'geometry.bin').write_bytes(data)
        with self.assertRaises(ValueError): scene.inspect(self.path)
    def test_no_overwrite(self):
        p=scene.prepare(self.path,self.root/'revision')
        with self.assertRaises(ValueError): scene.prepare(self.path,self.root/'revision')
        self.assertEqual(scene.read_plan(self.root/'revision'),p)
    def test_frozen_file_changed(self):
        scene.prepare(self.path,self.root/'revision');(self.root/'revision/scene.glb').write_bytes(b'changed')
        with self.assertRaises(ValueError): scene.read_plan(self.root/'revision')
    def test_frozen_plan_changed(self):
        scene.prepare(self.path,self.root/'revision');p=self.root/'revision/plan.json';d=json.loads(p.read_text());d['nodes'][0]['name']='changed';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError): scene.read_plan(self.root/'revision')
    def test_old_pipeline_still_rejects_complex_assets(self):
        scene.prepare(self.path,self.root/'revision')
        with self.assertRaises(ValueError): static_assets.inspect_glb(self.root/'revision/scene.glb')
    def test_uniform_scale_matrix(self):
        self.changed(lambda d: d['nodes'][0].update(scale=[2,2,2]))
        p=scene.prepare(self.path,self.root/'revision');self.assertEqual(p['nodes'][0]['local_matrix'][5],2)
    def test_glb_truncation(self):
        scene.prepare(self.path,self.root/'revision');p=self.root/'revision/scene.glb';p.write_bytes(p.read_bytes()[:-4])
        with self.assertRaises(ValueError): scene.inspect(p)


if __name__ == '__main__': unittest.main()

import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import scene_handoff as h
from static_scene import sha,fingerprint
from templates.static_scene.make_fixtures import create

class SceneHandoffTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.project=self.root/'author';self.project.mkdir()
  (self.project/'RECEIVE.md').write_text('Declared entry; no automatic execution');(self.project/'provenance.md').write_text('Project-authored fixture; explicit source record')
  create(self.project/'source')
  self.spec={'id':'Reception','files':['RECEIVE.md','provenance.md','source/door.gltf'],'engines':{'godot':'4.7.2','unreal':'5.8.2'},'entrypoints':{'instructions':'RECEIVE.md'},'provenance':['provenance.md']}
  self.snapshot=self.root/'snapshot'
 def build(self):return h.create(self.project,self.spec,self.snapshot)
 def test_auto_dependencies_and_roundtrip(self):
  before={p:sha(p) for p in self.project.rglob('*') if p.is_file()};created=self.build()
  self.assertTrue((self.snapshot/'source/geometry.bin').is_file());self.assertTrue((self.snapshot/'source/textures/color.png').is_file())
  self.assertEqual(h.receive(self.snapshot,self.root/'receiver')['snapshot_id'],created['snapshot_id']);self.assertTrue(all(sha(p)==digest for p,digest in before.items()))
 def test_missing_declared_source(self):
  self.spec['files'].append('absent');self.assertRaises(ValueError,self.build);self.assertFalse(self.snapshot.exists())
 def test_missing_gltf_dependency(self):
  (self.project/'source/geometry.bin').unlink();self.assertRaises(ValueError,self.build);self.assertFalse(self.snapshot.exists())
 def test_changed_source_after_pack_not_required(self):
  self.build();(self.project/'source/geometry.bin').write_bytes(b'changed');self.assertTrue(h.receive(self.snapshot,self.root/'receiver')['ok'])
 def test_tampered_payload(self):
  self.build();(self.snapshot/'source/geometry.bin').write_bytes(b'bad');self.assertRaises(ValueError,h.receive,self.snapshot,self.root/'receiver');self.assertFalse((self.root/'receiver').exists())
 def test_missing_payload(self):
  self.build();(self.snapshot/'source/geometry.bin').unlink();self.assertRaises(ValueError,h.check,self.snapshot)
 def test_unexpected_file(self):
  self.build();(self.snapshot/'unlisted.py').write_text('do not execute');self.assertRaises(ValueError,h.receive,self.snapshot,self.root/'receiver')
 def test_nonpristine_receiver_can_have_generated_files(self):
  self.build();h.receive(self.snapshot,self.root/'receiver');(self.root/'receiver/generated.txt').write_text('native output');self.assertTrue(h.check(self.root/'receiver')['ok'])
 def test_tampered_manifest(self):
  self.build();p=self.snapshot/h.MANIFEST;d=json.loads(p.read_text());d['engines']['unreal']='other';p.write_text(json.dumps(d));self.assertRaises(ValueError,h.check,self.snapshot)
 def test_duplicate_casefold_path(self):
  self.spec['files'].append('receive.md');self.assertRaises(ValueError,self.build)
 def test_missing_entrypoint(self):
  self.spec['entrypoints']['code']='unknown';self.assertRaises(ValueError,self.build)
 def test_missing_provenance(self):
  self.spec['provenance']=[];self.assertRaises(ValueError,self.build)
 def test_output_inside_author_refused(self):self.assertRaises(ValueError,h.create,self.project,self.spec,self.project/'output')
 def test_no_receiver_overwrite(self):
  self.build();d=self.root/'receiver';d.mkdir();(d/'custom').write_text('keep');self.assertRaises(ValueError,h.receive,self.snapshot,d);self.assertEqual((d/'custom').read_text(),'keep')
 def test_unsafe_paths(self):
  for name in ['../secret','/absolute','C:/absolute','a\\b','./a','a//b']:
   with self.subTest(name=name):self.assertRaises(ValueError,h.path,self.project,name)
 def test_reserved_metadata(self):
  (self.project/h.MANIFEST).write_text('{}');self.spec['files'].append(h.MANIFEST);self.assertRaises(ValueError,self.build)
 def test_rehashed_escape_still_refused(self):
  self.build();p=self.snapshot/h.MANIFEST;d=json.loads(p.read_text());d['files']['../secret']='0'*64;d['snapshot_id']=fingerprint({k:v for k,v in d.items() if k!='snapshot_id'});p.write_text(json.dumps(d));self.assertRaises(ValueError,h.check,self.snapshot)
 def test_interrupted_receive_never_claims_complete(self):
  self.build();dest=self.root/'partial';real=h.shutil.copy2;count=0
  def fail(source,target):
   nonlocal count
   count+=1
   if count==3:raise OSError('Injected storage failure')
   return real(source,target)
  with patch.object(h.shutil,'copy2',fail):self.assertRaises(OSError,h.receive,self.snapshot,dest)
  self.assertFalse((dest/h.MANIFEST).exists());self.assertRaises(ValueError,h.receive,self.snapshot,dest)
  self.assertTrue(h.receive(self.snapshot,self.root/'fresh')['ok'])
 def test_remote_dependency_refused(self):
  p=self.project/'source/door.gltf';d=json.loads(p.read_text());d['buffers'][0]['uri']='https://example.test/data.bin';p.write_text(json.dumps(d));self.assertRaises(ValueError,self.build)

if __name__=='__main__':unittest.main()

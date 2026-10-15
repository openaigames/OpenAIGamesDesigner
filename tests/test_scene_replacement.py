"""Immutable replacement transactions and rejection boundaries (no engine mock pass)."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import static_scene,scene_replacement as replacement
from templates.static_scene.make_fixtures import create

class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        create(self.root/'source');self.asset=static_scene.prepare(self.root/'source/door.gltf',self.root/'revision')
        self.baseline={'schema':'oagd.scene-baseline/1','engine':'godot','objects':{'GrayDoor':{'snapshot':{'class':'MeshInstance3D'},'fingerprint':'a'*64}}}
        self.manifest={'schema':replacement.SCHEMA,'id':'DoorUpgrade','assets':{'door':{'revision':'revision','plan_id':self.asset['plan_id']}},'replacements':[{'id':'Door','targets':['GrayDoor'],'asset':'door','position':[0,0,0],'yaw_degrees':0,'scale':1,'collision':{'policy':'boxes','boxes':[{'node':5,'center':[.55,1.025,0],'size':[1.1,2.05,.08]}]}}]}
    def write(self):
        (self.root/'baseline.json').write_text(json.dumps(self.baseline));(self.root/'mapping.json').write_text(json.dumps(self.manifest))
    def prepare(self):
        self.write();return replacement.prepare(self.root,'baseline.json','mapping.json',self.root/'transaction')
    def reject(self,edit):
        edit(self.manifest['replacements'][0])
        with self.assertRaises((ValueError,TypeError,KeyError)):self.prepare()
        self.assertFalse((self.root/'transaction').exists())
    def test_roundtrip_frozen_dependencies(self):
        before={p:static_scene.sha(p) for p in self.root.rglob('*') if p.is_file()};p=self.prepare()
        self.assertEqual(replacement.read_plan(self.root/'transaction'),p)
        self.assertEqual(static_scene.sha(self.root/'transaction/assets/door/scene.glb'),static_scene.sha(self.root/'revision/scene.glb'))
        self.assertTrue(all(static_scene.sha(p)==h for p,h in before.items()))
    def test_unreal_plan(self):
        self.baseline['engine']='unreal';self.assertEqual(self.prepare()['engine'],'unreal')
    def test_signed_zero_roundtrip_identity(self):
        self.assertEqual(static_scene.fingerprint([replacement.state_number(-0.0)]),static_scene.fingerprint([replacement.state_number(0.0)]))
        self.assertNotEqual(static_scene.fingerprint([replacement.state_number(-0.0,False)]),static_scene.fingerprint([replacement.state_number(0.0,False)]))
        self.assertNotEqual(replacement.state_number(.001),replacement.state_number(0))
    def test_unknown_native_fingerprint_format(self):
        self.baseline['fingerprint_format']='unknown'
        with self.assertRaises(ValueError):self.prepare()
    def test_fixed_mesh_selection(self):
        self.manifest['replacements'][0]['collision']={'policy':'source_mesh','nodes':[1,2,3,5]};self.prepare()
    def test_retain_collision(self):
        self.manifest['replacements'][0]['collision']={'policy':'retain_graybox'};self.prepare()
    def test_no_overwrite(self):
        p=self.prepare()
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(replacement.read_plan(self.root/'transaction'),p)
    def test_duplicate_target(self):self.reject(lambda r:r.update(targets=['GrayDoor','GrayDoor']))
    def test_unknown_target(self):self.reject(lambda r:r.update(targets=['Absent']))
    def test_unknown_asset(self):self.reject(lambda r:r.update(asset='Absent'))
    def test_target_name_collision(self):self.reject(lambda r:r.update(id='GrayDoor'))
    def test_pathlike_id(self):self.reject(lambda r:r.update(id='../Door'))
    def test_nan_position(self):self.reject(lambda r:r.update(position=[0,float('nan'),0]))
    def test_boolean_scale(self):self.reject(lambda r:r.update(scale=True))
    def test_negative_scale(self):self.reject(lambda r:r.update(scale=-1))
    def test_unbounded_scale(self):self.reject(lambda r:r.update(scale=1001))
    def test_missing_collision(self):self.reject(lambda r:r.pop('collision'))
    def test_implicit_collision(self):self.reject(lambda r:r.update(collision={'policy':'automatic'}))
    def test_mesh_on_empty_hinge(self):self.reject(lambda r:r.update(collision={'policy':'source_mesh','nodes':[4]}))
    def test_duplicate_mesh_nodes(self):self.reject(lambda r:r.update(collision={'policy':'source_mesh','nodes':[1,1]}))
    def test_boolean_mesh_node(self):self.reject(lambda r:r.update(collision={'policy':'source_mesh','nodes':[True]}))
    def test_mesh_nodes_wrong_type(self):self.reject(lambda r:r.update(collision={'policy':'source_mesh','nodes':'1'}))
    def test_zero_box_dimension(self):self.reject(lambda r:r['collision']['boxes'][0].update(size=[1,0,1]))
    def test_box_unknown_node(self):self.reject(lambda r:r['collision']['boxes'][0].update(node=99))
    def test_retain_cannot_add_proxy(self):self.reject(lambda r:r.update(collision={'policy':'retain_graybox','boxes':[]}))
    def test_multiple_groups_cannot_share_target(self):
        self.manifest['replacements'].append(copy.deepcopy(self.manifest['replacements'][0]));self.manifest['replacements'][1]['id']='Other'
        with self.assertRaises(ValueError):self.prepare()
    def test_missing_baseline_snapshot(self):
        self.baseline['objects']['GrayDoor'].pop('snapshot')
        with self.assertRaises(ValueError):self.prepare()
    def test_changed_revision_identity(self):
        self.manifest['assets']['door']['plan_id']='a'*64
        with self.assertRaises(ValueError):self.prepare()
    def test_project_path_escape(self):
        self.manifest['assets']['door']['revision']='../outside'
        with self.assertRaises(ValueError):self.prepare()
    def test_unused_asset(self):
        self.manifest['assets']['unused']=copy.deepcopy(self.manifest['assets']['door'])
        with self.assertRaises(ValueError):self.prepare()
    def test_plan_tamper(self):
        self.prepare();p=self.root/'transaction/plan.json';d=json.loads(p.read_text());d['replacements'][0]['scale']=2;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):replacement.read_plan(p.parent)
    def test_frozen_mesh_tamper(self):
        self.prepare();p=self.root/'transaction/assets/door/scene.glb';p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaises(ValueError):replacement.read_plan(self.root/'transaction')
    def rewrite_plan(self,edit):
        d=self.prepare();edit(d);d['plan_id']=static_scene.fingerprint({k:v for k,v in d.items() if k!='plan_id'});(self.root/'transaction/plan.json').write_text(json.dumps(d))
    def test_rehashed_inconsistent_nodes(self):
        self.rewrite_plan(lambda d:d['assets']['door']['nodes'][0].update(mesh=99))
        with self.assertRaises(ValueError):replacement.read_plan(self.root/'transaction')
    def test_rehashed_wrong_engine(self):
        self.rewrite_plan(lambda d:d.update(engine='unreal'))
        with self.assertRaises(ValueError):replacement.read_plan(self.root/'transaction')

if __name__=='__main__':unittest.main()

"""Source integrity and replacement conflict tests; native proof lives in the case."""
import copy,json,struct,sys,tempfile,unittest,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import static_assets as static
import runtime_components as runtime
class StaticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        runtime.create(self.root/'g','godot','static');self.project=self.root/'g';self.inputs=self.project/'generated/static-input';self.manifest=json.loads((self.inputs/'manifest.json').read_text());self.out=self.root/'new-plan'
    def prepare(self,m=None):
        (self.inputs/'manifest.json').write_text(json.dumps(m or self.manifest));return static.prepare(self.project,'generated/scene/scene.json','generated/static-input/manifest.json',self.out)
    def invalid(self,m):
        with self.assertRaises((ValueError,TypeError)):self.prepare(m)
        self.assertFalse(self.out.exists())
    def test_frozen_sources_and_existing_output_protection(self):
        before=static.sha(self.inputs/'portal.glb');p=self.prepare();self.assertEqual(static.read_plan(self.out),p);self.assertEqual(static.sha(self.inputs/'portal.glb'),before)
        self.assertEqual(p['assets'][0]['triangles'],13524);self.assertEqual(len(p['replacements']),3)
        with self.assertRaisesRegex(ValueError,'new version'):self.prepare()
    def test_changed_source_or_baseline_rejected_before_write(self):
        for field in ('scene','asset'):
            m=copy.deepcopy(self.manifest)
            if field=='scene':m['scene_sha256']='wrong'
            else:m['assets'][0]['sha256']='wrong'
            self.invalid(m)
    def test_unknown_duplicate_and_overlapping_target_mappings(self):
        for mutate in [lambda m:m['replacements'][0].update(targets=['missing']),lambda m:m['replacements'][1].update(targets=m['replacements'][0]['targets']),lambda m:m['replacements'][1].update(id=m['replacements'][0]['id']),lambda m:m['replacements'][0].update(asset='missing')]:
            m=copy.deepcopy(self.manifest);mutate(m);self.invalid(m)
    def test_path_escape_and_non_glb_rejected(self):
        for path in ('../outside.glb','/absolute.glb','C:/outside.glb','generated/scene/scene.json'):
            m=copy.deepcopy(self.manifest);m['assets'][0]['source']=path;self.invalid(m)
    def test_nonfinite_transform_and_ambiguous_collision_rejected(self):
        for field,value in [('scale',-1),('scale',float('nan')),('yaw_degrees',181),('position',[0,0]),('collision','auto')]:
            m=copy.deepcopy(self.manifest);m['replacements'][0][field]=value;self.invalid(m)
    def test_frozen_plan_and_copied_sources_cannot_silently_change(self):
        self.prepare();p=self.out/'plan.json';original=p.read_bytes();d=json.loads(original);d['replacements'][0]['position'][0]+=1;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'plan changed'):static.read_plan(self.out)
        p.write_bytes(original);(self.out/'sources/portal.glb').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source changed'):static.read_plan(self.out)
    def test_unsupported_material_and_animation_do_not_pass_as_static(self):
        original=(self.inputs/'portal.glb').read_bytes();length=struct.unpack('<I',original[12:16])[0];doc=json.loads(original[20:20+length]);tail=original[20+length:]
        for mutate in [lambda d:d.update(animations=[{}]),lambda d:d.update(textures=[{}]),lambda d:d['materials'][0].update(doubleSided=True),lambda d:d['nodes'][0].update(scale=[2,2,2])]:
            d=copy.deepcopy(doc);mutate(d);chunk=json.dumps(d).encode();chunk+=b' '*((-len(chunk))%4);data=struct.pack('<4sII',b'glTF',2,20+len(chunk)+len(tail))+struct.pack('<I4s',len(chunk),b'JSON')+chunk+tail
            f=self.root/'unsupported.glb';f.write_bytes(data)
            with self.assertRaises(ValueError):static.inspect_glb(f)
    def test_truncated_glb_rejected(self):
        p=self.root/'bad.glb';p.write_bytes((self.inputs/'portal.glb').read_bytes()[:-1])
        with self.assertRaises(ValueError):static.inspect_glb(p)
    def test_each_engine_owns_mapping_and_required_resources(self):
        build=self.root/'ue/Engine/Build';build.mkdir(parents=True);(build/'Build.version').write_text('{"MajorVersion":5,"MinorVersion":8,"PatchVersion":2}')
        u=self.root/'u';runtime.create(u,'unreal','static',self.root/'ue');runtime.create(self.root/'g2','godot','static')
        self.assertEqual((u/'Content/generated/static/plan.json').read_bytes(),(self.project/'generated/static/plan.json').read_bytes())
        self.assertTrue((u/'static_replacement.py').exists());self.assertIn('/Game/Static',(u/'Config/DefaultGame.ini').read_text())
        self.assertIn('generated/static/*.json',(self.project/'export_presets.cfg').read_text())
        (self.project/'generated/static/plan.json').write_text('project change');static.read_plan(self.root/'g2/generated/static')
        self.assertEqual(runtime.status(u)['changed'],[])
if __name__=='__main__':unittest.main()

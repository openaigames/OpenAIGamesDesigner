import copy,json,math,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from adapters.processing import procedural_worker as gen
import procedural_assets as revisions
import runtime_components as runtime
import asset_workflow as assets

class SceneGenerationTests(unittest.TestCase):
    def spec(self):return json.loads((ROOT/'templates/procedural/scene.json').read_text())
    def test_known_clearance_slope_gap_and_components(self):
        s=gen.generate(self.spec());n=s['navigation']
        self.assertEqual({q['id']:q['expected_reachable'] for q in n['queries']},{'curve':True,'ramp':True,'narrow':False,'low':False,'broken':False,'steep':False,'island':False})
        paths={p['id']:p for p in n['paths']}
        for key,reason in [('narrow','narrow_clearance'),('low','low_headroom'),('broken','broken_surface'),('steep','excessive_slope')]:self.assertIn(reason,paths[key]['reasons'])
        self.assertAlmostEqual(paths['ramp']['max_sampled_slope_degrees'],math.degrees(math.atan(.3)),places=3)
        self.assertEqual(n['native_status'],'not_run')
        self.assertGreater(len(paths['curve']['centerline']),4)
    def test_dimensions_change_clearance_without_editing_geometry(self):
        small=self.spec();small['agent'].update(radius_m=.1,height_m=.5,clearance_m=.05,headroom_m=.05)
        original=gen.generate(self.spec());changed=gen.generate(small)
        self.assertEqual(original['meshes'],changed['meshes'])
        expected={q['id']:q['expected_reachable'] for q in changed['navigation']['queries']}
        self.assertTrue(expected['narrow']);self.assertTrue(expected['low']);self.assertFalse(expected['broken'])
    def test_deterministic_geometry_and_order_independent_ids(self):
        spec=self.spec();a=gen.generate(spec);b=gen.generate(spec)
        self.assertEqual(a,b);self.assertEqual(gen.glb(a),gen.glb(b))
        spec['rooms'].reverse();spec['paths'].reverse();c=gen.generate(spec)
        self.assertEqual(a['meshes'],c['meshes']);self.assertEqual(gen.glb(a),gen.glb(c))
        ids=[m['id'] for m in a['meshes']];self.assertEqual(len(ids),len(set(ids)))
    def test_closed_mesh_normals_and_triangle_budget(self):
        s=gen.generate(self.spec())
        for m in s['meshes']:
            for n in m['normals']:self.assertAlmostEqual(sum(x*x for x in n),1,places=5)
            for i in range(0,len(m['indices']),3):
                tri=[m['positions'][k] for k in m['indices'][i:i+3]]
                a=[tri[1][k]-tri[0][k] for k in range(3)];b=[tri[2][k]-tri[0][k] for k in range(3)]
                cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
                self.assertGreater(sum(cross[k]*m['normals'][m['indices'][i]][k] for k in range(3)),0)
        for m in s['meshes']:
            if m['id'].startswith('path_'):
                self.assertGreater(m['normals'][0][1],0);self.assertLess(m['normals'][6][1],0)
        spec=self.spec();spec['triangle_budget']=10
        with self.assertRaisesRegex(ValueError,'Triangle budget'):gen.generate(spec)
    def test_invalid_inputs_fail_before_output_creation(self):
        variants=[]
        def variant(mutator):s=self.spec();mutator(s);variants.append(s)
        variant(lambda s:s['rooms'].append(copy.deepcopy(s['rooms'][0])))
        variant(lambda s:s['paths'][0].update(to='missing'))
        variant(lambda s:s['paths'][0].update(controls=[[0,0,5],[1,0,0]]))
        variant(lambda s:s['paths'][0].update(gap_segments=[-1]))
        variant(lambda s:s['paths'][0].update(width=float('nan')))
        variant(lambda s:s['rooms'][0]['ports'][0].update(offset=9))
        variant(lambda s:s['rooms'][0]['ports'].append({'id':'overlap','side':'east','width':2,'height':2}))
        variant(lambda s:s['rooms'][1].update(position=s['rooms'][0]['position']))
        variant(lambda s:s['agent'].update(radius_m=2,height_m=1))
        variant(lambda s:s['paths'].append({**s['paths'][0],'id':'again'}))
        with tempfile.TemporaryDirectory() as d:
            for i,s in enumerate(variants):
                with self.subTest(i=i),self.assertRaises(ValueError):gen.write(s,Path(d)/str(i))
                self.assertFalse((Path(d)/str(i)).exists())
    def test_merge_preserves_local_changes_but_invalidates_navigation(self):
        before=gen.generate(self.spec());local=copy.deepcopy(before);local['meshes'][0]['color']=[1,0,0,1]
        spec=self.spec();spec['paths'][0]['color']=[.1,.7,.2,1];new=gen.generate(spec)
        merged=revisions.merge(before,new,local)
        self.assertEqual(merged['meshes'][0]['color'],[1,0,0,1]);self.assertNotIn('navigation',merged);self.assertNotIn('spec_sha256',merged)
        new=copy.deepcopy(before);new['meshes'][0]['color']=[0,1,0,1]
        with self.assertRaisesRegex(ValueError,'conflict'):revisions.merge(before,new,local)
    def test_project_copy_and_packaging_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);runtime.create(p/'g','godot','scene')
            self.assertIn('generated/scene/*.json',(p/'g/export_presets.cfg').read_text())
            self.assertTrue((p/'g/generated/scene/scene.glb').is_file())
            ue=p/'ue/Engine/Build';ue.mkdir(parents=True);(ue/'Build.version').write_text('{"MajorVersion":5,"MinorVersion":8,"PatchVersion":2}')
            runtime.create(p/'u','unreal','scene',p/'ue')
            self.assertEqual((p/'g/generated/scene/scene.json').read_bytes(),(p/'u/Content/generated/scene/scene.json').read_bytes())
            self.assertIn('AgentMaxSlope=35.0',(p/'u/Config/DefaultEngine.ini').read_text())
            self.assertIn('/Game/Scene',(p/'u/Config/DefaultGame.ini').read_text())
            self.assertFalse((p/'u/Plugins/OAGDPlayback').exists())
            self.assertEqual(runtime.status(p/'g')['changed'],[])
    def test_asset_worker_subprocess_registers_scene_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();job=assets.new_job(root,'procedural',{'parameters':{'spec':self.spec()}},{})
            result=assets.execute_job(root,job['job_id'],30)
            self.assertEqual(result['status'],'succeeded',result)
            self.assertNotIn('version_registration_error',result)
            self.assertNotIn('art_registration_error',result)
            self.assertEqual(len(result['artifacts']),4)
            self.assertIsNotNone(result.get('asset_version'))
    def test_custom_spec_is_project_owned_and_invalid_spec_leaves_no_project(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);spec=self.spec();spec['agent'].update(radius_m=.2,height_m=1.2)
            f=p/'custom.json';f.write_text(json.dumps(spec));runtime.create(p/'custom','godot','scene',scene_spec=f)
            saved=p/'custom/generated/scene/spec.json';self.assertEqual(json.loads(saved.read_text()),spec)
            f.write_text('{}');self.assertEqual(json.loads(saved.read_text()),spec)
            with self.assertRaises(ValueError):runtime.create(p/'bad','godot','scene',scene_spec=f)
            self.assertFalse((p/'bad').exists())
            with self.assertRaises(ValueError):runtime.create(p/'wrong','godot','navigation',scene_spec=saved)
            self.assertFalse((p/'wrong').exists())
if __name__=='__main__':unittest.main()

import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from adapters.processing import procedural_worker as gen
import procedural_assets as revisions
import runtime_components as runtime
import asset_workflow as assets


class GeometryTests(unittest.TestCase):
    def spec(self):return json.loads((ROOT/'templates/procedural/parts.json').read_text())

    def test_primitive_faces_point_outwards_and_mirror_preserves_winding(self):
        for shape in ('box','ramp','cylinder'):
            spec={'schema_version':1,'kind':'parts','parts':[{'id':'body','shape':shape,'size':[2,2,2],'position':[3,0,0],'mirror':'x'}]}
            scene=gen.generate(spec)
            for mesh in scene['meshes']:
                center=[3 if mesh['id']=='body' else -3, -.3 if shape=='ramp' else 0,-.3 if shape=='ramp' else 0]
                for i in range(0,len(mesh['indices']),3):
                    tri=[mesh['positions'][j] for j in mesh['indices'][i:i+3]]
                    normal=mesh['normals'][mesh['indices'][i]]
                    centroid=[sum(p[k] for p in tri)/3 for k in range(3)]
                    self.assertGreater(sum((centroid[k]-center[k])*normal[k] for k in range(3)),0)

    def test_glb_byte_layout_and_determinism(self):
        scene=gen.generate(self.spec());data=gen.glb(scene)
        magic,version,size=struct.unpack('<4sII',data[:12]);self.assertEqual((magic,version,size),(b'glTF',2,len(data)))
        length,kind=struct.unpack('<I4s',data[12:20]);self.assertEqual(kind,b'JSON')
        doc=json.loads(data[20:20+length]);self.assertEqual(len(doc['nodes']),8)
        self.assertEqual(data,gen.glb(gen.generate(self.spec())))

    def test_invalid_graph_numbers_thickness_budget_and_mirror_ids(self):
        variants=[]
        s=self.spec();s['parts'][0]['parent']='cap';s['parts'][-1]['parent']='floor';variants.append(s)
        s=self.spec();s['parts'][0]['parent']='missing';variants.append(s)
        s=self.spec();s['parts'][0]['size'][0]=float('nan');variants.append(s)
        s=self.spec();s['parts'][0]['size'][0]=.001;variants.append(s)
        s=self.spec();s['triangle_budget']=1;variants.append(s)
        s=self.spec();s['parts'][0]['id']='post_mirror';variants.append(s)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):gen.generate(value)

    def test_attachment_tracks_resized_parent(self):
        spec=self.spec();before=gen.generate(spec)
        spec['parts'][-2]['size'][1]=4
        after=gen.generate(spec)
        get=lambda s,name:next(m for m in s['meshes'] if m['id']==name)
        self.assertAlmostEqual(get(after,'cap')['bounds'][0][1],get(after,'post')['bounds'][1][1])
        self.assertAlmostEqual(get(after,'cap')['bounds'][0][1]-get(before,'cap')['bounds'][0][1],1)

    def test_terrain_profiles_clearance_and_impossible_scatter(self):
        spec=json.loads((ROOT/'templates/procedural/terrain.json').read_text())
        for profile in ('flat','hills','basin','canyon'):
            spec['profile']=profile;scene=gen.generate(spec)
            self.assertEqual(len(scene['meshes']),13)
            for mesh in scene['meshes'][1:]:
                lower,upper=mesh['bounds']
                self.assertTrue(lower[0]>=2.1 or upper[0]<=-2.1)
            self.assertEqual(scene,gen.generate(spec))
        spec['clearances']=[{'center':[0,0,0],'size':[100,1,100]}]
        with self.assertRaisesRegex(ValueError,'requested objects'):gen.generate(spec)

    def test_regeneration_preserves_unrelated_manual_changes_and_rejects_conflicts(self):
        base=gen.generate(self.spec());current=copy.deepcopy(base);new=copy.deepcopy(base)
        current['meshes'][0]['color']=[1,0,0,1];new['meshes'][1]['color']=[0,1,0,1]
        merged=revisions.merge(base,new,current);values={m['id']:m for m in merged['meshes']}
        self.assertEqual(values['floor']['color'],[1,0,0,1]);self.assertEqual(values['wall']['color'],[0,1,0,1])
        new['meshes'][0]['color']=[0,0,1,1]
        with self.assertRaisesRegex(ValueError,'floor'):revisions.merge(base,new,current)
        new=copy.deepcopy(base);new['meshes']=new['meshes'][1:]
        with self.assertRaisesRegex(ValueError,'floor'):revisions.merge(base,new,current)

    def test_real_asset_job_registers_companion_version_and_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            job=assets.new_job(root,'procedural',{'parameters':{'spec':self.spec()}},{})
            result=assets.execute_job(root,job['job_id'],30)
            self.assertEqual(result['status'],'succeeded',result)
            self.assertNotIn('version_registration_error',result)
            self.assertNotIn('art_registration_error',result)
            self.assertEqual(len(result['artifacts']),4)
            self.assertIsNotNone(result.get('asset_version'))
            self.assertTrue(all(a['quality_validation']=='not_checked' for a in result['artifacts']))
            retry=assets.new_job(root,'procedural',result['request'],{},job['job_id'])
            again=assets.execute_job(root,retry['job_id'],30)
            self.assertEqual(again['status'],'succeeded')
            self.assertEqual([a['sha256'] for a in result['artifacts']],[a['sha256'] for a in again['artifacts']])


class RuntimeIsolationTests(unittest.TestCase):
    def test_state_examples_isolate_saves_and_package_required_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=root/'godot-a';b=root/'godot-b'
            runtime.create(a,'godot','state');runtime.create(b,'godot','state')
            first=json.loads((a/'input-profile.json').read_text())
            second=json.loads((b/'input-profile.json').read_text())
            self.assertNotEqual(first['id'],second['id'])
            self.assertIn(first['id'],(a/'project.godot').read_text())
            self.assertTrue((a/'room_a.tscn').is_file())
            self.assertTrue((a/'room_b.tscn').is_file())
            self.assertTrue((a/'addons/oagd/oagd_store.gd').is_file())
            self.assertEqual(runtime.status(a)['changed'],[])
            self.assertFalse((a/'addons/oagd_playback').exists())
            # A fixture verifies packaging configuration without claiming engine execution.
            fake=root/'ue/Engine/Build';fake.mkdir(parents=True)
            (fake/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':8,'PatchVersion':2}))
            u=root/'unreal';runtime.create(u,'unreal','state',root/'ue')
            config=(u/'Config/DefaultGame.ini').read_text()
            for name in ('Example','Room_a','Room_b','InvalidRoom'):
                self.assertIn(f'+MapsToCook=(FilePath="/Game/{name}")',config)
            self.assertTrue((u/'Plugins/OAGDCore/Source/OAGDCore/Public/OAGDStore.h').is_file())
            self.assertFalse((u/'Plugins/OAGDPlayback').exists())
            self.assertEqual(runtime.status(u)['changed'],[])

    def test_input_examples_are_independent_and_have_no_animation_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'a';b=Path(directory)/'b'
            runtime.create(a,'godot','input');runtime.create(b,'godot','input')
            first=json.loads((a/'input-profile.json').read_text())
            second=json.loads((b/'input-profile.json').read_text())
            self.assertNotEqual(first['id'],second['id'])
            self.assertIn(first['id'],(a/'project.godot').read_text())
            self.assertTrue((a/'addons/oagd/oagd_input.gd').is_file())
            self.assertTrue((a/'addons/oagd/oagd_focus.gd').is_file())
            self.assertFalse((a/'addons/oagd_playback').exists())
            self.assertEqual(runtime.status(a)['changed'],[])
            missing=Path(directory)/'invalid'
            with self.assertRaises(ValueError):runtime.create(missing,'godot','unknown')
            self.assertFalse(missing.exists())

    def test_games_own_copies_and_installer_rejects_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a=root/'a';b=root/'b'
            runtime.create(a,'godot','training');runtime.create(b,'godot','puzzle')
            source=b/'addons/oagd/oagd_actor.gd';expected=source.read_bytes()
            (a/'addons/oagd/oagd_actor.gd').write_text('# project customization',encoding='utf-8')
            self.assertEqual(source.read_bytes(),expected)
            self.assertEqual(len(runtime.status(a)['changed']),1)
            with self.assertRaisesRegex(ValueError,'local edits'):runtime.install(a,'godot')
            self.assertFalse(runtime.status(b)['changed'])
            self.assertEqual(runtime.install(b,'godot')['component_version'],runtime.VERSION)

    def test_unmanaged_collision_preflight_and_engine_version_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'project.godot').touch()
            dest=root/'addons/oagd';dest.mkdir(parents=True);(dest/'oagd_session.gd').write_text('mine')
            with self.assertRaisesRegex(ValueError,'unowned'):runtime.install(root,'godot')
            self.assertEqual(list(dest.iterdir()),[dest/'oagd_session.gd'])
            fake=root/'ue/Engine/Build';fake.mkdir(parents=True)
            (fake/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':7,'PatchVersion':0}))
            with self.assertRaisesRegex(ValueError,'5.8 only'):runtime.create(root/'game','unreal','training',root/'ue')
            self.assertFalse((root/'game').exists())

if __name__=='__main__':unittest.main()

import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from environment import materials, surfaces, placement, views, handoff
from environment.common import digest, read, write


def png(path, width=2, height=2):
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
                     chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\0\0'*width)*height))+chunk(b'IEND',b''))


def spatial():
    return {'schema':'spatial-drawings/1','revision':'test','source':'fixture','coordinate':'XY floor, +Z up',
            'unit':'m','up':'+Z','objects':[], 'routes':[]}


def block(name, x, y, z=0):
    return {'id':name,'footprint':[[x,y],[x+.2,y],[x+.2,y+.2],[x,y+.2]],'z_min':z,'z_max':z+1}


class SurfaceTests(unittest.TestCase):
    def test_real_meter_scale_and_mapping(self):
        p = [[0,0,0],[1,0,0],[0,1,0]]
        uv = [[0,0],[1,0],[0,1]]
        a = surfaces.triangle_metrics(p,uv,[256,256])
        self.assertAlmostEqual(a['texels_per_m'],256)
        self.assertAlmostEqual(a['anisotropy'],1)
        b = surfaces.triangle_metrics([[x*2,y*2,z*2] for x,y,z in p],uv,[256,256])
        self.assertAlmostEqual(b['texels_per_m'],128)
        c = surfaces.triangle_metrics(p,[[u*2,v] for u,v in uv],[256,256])
        self.assertAlmostEqual(c['anisotropy'],2)

    def test_rotation_and_winding_do_not_change_density(self):
        p = [[0,0,0],[0,0,1],[0,1,0]]
        a = surfaces.triangle_metrics(p,[[0,0],[1,0],[0,1]],[128,256])
        b = surfaces.triangle_metrics(list(reversed(p)),[[0,1],[1,0],[0,0]],[128,256])
        self.assertAlmostEqual(a['texels_per_m'],b['texels_per_m'])

    def test_degenerate_uv_is_not_passing(self):
        a = surfaces.triangle_metrics([[0,0,0],[1,0,0],[0,1,0]],[[0,0]]*3,[256,256])
        self.assertEqual(a['status'],'degenerate_uv')
        report = surfaces.summarize([a])
        self.assertEqual(report['measured_area_m2'],0)
        self.assertIsNone(report['density_p50'])

    def test_distribution_is_area_weighted(self):
        rows = [{'area_m2':9,'status':'ok','texels_per_m':100,'anisotropy':1},
                {'area_m2':1,'status':'ok','texels_per_m':1000,'anisotropy':4}]
        report = surfaces.summarize(rows,{'min_texels_per_m':200,'max_anisotropy':2})
        self.assertEqual(report['density_p50'],100)
        self.assertAlmostEqual(report['below_density_area_fraction'],.9)
        self.assertAlmostEqual(report['stretched_area_fraction'],.1)

    def test_nonfinite_input_rejected(self):
        with self.assertRaises(ValueError):
            surfaces.triangle_metrics([[0,0,0],[1,0,0],[0,float('nan'),0]],[[0,0],[1,0],[0,1]],[256,256])


class PlacementTests(unittest.TestCase):
    def test_measured_roles_use_actual_bounds(self):
        spec={'schema':'environment-placement/1','spatial':spatial(),
              'measured_objects':[{'objects':['chair'],'purpose':'furniture','blocks_routes':True}]}
        measurement={'schema':'environment-surface-report/1','coordinate':'XY floor, +Z up','source':'scene.blend',
            'source_sha256':'fixture','objects':[{'id':'chair','bounds_m':[[0,1],[0,1],[0,1]],
                                              'footprint_m':[[0,0],[1,0],[1,1],[0,1]]}]}
        result=placement.measured_input(spec,measurement)
        self.assertEqual(result['spatial']['objects'][0]['z_max'],1)
        self.assertEqual(spec['spatial']['objects'],[])
        measurement['coordinate']='different origin'
        with self.assertRaises(ValueError):placement.measured_input(spec,measurement)

    def test_furniture_blocks_route_but_overhead_does_not(self):
        data = spatial()
        data['objects']=[block('cabinet',.4,-.1),block('lamp',.4,-.1,3)]
        data['routes']=[{'id':'walk','centerline':[[0,0],[2,0]],'width':.6,'z_min':0,'z_max':1.8}]
        r=placement.analyze({'schema':'environment-placement/1','spatial':data})
        self.assertEqual({i['object'] for i in r['issues']},{'cabinet'})
        self.assertEqual(r['engine_collision_test'],'not_performed')

    def test_door_sweep_finds_mid_motion_obstacle(self):
        data=spatial();data['objects']=[block('stool',.6,.6)]
        door={'id':'leaf','purpose':'decoration','hinge':[0,0],'width':1,'thickness':.04,
              'closed_yaw_deg':0,'angle_deg':90,'check_travel':True,'z_min':0,'z_max':2}
        result=placement.analyze({'schema':'environment-placement/1','spatial':data,'doors':[door]})
        self.assertTrue(any(i['code']=='door_sweep_candidate' for i in result['issues']))
        door['check_travel']=False
        self.assertEqual(placement.analyze({'schema':'environment-placement/1','spatial':data,'doors':[door]})['issues'],[])

    def test_sealed_door_and_clearance_use(self):
        data=spatial();data['objects']=[block('box',0,0)]
        zone={'id':'entry','purpose':'entry clearance','footprint':[[-1,-1],[1,-1],[1,1],[-1,1]],'z_min':0,'z_max':2}
        result=placement.analyze({'schema':'environment-placement/1','spatial':data,'clearances':[zone]})
        self.assertTrue(any(i['code']=='clearance_occupied' for i in result['issues']))
        zone['ignore']=['does_not_exist']
        with self.assertRaises(ValueError):
            placement.analyze({'schema':'environment-placement/1','spatial':data,'clearances':[zone]})


class FileWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'source.txt').write_text('fixture',encoding='utf8')

    def test_material_owner_conflict_and_missing_mapping(self):
        data={'schema':'environment-materials/1','revision':'1','style':'project choice','basis':'chosen direction',
              'sources':[{'id':'one','kind':'shader','path':'source.txt','consumer':'surface','parameters':['roughness']},
                         {'id':'two','kind':'shader','path':'source.txt','consumer':'surface','parameters':['roughness']}],
              'materials':[{'id':'mat','purpose':'wall','source_ids':['missing']}], 'regions':[]}
        r=materials.check(data,self.root)
        self.assertFalse(r['checks_ok'])
        self.assertEqual({i['code'] for i in r['issues'] if i['severity']=='error'}, {'multiple_parameter_owners','unknown_material_source'})

    def plan(self):
        return {'schema':'environment-views/1','revision':'a','engine':'fixture','scene':'scene','coordinate':'XYZ',
                'unit':'m','rotation_order':'XYZ','resolution':[2,2],'conditions':{'exposure':0},
                'dependencies':['source.txt'],'views':[{'id':'one','position':[0,0,1], 'rotation_deg':[0,0,0], 'fov_deg':80}]}

    def capture_files(self, directory, offset=0):
        directory.mkdir()
        png(directory/'one.png')
        p=self.plan()
        write(directory/'one.json',{'schema':'environment-view/1','id':'one','source':'fixture render',
              'position':[offset,0,1],'rotation_deg':[0,0,360],'fov_deg':80,
              **{k:p[k] for k in ('engine','scene','coordinate','unit','rotation_order','resolution','conditions')}})

    def test_actual_camera_offset_detected(self):
        self.capture_files(self.root/'a',.2)
        report=views.record(self.plan(),self.root/'a',self.root)
        self.assertFalse(report['checks_ok'])
        self.assertEqual(report['issues'][0]['code'],'camera_mismatch')

    def test_conditions_missing_do_not_become_verified(self):
        self.capture_files(self.root/'a')
        path=self.root/'a/one.json'; receipt=read(path);receipt['conditions']={}
        path.write_text(json.dumps(receipt),'utf8')
        report=views.record(self.plan(),self.root/'a',self.root)
        self.assertTrue(any(i['code']=='condition_unverified_or_changed' for i in report['issues']))

    def test_portable_comparison_and_tamper_detection(self):
        self.capture_files(self.root/'a')
        report=views.record(self.plan(),self.root/'a',self.root)
        result=views.compare(report,report,self.root/'compare')
        self.assertTrue(result['checks_ok'])
        self.assertTrue((self.root/'compare/before-one.png').exists())
        (self.root/'a/one.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):views.compare(report,report,self.root/'bad')

    def test_runner_failure_is_not_capture_success(self):
        write(self.root/'plan.json',self.plan())
        write(self.root/'runner.json',{'argv':[sys.executable,'-c','import sys;sys.exit(3)','{plan}','{output}']})
        with self.assertRaises(ValueError):
            views.capture(self.root/'plan.json',self.root/'runner.json',self.root,self.root/'capture')
        self.assertTrue((self.root/'capture/failure.json').exists())
        self.assertFalse((self.root/'capture/report.json').exists())

    def test_bad_capture_does_not_pass_comparison(self):
        self.capture_files(self.root/'a',1)
        report=views.record(self.plan(),self.root/'a',self.root)
        self.assertFalse(views.compare(report,report,self.root/'compare')['checks_ok'])

    def test_unsafe_view_names_rejected(self):
        plan=self.plan();plan['views'][0]['id']='../../elsewhere'
        with self.assertRaises(ValueError):views.validate_plan(plan)

    def test_handoff_path_escape_rejected(self):
        plan=self.package_plan();plan['files'][0]['path']='../outside'
        with self.assertRaises(ValueError):handoff.build(plan,self.root)

    def package_plan(self):
        return {'schema':'environment-handoff/1','revision':'one','selection_source':'source.txt',
                'selection_sha256':digest(self.root/'source.txt'),'coordinate':'+Y up','unit':'m','target_engine':'godot',
                'files':[{'id':'selected','path':'source.txt','sha256':digest(self.root/'source.txt'),
                          'role':'selection','transfer':'reference'}]}

    def test_package_identity_and_no_overwrite(self):
        plan=self.package_plan();result=handoff.build(plan,self.root,self.root/'package')
        self.assertEqual(result['target_engine_validation'],'not_run')
        self.assertEqual((self.root/'package/source.txt').read_bytes(),(self.root/'source.txt').read_bytes())
        with self.assertRaises(FileExistsError):handoff.build(plan,self.root,self.root/'package')
        (self.root/'source.txt').write_text('new revision','utf8')
        with self.assertRaises(ValueError):handoff.build(plan,self.root)

    def test_gltf_dependency_closure_and_escape(self):
        (self.root/'tex.png').write_bytes(b'fixture texture')
        write(self.root/'asset.gltf',{'asset':{'version':'2.0'},'images':[{'uri':'tex.png'}]})
        plan=self.package_plan(); plan['files'].append({'id':'model','path':'asset.gltf',
            'sha256':digest(self.root/'asset.gltf'),'role':'mesh','transfer':'portable'})
        r=handoff.build(plan,self.root,self.root/'package')
        self.assertIn('tex.png',[x['path'] for x in r['files']])
        self.assertTrue((self.root/'package/tex.png').exists())
        (self.root/'asset.gltf').write_text(json.dumps({'images':[{'uri':'../outside.png'}]}),'utf8')
        plan['files'][-1]['sha256']=digest(self.root/'asset.gltf')
        with self.assertRaises(ValueError):handoff.build(plan,self.root)

    def test_corrupt_glb_rejected(self):
        p=self.root/'bad.glb';p.write_bytes(b'glTF'+b'\0'*24)
        with self.assertRaises(ValueError):handoff.gltf_document(p)


if __name__=='__main__':
    unittest.main()

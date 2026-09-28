import copy, importlib.util, json, math, tempfile, unittest, os, uuid, shutil
from contextlib import contextmanager
from pathlib import Path

spec=importlib.util.spec_from_file_location('pipeline',Path(__file__).resolve().parents[1] / 'anim_pipeline.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@contextmanager
def workspace():
    base=Path(os.environ.get('ANIMLAB_TEST_TMP',tempfile.gettempdir())).resolve();base.mkdir(parents=True,exist_ok=True)
    target=(base/('animlab-test-'+uuid.uuid4().hex)).resolve();target.mkdir()
    if target.parent!=base:raise RuntimeError('Unexpected temporary test path')
    try:yield str(target)
    finally:
        if target.resolve().parent!=base:raise RuntimeError('Unsafe test cleanup path')
        shutil.rmtree(target)

def t(pos):return {'p':pos,'q':[0,0,0,1],'s':[1,1,1]}
def fixture():
    names=['root','pelvis','spine_05','head','hand_r','hand_l']
    positions=[[0,0,0],[0,0,90],[0,0,140],[0,0,165],[40,0,100],[20,0,100]]
    bones=[{'name':n,'parent':i-1,'rest':t(v)} for i,(n,v) in enumerate(zip(names,positions))]
    clip={'id':'sword_test','weapon':'sword','fps':60,'duration_s':1/60,'role':'candidate','ue_asset':'/Game/Lab/Test.Test','fbx':'exports/test.fbx','timing':{'contact_s':0},'test_distance_cm':100,'frames':[{'t':i/60,'pose':[t(v) for v in positions],'weapon':t([40,0,100])} for i in range(2)]}
    w={'bone':'hand_r','binding':t([0,0,0]),'grips':{'right':[0,0,0]},'segment_a':[5,0,0],'segment_b':[60,0,0],'radius_cm':2,'sections':[]}
    m={'schema':'animlab.manifest/1','revision':'test','root_motion_owner':'character','space':{'units':'cm'},'rig':{},'weapons':{'sword':w},'clips':[{k:copy.deepcopy(v) for k,v in clip.items() if k!='frames'}], 'tolerances':{'grip_cm':3,'hand_step_cm':18,'contact_gap_cm':8,'roundtrip_position_cm':1,'roundtrip_rotation_deg':2,'foot_slide_cm':3},'body_proxies':[]}
    c={'schema':'animlab.capture/1','stage':'unreal_roundtrip','bones':bones,'clips':[clip]}
    return m,c

class PipelineTests(unittest.TestCase):
    def test_crossing_and_degenerate_segments(self):
        self.assertAlmostEqual(p.segment_distance([-2,0,0],[2,0,0],[0,-2,0],[0,2,0]),0)
        self.assertAlmostEqual(p.segment_distance([0,0,0],[0,0,0],[2,0,0],[3,0,0]),2)
        self.assertAlmostEqual(p.segment_distance([0,0,0],[1,0,0],[0,3,0],[1,3,0]),3)
    def test_space_transform(self):
        transform={'p':[10,0,0],'q':[0,0,math.sqrt(.5),math.sqrt(.5)],'s':[1,1,1]}
        self.assertLess(p.distance(p.point(transform,[1,0,0]),[10,1,0]),1e-8)
    def test_capture_rejects_time_and_nan(self):
        _,c=fixture();c['clips'][0]['frames'][1]['t']=0
        with self.assertRaises(ValueError):p.validate_capture(c)
        _,c=fixture();c['clips'][0]['frames'][1]['pose'][0]['p'][0]=math.nan
        with self.assertRaises(ValueError):p.validate_capture(c)
    def test_duplicate_clip_rejected(self):
        _,c=fixture();c['clips'].append(copy.deepcopy(c['clips'][0]))
        with self.assertRaises(ValueError):p.validate_capture(c)
    def test_no_path_escape(self):
        with workspace() as d:
            with self.assertRaises(ValueError):p.local(Path(d),'../outside')
    def test_analyzer_detects_actual_grip_change(self):
        with workspace() as d:
            root=Path(d);m,c=fixture();c['clips'][0]['frames'][1]['weapon']['p'][0]+=10
            p.write(root/'m.json',m);p.write(root/'c.json',c)
            p.analyze(root/'m.json',root/'c.json',root/'r.json')
            result=p.read(root/'r.json')
            self.assertIn('right_grip_cm',[x['code'] for x in result['issues']])
            self.assertEqual(result['clips'][0]['foot_contact_status'],'not_measured_no_authored_contact_intervals')
    def test_gate_checks_current_evidence_and_baseline(self):
        with workspace() as d:
            root=Path(d);m,c=fixture();m['evidence_dependencies']=['source.blend','engine.uasset']
            for path in p.asset_paths(m):
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'test fixture only')
            p.write(root/'m.json',m);p.write(root/'c.json',c)
            p.analyze(root/'m.json',root/'c.json',root/'r.json',root/'c.json');(root/'playback.mp4').write_bytes(b'fixture only')
            v={'manifest_sha256':p.digest(root/'m.json'),'report_sha256':p.digest(root/'r.json'),'reviewer':'test fixture','clips':{'sword_test':{'decision':'accepted','evidence':['playback.mp4'],'evidence_sha256':{'playback.mp4':p.digest(root/'playback.mp4')},'waivers':[]}}};p.write(root/'v.json',v)
            self.assertTrue(p.gate(root/'m.json',root/'r.json',root/'v.json',root/'out.json')['eligible'])
            (root/'source.blend').write_bytes(b'changed source')
            self.assertFalse(p.gate(root/'m.json',root/'r.json',root/'v.json',root/'out.json')['eligible'])
            (root/'source.blend').write_bytes(b'test fixture only')
            (root/'playback.mp4').write_bytes(b'changed recording')
            self.assertFalse(p.gate(root/'m.json',root/'r.json',root/'v.json',root/'out.json')['eligible'])
            (root/'playback.mp4').write_bytes(b'fixture only')
            c['clips'][0]['frames'][1]['weapon']['p'][0]+=1;p.write(root/'c.json',c)
            self.assertFalse(p.gate(root/'m.json',root/'r.json',root/'v.json',root/'out.json')['eligible'])
            m['clips'][0]['role']='baseline';p.write(root/'m.json',m)
            self.assertFalse(p.gate(root/'m.json',root/'r.json',root/'v.json',root/'out.json')['eligible'])
    def test_roundtrip_rejects_missing_motion_tail(self):
        with workspace() as d:
            root=Path(d);m,c=fixture();source=copy.deepcopy(c);source['clips'][0]['frames'].append(dict(copy.deepcopy(source['clips'][0]['frames'][-1]),t=2/60))
            p.write(root/'m.json',m);p.write(root/'c.json',c);p.write(root/'source.json',source)
            with self.assertRaises(ValueError):p.analyze(root/'m.json',root/'c.json',root/'r.json',root/'source.json')
    def test_binding_draft_rejects_stale_manifest(self):
        with workspace() as d:
            root=Path(d);m,_=fixture();draft={'schema':'animlab.binding-draft/1','weapon':'sword','source_manifest':copy.deepcopy(m),'binding':t([2,0,0])};p.write(root/'m.json',m);p.write(root/'d.json',draft)
            p.apply_binding(root/'m.json',root/'d.json',root/'next.json')
            self.assertEqual(p.read(root/'m.json')['weapons']['sword']['binding']['p'],[0,0,0])
            m['revision']='changed';p.write(root/'m.json',m)
            with self.assertRaises(ValueError):p.apply_binding(root/'m.json',root/'d.json',root/'next.json')

if __name__=='__main__':unittest.main()

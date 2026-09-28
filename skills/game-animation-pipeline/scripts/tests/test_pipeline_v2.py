import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import anim_pipeline as p
import pipeline_v2 as v2

def t(x=0,q=None):return {'p':[x,0,0],'q':q or [0,0,0,1],'s':[1,1,1]}
def fixture(mode='native_reuse',weapon=True):
    clip={'id':'idle','source_ref':'/Game/Idle','duration_s':1,'weapon':'staff' if weapon else None,'grip_intervals':{'primary':[[0,1]],'support':[[0,.4]]} if weapon else {}}
    m={'schema':'animlab.manifest/2','mode':mode,'mode_basis':{'source_type':{'external':'dcc_export','native_reuse':'engine_native','local_change':'existing_consumer'}[mode],'reason':'unit test contract only'},'space':{'units':'cm','axes':'X forward Y right Z up'},'root_motion_owner':'character','clips':[clip],
       'tolerance_basis':'Test rig exact transforms; not game art approval','tolerances':dict(binding_position_cm=.1,binding_rotation_deg=2,grip_position_cm=.1,grip_rotation_deg=2,comparison_position_cm=.1,comparison_rotation_deg=2,sample_time_s=.05,foot_slide_cm=1,contact_gap_cm=1),
       'evidence_dependencies':{role:[role+'.txt'] for role in v2.MODES[mode]},'weapons':{}}
    if mode=='external':clip['fbx']='clip.fbx'
    if weapon:m['weapons']={'staff':{'attachment':{'parent':'socket_grip','kind':'socket','source':'explicit source binding','relative':t(5)},'grips':{'primary':{'bone':'main_hand','hand_marker':t(),'weapon_marker':t()},'support':{'bone':'other_hand','hand_marker':t(),'weapon_marker':t(10)}}}}
    c={'schema':'animlab.capture/2','context':{'engine_version':'test','execution_ref':'run.json','method':'unit fixture','sampling':'2Hz','conditions':['synthetic unit data; not runtime evidence']},'stage':'runtime_consumer','bones':[{'name':'main_hand','parent':-1},{'name':'other_hand','parent':0}],'clips':[{'id':'idle','frames':[{'t':i/2,'pose':[t(5),t(15 if i==0 else 500)],**({'weapon':t(5),'attachment':{'parent':'socket_grip','kind':'socket','exists':True,'relative':t(5)}} if weapon else {})} for i in range(3)]}]}
    return m,c

class Modes(unittest.TestCase):
    def audit(self,root,m,c,baseline=None):
        for files in m['evidence_dependencies'].values():
            for f in files:(root/f).write_text('synthetic fixture')
        (root/'run.json').write_text('{}')
        if m['mode']=='external':(root/'clip.fbx').write_text('test fixture')
        p.write(root/'m.json',m);p.write(root/'c.json',c)
        if baseline:p.write(root/'b.json',baseline)
        p.analyze(root/'m.json',root/'c.json',root/'audit.json',root/'b.json' if baseline else None)
        return p.read(root/'audit.json')
    def test_explicit_offset_and_release_interval_not_false_positive(self):
        with tempfile.TemporaryDirectory() as d:
            report=self.audit(Path(d),*fixture())
            self.assertFalse(report['issues'])
            self.assertEqual(report['clips'][0]['metrics']['support:grip_position_cm'],0)
    def test_rotation_only_and_missing_socket_detected(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=fixture();c['clips'][0]['frames'][1]['attachment']['relative']['q']=[0,0,1,0]
            c['clips'][0]['frames'][2]['attachment']['exists']=False
            codes={i['code'] for i in self.audit(Path(d),m,c)['issues']}
            self.assertIn('binding_rotation_deg',codes);self.assertIn('missing_binding',codes)
            self.assertNotIn('binding_position_cm',codes)
    def test_unarmed_noncontact_can_be_audited_without_fake_fields(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.audit(Path(d),*fixture(weapon=False))
            self.assertEqual(r['clips'][0]['checks']['binding'],'not_applicable_unarmed')
            self.assertEqual(r['clips'][0]['checks']['feet'],'not_measured_no_planted_intervals')
    def test_modes_require_distinct_current_evidence(self):
        for mode in v2.MODES:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                root=Path(d);m,c=fixture(mode,False)
                if mode=='external':c['stage']='unreal_roundtrip'
                self.audit(root,m,c,copy.deepcopy(c) if mode!='native_reuse' else None)
                (root/'playback.txt').write_text('synthetic review fixture only')
                v={'schema':'animlab.review/2','manifest_sha256':p.digest(root/'m.json'),'report_sha256':p.digest(root/'audit.json'),'reviewer':'test fixture','clips':{'idle':{'decision':'accepted','evidence':['playback.txt'],'evidence_sha256':{'playback.txt':p.digest(root/'playback.txt')},'waivers':[]}}}
                p.write(root/'v.json',v)
                self.assertTrue(p.gate(root/'m.json',root/'audit.json',root/'v.json',root/'gate.json')['eligible'])
                (root/'runtime_consumer.txt').write_text('changed')
                self.assertFalse(p.gate(root/'m.json',root/'audit.json',root/'v.json',root/'gate.json')['eligible'])
    def test_external_and_local_cannot_skip_comparison(self):
        for mode in ['external','local_change']:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);m,c=fixture(mode,False);self.audit(root,m,c);p.write(root/'v.json',{})
                result=p.gate(root/'m.json',root/'audit.json',root/'v.json',root/'gate.json')
                self.assertIn('comparison missing/changed',result['reasons'])
    def test_missing_config_and_mode_change_fail(self):
        m,c=fixture();del m['weapons']['staff']['attachment']['parent']
        with self.assertRaises(ValueError):v2.validate(m)
        m,c=fixture();m['mode']='external'
        with self.assertRaises(ValueError):v2.validate(m)
    def test_unobserved_grip_window_is_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=fixture();m['clips'][0]['grip_intervals']['support']=[[.1,.2]]
            self.assertIn('grip_coverage:support',{i['code'] for i in self.audit(Path(d),m,c)['issues']})

if __name__=='__main__':unittest.main()

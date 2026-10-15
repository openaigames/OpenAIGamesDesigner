import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import motion_workflow as motion


class MotionContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        f=self.root/'rig.blend';f.write_bytes(b'contract fixture, not a Blender file')
        asset={'file':'rig.blend','armature':'Rig','sha256':motion.digest(f)}
        self.spec={'schema':'oagd.motion/1','source':asset.copy(),'target':asset.copy(),
            'mapping':{'root':'Root','arm':'Arm','leg':'Leg','shin':'Shin','foot':'Foot'},'alignment_xyzw':[0,0,0,1],
            'root_motion':{'bone':'root','owner':'animation','translation':'scaled','scale':1},'tolerances':{'contact_m':.001},
            'clips':[{'id':'walk','action':'Walk','start_frame':1,'end_frame':31,'fps':30}]}
    def test_valid_input_resolves_paths_without_mutating_spec(self):
        old=copy.deepcopy(self.spec);result=motion.validate(self.spec,self.root)
        self.assertTrue(Path(result['source']['file']).is_absolute());self.assertEqual(old,self.spec)
    def test_stale_source_rejected(self):
        (self.root/'rig.blend').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'sha256'):motion.validate(self.spec,self.root)
    def test_double_root_drive_rejected(self):
        self.spec['root_motion']['owner']='controller'
        with self.assertRaisesRegex(ValueError,'double movement'):motion.validate(self.spec,self.root)
    def test_duplicate_mapping_rejected(self):
        self.spec['mapping']['arm']='Root'
        with self.assertRaisesRegex(ValueError,'one-to-one'):motion.validate(self.spec,self.root)
    def test_invalid_alignment_and_nonfinite_numbers(self):
        for q in ([0,0,0,0],[0,0,0,2],[0,float('nan'),0,1]):
            with self.subTest(q=q):
                self.spec['alignment_xyzw']=q
                with self.assertRaises(ValueError):motion.validate(self.spec,self.root)
    def test_no_root_loop_repair(self):
        self.spec['clips'][0]['repairs']={'loop':{'bones':['root'],'blend_s':.2}}
        with self.assertRaisesRegex(ValueError,'non-root'):motion.validate(self.spec,self.root)
    def test_invalid_spike_rule(self):
        self.spec['clips'][0]['repairs']={'rotation_spikes':{'bones':['arm'],'threshold_deg':40,'neighbor_deg':45}}
        with self.assertRaises(ValueError):motion.validate(self.spec,self.root)
    def test_clip_id_cannot_escape_revision(self):
        for value in ('../walk','walk/evil','walk\\evil','',True):
            with self.subTest(value=value):
                self.spec['clips'][0]['id']=value
                with self.assertRaises(ValueError):motion.validate(self.spec,self.root)
    def test_contact_transition_and_overlap(self):
        contact={'chain':['leg','shin','foot'],'start_s':.2,'end_s':.8,'blend_s':.1,'anchor':'first_sample','pole':[0,-1,0],'max_correction_m':.1}
        self.spec['clips'][0]['repairs']={'contacts':[contact]};motion.validate(self.spec,self.root)
        self.spec['clips'][0]['repairs']['contacts'].append(contact.copy())
        with self.assertRaisesRegex(ValueError,'Overlapping'):motion.validate(self.spec,self.root)
        self.spec['clips'][0]['repairs']['contacts']=[{**contact,'start_s':0}]
        with self.assertRaisesRegex(ValueError,'transition'):motion.validate(self.spec,self.root)
    def test_existing_output_not_reused_even_for_failure(self):
        with self.assertRaises(FileExistsError):motion.launch('not-run',self.root,{'mode':'inspect'})
    def test_changed_output_invalidates_evidence(self):
        artifact=self.root/'clip.glb';artifact.write_bytes(b'v1')
        motion.write(self.root/'report.json',{'ok':True,'artifacts':{'clip.glb':motion.digest(artifact)},'dependencies':{}})
        self.assertTrue(motion.verify(self.root)['ok']);artifact.write_bytes(b'v2');self.assertFalse(motion.verify(self.root)['ok'])
    def test_mapping_suggestion_does_not_approve_ambiguity(self):
        src={'sha256':'s','rigs':[{'name':'A','bones':[{'name':'pelvis'},{'name':'hips'},{'name':'LeftArm'}]}]}
        dst={'sha256':'t','rigs':[{'name':'B','bones':[{'name':'dst_hips'},{'name':'dst_upperarm_L'}]}]}
        r=motion.suggest(src,dst,'A','B');self.assertEqual(r['ambiguous'],['dst_hips'])
        self.assertIn('requires_',r['status']);self.assertNotIn('dst_hips',r['mapping'])


if __name__=='__main__':unittest.main()

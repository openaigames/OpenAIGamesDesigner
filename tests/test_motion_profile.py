import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import motion_profile as profile
import motion_workflow as motion


class ProfileContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'rig.blend').write_bytes(b'contract fixture, not native evidence')
        asset={'file':'rig.blend','sha256':motion.digest(self.root/'rig.blend'),'armature':'Rig'}
        self.p={'schema':'oagd.character-profile/1','id':'test','revision':1,'source':asset,'target':asset.copy(),
          'roles':{r:{'source':'src_'+r,'target':'dst_'+r} for r in profile.ROLES},
          'coordinates':{s:{'up':'+Z','forward':'-Y','unit':'metre'} for s in ('source','target')},
          'reference_pose':{s:{'local_rotations_xyzw':{},'basis':'original bind'} for s in ('source','target')},
          'unmapped_bones':{'source':{},'target':{}},
          'root_motion':{'owner':'controller','translation':'in_place','scale':1,'translation_roles':['hips']},
          'repair_budget':{'max_position_m':.1,'max_rotation_deg':30,'max_edited_fraction':.5},
          'clip_policies':{'walk':{'repairs':{}}}}
        self.s={'schema':'oagd.motion/1','clips':[{'id':'walk','action':'Walk','start_frame':1,'end_frame':31,'fps':30}],'tolerances':{'contact_m':.002}}
    def spec(self):
        motion.write(self.root/'profile.json',self.p)
        return {**self.s,'profile':{'file':'profile.json','sha256':motion.digest(self.root/'profile.json'),'revision':1}}
    def test_profile_resolves_without_changing_authored_input(self):
        before=copy.deepcopy(self.p);s=self.spec();result=motion.validate(s,self.root)
        self.assertEqual(self.p,before);self.assertNotIn('mapping',s)
        self.assertEqual(result['mapping']['dst_hand_L'],'src_hand_L')
        self.assertTrue(Path(result['source']['file']).is_absolute())
    def test_changed_profile_requires_new_hash(self):
        s=self.spec();self.p['revision']=2;motion.write(self.root/'profile.json',self.p)
        with self.assertRaisesRegex(ValueError,'sha256'):motion.validate(s,self.root)
    def test_revision_mismatch_is_rejected(self):
        s=self.spec();s['profile']['revision']=2
        with self.assertRaisesRegex(ValueError,'revision mismatch'):motion.validate(s,self.root)
    def test_no_two_sources_of_mapping_truth(self):
        s=self.spec();s['mapping']={'root':'root'}
        with self.assertRaisesRegex(ValueError,'duplicate'):motion.validate(s,self.root)
    def test_missing_role_and_case_duplicate(self):
        del self.p['roles']['head']
        with self.assertRaisesRegex(ValueError,'16 humanoid'):self.spec_and_validate()
        self.setUp();self.p['roles']['head']['target']='DST_HIPS'
        with self.assertRaisesRegex(ValueError,'duplicate role'):self.spec_and_validate()
    def test_units_and_axes_are_not_relabelled(self):
        self.p['coordinates']['source']['unit']='centimetre'
        with self.assertRaisesRegex(ValueError,'normalize'):self.spec_and_validate()
    def test_reference_quaternion_and_unsupported_twist_policy(self):
        self.p['reference_pose']['target']['local_rotations_xyzw']={'dst_thigh_L':[0,0,0,2]}
        with self.assertRaises(ValueError):self.spec_and_validate()
        self.p['reference_pose']['target']['local_rotations_xyzw']={}
        self.p['unmapped_bones']['target']={'twist':'automatic_distribution'}
        with self.assertRaisesRegex(ValueError,'twist redistribution'):self.spec_and_validate()
    def test_nonfinite_and_zero_repair_budget(self):
        self.p['repair_budget']['max_rotation_deg']=float('nan')
        with self.assertRaises(ValueError):profile.validate(self.p)
        self.p['repair_budget']['max_rotation_deg']=0
        self.assertEqual(profile.validate(self.p)['repair_budget']['max_rotation_deg'],0)
    def test_offset_cannot_move_root_or_unpermitted_bone(self):
        self.p['clip_policies']['walk']['translation_offsets_m']={'root':[0,0,.1]}
        with self.assertRaisesRegex(ValueError,'permitted translation'):self.spec_and_validate()
        self.p['clip_policies']['walk']['translation_offsets_m']={'hips':[0,0,.01]}
        self.assertEqual(self.spec_and_validate()['clips'][0]['target_translation_offsets_m']['dst_hips'],[0,0,.01])
    def test_contact_velocity_requires_compatible_root_owner(self):
        self.p['clip_policies']['walk']['repairs']={'contacts':[{'chain_roles':['thigh_L','shin_L','foot_L'],
            'start_s':.1,'end_s':.4,'blend_s':.05,'anchor':'first_sample','pole':[0,-1,0],
            'max_correction_m':.03,'controller_velocity_mps':[0,-.8,0]}]}
        self.spec_and_validate()
        self.p['root_motion'].update(owner='animation',translation='scaled')
        with self.assertRaisesRegex(ValueError,'controller-owned'):self.spec_and_validate()
    def test_forward_axes_produce_explicit_alignment(self):
        self.p['coordinates']['source']['forward']='+X'
        q=self.spec_and_validate()['alignment_xyzw'];self.assertAlmostEqual(q[2],-2**-.5)
    def test_no_silent_policy_for_new_clips(self):
        self.s['clips'][0]['id']='unknown'
        with self.assertRaisesRegex(ValueError,'Missing profile policy'):self.spec_and_validate()
    def spec_and_validate(self):return motion.validate(self.spec(),self.root)


if __name__=='__main__':unittest.main()

"""Intent and captured-track rejection tests; real engine proof lives in root audit."""
import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import motion_root as r
class RootContract(unittest.TestCase):
 def binding(self):return {'root_motion':dict(r.POLICY),'clips':[{'motion_owner':'animation','in_place':False,'loop':False}]}
 def frames(self,points):return [{'bones':{'root':{'p':p,'q':[0,0,0,1]}}} for p in points]
 def test_optional(self):self.assertIsNone(r.settings({}))
 def test_output_inside_input_rejected_before_io(self):
  base=Path(__file__).resolve().parent/'never-created-base';rooted=base.with_name('never-created-rooted')
  for out in (base,base/'new',rooted/'new'):
   with self.subTest(out=out),self.assertRaises(ValueError):r.compose(base,rooted,out)
 def test_explicit_planar_policy(self):self.assertEqual(r.settings(self.binding()),r.POLICY)
 def test_reject_mixed_graphs(self):
  for key in ('layers','turning','locomotion'):
   b=self.binding();b[key]={}
   with self.subTest(key=key),self.assertRaises(ValueError):r.settings(b)
 def test_reject_ambiguous_owners(self):
  for key,value in [('loop',True),('in_place',True),('layer_only',True),('motion_owner','controller')]:
   b=self.binding();b['clips'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):r.settings(b)
 def test_reject_unimplemented_policies(self):
  for key,value in [('vertical','animation'),('rotation','animation'),('transition_s',.12),('transition_s',False),('mode','all')]:
   b=self.binding();b['root_motion'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):r.settings(b)
 def test_out_and_back_root_is_not_inplace(self):
  f=self.frames([[0,0,0],[0,-1,0],[0,0,0]])
  r.check_track(f,'root',True)
  with self.assertRaises(ValueError):r.check_track(f,'root',False)
 def test_interior_vertical_motion_rejected(self):
  with self.assertRaises(ValueError):r.check_track(self.frames([[0,0,0],[0,-1,.2],[0,-2,0]]),'root',True)
 def test_root_rotation_rejected(self):
  f=self.frames([[0,0,0],[0,-1,0]]);f[1]['bones']['root']['q']=[0,0,math.sin(.2),math.cos(.2)]
  with self.assertRaises(ValueError):r.check_track(f,'root',True)
 def test_stationary_or_empty_animation_owner_rejected(self):
  for f in ([],self.frames([[0,0,0],[0,0,0]])):
   with self.assertRaises(ValueError):r.check_track(f,'root',True)
 def test_invalid_sample_rejected(self):
  for v in (float('nan'),float('inf')):
   with self.assertRaises(ValueError):r.check_track(self.frames([[0,0,0],[v,-1,0]]),'root',True)
 def test_quaternion_sign_is_equivalent(self):
  f=self.frames([[0,0,0],[0,-1,0]]);f[1]['bones']['root']['q']=[0,0,0,-1];r.check_track(f,'root',True)
 def test_stationary_controller_allowed(self):r.check_track(self.frames([[0,0,0],[0,0,0]]),'root',False)
if __name__=='__main__':unittest.main()

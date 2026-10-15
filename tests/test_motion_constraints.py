import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import motion_constraints as c

class ConstraintContract(unittest.TestCase):
 def setUp(self):
  socket={'position':[0,0,0],'rotation_xyzw':[0,0,0,1]}
  self.feet={'pelvis':'hips','left':['a','b','c'],'right':['d','e','f'],'sole_offset_m':.1,'probe_up_m':.4,'probe_down_m':.5,'max_step_m':.2,'max_slope_deg':35,'max_pelvis_m':.2,'blend_s':.15,'knee_pole':[1,0,0]}
  self.grip={'main_hand':'hand','offhand':['u','v','w'],'blend_s':.15,'elbow_pole':[0,-1,-1],'sockets':{e:{'main':copy.deepcopy(socket),'support':copy.deepcopy(socket)} for e in ('godot','unreal')}}
  self.d={'constraints':{'mode':'contacts_v1','feet':self.feet,'grip':self.grip}}
 def test_independent_opt_in(self):
  self.assertIsNone(c.settings({}))
  for k in ('feet','grip'):self.assertTrue(c.settings({'constraints':{'mode':'contacts_v1',k:copy.deepcopy(self.d['constraints'][k])}}))
 def test_probe_must_cover_height(self):
  self.feet['probe_up_m']=.1
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_nonfinite_and_bool(self):
  for v in (True,float('nan'),float('inf'),-.1,2):
   self.feet['blend_s']=v
   with self.subTest(v=v),self.assertRaises(ValueError):c.settings(self.d)
 def test_disjoint_limbs(self):
  self.feet['right'][0]='a'
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_main_cannot_be_support(self):
  self.grip['main_hand']='w'
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_native_socket_not_guessed(self):
  del self.grip['sockets']['unreal']
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_unit_rotation_required(self):
  self.grip['sockets']['godot']['support']['rotation_xyzw']=[0,0,0,2]
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_zero_pole_rejected(self):
  self.feet['knee_pole']=[0,0,0]
  with self.assertRaises(ValueError):c.settings(self.d)
 def test_capture_bone_must_exist_every_frame(self):
  names=['hips','a','b','c','d','e','f','hand','u','v','w'];frames=[{'bones':dict.fromkeys(names)},{'bones':dict.fromkeys(names[:-1])}]
  with self.assertRaises(ValueError):c.check_capture(self.d,frames)
 def test_empty_module_not_accepted(self):
  for row in ({'mode':'contacts_v1'},{'mode':'contacts_v1','feet':{}},{'mode':'contacts_v1','grip':{}}):
   with self.subTest(row=row),self.assertRaises(ValueError):c.settings({'constraints':row})

if __name__=='__main__':unittest.main()

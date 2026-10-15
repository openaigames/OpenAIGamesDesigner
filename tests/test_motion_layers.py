"""Reject ambiguous layer masks and event contracts before creating either engine project."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import motion_playback as p

class LayerContracts(unittest.TestCase):
 def binding(self):
  return {'layers':{'mode':'upper_full_v1','upper_root':'dst_spine','clips':['wave'],'fade_in_s':.12,'fade_out_s':.16,'replace_s':.12,'event_policy':'current_visible'},'clips':[{'id':'wave','clip':'action','layer_only':True,'duration_s':1.2,'loop':False,'markers':[{'name':'start','at_s':0},{'name':'pulse','at_s':.65},{'name':'finish','at_s':1.2}]}]}
 def test_optional_legacy_graph(self):self.assertIsNone(p.layer_settings({}))
 def test_boundaries_are_supported_for_nonloops(self):self.assertEqual(p.layer_settings(self.binding())['clips'],['wave'])
 def test_loop_uses_zero_seam(self):
  b=self.binding();b['clips'][0]['loop']=True;b['clips'][0]['markers'].pop();self.assertIsNotNone(p.layer_settings(b))
 def test_missing_policy_fails(self):
  b=self.binding();del b['layers']
  with self.assertRaises(ValueError):p.layer_settings(b)
 def test_uncalibrated_or_leg_mask_fails(self):
  for name in ('dst_hips','dst_root','dst_foot_L','missing'):
   b=self.binding();b['layers']['upper_root']=name
   with self.subTest(name=name),self.assertRaises(ValueError):p.layer_settings(b)
 def test_nonfinite_or_zero_envelopes_fail(self):
  for name in ('fade_in_s','fade_out_s','replace_s'):
   for value in (0,-1,float('nan'),float('inf'),True,2):
    b=self.binding();b['layers'][name]=value
    with self.subTest(name=name,value=value),self.assertRaises(ValueError):p.layer_settings(b)
 def test_aliases_are_separate_from_base_actions(self):
  for name in ('idle','walk','run','action','action_v2','locomotion','turn_r_90'):
   b=self.binding();b['clips'][0]['id']=name;b['layers']['clips']=[name]
   with self.subTest(name=name),self.assertRaises(ValueError):p.layer_settings(b)
 def test_alias_sets_must_match(self):
  for ids in ([],['missing'],['wave','wave']):
   b=self.binding();b['layers']['clips']=ids
   with self.subTest(ids=ids),self.assertRaises(ValueError):p.layer_settings(b)
 def test_layer_only_requires_bool(self):
  for value in ('true',1,None):
   b=self.binding();b['clips'][0]['layer_only']=value
   with self.subTest(value=value),self.assertRaises(ValueError):p.layer_settings(b)
 def test_default_action_cannot_select_layer(self):
  b=self.binding();b['default_action']='wave'
  with self.assertRaises(ValueError):p.layer_settings(b)
 def test_nonpositive_duration_fails(self):
  for value in (0,-1,float('nan')):
   b=self.binding();b['clips'][0]['duration_s']=value
   with self.subTest(value=value),self.assertRaises(ValueError):p.layer_settings(b)
 def test_loop_end_marker_fails(self):
  b=self.binding();b['clips'][0]['loop']=True
  with self.assertRaises(ValueError):p.layer_settings(b)
 def test_duplicate_unordered_or_outside_events_fail(self):
  for markers in ([{'name':'x','at_s':.5},{'name':'x','at_s':.6}],[{'name':'a','at_s':.8},{'name':'b','at_s':.2}],[{'name':'x','at_s':-1}],[{'name':'x','at_s':2}],[{'name':'x','at_s':float('nan')}],[{'name':'unsafe name','at_s':.3}]):
   b=self.binding();b['clips'][0]['markers']=markers
   with self.subTest(markers=markers),self.assertRaises(ValueError):p.layer_settings(b)
 def test_unknown_mode_or_event_policy_fails(self):
  for name,value in [('mode','additive'),('event_policy','all_sources')]:
   b=self.binding();b['layers'][name]=value
   with self.subTest(name=name),self.assertRaises(ValueError):p.layer_settings(b)

if __name__=='__main__':unittest.main()

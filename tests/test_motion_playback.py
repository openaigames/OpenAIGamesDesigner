"""Failure cases for project activation; these tests never launch or fake an engine."""
import unittest,tempfile,sys,json,hashlib,uuid,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import motion_playback as p

class ActivationTests(unittest.TestCase):
 def setUp(self):
  self.parent=Path(tempfile.gettempdir()).resolve();self.root=self.parent/('oagd-playback-'+uuid.uuid4().hex);self.root.mkdir()
  (self.root/'.openaigame').mkdir();(self.root/'Config').mkdir();(self.root/'Content').mkdir()
  p.motion.write(self.root/p.LOCK,{'engine':'unreal'})
  p.motion.write(self.root/'bindings.json',{'revision':'old'})
  (self.root/'Config/DefaultEngine.ini').write_text('GameDefaultMap=/Game/PlaybackOld/Example\nEditorStartupMap=/Game/PlaybackOld/Example\n')
  (self.root/'Config/DefaultGame.ini').write_text('[/Script/UnrealEd.ProjectPackagingSettings]\n+MapsToCook=(FilePath="/Game/PlaybackOld/Example")\n+DirectoriesToAlwaysCook=(Path="/Game/PlaybackOld")\n+DirectoriesToAlwaysCook=(Path="/Engine/BasicShapes")\n\n[OAGDPlayback]\nRevisionRoot=/Game/PlaybackOld\n')
  (self.root/'Content/test.uasset').write_bytes(b'fixture native evidence only')
  self.binding={'revision':'new','character_scene':'character_new.tscn','unreal_root':'/Game/PlaybackNew','source_hashes':{}}
  p.motion.write(self.root/'bindings.pending.json',self.binding)
  p.motion.write(self.root/'PlaybackNew-import-report.json',{'ok':True,'binding_sha256':p.motion.digest(self.root/'bindings.pending.json'),'native_files':{'Content/test.uasset':p.motion.digest(self.root/'Content/test.uasset')}})
  self.original={n:(self.root/n).read_bytes() for n in ('bindings.json','Config/DefaultEngine.ini','Config/DefaultGame.ini')}
 def tearDown(self):
  assert self.root.resolve().is_relative_to(self.parent) and self.root.name.startswith('oagd-playback-')
  shutil.rmtree(self.root)
 def unchanged(self):
  for n,value in self.original.items():self.assertEqual((self.root/n).read_bytes(),value)
 def test_no_report_cannot_activate(self):
  (self.root/'PlaybackNew-import-report.json').unlink()
  with self.assertRaises(OSError):p.activate(self.root)
  self.unchanged()
 def test_changed_binding_cannot_activate(self):
  self.binding['default_action']='changed';p.motion.write(self.root/'bindings.pending.json',self.binding)
  with self.assertRaises(ValueError):p.activate(self.root)
  self.unchanged()
 def test_changed_native_asset_cannot_activate(self):
  (self.root/'Content/test.uasset').write_bytes(b'edited')
  with self.assertRaises(ValueError):p.activate(self.root)
  self.unchanged()
 def test_path_escape_cannot_activate(self):
  self.binding['revision']='../escape';p.motion.write(self.root/'bindings.pending.json',self.binding)
  with self.assertRaises(ValueError):p.activate(self.root)
  self.unchanged()
 def test_success_preserves_engine_dependency_and_old_revision(self):
  result=p.activate(self.root);self.assertEqual(result['active'],'new')
  self.assertIn('/Engine/BasicShapes',(self.root/'Config/DefaultGame.ini').read_text())
  for n,value in self.original.items():self.assertEqual((Path(result['backup'])/'before'/n).read_bytes(),value)
  self.assertFalse((self.root/'bindings.pending.json').exists())
 def test_io_failure_rolls_back_and_retry_preserves_failure_record(self):
  original=p.os.replace;count=0
  def fail_second(a,b):
   nonlocal count
   count+=1
   if count==2:raise OSError('injected disk error')
   return original(a,b)
  with patch.object(p.os,'replace',fail_second):
   with self.assertRaises(OSError):p.activate(self.root)
  self.unchanged();self.assertTrue((self.root/'bindings.pending.json').exists())
  failed=self.root/'.openaigame/playback-history/new/activation.json'
  self.assertEqual(p.motion.read(failed)['state'],'rolled_back')
  result=p.activate(self.root);self.assertNotEqual(Path(result['backup']).name,'new');self.assertTrue(failed.is_file())
 def test_create_existing_project_preserves_user_file(self):
  # Source validation may succeed, but installation must never overwrite this project.
  with patch.object(p,'checked_bindings',return_value={}),patch.object(p.motion,'read',return_value={'revision':'x'}),patch.object(p.runtime_components,'engine_version',return_value='4'):
   with self.assertRaises(ValueError):p.create(self.root,'godot',self.root,self.root/'unused')
  self.unchanged()

class CharacterProfileTests(unittest.TestCase):
 def test_legacy_profile_keeps_original_defaults(self):
  self.assertEqual(p.observation_bones({}),{n:n for n in p.OBSERVATION_ROLES})
  self.assertIn('RunSpeedMps=2.5',p.example_settings({}))
 def test_partial_or_duplicate_native_roles_are_rejected(self):
  mapping={n:'Character_'+n for n in p.OBSERVATION_ROLES}
  partial=dict(mapping);partial.pop('dst_head')
  duplicate=dict(mapping);duplicate['dst_head']=duplicate['dst_spine'].upper()
  for value in (partial,duplicate):
   with self.subTest(value=value),self.assertRaises(ValueError):p.observation_bones({'observation_bones':value})
 def test_invalid_movement_profile_is_rejected(self):
  for value in ({'walk':1},{'walk':float('nan'),'run':2},{'walk':True,'run':2},{'walk':-1,'run':2}):
   with self.subTest(value=value),self.assertRaises(ValueError):p.example_settings({'movement_speeds_mps':value})
 def test_bone_name_cannot_inject_an_ini_setting(self):
  mapping={n:n for n in p.OBSERVATION_ROLES};mapping['dst_head']='Head\nRunSpeedMps=20'
  with self.assertRaises(ValueError):p.example_settings({'observation_bones':mapping})

class LocomotionContractTests(unittest.TestCase):
 def binding(self):
  return {'movement_speeds_mps':{'walk':1.,'run':2.5},'locomotion':{'mode':'speed_phase','acceleration_mps2':3.,'deceleration_mps2':4.,'turn_speed_deg_s':240.,'transition_s':.18,'contact_phase':{'L':[1/6,1/3],'R':[2/3,5/6]}},'clips':[{'id':n,'clip':n,'duration_s':d,'loop':True} for n,d in [('idle',2),('walk',1),('run',.6)]]}
 def test_legacy_is_opt_in(self):
  self.assertIsNone(p.locomotion_settings({}))
  self.assertIn('LocomotionEnabled=false',p.example_settings({}))
 def test_config_is_exported_to_project(self):
  text=p.example_settings(self.binding())
  self.assertIn('AccelerationMps2=3.0',text);self.assertIn('LocomotionEnabled=true',text)
 def test_missing_or_nonsensical_policy_is_rejected(self):
  for key,value in [('mode','strafe'),('acceleration_mps2',0),('deceleration_mps2',float('nan')),('turn_speed_deg_s',True),('transition_s',3)]:
   b=self.binding();b['locomotion'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):p.example_settings(b)
  b=self.binding();del b['locomotion']['transition_s']
  with self.assertRaises(ValueError):p.example_settings(b)
 def test_contact_speeds_must_be_ordered(self):
  b=self.binding();b['movement_speeds_mps']['run']=.5
  with self.assertRaises(ValueError):p.example_settings(b)
 def test_gait_events_nonlooping_and_missing_assets_rejected(self):
  for change in ['marker','nonloop','missing','reserved']:
   b=self.binding()
   if change=='marker':b['clips'][1]['markers']=[{'name':'step','at_s':.3}]
   if change=='nonloop':b['clips'][1]['loop']=False
   if change=='missing':b['clips'].pop()
   if change=='reserved':b['clips'].append({'id':'locomotion'})
   with self.subTest(change=change),self.assertRaises(ValueError):p.example_settings(b)
 def test_unverified_or_opposite_foot_phase_rejected(self):
  b=self.binding();spec={'clips':[{'id':n} for n in ('walk','run')]}
  with self.assertRaises(ValueError):p.check_locomotion_phases(b,spec)
  for clip in spec['clips']:
   duration=1 if clip['id']=='walk' else .6
   clip['repairs']={'contacts':[{'chain':['dst_foot_'+side],'start_s':lo*duration,'end_s':hi*duration,'blend_s':0} for side,(lo,hi) in b['locomotion']['contact_phase'].items()]}
  p.check_locomotion_phases(b,spec)
  spec['clips'][1]['repairs']['contacts'][0]['chain']=['dst_foot_R']
  with self.assertRaises(ValueError):p.check_locomotion_phases(b,spec)

class TurningContractTests(unittest.TestCase):
 def binding(self):
  b=LocomotionContractTests().binding();b['turning']={'mode':'step_turn_v1','trigger_deg':30,'settle_s':.2,'recover_s':.2}
  b['turn_observation_bones']={k:k for k in ('dst_hips','dst_thigh_L','dst_thigh_R','dst_shin_L','dst_shin_R')}
  b['clips'] += [{'id':f'turn_{s}_{a}','duration_s':.4+a/45*.6,'loop':False} for s in ('l','r') for a in (45,90,180)]
  return b
 def test_old_projects_do_not_enable_turning(self):
  self.assertIn('TurningEnabled=false',p.example_settings({}))
 def test_missing_direction_rejected(self):
  b=self.binding();b['clips'].pop()
  with self.assertRaises(ValueError):p.example_settings(b)
 def test_controller_and_clip_timing_must_match(self):
  b=self.binding();b['clips'][-1]['duration_s']=1.4
  with self.assertRaises(ValueError):p.example_settings(b)
 def test_controller_profile_cannot_silently_warp_assets(self):
  for field,value in [('trigger_deg',0),('settle_s',0),('mode','root_motion')]:
   b=self.binding();b['turning'][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):p.example_settings(b)
 def test_knees_must_be_observable(self):
  b=self.binding();del b['turn_observation_bones']['dst_shin_L']
  with self.assertRaises(ValueError):p.example_settings(b)
 def test_valid_turns_export_policy_and_leg_observers(self):
  text=p.example_settings(self.binding());self.assertIn('TurningEnabled=true',text);self.assertIn('+ObservedBones=dst_shin_R=dst_shin_R',text)

if __name__=='__main__':unittest.main()

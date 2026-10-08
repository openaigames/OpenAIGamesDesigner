import copy,hashlib,json,sys,tempfile,unittest,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from workbench import action_edit as a

class EditorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  self.seq={'schema':'action-sequence/1','id':'jump','title':'Jump','duration_s':2,'tracks':[{'id':'audio','label':'Sound','kind':'audio'},{'id':'logic','label':'Logic','kind':'logic'}],'assets':[{'id':'land','label':'Landing','kind':'audio','binding':'local_land','duration_s':1,'preview':'sound.wav','sha256':''}],'clips':[{'id':'sound','label':'Land','track':'audio','asset':'land','start_s':.2,'source_in_s':0,'source_out_s':1,'rate':1,'blend_in_s':.01,'blend_out_s':.02,'volume':.5}],'events':[{'id':'hit','label':'Contact','track':'logic','time_s':.2}],'windows':[{'id':'lock','label':'Lock','track':'logic','start_s':0,'end_s':1}]}
  with wave.open(str(self.root/'sound.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\x00\x40'*8000)
  self.seq['assets'][0]['sha256']=a.digest(self.root/'sound.wav');a.write(self.root/'config.json',self.seq)
  a.write(self.root/a.MANIFEST,{'schema':'action-editor/1','actions':[{'id':'jump','title':'Jump','engine':'web','file':'config.json','editable':{'sound':['start_s','source_in_s','source_out_s','rate','blend_in_s','blend_out_s','volume'],'hit':['time_s'],'lock':['end_s']}}]})
 def request(self):return {'id':'jump','base_hash':a.digest(self.root/'config.json'),'sequence':copy.deepcopy(self.seq)}
 def test_apply_and_restore(self):
  d=self.request();d['sequence']['clips'][0]['start_s']=.4;d['draft_hash']=a.save(self.root,d)['draft_hash'];r=a.apply(self.root,d)
  self.assertEqual(a.detail(self.root,'jump')['sequence']['clips'][0]['start_s'],.4)
  a.restore(self.root,{'id':'jump','base_hash':r['hash'],'history_id':r['id']});self.assertEqual(a.detail(self.root,'jump')['sequence'],self.seq)
 def test_conflict_keeps_external_edit(self):
  d=self.request();d['sequence']['events'][0]['time_s']=.4;a.save(self.root,d)
  self.seq['events'][0]['time_s']=.8;a.write(self.root/'config.json',self.seq)
  with self.assertRaises(ValueError):a.apply(self.root,d)
  self.assertTrue(a.detail(self.root,'jump')['draft']['stale']);self.assertEqual(a.current(self.root,'jump')[1],self.seq)
 def test_draft_does_not_apply(self):
  d=self.request();d['sequence']['clips'][0]['volume']=.8;d['draft_hash']=a.save(self.root,d)['draft_hash'];self.assertEqual(a.digest(self.root/'config.json'),d['base_hash'])
 def test_waveform_from_audio(self):
  w=a.waveform(self.root,'jump','land');self.assertAlmostEqual(w['duration_s'],1);self.assertTrue(all(p==.5 for p in w['peaks']))
 def test_changed_media_rejected(self):
  (self.root/'sound.wav').write_bytes(b'changed')
  with self.assertRaises(ValueError):a.audio_path(self.root,'jump','land')
 def test_traversal(self):
  with self.assertRaises(ValueError):a.detail(self.root,'../jump')
  with self.assertRaises(ValueError):a.restore(self.root,{'id':'jump','history_id':'../../x'})
 def test_invalid_numbers_and_ranges(self):
  for field,value in [('start_s',float('nan')),('rate',0),('source_out_s',3),('source_in_s',1.1),('blend_in_s',2),('volume',-1)]:
   with self.subTest(field=field):
    d=self.request();d['sequence']['clips'][0][field]=value
    with self.assertRaises(ValueError):a.save(self.root,d)
 def test_unknown_fields_rejected(self):
  d=self.request();d['sequence']['clips'][0]['ignored']=100
  with self.assertRaises(ValueError):a.save(self.root,d)
 def test_binding_changes_rejected(self):
  d=self.request();d['sequence']['assets'][0]['binding']='something_else'
  with self.assertRaises(ValueError):a.save(self.root,d)
 def test_unsupported_field_rejected(self):
  d=self.request();d['sequence']['windows'][0]['start_s']=.1
  with self.assertRaises(ValueError):a.save(self.root,d)
 def test_restore_conflict(self):
  d=self.request();d['sequence']['clips'][0]['volume']=.7;d['draft_hash']=a.save(self.root,d)['draft_hash'];r=a.apply(self.root,d)
  a.write(self.root/'config.json',self.seq)
  with self.assertRaises(ValueError):a.restore(self.root,{'id':'jump','base_hash':a.digest(self.root/'config.json'),'history_id':r['id']})
 def test_immutable_backup_hash(self):
  d=self.request();d['sequence']['clips'][0]['volume']=.7;d['draft_hash']=a.save(self.root,d)['draft_hash'];r=a.apply(self.root,d)
  (self.root/a.PREFIX/'jump/history'/(r['id']+'.before')).write_text('{}')
  with self.assertRaises(ValueError):a.restore(self.root,{'id':'jump','base_hash':r['hash'],'history_id':r['id']})
 def test_second_browser_draft_conflict(self):
  first=self.request();first['sequence']['clips'][0]['volume']=.7;first['draft_hash']=a.save(self.root,first)['draft_hash']
  second=self.request();second['sequence']['clips'][0]['volume']=.2;a.save(self.root,second)
  with self.assertRaises(ValueError):a.apply(self.root,first)
  self.assertEqual(a.current(self.root,'jump')[1],self.seq)
if __name__=='__main__':unittest.main()

"""Mailbox isolation and versioning; these fixtures are not engine verification."""
import copy,json,os,sys,tempfile,time,unittest
import http.client,threading
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from workbench import action_edit as edit, action_preview as preview
import project_workbench,record_io

class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.seq={'schema':'action-sequence/1','id':'test','title':'Test','duration_s':2,'tracks':[{'id':'logic','label':'Logic','kind':'logic'}], 'assets':[],'clips':[], 'events':[{'id':'hit','label':'Hit','track':'logic','time_s':1}], 'windows':[]}
        edit.write(self.root/'game/config.json',self.seq)
        edit.write(self.root/edit.MANIFEST,{'schema':'action-editor/1','actions':[{'id':'test','title':'Test','engine':'godot','file':'game/config.json','editable':{'hit':['time_s']},'preview':{'protocol':preview.PROTOCOL,'consumer':'lab'}}]})
        self.base=self.root/preview.PREFIX/'lab'
        self.ready={'schema':preview.PROTOCOL,'instance':'engine1','engine':'godot','engine_version':'fixture','actions':['test'],'views':[{'id':'front','label':'Front'}],'controls':['replay','pause','resume','step','view','speed','stop']}
        edit.write(self.base/'ready.json',self.ready)
    def data(self,operation='replay'):
        return {'id':'test','instance':'engine1','client':'browser1','operation':operation,'sequence':copy.deepcopy(self.seq),'base_hash':edit.digest(self.root/'game/config.json')}
    def test_draft_does_not_write_live_or_saved_draft(self):
        data=self.data();before=(self.root/'game/config.json').read_bytes();data['sequence']['events'][0]['time_s']=.5
        result=preview.command(self.root,data)
        self.assertEqual((self.root/'game/config.json').read_bytes(),before)
        self.assertFalse((self.root/edit.PREFIX).exists())
        self.assertEqual(edit.digest(self.base/'runs'/result['run']/'sequence.json'),result['sequence_sha256'])
    def test_stale_base_and_unsupported_fields_rejected(self):
        data=self.data();data['base_hash']='old'
        with self.assertRaises(ValueError):preview.command(self.root,data)
        data=self.data();data['sequence']['duration_s']=3
        with self.assertRaises(ValueError):preview.command(self.root,data)
    def test_offline_and_restart_rejected(self):
        old=time.time()-10;os.utime(self.base/'ready.json',(old,old))
        self.assertFalse(preview.status(self.root,'test')['online'])
        with self.assertRaises(ValueError):preview.command(self.root,self.data())
        self.ready['instance']='engine2';edit.write(self.base/'ready.json',self.ready)
        with self.assertRaises(ValueError):preview.command(self.root,self.data())
    def test_new_run_and_owner_are_required_for_controls(self):
        first=preview.command(self.root,self.data());second=preview.command(self.root,self.data())
        data=self.data('pause');data['run']=first['run']
        with self.assertRaises(ValueError):preview.command(self.root,data)
        data['run']=second['run'];preview.command(self.root,data)
        data=self.data();data['client']='browser2'
        with self.assertRaises(ValueError):preview.command(self.root,data)
        preview.heartbeat(self.root,{'id':'test','instance':'engine1','client':'browser1','release':True})
        preview.command(self.root,data)
    def test_old_instance_never_acknowledges_new_request(self):
        edit.write(self.base/'status.json',{'instance':'old','action':'test','applied':True})
        self.assertNotIn('state',preview.status(self.root,'test'))
    def test_late_heartbeat_cannot_revive_released_scene(self):
        preview.command(self.root,self.data())
        pulse={'id':'test','instance':'engine1','client':'browser1'}
        preview.heartbeat(self.root,pulse|{'release':True})
        with self.assertRaises(ValueError):preview.heartbeat(self.root,pulse)
        preview.command(self.root,self.data());preview.heartbeat(self.root,pulse)
    def test_camera_speed_and_path_validation(self):
        result=preview.command(self.root,self.data())
        for operation,extra in [('view',{'view':'absent'}),('speed',{'speed':float('nan')}),('speed',{'speed':20})]:
            data=self.data(operation);data.update(run=result['run'],**extra)
            with self.assertRaises(ValueError):preview.command(self.root,data)
        with self.assertRaises(ValueError):preview.frame_path(self.root,'test','../../x','1')
    def test_frame_requires_acknowledged_version(self):
        request=preview.command(self.root,self.data())
        with self.assertRaises(ValueError):preview.frame_path(self.root,'test',request['run'],'1')
        edit.write(self.base/'status.json',{'instance':'engine1','action':'test','run':request['run'],'applied':True})
        path=self.base/'runs'/request['run']/'frame-1.png';path.write_bytes(b'fixture')
        for root in (self.root, self.root/'..'/self.root.name):
            with self.subTest(root=root):
                self.assertEqual(preview.frame_path(root,'test',request['run'],'1'),path.resolve())
        with self.assertRaises(ValueError):preview.frame_path(self.root,'test','different','1')
    def test_completed_capture_preserved_once_and_matches_config(self):
        request=preview.command(self.root,self.data());folder=self.base/'runs'/request['run']
        capture={'schema':'action-events/1','engine':'godot','engine_version':'fixture','action':'test','revision':request['sequence_sha256'],'source':'unit fixture','input_mode':'software','input_description':'one replay','clock':'monotonic_seconds','zero_s':0,'duration_s':2,'complete':True,'dropped_events':0,'events':[],'preview_sequence':self.seq}
        edit.write(folder/'capture.json',capture)
        data={'id':'test','run':request['run']};first=preview.preserve(self.root,data)
        for root in (self.root, self.root/'..'/self.root.name):
            with self.subTest(root=root):
                second=preview.preserve(root,data)
                self.assertEqual(first['id'],second['id'])
        capture['revision']='wrong';edit.write(folder/'capture.json',capture)
        with self.assertRaises(ValueError):preview.preserve(self.root,data)
    def test_missing_registration_is_not_a_live_capability(self):
        path=self.root/edit.MANIFEST;doc=json.loads(path.read_text());doc['actions'][0].pop('preview');edit.write(path,doc)
        self.assertFalse(preview.status(self.root,'test')['configured'])
        with self.assertRaises(ValueError):preview.command(self.root,self.data())
    def test_replacement_gap_is_retried(self):
        original=preview.review.read_json
        with patch.object(preview.review,'read_json',side_effect=[FileNotFoundError(),original(self.base/'ready.json')]):
            self.assertEqual(preview.read_optional(self.base/'ready.json')['instance'],'engine1')
    def test_multiple_workbench_writers_share_lock(self):
        with record_io.project_lock(self.root,'action-preview'):
            with self.assertRaises(ValueError):preview.command(self.root,self.data())
        preview.command(self.root,self.data())
    def test_preview_routes_keep_session_and_csrf_boundary(self):
        with project_workbench.WorkbenchServer(self.root,view='actions') as server:
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                def call(method,path,body=None,headers=None):
                    conn.request(method,path,json.dumps(body) if body is not None else None,headers or {})
                    res=conn.getresponse();raw=res.read();return res.status,dict(res.getheaders()),json.loads(raw)
                self.assertEqual(call('GET','/api/action-preview-status?id=test')[0],401)
                origin={'Origin':server.origin,'Content-Type':'application/json','X-Workbench-Connect':'1'}
                _,headers,_=call('POST','/session',{},origin);cookie={'Cookie':headers['Set-Cookie'].split(';')[0]}
                _,_,session=call('GET','/api/session',headers=cookie)
                self.assertEqual(call('POST','/api/action-preview-command',self.data(),origin|cookie)[0],403)
                self.assertEqual(call('POST','/api/action-preview-command',self.data(),origin|cookie|{'X-CSRF-Token':session['csrf']})[0],200)
                self.assertTrue(call('GET','/api/action-preview-status?id=test',headers=cookie)[2]['online'])
                self.assertEqual(call('GET','/api/action-preview-status?id=test&project=other',headers=cookie)[0],404)
                conn.close()
            finally:server.shutdown();worker.join()

if __name__=='__main__':unittest.main()

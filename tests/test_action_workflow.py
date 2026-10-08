"""Timing snapshots, input compatibility, and workbench session boundaries."""
import copy
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT)]
from workbench import action_review as ar
import action_workflow
import project_workbench


def capture():
    return {'schema':'action-events/1','engine':'web','engine_version':'fixture','action':'interaction',
        'revision':'one','source':'unit fixture, not gameplay','input_mode':'software','input_description':'one press',
        'clock':'monotonic_seconds','zero_s':0,'duration_s':1,'complete':True,'dropped_events':0,
        'events':[{'track':'logic','id':'commit#1','t_s':0.5,'uncertainty_s':0.01}]}


def spec():
    return {'schema':'action-timeline/1','action':'interaction','revision':'intent-v1','duration_s':1,
        'events':[{'track':'logic','id':'commit#1','time_s':0.5,'tolerance_s':0.02}]}


class ActionTests(unittest.TestCase):
    def setUp(self):
        base=Path(os.environ.get('ACTION_TEST_ROOT',str(Path.cwd()/'action-test-output'))).resolve()
        self.root=base/uuid.uuid4().hex;self.root.mkdir(parents=True)
        self.write('capture.json',capture());self.write('spec.json',spec())

    def write(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),'utf8');return p

    def register(self,**kwargs):return ar.register(self.root,{'capture':'capture.json','spec':'spec.json',**kwargs})

    def test_immutable_source_snapshot(self):
        run=self.register();self.write('capture.json',{'changed':True})
        self.assertEqual(ar.detail(self.root,run['id'])['capture'],capture())
        self.assertEqual(run['status'],'within_tolerance')

    def test_unsupported_engine(self):
        c=capture();c['engine']='imaginary'
        with self.assertRaises(ValueError):ar.evaluate(c,spec())

    def test_invalid_display_names_and_pair_references(self):
        for change in [{'track_labels':[]},{'event_labels':{'logic':[]}},{'delays':[{'from':[],'to':['logic','commit#1'],'min_s':0,'max_s':1}]}]:
            with self.assertRaises(ValueError):ar.evaluate(capture(),spec()|change)

    def test_unknown_clock(self):
        c=capture();c['clock']='wall_clock'
        with self.assertRaises(ValueError):ar.evaluate(c,spec())

    def test_no_standard_is_not_pass(self):
        self.assertEqual(ar.evaluate(capture())['status'],'observed')
        s=spec();s['events']=[];self.assertEqual(ar.evaluate(capture(),s)['status'],'observed')

    def test_incomplete_and_overflow(self):
        for field,value in [('complete',False),('dropped_events',1)]:
            c=capture();c[field]=value;self.assertEqual(ar.evaluate(c,spec())['status'],'incomplete')

    def test_missing_is_not_pass(self):
        c=capture();c['events']=[];self.assertEqual(ar.evaluate(c,spec())['status'],'issues')

    def test_relative_delay_does_not_depend_on_record_start(self):
        c=capture();c['duration_s']=6;c['events']=[{'track':'input','id':'start#1','t_s':5}, {'track':'logic','id':'commit#1','t_s':5.25}]
        s=spec();s['duration_s']=6;s['events']=[];s['delays']=[{'from':['input','start#1'],'to':['logic','commit#1'],'min_s':0.24,'max_s':0.28}]
        self.assertEqual(ar.evaluate(c,s)['status'],'within_tolerance')
        c['events'][1]['t_s']=5.5;self.assertEqual(ar.evaluate(c,s)['status'],'issues')

    def test_uncertain_is_not_pass(self):
        c=capture();c['events'][0]['uncertainty_s']=0.1
        r=ar.evaluate(c,spec());self.assertEqual(r['status'],'issues')
        self.assertEqual(r['report']['events'][0]['status'],'uncertain')

    def test_nonfinite_and_bool_rejected(self):
        for value in [float('nan'),float('inf'),True,-1]:
            c=capture();c['events'][0]['t_s']=value
            with self.assertRaises(ValueError):ar.evaluate(c,spec())

    def test_duplicate_rejected(self):
        c=capture();c['events']*=2
        with self.assertRaises(ValueError):ar.evaluate(c,spec())

    def test_outside_recording_rejected(self):
        c=capture();c['events'][0]['t_s']=1.1
        with self.assertRaises(ValueError):ar.evaluate(c,spec())

    def test_missing_window_rejected_even_without_event(self):
        c=capture();c['events']=[];s=spec();s['events'][0]['window']='missing'
        with self.assertRaises(ValueError):ar.evaluate(c,s)

    def test_path_traversal_and_absolute_rejected(self):
        for name in ['../capture.json','C:/capture.json','/capture.json','capture.json:stream']:
            with self.assertRaises(ValueError):self.register(capture=name)

    def test_oversized_input(self):
        p=self.root/'large.json';p.write_bytes(b' '* (ar.MAX_BYTES+1))
        with self.assertRaises(ValueError):self.register(capture='large.json')

    def test_compare_reports_delta(self):
        a=self.register();c=capture();c['events'][0]['t_s']=0.6;c['revision']='two';self.write('capture.json',c);b=self.register()
        d=ar.compare(self.root,a['id'],b['id']);self.assertAlmostEqual(d['rows'][0]['delta_s'],0.1)

    def test_different_inputs_not_equivalent(self):
        a=self.register();c=capture();c['input_description']='different press';self.write('capture.json',c);b=self.register()
        with self.assertRaises(ValueError):ar.compare(self.root,a['id'],b['id'])

    def test_video_mutation_rejected(self):
        (self.root/'video.mp4').write_bytes(b'fixture media');run=self.register(video='video.mp4',video_zero_s=0)
        (self.root/'video.mp4').write_bytes(b'changed')
        with self.assertRaises(ValueError):ar.media_path(self.root,run['id'])

    def test_installer_keeps_user_edits(self):
        out=self.root/'adapter';action_workflow.install('web',out)
        (out/'action-recorder.mjs').write_text('// user edit','utf8')
        with self.assertRaises(ValueError):action_workflow.install('web',out)
        self.assertEqual((out/'action-recorder.mjs').read_text('utf8'),'// user edit')

    def test_http_auth_and_import(self):
        with project_workbench.WorkbenchServer(self.root,view='actions') as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                def request(method,path,body=None,headers=None):
                    conn.request(method,path,json.dumps(body) if body is not None else None,headers or {})
                    response=conn.getresponse();data=response.read();return response.status,dict(response.getheaders()),json.loads(data)
                self.assertEqual(request('GET','/api/action-runs')[0],401)
                base={'Origin':server.origin,'Content-Type':'application/json','X-Workbench-Connect':'1'}
                self.assertEqual(request('POST','/session',{},base|{'Origin':'https://wrong.invalid'})[0],403)
                code,headers,_=request('POST','/session',{},base);self.assertEqual(code,200)
                cookie={'Cookie':headers['Set-Cookie'].split(';')[0]}
                code,_,session=request('GET','/api/session',headers=cookie);self.assertEqual(code,200)
                body={'capture':'capture.json','spec':'spec.json'}
                self.assertEqual(request('POST','/api/action-import',body,base|cookie)[0],403)
                code,_,run=request('POST','/api/action-import',body,base|cookie|{'X-CSRF-Token':session['csrf']});self.assertEqual(code,201)
                code,_,detail=request('GET','/api/action-run?id='+run['id'],headers=cookie);self.assertEqual(code,200)
                self.assertEqual(detail['result']['status'],'within_tolerance')
                self.assertEqual(request('GET','/api/action-runs?project=other',headers=cookie)[0],404)
                conn.close()
            finally:server.shutdown();t.join()


if __name__=='__main__':unittest.main()

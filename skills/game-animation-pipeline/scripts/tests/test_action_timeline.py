import copy
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/'action_timeline.py'
s=importlib.util.spec_from_file_location('timeline',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.spec={'schema':'action-timeline/1','revision':'test','duration_s':2,
            'events':[{'track':'logic','id':'pickup','time_s':.5,'tolerance_s':.05}],
            'windows':[{'track':'logic','id':'allowed','start_s':.3,'end_s':.8}]}
        self.cap={'schema':'action-events/1','revision':'test','source':'synthetic test','zero_s':10,
            'events':[{'track':'logic','id':'pickup','t_s':10.52,'uncertainty_s':.01}]}

    def test_non_shooting_event(self):self.assertFalse(m.analyze(self.spec,self.cap)['issues'])
    def test_missing_event(self):
        self.cap['events']=[]
        self.assertEqual(m.analyze(self.spec,self.cap)['events'][0]['status'],'missing')
    def test_sample_uncertainty(self):
        self.cap['events'][0].update(t_s=10.57,uncertainty_s=.03)
        self.assertEqual(m.analyze(self.spec,self.cap)['events'][0]['status'],'uncertain')
    def test_late_event(self):
        self.cap['events'][0]['t_s']=11
        self.assertEqual(m.analyze(self.spec,self.cap)['events'][0]['status'],'outside_tolerance')
    def test_window_violation(self):
        self.spec['events'][0].update(window='allowed',tolerance_s=2)
        self.cap['events'][0]['t_s']=11
        self.assertIn('outside_window',[r['kind'] for r in m.analyze(self.spec,self.cap)['issues']])
    def test_duplicate_rejected(self):
        self.cap['events']*=2
        with self.assertRaises(ValueError):m.analyze(self.spec,self.cap)
    def test_dual_view_offset(self):
        self.cap['events'].append({'track':'third','id':'pickup','t_s':10.7})
        self.spec['synchronize']=[{'a':['logic','pickup'],'b':['third','pickup'],'tolerance_s':.04}]
        self.assertEqual(m.analyze(self.spec,self.cap)['synchronization'][0]['status'],'outside_tolerance')
    def test_nan_rejected(self):
        self.cap['events'][0]['t_s']=float('nan')
        with self.assertRaises(ValueError):m.analyze(self.spec,self.cap)
    def test_escaping(self):
        self.cap['source']='<script>attack</script>'
        page=m.render(self.spec,self.cap,m.analyze(self.spec,self.cap))
        self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)


if __name__=='__main__':unittest.main()

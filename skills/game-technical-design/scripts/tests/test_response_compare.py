import copy
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'response_compare.py'
s=importlib.util.spec_from_file_location('response',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.ch={'key':'x','unit':'cm','layer':'visual','baseline':0,'threshold':.1}
        self.spec={'schema':'response-comparison/1','recovery_dwell_s':.2,'channels':[self.ch]}
        self.cap={'schema':'response-capture/1','id':'one','source':'synthetic','conditions':{'rate':10},
            'inputs':[{'t_s':0,'action':'press'}],'fire_end_s':.5,
            'samples':[{'t_s':t,'x':x} for t,x in [(0,0),(.5,3),(1,-2),(1.2,.5),(1.5,0),(1.8,0)]]}
    def test_oscillation(self):
        r=m.analyze(self.spec,[self.cap])['captures'][0]['channels']['x']
        self.assertEqual(r['post_fire_zero_crossings'],2);self.assertEqual(r['end_of_firing'],3)
        self.assertAlmostEqual(r['recovery_s'],1)
    def test_no_recovery_is_not_zero(self):
        self.cap['samples']=self.cap['samples'][:4]
        self.assertIsNone(m.analyze(self.spec,[self.cap])['captures'][0]['channels']['x']['recovery_s'])
    def test_different_input_rejected_for_comparison(self):
        b=copy.deepcopy(self.cap);b['id']='two';b['inputs'][0]['t_s']=.1
        self.assertFalse(m.analyze(self.spec,[self.cap,b])['captures'][1]['comparable_to_first'])
    def test_missing_inputs(self):
        self.cap['inputs']=[]
        self.assertTrue(m.analyze(self.spec,[self.cap])['issues'])
    def test_non_monotonic_time(self):
        self.cap['samples'][2]['t_s']=.5
        with self.assertRaises(ValueError):m.analyze(self.spec,[self.cap])
    def test_neutral_offset(self):
        self.ch['baseline']=4
        for row in self.cap['samples']:row['x']+=4
        self.assertEqual(m.analyze(self.spec,[self.cap])['captures'][0]['channels']['x']['peak_abs'],3)


if __name__=='__main__':unittest.main()

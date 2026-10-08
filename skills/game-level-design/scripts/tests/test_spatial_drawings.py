import copy
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'spatial_drawings.py'
s=importlib.util.spec_from_file_location('spatial',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.ob={'id':'box','footprint':[[4,.8],[5,.8],[5,2],[4,2]],'z_min':0,'z_max':1}
        self.data={'schema':'spatial-drawings/1','revision':'test','source':'synthetic',
            'coordinate':'test coordinates','unit':'m','up':'+Z','objects':[self.ob],
            'routes':[{'id':'walk','centerline':[[0,0],[10,0]],'width':2,'z_min':0,'z_max':2}]}
    def test_width_hits_even_when_center_does_not(self):
        r=m.analyze(self.data)['issues'][0]
        self.assertEqual(r['kind'],'route_clearance');self.assertAlmostEqual(r['intrusion'],.2)
    def test_high_object_does_not_block(self):
        self.ob.update(z_min=3,z_max=4)
        self.assertFalse(m.analyze(self.data)['issues'])
    def test_narrow_intrusion_not_sampled_away(self):
        self.ob['footprint']=[[4.001,.999],[4.002,.999],[4.002,1.5],[4.001,1.5]]
        self.assertTrue(m.analyze(self.data)['issues'])
    def test_concave_boundary(self):
        boundary=[[0,0],[4,0],[4,4],[3,4],[3,1],[1,1],[1,4],[0,4]]
        self.assertFalse(m.contained([[.5,3.5],[3.5,3.5],[3.5,3.8],[.5,3.8]],boundary))
    def test_section_handles_concavity(self):
        poly=[[0,0],[4,0],[4,4],[3,4],[3,1],[1,1],[1,4],[0,4]]
        self.assertEqual(m.section_intervals(poly,0,2),[(0,1),(3,4)])
    def test_stair_risers_and_treads(self):
        self.data['objects']=[{'id':'stairs','footprint':[[0,0],[3.3,0],[3.3,2],[0,2]],'z_min':0,'z_max':1.8,
            'kind':'stairs','risers':12,'treads':11,'run':3.3,'blocks_routes':False}]
        self.data['limits']={'max_step_height':.16,'min_tread_depth':.28}
        r=m.analyze(self.data);self.assertFalse(r['issues']);self.assertAlmostEqual(r['measurements'][0]['tread'],.3)
    def test_self_intersection_rejected(self):
        self.ob['footprint']=[[0,0],[2,2],[2,0],[0,2]]
        with self.assertRaises(ValueError):m.analyze(self.data)
    def test_move_proposal_keeps_original(self):
        after=copy.deepcopy(self.data);after['revision']='proposal'
        after['objects'][0]['footprint']=[[4,3],[5,3],[5,4],[4,4]]
        r=m.compare(self.data,after)
        self.assertTrue(r['before']['issues']);self.assertFalse(r['after']['issues']);self.assertEqual(self.ob['footprint'][0],[4,.8])
    def test_opening_bounds(self):
        self.ob['openings']=[{'id':'door','edge':0,'start':0,'end':2,'z_min':0,'z_max':1}]
        self.assertIn('opening_outside_wall',[r['kind'] for r in m.analyze(self.data)['issues']])


if __name__=='__main__':unittest.main()

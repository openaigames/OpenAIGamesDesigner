import copy
import importlib.util
from pathlib import Path
import unittest


def load(name):
    p=Path(__file__).resolve().parents[1]/(name+'.py')
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


a=load('asset_compare');w=load('weapon_fit')


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.snap={'schema':'asset-snapshot/1','unit':'cm','coordinate':'Z up',
            'rigs':{'body':{'root':{'parent':None,'head_cm':[0,0,0],'tail_cm':[0,0,1],
                'rest_matrix':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],'deform':True}}},
            'meshes':{'body':{'triangles':12,'bounds_cm':{'size':[2,2,2]},
                'weights':{'unweighted_vertices':0,'weight_sum_max_error':0,'declared_rig_attached':True},'sections':{}}},'frames':[]}
        self.limits={'joint_cm':.01,'axis_deg':.1,'weight_error':.001,'volume_ratio_min':.8,'volume_ratio_max':1.2,'stretch_max':2}
    def test_same_snapshot(self):self.assertFalse(a.compare(self.snap,self.snap,self.limits)['issues'])
    def test_bone_axis_flip(self):
        b=copy.deepcopy(self.snap);b['rigs']['body']['root']['rest_matrix'][0][0]=-1
        self.assertEqual(a.compare(self.snap,b,self.limits)['rigs']['body']['bones']['root']['axis_angle_max_deg'],180)
    def test_unweighted_vertices(self):
        b=copy.deepcopy(self.snap);b['meshes']['body']['weights']['unweighted_vertices']=3
        self.assertIn('skin_weights',[r['kind'] for r in a.compare(self.snap,b,self.limits)['issues']])
    def test_unknown_section_volume(self):
        sec={'definition':{},'slab_volume_estimate_cm3':None,'slices':[{'area_cm2':None}]}
        self.snap['meshes']['body']['sections']['arm']=sec
        self.assertEqual(a.compare(self.snap,self.snap,self.limits)['issues'][0]['kind'],'section_open_or_ambiguous')
    def test_different_coordinate_rejected(self):
        b=copy.deepcopy(self.snap);b['coordinate']='Y up'
        with self.assertRaises(ValueError):a.compare(self.snap,b,self.limits)
    def test_weapon_missing_binding(self):
        fit={'schema':'weapon-fit/1','unit':'cm','space':'weapon_local','coordinate':'Z up','source':'synthetic',
            'bones':['grip'],'points':{'muzzle':{'position_cm':[0,4,0],'bone':'unknown'}},
            'parts':[{'id':'magazine','bounds_cm':{'min':[0,0,0],'max':[1,1,1]},'moving':True}]}
        kinds=[r['kind'] for r in w.analyze(fit)['issues']]
        self.assertIn('missing_bone',kinds);self.assertIn('moving_part_binding_missing',kinds)
    def test_weapon_same_space_error(self):
        fit={'schema':'weapon-fit/1','unit':'cm','space':'weapon_local','coordinate':'Z up','source':'synthetic',
            'bones':['grip'],'points':{'muzzle':{'position_cm':[0,4,0]}},
            'targets':{'muzzle':{'position_cm':[0,5,0],'tolerance_cm':.2}}}
        self.assertAlmostEqual(w.analyze(fit)['point_errors']['muzzle']['error_cm'],1)


if __name__=='__main__':unittest.main()

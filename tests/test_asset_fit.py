import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import asset_fit
from record_io import write_json

class FitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'goal.md').write_text('Original agile player; monster boss. Do not move sword rules to boss.')
        (self.root/'preview.txt').write_text('unit fixture only')
        self.spec={'schema_version':1,'id':'C1','title':'Monster set','object':'boss','role':'boss','use':'Pressure creature','goal_ref':'goal.md','sources':[{'url':'https://example.com/creature','title':'Fixture source','version':'test','price':'free claim, not live verified','license':'unknown','evidence':[]}],
            'members':[{'id':'creature','source_url':'https://example.com/creature','capabilities':[{'id':'claw','kind':'motion','label':'Claw','availability':'observed','preview_type':'motion','evidence':['preview.txt'],'conditions':'test fixture'}]}],
            'requirements':[{'id':'claw','description':'Claw windup and recovery','coverage':'supported','member':'creature','capability':'claw','notes':'observed in fixture'},{'id':'stagger','description':'Reaction opportunity','coverage':'missing','notes':'No observed reaction yet'}],'tradeoffs':['Missing reaction is retained; no silent target downgrade']}
    def test_model_image_cannot_cover_motion(self):
        self.spec['members'][0]['capabilities'][0]['preview_type']='image'
        with self.assertRaises(ValueError):asset_fit.register(self.root,self.spec)
    def test_coverage_versions_and_goal_staleness(self):
        result=asset_fit.register(self.root,self.spec)
        self.assertEqual(result['location'],'candidate');self.assertEqual(len(result['gaps']),1)
        (self.root/'goal.md').write_text('changed scope')
        self.assertEqual(asset_fit.read(self.root,'C1')['status'],'stale')
    def test_claims_cannot_be_supported_and_no_promotion(self):
        self.spec['members'][0]['capabilities'][0]['availability']='claimed'
        with self.assertRaises(ValueError):asset_fit.register(self.root,self.spec)
        self.spec['requirements'][0]['coverage']='unknown'
        result=asset_fit.register(self.root,self.spec)
        self.assertEqual(result['location'],'candidate')
        self.assertFalse((self.root/'game').exists())
    def test_real_layout_and_versioned_revision(self):
        write_json(self.root/'.openaigame/project.json',{'schema_version':1,'engine':'unreal','engine_root':'.'})
        (self.root/'Content').mkdir();(self.root/'Content/Monster.uasset').write_bytes(b'fixture only')
        self.spec['members'][0]['path']='Content/Monster.uasset'
        self.assertEqual(asset_fit.register(self.root,self.spec)['location'],'game')
        updated=copy.deepcopy(self.spec);updated.update(id='C2',supersedes='C1')
        asset_fit.register(self.root,updated)
        self.assertEqual([r['id'] for r in asset_fit.snapshot(self.root)['fits']],['C2'])
        self.assertEqual(asset_fit.snapshot(self.root)['historical_fits'],['C1'])

if __name__=='__main__':unittest.main()

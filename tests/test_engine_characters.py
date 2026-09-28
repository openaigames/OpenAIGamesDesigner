"""Native export provenance and selective character invalidation (synthetic files)."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import engine_characters as native
from record_io import write_json,digest
from workbench import asset_browser

class NativeCharacters(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
    def file(self,name,content=b'synthetic native test fixture'):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);return str(p)
    def session(self,name='export1',character='hero'):
        r=self.root
        model=self.file('game/'+character+'.uasset');animation=self.file('game/'+character+'-attack.uasset')
        code=self.file('game/main.cpp');preview=self.file('previews/engine/'+name+'/'+character+'.fbx')
        hashes={Path(p).relative_to(r/'game').as_posix():digest(p) for p in [model,animation,code]}
        result={'success':True,'request_id':name,'characters':[{'id':character,'title':character,'role':'player','model':model,'preview':preview,'preview_sha256':digest(preview),
            'actions':[{'label':'Attack','file':animation,'asset':'/Game/Attack.Attack','basis':'static_single_node_reference','preview':None}],
            'dependencies':[model,animation],'scope':'Synthetic fixture only','consumer':{'path':'/Game/Map:Hero'}}]}
        folder=r/'runs'/name;write_json(folder/'result.json',result)
        write_json(folder/'session.json',{'status':'completed','project':str(r/'game'),'before':hashes,'after':hashes,'evidence_hashes':{'result.json':digest(folder/'result.json')}})
        return result
    def test_sync_reads_actual_actions_and_preview(self):
        self.session();native.sync(self.root,'export1')
        board=asset_browser.scan(self.root)
        self.assertEqual(board['characters'][0]['actions'][0]['basis'],'static_single_node_reference')
        self.assertEqual(board['characters'][0]['consumer'],'/Game/Map:Hero')
    def test_changed_export_or_native_result_rejected(self):
        result=self.session();Path(result['characters'][0]['preview']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'preview'):native.sync(self.root,'export1')
        self.assertFalse((self.root/'.asset-browser/characters.json').exists())
    def test_unrelated_character_not_refreshed_or_hidden(self):
        self.session();native.sync(self.root,'export1')
        self.session('export2','boss');native.sync(self.root,'export2')
        (self.root/'game/hero-attack.uasset').write_bytes(b'changed')
        board=asset_browser.scan(self.root)
        self.assertEqual([c['id'] for c in board['characters']],['boss'])
        self.assertIn('hero',board['characterBindingError'])
    def test_modified_native_source_requires_fresh_export(self):
        self.session();(self.root/'game/main.cpp').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):native.sync(self.root,'export1')

if __name__=='__main__':unittest.main()

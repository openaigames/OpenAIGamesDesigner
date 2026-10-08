"""Legacy routes and registered provenance remain usable after the UI deferral."""
from pathlib import Path
import hashlib, sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from project_workbench import normalize_view
from workbench.art_registry import classify

class SurfaceTests(unittest.TestCase):
    def test_saved_action_launch_redirects_to_assets(self):
        self.assertEqual(normalize_view('actions'),'assets')
        for current in ('assets','tasks','services'):
            self.assertEqual(normalize_view(current),current)

    def test_registered_source_survives_scan_and_is_marked_after_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'asset.glb';p.write_bytes(b'file identity fixture')
            record={'id':'A1','objectId':'O1','stage':'已导入，未验证',
                    'source':'自制模型；项目许可','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            data={'assets':{'asset.glb':record},'objects':{'O1':{'label':'角色','tags':['主角']}}}
            art=classify(root,{'path':'asset.glb'},data)
            self.assertEqual(art['source'],record['source']);self.assertEqual(art['state'],'linked')
            p.write_bytes(b'new content')
            changed=classify(root,{'path':'asset.glb'},data)
            self.assertEqual(changed['state'],'version-changed')
            self.assertEqual(changed['source'],record['source'])

if __name__=='__main__':unittest.main()

import json
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import bundle_upgrade as upgrade
from check_installation import MANIFEST,bundle_id,check


def bundle(root,files):
    hashes={}
    for relative,text in files.items():
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        hashes[relative]=upgrade.sha(path.read_bytes())
    manifest=root/MANIFEST;manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps({'version':1,'files':hashes,'bundle_id':bundle_id(hashes)}))


class UpgradeTests(unittest.TestCase):
    def test_preserve_local_extension_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);old,new,installed,candidate,backup=[base/x for x in ('old','new','installed','candidate','backup')]
            rel='game-preproduction/runtime/tools/example.py'
            original='start\na = 1\nend\n'
            bundle(old,{rel:original});bundle(new,{rel:'start\na = 2\nend\n','game-preproduction/runtime/tools/add.py':'new'})
            bundle(installed,{rel:original});(installed/rel).write_text(original+'# local extension\n')
            extra='game-preproduction/runtime/tools/custom.py';(installed/extra).write_text('custom')
            outside=installed/'unrelated-skill/note.txt';outside.parent.mkdir();outside.write_text('keep')
            report=upgrade.prepare(old,new,installed,candidate,[extra])
            self.assertIn(rel,report['preserved_local_files'])
            self.assertEqual((candidate/rel).read_text(),'start\na = 2\nend\n# local extension\n')
            upgrade.apply(candidate,installed,backup)
            self.assertEqual(check(installed)['changed'],[])
            self.assertEqual(outside.read_text(),'keep')
            upgrade.rollback(backup)
            self.assertEqual((installed/rel).read_text(),original+'# local extension\n')
            self.assertFalse((installed/'game-preproduction/runtime/tools/add.py').exists())
            self.assertEqual((installed/extra).read_text(),'custom')

    def test_conflict_and_stale_install_do_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);old,new,installed,candidate,backup=[base/x for x in ('old','new','installed','candidate','backup')]
            rel='game-preproduction/runtime/tools/example.py'
            bundle(old,{rel:'start\na = 1\nend\n'});bundle(new,{rel:'start\na = 2\nend\n'});bundle(installed,{rel:'start\na = 7\nend\n'})
            with self.assertRaisesRegex(ValueError,'explicit merge'):upgrade.prepare(old,new,installed,candidate)
            self.assertFalse(candidate.exists())
            (installed/rel).write_bytes((old/rel).read_bytes())
            upgrade.prepare(old,new,installed,candidate)
            (installed/rel).write_text('user edit after prepare')
            with self.assertRaisesRegex(ValueError,'changed since preparation'):upgrade.apply(candidate,installed,backup)
            self.assertFalse(backup.exists())
            self.assertEqual((installed/rel).read_text(),'user edit after prepare')

    def test_post_install_edits_stop_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);old,new,installed,candidate,backup=[base/x for x in ('old','new','installed','candidate','backup')]
            rel='game-preproduction/runtime/tools/example.py'
            bundle(old,{rel:'old'});bundle(new,{rel:'new'});bundle(installed,{rel:'old'})
            upgrade.prepare(old,new,installed,candidate);upgrade.apply(candidate,installed,backup)
            (installed/rel).write_text('new user edit')
            with self.assertRaisesRegex(ValueError,'prevent rollback'):upgrade.rollback(backup)
            self.assertEqual((installed/rel).read_text(),'new user edit')

if __name__=='__main__':unittest.main()

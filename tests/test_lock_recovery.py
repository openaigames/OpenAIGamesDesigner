import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from record_io import write_json,recover_lock,read_json

class LockRecovery(unittest.TestCase):
    def test_live_wrong_and_dead_lock_recovery_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lock=root/'.openaigame/task-state.lock'
            write_json(lock,{'pid':os.getpid(),'token':'same','created_at':'test'})
            (root/'inspection.txt').write_text('Synthetic recovery test; not engine evidence')
            with self.assertRaisesRegex(ValueError,'identity'):recover_lock(root,'task-state','other','inspection',['inspection.txt'])
            with self.assertRaisesRegex(ValueError,'alive'):recover_lock(root,'task-state','same','inspection',['inspection.txt'])
            self.assertTrue(lock.exists())
            with patch('adapters.engines.sessions.process_alive',return_value=False):
                r=recover_lock(root,'task-state','same','verified stopped writer',['inspection.txt'])
            self.assertFalse(lock.exists());self.assertFalse(r['work_replayed'])
            self.assertEqual(read_json(root/r['receipt'])['lock']['token'],'same')

if __name__=='__main__':unittest.main()

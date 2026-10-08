"""Offline tests: no credentials, network, authorization receipts, or paid tasks."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.assets import tripo,tripo_inputs,api_common
class TripoMultiviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rows=[]
        for view in ('back','front','left'):
            p=self.root/(view+'.png');p.write_bytes(view.encode())
            self.rows.append({'path':p.name,'snapshot':str(p),'view':view,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        self.r={'parameters':{'type':'multiview_to_model','model_version':'v3.1-20260211','pbr':True},'inputs':self.rows}
    def test_wire_order_and_missing_right(self):
        with patch.object(api_common,'credential',return_value='fixture'):c=tripo.Client({})
        with patch.object(c,'call',side_effect=[{'image_token':'front-token'},{'image_token':'left-token'},{'image_token':'back-token'},{'task_id':'task-1'}]) as call:
            self.assertEqual(c.submit(self.r),'task-1')
            p=call.call_args.args[1]
            self.assertEqual(p['files'],[{'type':'png','file_token':'front-token'},{'type':'png','file_token':'left-token'},{'type':'png','file_token':'back-token'},{}])
            self.assertNotIn('prompt',p)
            self.assertEqual(call.call_count,4)
    def test_reject_before_network_if_any_image_changed(self):
        Path(self.rows[0]['snapshot']).write_bytes(b'changed')
        with patch.object(api_common,'credential',return_value='fixture'):c=tripo.Client({})
        with patch.object(c,'call') as call:
            with self.assertRaises(ValueError):c.submit(self.r)
            call.assert_not_called()
    def test_reject_bad_directions_and_mixed_prompt(self):
        for mutate in ('missingfront','duplicateview','duplicatefile','prompt'):
            r=json.loads(json.dumps(self.r))
            if mutate=='missingfront':r['inputs'][1]['view']='right'
            if mutate=='duplicateview':r['inputs'][0]['view']='left'
            if mutate=='duplicatefile':r['inputs'][0]['snapshot']=r['inputs'][1]['snapshot']
            if mutate=='prompt':r['parameters']['prompt']='ignored?'
            with self.assertRaises(ValueError):tripo_inputs.validate(r)
    def test_receipt_uses_actual_order_labels(self):
        s=tripo_inputs.summary(self.r)
        self.assertEqual(s['wire_view_order'],['front','left','back','right'])
        self.assertEqual(s['omitted_views'],['right'])
        self.assertFalse(s['prompt_sent'])
if __name__=='__main__':unittest.main()


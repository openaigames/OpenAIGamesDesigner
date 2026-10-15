"""Portability and fail-closed identity checks, independent of native engines."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import motion_workflow as motion
import motion_handoff as handoff


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'author'; self.source.mkdir()
        self.dep = self.source/'source.blend'; self.dep.write_bytes(b'original source fixture')
        self.revision = self.source/'revision'; self.revision.mkdir()
        (self.revision/'clip.glb').write_bytes(b'export fixture')
        motion.write(self.revision/'job.json', {'mode':'process','spec':{'source':str(self.dep)}})
        motion.write(self.revision/'report.json', {'ok':True,'artifacts':{'clip.glb':motion.digest(self.revision/'clip.glb')},'dependencies':{str(self.dep):motion.digest(self.dep)}})
        self.output = self.root/'transfer'

    def test_receipt_survives_original_directory_disappearing_and_second_move(self):
        original = (self.revision/'report.json').read_bytes()
        self.assertTrue(handoff.pack(self.revision,self.output)['ok'])
        self.source.rename(self.root/'author-offline')
        received = self.root/'receiver with spaces'; shutil.copytree(self.output,received)
        self.output.rename(self.root/'archive-offline')
        self.assertTrue(handoff.check(received)['ok']); self.assertTrue(motion.verify(received)['ok'])
        self.assertEqual((received/'provenance/original-report.json').read_bytes(),original)

    def test_tamper_source_snapshot_export_and_job_rejected(self):
        handoff.pack(self.revision,self.output)
        manifest=motion.read(self.output/'handoff.json')
        for name in ('clip.glb','job.json',next(k for k in manifest['files'] if k.startswith('dependencies/'))):
            with self.subTest(name=name):
                path=self.output/name; original=path.read_bytes(); path.write_bytes(original+b'changed')
                self.assertFalse(handoff.check(self.output)['ok'])
                self.assertFalse(motion.verify(self.output)['ok'])
                path.write_bytes(original)

    def test_received_spec_edit_rejected_by_playback_verification_path(self):
        handoff.pack(self.revision,self.output)
        doc=motion.read(self.output/'job.json');doc['spec']['source']='different rig'
        motion.write(self.output/'job.json',doc)
        self.assertIn('Received motion metadata changed',motion.verify(self.output)['failures'])

    def test_missing_and_escaping_dependency_rejected(self):
        handoff.pack(self.revision,self.output)
        doc=motion.read(self.output/'report.json'); doc['dependencies']={'../source.blend':'0'*64}
        motion.write(self.output/'report.json',doc)
        self.assertFalse(motion.verify(self.output)['ok'])
        with self.assertRaises(ValueError):handoff.check(self.output)

    def test_changed_original_and_existing_destination_refused(self):
        self.dep.write_bytes(b'changed')
        with self.assertRaises(ValueError):handoff.pack(self.revision,self.output)
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        with self.assertRaises(ValueError):handoff.pack(self.revision,self.output)

    def test_nested_dependency_snapshot_is_included_and_checked(self):
        nested=self.source/'nested';nested.mkdir(); deeper=nested/'original.blend';deeper.write_bytes(b'deeper source')
        motion.write(nested/'report.json',{'dependencies':{str(deeper):motion.digest(deeper)}})
        doc=motion.read(self.revision/'report.json');doc['dependencies'][str(nested/'report.json')]=motion.digest(nested/'report.json');motion.write(self.revision/'report.json',doc)
        handoff.pack(self.revision,self.output)
        manifest=motion.read(self.output/'handoff.json');self.assertIn(str(deeper),manifest['dependency_mapping'])
        received=self.output/manifest['dependency_mapping'][str(deeper)];received.unlink()
        self.assertFalse(handoff.check(self.output)['ok'])


if __name__ == '__main__':unittest.main()

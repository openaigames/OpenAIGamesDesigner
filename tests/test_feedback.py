import array
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import runtime_components as runtime
from runtime_validation import inspect_audio
from templates.runtime_feedback.generate_audio import generate


class FeedbackTests(unittest.TestCase):
    def test_generated_cues_repeat_and_loop_seam_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=generate(root/'a');b=generate(root/'b')
            self.assertEqual(a,b)
            for asset in a:
                signal=inspect_audio(root/'a'/asset['file'])
                self.assertTrue(signal['non_silent']);self.assertEqual(signal['clipped_samples'],0)
            with wave.open(str(root/'a/zone.wav'),'rb') as stream:
                pcm=array.array('h',stream.readframes(stream.getnframes()))
            if sys.byteorder!='little':pcm.byteswap()
            self.assertLess(abs(pcm[0]-pcm[-1]),500)
            self.assertEqual(len(pcm),44100)

    def test_fresh_engine_examples_cook_assets_and_keep_project_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fake=root/'ue/Engine/Build';fake.mkdir(parents=True)
            (fake/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':8,'PatchVersion':2}))
            g=root/'godot';u=root/'unreal'
            runtime.create(g,'godot','feedback');runtime.create(u,'unreal','feedback',root/'ue')
            self.assertIn('feedback-profile.json',(g/'export_presets.cfg').read_text())
            self.assertIn('Path="/Game/Feedback"',(u/'Config/DefaultGame.ini').read_text())
            self.assertEqual((g/'audio/zone.wav').read_bytes(),(u/'Content/OAGDData/audio/zone.wav').read_bytes())
            profile=json.loads((g/'feedback-profile.json').read_text());profile['cues']['door']['volume']=0.1
            (g/'feedback-profile.json').write_text(json.dumps(profile))
            self.assertEqual(json.loads((u/'Content/OAGDData/feedback-profile.json').read_text())['cues']['door']['volume'],.45)
            self.assertEqual(runtime.status(g)['changed'],[])
            self.assertEqual(runtime.status(u)['changed'],[])
            self.assertFalse((g/'addons/oagd_playback').exists());self.assertFalse((u/'Plugins/OAGDPlayback').exists())

    def test_signal_check_does_not_accept_silent_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'silent.wav'
            with wave.open(str(path),'wb') as out:
                out.setparams((2,2,48000,4800,'NONE','not compressed'));out.writeframes(bytes(4800*4))
            result=inspect_audio(path)
            self.assertFalse(result['non_silent'])
            self.assertEqual(result['listening_acceptance'],'not_performed')

if __name__=='__main__':unittest.main()

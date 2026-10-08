"""Audio contracts, real sample edits and mocked cloud delivery; never spend credits."""
from array import array
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_workflow
import audio_workflow
from adapters.assets import api_common, audio_timing as timing, credential_store, elevenlabs, elevenlabs_worker as worker
from adapters.assets import generation_approval as approval, http_io


def wav(path, seconds=0.5, rate=16000, channels=2, silent=False):
    samples = array('h')
    for frame in range(round(seconds * rate)):
        value = 0 if silent or frame < rate * .02 else round(math.sin(frame * 2 * math.pi * 500 / rate) * 12000)
        samples.extend([value] * channels)
    if sys.byteorder != 'little': samples.byteswap()
    with wave.open(str(path), 'wb') as sound:
        sound.setnchannels(channels); sound.setframerate(rate); sound.setsampwidth(2); sound.writeframes(samples.tobytes())


def window():
    return {'event': 'sword.swing', 'window': {'start_seconds': .12, 'end_seconds': .36, 'play_rate': 1.2},
            'tail_seconds': .04, 'trim_start_seconds': .02, 'fade_in_seconds': .002, 'fade_out_seconds': .008}


class Response(io.BytesIO):
    def __init__(self, data=b'ID3audio', **headers):
        super().__init__(data)
        self.headers = {'Content-Type': 'audio/mpeg', 'Content-Length': str(len(data)), 'request-id': 'sample-id', **headers}


class AudioTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.settings = {'mode': 'api'}
        self.request = {'parameters': {'kind': 'sound_effect', 'text': 'single sword whoosh', 'timing': window()}, 'inputs': []}
        for context in (patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'synthetic-elevenlabs-test-key'}),
                        patch.object(credential_store, 'store_path', return_value=self.root / 'profile/keys.json')):
            context.start(); self.addCleanup(context.stop)

    def linked(self):
        config = self.root / 'combat.json'
        config.write_text(json.dumps({'swing': window()['window']}))
        request = copy.deepcopy(self.request)
        request['parameters']['timing'].pop('window')
        request['parameters']['timing']['source'] = {'path': 'combat.json', 'pointer': '/swing'}
        return config, request

    def test_window_conversion_minimum_generation_and_distinct_events(self):
        path, body = elevenlabs.payload(self.request)
        self.assertEqual(path, '/sound-generation'); self.assertEqual(body['duration_seconds'], .5)
        self.assertAlmostEqual(timing.timing_plan(window())['target_seconds'], .24)
        self.assertNotIn('timing', body); self.assertNotIn('event', body)
        p = self.request['parameters']
        p.pop('timing'); p.update(duration_seconds=2.75, loop=True)
        self.assertEqual(elevenlabs.payload(self.request)[1]['duration_seconds'], 2.75)
        self.assertTrue(elevenlabs.payload(self.request)[1]['loop'])

    def test_music_and_speech_have_separate_contracts(self):
        p = {'kind': 'music', 'text': 'combat music', 'music_length_ms': 30000}
        path, body = elevenlabs.payload({'parameters': p})
        self.assertEqual(path, '/music'); self.assertTrue(body['force_instrumental'])
        self.assertEqual(body['prompt'], 'combat music'); self.assertNotIn('text', body)
        p = {'kind': 'speech', 'text': 'stop', 'voice_id': 'voice_123'}
        path, body = elevenlabs.payload({'parameters': p})
        self.assertEqual(path, '/text-to-speech/voice_123'); self.assertEqual(body['text'], 'stop')
        self.assertNotIn('duration_seconds', body)
        p['timing'] = window()
        with self.assertRaises(ValueError): elevenlabs.payload({'parameters': p})

    def test_invalid_inputs_fail_before_job_directories_or_network(self):
        invalid = [{'kind':'sound_effect','text':'a','duration_seconds': True},
                   {'kind':'sound_effect','text':'a','duration_seconds': float('nan')},
                   {'kind':'sound_effect','text':'a','duration_seconds':31},
                   {'kind':'sound_effect','text':'a','loop':'false','duration_seconds':1},
                   {'kind':'speech','text':'a','voice_id':'../bad'},
                   {'kind':'music','text':'a','music_length_ms':3000.5},
                   {'kind':'music','text':'a','music_length_ms':3000,'api_key':'secret'}]
        for parameters in invalid:
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                asset_workflow.new_job(self.root,'elevenlabs',{'parameters':parameters},self.settings)
        bad = copy.deepcopy(self.request); bad['parameters']['timing']['window']['play_rate'] = 0
        with self.assertRaises(ValueError): asset_workflow.new_job(self.root,'elevenlabs',bad,self.settings)
        self.assertFalse((self.root / '.openaigame').exists())

    def test_linked_snapshot_stale_source_and_approval_binding(self):
        config, request = self.linked()
        job = asset_workflow.new_job(self.root,'elevenlabs',request,self.settings)
        self.assertEqual(job['request']['inputs'][0]['sha256'], timing.digest(config))
        self.assertEqual(timing.check_source(self.root,job['request']), 'current')
        fingerprint = approval.for_job(self.root,job); approval.approve(fingerprint)
        approval.require(fingerprint)
        edited = copy.deepcopy(job); edited['request']['parameters']['timing']['tail_seconds'] = .1
        self.assertNotEqual(approval.for_job(self.root,edited), fingerprint)
        with self.assertRaises(ValueError): approval.require(approval.for_job(self.root,edited))
        config.write_text(json.dumps({'swing': {'start_seconds':.1,'end_seconds':.5,'play_rate':1}}))
        with self.assertRaises(ValueError): approval.for_job(self.root,job)
        with patch.object(elevenlabs.Client,'generate') as post, self.assertRaises(ValueError):
            asset_workflow.execute_job(self.root,job['job_id'],10)
        post.assert_not_called()
        with self.assertRaises(ValueError): asset_workflow.new_job(self.root,'elevenlabs',job['request'],self.settings)

    def test_source_escape_and_stale_export_rejected(self):
        _, request = self.linked(); request['parameters']['timing']['source']['path'] = '../outside.json'
        with self.assertRaises(ValueError): asset_workflow.new_job(self.root,'elevenlabs',request,self.settings)
        _, request = self.linked(); request['parameters']['timing']['source']['pointer'] = '/missing'
        with self.assertRaises(ValueError): asset_workflow.new_job(self.root,'elevenlabs',request,self.settings)

    def test_fit_exact_samples_stereo_envelope_and_immutable_source(self):
        source = self.root/'source.wav'; target = self.root/'window.wav'; wav(source)
        original = source.read_bytes(); report = timing.fit(source,target,window())
        with wave.open(str(target),'rb') as sound:
            self.assertEqual(sound.getnframes(),3840); self.assertEqual(sound.getnchannels(),2)
        samples,_,rate = timing.read_pcm(target)
        self.assertEqual(list(samples[:2]),[0,0]); self.assertEqual(list(samples[-2:]),[0,0])
        original_samples,_,_ = timing.read_pcm(source)
        self.assertEqual(samples[1600:1700],original_samples[2240:2340]) # body remains unchanged, no pitch/speed shift
        self.assertEqual(source.read_bytes(),original); self.assertFalse(report['pitch_changed'])
        self.assertEqual(report['quality_validation'],'not_checked')
        with self.assertRaises(ValueError): timing.fit(source,target,window())

    def test_padding_and_silence_are_reported_not_quality_passes(self):
        source=self.root/'short.wav'; wav(source,.1,silent=True)
        report=timing.fit(source,self.root/'pad.wav',window())
        self.assertGreater(report['padded_frames'],0); self.assertTrue(report['measurement']['silent'])
        self.assertEqual(report['measurement']['listening_validation'],'not_checked')
        self.assertIsNone(report['measurement']['signal_start_seconds'])
        wrong=window();wrong['trim_start_seconds']=1
        with self.assertRaises(ValueError):timing.fit(source,self.root/'bad.wav',wrong)

    def test_local_fit_cli_never_calls_provider_and_records_source_hash(self):
        config,request=self.linked(); wav(self.root/'source.wav')
        (self.root/'request.json').write_text(json.dumps(request))
        with patch.object(elevenlabs.Client,'generate') as generate, patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(audio_workflow.main(['--project',str(self.root),'fit','--input','source.wav',
                '--request','request.json','--output','candidates/sword-r2.wav']),0)
        generate.assert_not_called()
        report=json.loads((self.root/'candidates/sword-r2.timing.json').read_text())
        self.assertEqual(report['timing_source_sha256'],timing.digest(config))
        self.assertTrue((self.root/'candidates/sword-r2.wav').is_file())

    def test_binary_transport_headers_receipt_limits_and_no_secret_leak(self):
        with patch.object(http_io,'open_url',return_value=Response(**{'character-cost':'7'})) as call:
            receipt=elevenlabs.Client(self.settings).generate(self.request,self.root/'original.mp3')
        url,data,headers,method=call.call_args.args
        self.assertEqual(method,'POST');self.assertTrue(url.startswith('https://api.elevenlabs.io/'))
        self.assertEqual(headers['xi-api-key'],'synthetic-elevenlabs-test-key')
        self.assertEqual(receipt['headers']['character-cost'],'7')
        self.assertNotIn('synthetic-elevenlabs-test-key',json.dumps(receipt))
        self.assertNotIn('window',json.loads(data))
        for index,response in enumerate([Response(b'{"secret":"bad"}',**{'Content-Type':'application/json'}),
                Response(b'ID3audio',**{'Content-Length':'100'}), Response(b'ID3toolong')]):
            with patch.object(http_io,'open_url',return_value=response),self.assertRaises(ValueError):
                elevenlabs.Client({'mode':'api','max_download_bytes':9}).generate(self.request,self.root/f'bad{index}.mp3')
            self.assertFalse((self.root/f'bad{index}.mp3').exists());self.assertFalse((self.root/f'bad{index}.part').exists())

    def test_api_key_redirect_is_blocked(self):
        request=urllib.request.Request('https://api.elevenlabs.io/v1/music',headers={'xi-api-key':'synthetic'})
        with patch.object(http_io,'public_url'),self.assertRaises(ValueError):
            http_io.Redirects().redirect_request(request,None,302,'redirect',{},'https://other.example/audio')

    def test_worker_uncertain_submission_never_auto_repeats_or_resumes(self):
        job=asset_workflow.new_job(self.root,'elevenlabs',self.request,self.settings)
        request=copy.deepcopy(job['request']);request['_approval']={'project':str(self.root),'job_id':job['job_id']}
        output=self.root/'output';output.mkdir();result=self.root/'result.json'
        approval.approve(approval.for_job(self.root,job))
        with patch.object(timing,'ffmpeg_executable',return_value=sys.executable),patch.object(elevenlabs.Client,'generate',side_effect=ValueError('disconnected')) as post:
            with self.assertRaises(ValueError):worker.run(self.settings,request,output,result)
            with self.assertRaises(ValueError):worker.run(self.settings,request,output,result)
        self.assertEqual(post.call_count,1);self.assertFalse(result.exists())
        self.assertEqual(json.loads((self.root/'remote.json').read_text())['status'],'submitting')
        with self.assertRaises(ValueError):approval.require(approval.for_job(self.root,job))
        with self.assertRaises(ValueError):asset_workflow.execute_job(self.root,job['job_id'],10,resume=True)

    def test_missing_decoder_does_not_consume_approval(self):
        job=asset_workflow.new_job(self.root,'elevenlabs',self.request,self.settings)
        fingerprint=approval.for_job(self.root,job);approval.approve(fingerprint)
        request=copy.deepcopy(job['request']);request['_approval']={'project':str(self.root),'job_id':job['job_id']}
        with patch.object(timing,'ffmpeg_executable',side_effect=ValueError('missing')),patch.object(elevenlabs.Client,'generate') as post,self.assertRaises(ValueError):
            worker.run(self.settings,request,self.root,self.root/'result.json')
        post.assert_not_called();approval.require(fingerprint)

    def test_mocked_generation_real_mp3_decode_and_window_output(self):
        try: executable=timing.ffmpeg_executable()
        except ValueError:self.skipTest('Install imageio-ffmpeg for real codec integration')
        source=self.root/'fixture.wav';wav(source);mp3=self.root/'fixture.mp3'
        subprocess.run([executable,'-nostdin','-v','error','-i',str(source),str(mp3)],check=True,capture_output=True)
        job=asset_workflow.new_job(self.root,'elevenlabs',self.request,self.settings)
        request=copy.deepcopy(job['request']);request['_approval']={'project':str(self.root),'job_id':job['job_id']}
        approval.approve(approval.for_job(self.root,job));output=self.root/'output';output.mkdir()
        with patch.object(http_io,'open_url',return_value=Response(mp3.read_bytes())) as post:
            worker.run(self.settings,request,output,self.root/'result.json')
        self.assertEqual(post.call_count,1)
        result=json.loads((self.root/'result.json').read_text())
        files=asset_workflow.artifacts(self.root,output,result,job)
        self.assertEqual(len(files),3);self.assertTrue(all(x['quality_validation']=='not_checked' for x in files))
        self.assertAlmostEqual(timing.inspect(output/'window.wav')['duration_seconds'],.24)
        self.assertEqual((output/'original.mp3').read_bytes(),mp3.read_bytes())
        self.assertEqual(json.loads((self.root/'remote.json').read_text())['status'],'completed')


if __name__=='__main__':unittest.main()

"""Measured clocks, version changes, spatial provenance and parameters."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import observation


def capture():
    return {'schema_version':1,'context':{'engine':'fixture','engine_version':'1','project':'fixture',
            'build':'controlled','input_mode':'component_call','method':'test fixture','conditions':['not a real engine run'],
            'sampling_overhead':'not measured'},'objects':[{'id':'hero','label':'Hero','source':'node','kind':'actor'}],
            'clocks':[{'id':'game','unit':'seconds','description':'game time'}],
            'events':[{'id':'request','object':'hero','clock':'game','time':0.1,'event':'input_request'},
                      {'id':'commit','object':'hero','clock':'game','time':0.2,'event':'rule_commit'},
                      {'id':'cancel','object':'hero','clock':'game','time':0.25,'event':'cancel'},
                      {'id':'cleanup','object':'hero','clock':'game','time':0.4,'event':'cleanup'}],
            'parameters':[{'id':'speed','object':'hero','value':5,'unit':'m/s','provenance':'project_authored',
                           'source':'config.json','conditions':'design target'},
                          {'id':'speed','object':'hero','value':4,'unit':'m/s','provenance':'runtime_readback',
                           'source':'actor.speed','conditions':'runtime modifier active'}],
            'space':{'dimensions':2,'unit':'m','axes':'+X right, +Y down','objects':[{'id':'hero','position':[0,1],
                      'kind':'actor','measurement':'runtime_sample','bounds':[[-1,0],[1,2]]}],
                     'routes':[{'id':'route','object':'hero','clock':'game','measurement':'actual_movement',
                                'samples':[[0,0,1],[1,1,1]],'conditions':'normal movement'}]},
            'limitations':['fixture only']}


class ObservationTests(unittest.TestCase):
    def test_delayed_cleanup_and_parameter_override_are_observable(self):
        data=capture()
        self.assertAlmostEqual(observation.elapsed(data,'cancel','cleanup')['seconds'],0.15)
        values=observation.parameter_comparison(data,'speed')
        self.assertEqual([v['value'] for v in values['values']],[5,4])
        self.assertTrue(values['runtime_observed'])
        self.assertEqual(observation.elapsed(data,'request','commit')['hardware_latency'],'not_measured')

    def test_different_clocks_cannot_be_subtracted(self):
        data=capture()
        data['clocks'].append({'id':'wall','unit':'seconds','description':'monotonic real time'})
        data['events'][-1]['clock']='wall'
        with self.assertRaises(ValueError):observation.elapsed(data,'cancel','cleanup')

    def test_unknown_events_missing_samples_and_invalid_spatial_geometry_are_not_invented(self):
        data=capture()
        with self.assertRaises(KeyError):observation.elapsed(data,'request','hit')
        self.assertNotIn('hit',[e['event'] for e in data['events']])
        data['space']['objects'][0]['bounds']=[[2,2],[0,0]]
        with self.assertRaises(ValueError):observation.validate_capture(data)

    def test_nan_time_unknown_object_and_time_reversal_are_rejected(self):
        for change in ('nan','object','reversal'):
            data=capture()
            if change=='nan':data['events'][0]['time']=float('nan')
            if change=='object':data['events'][0]['object']='unobserved'
            if change=='reversal':data['events'][-1]['time']=0.01
            with self.assertRaises(ValueError):observation.validate_capture(data)

    def test_registered_capture_detects_changed_inputs_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            (root/'capture.json').write_text(json.dumps(capture()),encoding='utf-8')
            (root/'scene.tscn').write_text('scene v1',encoding='utf-8')
            observation.register(root,'capture.json','O001',['scene.tscn'])
            self.assertEqual(observation.read(root,'O001')['status'],'current')
            (root/'scene.tscn').write_text('scene v2',encoding='utf-8')
            current=observation.read(root,'O001')
            self.assertEqual(current['status'],'stale')
            self.assertEqual(current['data']['events'],capture()['events'])
            with self.assertRaises(FileExistsError):observation.register(root,'capture.json','O001')

    def test_paused_or_reversed_media_mapping_is_rejected(self):
        data=capture()
        data['media']=[{'path':'clip.mp4','kind':'video','clock':'game','anchors':[[0,0],[0,1]],
                       'description':'invalid pause mapping','audio_coverage':'unknown'}]
        with self.assertRaises(ValueError):observation.validate_capture(data)


if __name__=='__main__':unittest.main()

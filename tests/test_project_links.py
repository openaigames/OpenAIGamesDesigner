"""Explicit consumers and semantic source changes, without blanket invalidation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import project_links


class ProjectLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config={'door_width':140,'speed':500,'commit':.3,'unrelated':'red'}
        self.save()
        (self.root/'rules.gd').write_text('source test fixture')
        constraints=[]
        for cid,domain,unit in [('door_width','scale','cm'),('speed','movement','cm/s'),('commit','timing','s')]:
            constraints.append({'id':cid,'domain':domain,'description':'Explicit fixture standard','unit':unit,
                'source':{'kind':'json','path':'config.json','pointer':'/'+cid,'locator':cid,'provenance':'project_authored'},
                'consumers':[{'object':'hero','source':'rules.gd','locator':cid,'checks':[cid+' actual consumer check']}]})
        self.spec={'schema_version':1,'objects':[{'id':'hero','title':'Hero'}],'constraints':constraints}
        self.spec_path=self.root/'standards.json';self.spec_path.write_text(json.dumps(self.spec))

    def save(self):
        (self.root/'config.json').write_text(json.dumps(self.config))

    def test_scale_movement_timing_changes_identify_only_declared_consumers(self):
        project_links.snapshot(self.root,'standards.json','baseline')
        self.config['speed']=600;self.config['unrelated']='blue';self.save()
        result=project_links.impact(self.root,'baseline')
        self.assertEqual([r['constraint'] for r in result['affected']],['speed'])
        self.assertEqual(result['affected'][0]['consumers'][0]['checks'],['speed actual consumer check'])
        self.assertEqual(set(result['unaffected']),{'door_width','commit'})
        for key,value in [('door_width',90),('commit',.1)]:
            self.config[key]=value;self.save()
            self.assertIn(key,[r['constraint'] for r in project_links.impact(self.root,'baseline')['affected']])

    def test_opaque_native_source_change_is_potential_not_invented_numeric_value(self):
        native=self.root/'parameters.uasset';native.write_bytes(b'opaque native fixture')
        self.spec['constraints'][0]['source']={'kind':'native','path':'parameters.uasset','locator':'DoorWidth','provenance':'project_authored'}
        self.spec_path.write_text(json.dumps(self.spec));project_links.snapshot(self.root,'standards.json','native')
        native.write_bytes(b'changed native fixture')
        row=project_links.impact(self.root,'native')['affected'][0]
        self.assertEqual(row['reason'],'source_changed_requires_review');self.assertIsNone(row['after'])

    def test_missing_consumer_and_escaping_source_do_not_create_snapshots(self):
        self.spec['constraints'][0]['consumers'][0]['source']='missing.gd'
        self.spec_path.write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):project_links.snapshot(self.root,'standards.json','invalid')
        self.assertFalse((self.root/'.openaigame/link-snapshots/invalid.json').exists())


if __name__=='__main__':unittest.main()

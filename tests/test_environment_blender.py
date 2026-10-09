"""Optional actual Blender checks; OAGD_BLENDER names an installed executable."""
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from environment.common import digest
from environment import views


@unittest.skipUnless(os.environ.get('OAGD_BLENDER'),'Set OAGD_BLENDER to run real Blender processing')
class ActualBlenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('OAGD_TEST_ROOT'):
            parent=Path(os.environ['OAGD_TEST_ROOT']).resolve()
            cls.path=parent/('environment-'+uuid.uuid4().hex)
            cls.path.mkdir(parents=True)
            def cleanup():
                actual=cls.path.resolve()
                if actual.parent != parent or not actual.name.startswith('environment-'):
                    raise ValueError('Unexpected test cleanup path')
                shutil.rmtree(actual)
            cls.addClassCleanup(cleanup)
        else:
            cls.temp=tempfile.TemporaryDirectory()
            cls.addClassCleanup(cls.temp.cleanup)
            cls.path=Path(cls.temp.name)
        executable=os.environ['OAGD_BLENDER']
        create=ROOT/'tests/fixtures/environment-production/create_fixture.py'
        cls.run_blender(executable,create,[str(cls.path/'fixture')])
        cls.fixture=cls.path/'fixture'
        cls.before=digest(cls.fixture/'source.blend')
        recipe=ROOT/'adapters/processing/blender_environment.py'
        for operation in ('audit','export','bake','capture'):
            cls.run_blender(executable,recipe,['--request',str(cls.fixture/(operation+'.json')),
                                               '--out',str(cls.path/operation)])
        spec=json.loads((cls.fixture/'export.json').read_text('utf8'));spec['meters_per_unit']=.01
        (cls.fixture/'cm.json').write_text(json.dumps(spec),'utf8')
        cls.run_blender(executable,recipe,['--request',str(cls.fixture/'cm.json'),'--out',str(cls.path/'cm')])

    @classmethod
    def run_blender(cls,exe,script,arguments):
        result=subprocess.run([exe,'--background','--factory-startup','--python-exit-code','1','--python',str(script),'--',*arguments],
                              capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180)
        if result.returncode:
            raise RuntimeError(result.stdout[-5000:]+result.stderr[-1000:])

    def report(self,name):
        return json.loads((self.path/name/'report.json').read_text('utf8'))

    def test_density_includes_uv_mapping_and_object_scale(self):
        row=self.report('audit')['objects'][0]['surfaces'][0]
        self.assertAlmostEqual(row['density_p50'],math.sqrt(256*512),places=3)
        self.assertAlmostEqual(row['area_m2'],2)

    def test_cm_export_has_actual_meter_dimensions(self):
        self.assertAlmostEqual(self.report('export')['reimported_bounds_m'][0][1]*2,2,places=5)
        self.assertAlmostEqual(self.report('cm')['reimported_bounds_m'][0][1]*2,.02,places=6)

    def test_bake_files_are_real_images_and_source_unchanged(self):
        files=self.report('bake')['files']
        self.assertEqual({x['channel'] for x in files},{'base_color','roughness','metallic','normal'})
        for f in files:
            self.assertEqual(views.png_size(f['path']),[64,64])
        self.assertEqual(digest(self.fixture/'source.blend'),self.before)

    def test_capture_readback_matches_plan(self):
        plan=json.loads((self.fixture/'views.json').read_text('utf8'))
        report=views.record(plan,self.path/'capture',self.fixture)
        self.assertTrue(report['checks_ok'])
        self.assertEqual(report['issues'],[])


if __name__=='__main__':unittest.main()

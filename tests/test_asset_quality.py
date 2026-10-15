"""Evidence boundaries, measured comparisons and honest review state transitions."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tools'))
from adapters.assets import quality as q, multiview, input_preparation as prep, model_prompt_policy
from adapters.assets.model_evidence import self_contained_glb
from tools.workbench import asset_review, asset_versions

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    Image = None


def picture(root, name, box=(30,25,170,175), color='red', opaque=False):
    image = Image.new('RGBA', (200,200), 'white' if opaque else (0,0,0,0))
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=color)
    draw.rectangle((box[0]+5, box[1]+5, box[0]+15, box[1]+20), fill='yellow')
    image.save(root/name)


def plan_fixture():
    return {'schema_version':1,'asset_id':'fixture_crate','kind':'image',
        'use':'Warehouse prop silhouette','environment':'Source asset comparison',
        'files':['front.png'], 'views':[
            {'id':name,'path':name+'.png','set':'result','direction':name,
             'projection':'orthographic','segmentation':{'alpha':True},
             'calibration':{'group':'shared_pose','pixels_per_unit':100,'baseline_y':176}}
            for name in ('front','back')],
        'required_views':[{'set':'result','directions':['front','back']}],
        'checks':[{'id':'height','metric':'height','a':'front','b':'back','priority':'must','tolerance':0.04}],
        'criteria':[{'id':'shape','dimension':'structure','priority':'must',
                     'description':'The crate silhouette and required parts match the brief'}]}


def reviewed(evidence, status='pass'):
    return {'schema_version':1,'reviewer':'synthetic test fixture; not a production art approval',
        'criteria':[{'id':c['id'],'status':status,'score':3 if status=='pass' else 1 if status=='fail' else None,
                     'confidence':'high','expected':c['description'],
                     'observed':'Fixture observation for testing gate behavior',
                     'evidence':list(evidence['evidence'])} for c in evidence['plan']['criteria']],
        'findings':[{'id':f['id'],'status':'explained','reason':'Intentional symmetry in this synthetic fixture',
                     'evidence':f['evidence']} for f in evidence['findings'] if f['kind']!='missing_view']}


@unittest.skipUnless(Image, 'Pillow is required for image evidence tests')
class QualityTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT/'dist'/('quality-test-'+uuid4().hex)
        self.root.mkdir(parents=True)
        def cleanup():
            assert self.root.resolve().is_relative_to((ROOT/'dist').resolve())
            shutil.rmtree(self.root)
        self.addCleanup(cleanup)
        picture(self.root,'front.png')
        picture(self.root,'back.png',color='blue')
        self.plan = plan_fixture()

    def collect(self):
        q.write(self.root/'plan.json',self.plan)
        return q.collect(self.root,'plan.json','evidence')

    def assessment(self, change=None):
        evidence = self.collect()
        review = reviewed(evidence)
        if change:
            change(review)
        q.write(self.root/'review.json',review)
        return q.assess(self.root,'evidence/evidence.json','review.json','assessment')

    def record(self, **overrides):
        fields = {'title':'Crate','kind':'image','files':self.plan['files'],'use':self.plan['use'],
                  'environment':self.plan['environment'],'testPlan':'Inspect source evidence',**overrides}
        rid = asset_review.mutate(self.root,{'action':'create','revision':asset_review.load(self.root)[1],
                                           'record':fields})['selectedId']
        asset_review.mutate(self.root,{'action':'start','revision':asset_review.load(self.root)[1],'id':rid})
        return rid

    def test_collection_produces_real_sheet_and_unknown_review(self):
        e=self.collect()
        self.assertEqual(e['checks'][0]['status'],'pass')
        with Image.open(self.root/e['contact_sheet']) as sheet:
            self.assertEqual(sheet.size,(900,330))
        t=q.read(self.root,'evidence/review-template.json');t['reviewer']='test'
        self.assertEqual(q.evaluate(e,t)['status'],'needs_review')

    def test_pass_is_external_only(self):
        report=self.assessment()
        self.assertEqual(report['result']['status'],'pass')
        self.assertFalse(report['result']['engine_verified'])
        self.assertEqual(q.inspect(self.root,'assessment/quality.json')[0],report)

    def test_calibrated_height_drift_fails_despite_high_agent_score(self):
        picture(self.root,'back.png',box=(30,80,170,175),color='blue')
        report=self.assessment()
        self.assertEqual(report['result']['status'],'fail')
        self.assertIn('height',report['result']['failed'])

    def test_explicit_scale_conversion_is_not_independent_image_normalization(self):
        picture(self.root,'back.png',box=(30,100,170,175),color='blue')
        self.plan['views'][1]['calibration']['pixels_per_unit']=100*76/151
        self.assertEqual(self.collect()['checks'][0]['status'],'pass')

    def test_perspective_is_unknown(self):
        self.plan['views'][1]['projection']='perspective'
        self.assertEqual(self.assessment()['result']['status'],'needs_review')

    def test_missing_calibration_is_unknown(self):
        del self.plan['views'][0]['calibration']
        self.assertEqual(self.collect()['checks'][0]['status'],'unknown')

    def test_opaque_images_have_no_invented_mask(self):
        picture(self.root,'back.png',color='blue',opaque=True)
        self.assertEqual(self.collect()['checks'][0]['status'],'unknown')

    def test_explicit_mask_enables_opaque_image_measurement(self):
        picture(self.root,'back.png',color='blue',opaque=True)
        Image.open(self.root/'front.png').getchannel('A').convert('RGB').save(self.root/'mask.png')
        self.plan['views'][1]['segmentation']={'mask':'mask.png'}
        self.assertEqual(self.collect()['checks'][0]['status'],'pass')

    def test_bad_mask_size_rejected(self):
        Image.new('RGB',(20,20),'white').save(self.root/'mask.png')
        self.plan['views'][0]['segmentation']={'mask':'mask.png'}
        with self.assertRaisesRegex(ValueError,'Mask dimensions'):self.collect()

    def test_cropped_silhouette_unknown(self):
        picture(self.root,'back.png',box=(0,25,170,175),color='blue')
        self.assertEqual(self.collect()['checks'][0]['status'],'unknown')

    def test_missing_required_back_view_stays_unknown(self):
        self.plan['views'].pop();self.plan['checks']=[]
        self.assertEqual(self.assessment()['result']['pending'],['missing:result:back'])

    def test_mirror_is_cue_and_needs_explicit_disposition(self):
        ImageOps.mirror(Image.open(self.root/'front.png')).save(self.root/'back.png')
        e=self.collect();self.assertEqual(e['findings'][0]['kind'],'mirror')
        r=reviewed(e);r['findings'][0]['status']='unknown'
        self.assertEqual(q.evaluate(e,r)['status'],'needs_review')
        r['findings'][0]['status']='confirmed'
        self.assertEqual(q.evaluate(e,r)['status'],'fail')
        r['findings'][0]['status']='explained'
        self.assertEqual(q.evaluate(e,r)['status'],'pass')

    def test_duplicate_view_requires_both_images_in_explanation(self):
        shutil.copyfile(self.root/'front.png',self.root/'back.png')
        e=self.collect();self.assertEqual(e['findings'][0]['kind'],'duplicate')
        r=reviewed(e);r['findings'][0]['evidence']=['front']
        with self.assertRaisesRegex(ValueError,'both implicated'):q.evaluate(e,r)

    def test_iou_never_compares_front_against_side(self):
        self.plan['checks'][0].update(metric='silhouette_iou',tolerance=0.9)
        self.assertEqual(self.collect()['checks'][0]['status'],'unknown')

    def test_same_view_iou_measures_shape_difference(self):
        self.plan['views'][1].update(set='reference',direction='front')
        self.plan['required_views']=[]
        self.plan['checks'][0].update(metric='silhouette_iou',tolerance=0.9)
        picture(self.root,'back.png',box=(80,25,170,175),color='blue')
        self.assertEqual(self.collect()['checks'][0]['status'],'fail')

    def test_landmark_occlusion_does_not_become_coordinate_failure(self):
        self.plan['checks'][0].update(metric='landmark_height',landmark='handle',tolerance=0.01)
        for view in self.plan['views']:
            view['landmarks']={'handle':{'x':0.3,'y':0.5,'visibility':'occluded'}}
        self.assertEqual(self.collect()['checks'][0]['status'],'unknown')

    def test_visible_landmark_height_is_measured(self):
        self.plan['checks'][0].update(metric='landmark_height',landmark='handle',tolerance=0.01)
        for i,view in enumerate(self.plan['views']):
            view['landmarks']={'handle':{'x':0.3,'y':0.5+i*0.1,'visibility':'visible'}}
        self.assertEqual(self.collect()['checks'][0]['status'],'fail')

    def test_baseline_compares_common_ground(self):
        self.plan['checks'][0].update(metric='baseline',tolerance=0.01)
        self.plan['views'][1]['calibration']['baseline_y']=190
        self.assertEqual(self.collect()['checks'][0]['status'],'fail')

    def test_no_missing_or_duplicate_criterion_allowed(self):
        e=self.collect();r=reviewed(e)
        for rows in ([],r['criteria']*2):
            with self.subTest(rows=len(rows)),self.assertRaises(ValueError):q.evaluate(e,{**r,'criteria':rows})

    def test_judgment_requires_real_evidence_and_consistent_score(self):
        e=self.collect();original=reviewed(e)
        for changes in ({'evidence':[]},{'evidence':['absent']},{'score':1},{'status':'unknown','score':4},{'status':'na','score':None}):
            r=deepcopy(original);r['criteria'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):q.evaluate(e,r)

    def test_low_confidence_does_not_pass_mandatory_requirement(self):
        e=self.collect();r=reviewed(e);r['criteria'][0]['confidence']='low'
        result=q.evaluate(e,r)
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual(result['dimensions']['structure']['reviewed'],0)
        self.assertIsNone(result['dimensions']['structure']['mean_score'])

    def test_optional_failure_does_not_override_mandatory_pass(self):
        self.plan['criteria'].append({'id':'wear','priority':'preference','dimension':'style','description':'Subtle wear'})
        e=self.collect();r=reviewed(e);r['criteria'][1].update(status='fail',score=1)
        self.assertEqual(q.evaluate(e,r)['status'],'pass')

    def test_localized_region_must_fit_cited_image(self):
        e=self.collect();r=reviewed(e)
        r['criteria'][0]['regions']=[{'evidence':'front','x':0.9,'y':0.1,'width':0.3,'height':0.4}]
        with self.assertRaisesRegex(ValueError,'region'):q.evaluate(e,r)

    def test_corrupt_images_fail_before_output(self):
        (self.root/'back.png').write_bytes(b'not an image')
        with self.assertRaisesRegex(ValueError,'decode'):self.collect()
        self.assertFalse((self.root/'evidence').exists())

    def test_dependencies_all_invalidate_report(self):
        self.assessment()
        for relative in ('front.png','back.png','plan.json','review.json','evidence/contact-sheet.png','evidence/evidence.json'):
            file=self.root/relative;original=file.read_bytes();file.write_bytes(original+b'changed')
            try:
                with self.subTest(relative=relative),self.assertRaises(ValueError):q.inspect(self.root,'assessment/quality.json')
            finally:file.write_bytes(original)

    def test_report_cannot_promote_itself_by_editing_status(self):
        self.assessment(lambda r:r['criteria'][0].update(status='fail',score=1))
        p=self.root/'assessment/quality.json';report=q.read(self.root,'assessment/quality.json')
        report['result']['status']='pass';q.write(p,report)
        with self.assertRaisesRegex(ValueError,'conclusion differs'):q.inspect(self.root,'assessment/quality.json')

    def test_collection_cannot_edit_away_automatic_failure(self):
        picture(self.root,'back.png',box=(30,80,170,175),color='blue')
        evidence=self.collect();review=reviewed(evidence)
        evidence['checks'][0]['status']='pass'
        q.write(self.root/'evidence/evidence.json',evidence);q.write(self.root/'review.json',review)
        with self.assertRaisesRegex(ValueError,'facts changed'):
            q.assess(self.root,'evidence/evidence.json','review.json','assessment')

    def test_model_budget_without_capture_stays_unknown(self):
        self.plan['model_checks']=[{'id':'triangles','metric':'triangles','priority':'must','minimum':1,'maximum':100}]
        self.assertEqual(self.assessment()['result']['status'],'needs_review')

    def test_model_bounds_need_units_and_ordered_range(self):
        for check in ({'id':'size','metric':'size_x','priority':'must','minimum':1,'maximum':2},
                      {'id':'tris','metric':'triangles','priority':'must','minimum':200,'maximum':100}):
            plan=deepcopy(self.plan);plan['model_checks']=[check]
            with self.subTest(check=check),self.assertRaises(ValueError):q.validate_plan(plan)

    def test_output_overwrite_is_refused(self):
        self.assessment()
        with self.assertRaisesRegex(ValueError,'new evidence'):q.collect(self.root,'plan.json','evidence')
        with self.assertRaisesRegex(ValueError,'new assessment'):q.assess(self.root,'evidence/evidence.json','review.json','assessment')

    def test_invalid_numbers_and_ids_are_rejected(self):
        for value in (-1,float('nan'),float('inf')):
            p=deepcopy(self.plan);p['checks'][0]['tolerance']=value
            with self.subTest(value=value),self.assertRaises(ValueError):q.validate_plan(p)
        p=deepcopy(self.plan);p['views'].append(deepcopy(p['views'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):q.validate_plan(p)

    def test_paths_reject_escape_private_metadata_and_ads(self):
        for relative in ('../other','C:/other','/other','.git/config','.env','a:secret','a\\b','a/../b','a/./b','a.','a/\n'):
            with self.subTest(relative=relative),self.assertRaises(ValueError):q.path(self.root,relative)

    def test_publish_is_only_external_and_transitive_reference_change_stales_it(self):
        self.assessment();rid=self.record()
        q.publish(self.root,'assessment/quality.json',rid)
        row=asset_review.snapshot(self.root)['records'][0]
        self.assertEqual(row['checkResults']['external']['status'],'pass')
        self.assertEqual(row['checkResults']['engine']['status'],'not_run')
        self.assertFalse(row['canQualify'])
        picture(self.root,'back.png',color='green')
        self.assertEqual(asset_review.snapshot(self.root)['records'][0]['checkResults']['external']['status'],'stale')

    def test_publish_rejects_other_use_or_source(self):
        self.assessment()
        for fields in ({'use':'Different use'},{'environment':'Different environment'},{'files':['back.png']},{'kind':'model'}):
            rid=self.record(**fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):q.publish(self.root,'assessment/quality.json',rid)

    def test_publish_does_not_override_failed_measurement(self):
        picture(self.root,'back.png',box=(30,80,170,175),color='blue')
        self.assessment();rid=self.record()
        q.publish(self.root,'assessment/quality.json',rid)
        self.assertEqual(asset_review.snapshot(self.root)['records'][0]['checkResults']['external']['status'],'fail')
        picture(self.root,'back.png',color='green')
        self.assertEqual(asset_review.snapshot(self.root)['records'][0]['checkResults']['external']['status'],'stale')

    def test_pinned_version_and_original_working_file_are_independent(self):
        link=asset_versions.mutate(self.root,{'action':'create','title':'Crate','kind':'image','files':['front.png']})
        self.plan['version']={k:link[k] for k in ('group','version')}
        _,v=asset_versions.version(asset_versions.load(self.root),link['group'],link['version'])
        self.plan['files']=[f['path'] for f in v['files']]
        self.plan['views'][0]['path']=self.plan['files'][0]
        self.assessment();rid=self.record();q.publish(self.root,'assessment/quality.json',rid)
        picture(self.root,'front.png',color='green')
        self.assertEqual(q.inspect(self.root,'assessment/quality.json')[0]['result']['status'],'pass')

    def test_prepared_requirements_cannot_be_silently_dropped(self):
        spec={'schema_version':1,'asset_id':self.plan['asset_id'],'kind':'model','brief':'A crate',
              'requirements':[{'id':'shape','text':'Keep a rectangular crate','category':'identity','priority':'must'},
                              {'id':'collision','text':'Block player movement','category':'technical','priority':'must'}], 'references':[]}
        plan={'schema_version':1,'provider':'tripo','parameters':{'type':'text_to_model'},'references':[],
              'routes':[{'requirement':r['id'],'via':'prompt'} for r in spec['requirements']],
              'review':{'reviewer':'fixture','notes':'Routing fixture',**dict.fromkeys(prep.REVIEW_CHECKS,True)}}
        q.write(self.root/'requirements.json',spec);q.write(self.root/'inputs.json',plan)
        with patch.object(model_prompt_policy,'user_path',return_value=self.root/'policy.json'):
            prep.prepare(self.root,'requirements.json','inputs.json','prepared')
        self.plan['preparation']='prepared/preparation.json'
        self.plan['criteria'][0]['requirement']='shape'
        with self.assertRaisesRegex(ValueError,'Every mandatory'):self.collect()
        self.plan['deferred']=[{'requirement':'collision','gate':'engine','reason':'Needs engine collision test'}]
        self.assertEqual(self.assessment()['result']['deferred'][0]['requirement'],'collision')

    def test_cli_exit_codes(self):
        self.assessment()
        command=[sys.executable,'-B','-X','utf8',str(ROOT/'tools/asset_quality.py'),'--project',str(self.root),'check','--report','assessment/quality.json']
        r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        picture(self.root,'back.png',color='green')
        r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,2,r.stdout+r.stderr)


class ModelContainerTests(unittest.TestCase):
    def test_external_uris_and_unknown_extensions_rejected(self):
        root=ROOT/'dist'/('quality-glb-'+uuid4().hex);root.mkdir(parents=True)
        self.addCleanup(lambda:shutil.rmtree(root))
        def save(doc):
            data=json.dumps(doc).encode();data+=b' '*((-len(data))%4)
            file=root/'asset.glb';file.write_bytes(struct.pack('<4sIIII',b'glTF',2,20+len(data),len(data),0x4e4f534a)+data)
            return file
        for doc in ({'images':[{'uri':'https://example.com/texture.png'}]}, {'buffers':[{'uri':'../secret.bin'}]}, {'extensionsUsed':['CUSTOM_loader']}):
            with self.subTest(doc=doc),self.assertRaises(ValueError):self_contained_glb(save(doc))
        self.assertEqual(self_contained_glb(save({'asset':{'version':'2.0'}})),{'asset':{'version':'2.0'}})


if __name__=='__main__':
    unittest.main()

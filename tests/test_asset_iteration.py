"""Outcome-driven revisions must preserve intent, evidence and submission boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from adapters.assets import iteration as it, quality as q, input_preparation as prep, model_prompt_policy
from adapters.assets import generation_approval
from tools.workbench import asset_versions
import asset_workflow
from test_asset_quality import picture, Image
from test_asset_preparation import png


@unittest.skipUnless(Image, 'Pillow is needed for review evidence')
class IterationTests(unittest.TestCase):
    def setUp(self):
        self.root = getattr(self, 'case_root', ROOT/'dist'/('iteration-test-'+uuid4().hex))
        self.root.mkdir(parents=True)
        if not getattr(self, 'preserve_artifacts', False):
            self.addCleanup(lambda: shutil.rmtree(self.root))
        policy = patch.object(model_prompt_policy, 'user_path', return_value=self.root/'isolated-policy.json')
        policy.start(); self.addCleanup(policy.stop)
        self.spec = {'schema_version':1,'asset_id':'crate','kind':'image','brief':'A red rectangular crate.',
            'requirements':[{'id':'shape','text':'Preserve a rectangular silhouette.','category':'identity','priority':'must'},
                            {'id':'color','text':'Keep red surfaces.','category':'appearance','priority':'must'}], 'references':[]}
        self.inputs = {'schema_version':1,'provider':'image','parameters':{},'references':[],
            'routes':[{'requirement':r['id'],'via':'prompt'} for r in self.spec['requirements']],
            'review':self.review_flags()}

    def review_flags(self):
        return {'reviewer':'synthetic iteration test; not a production art approval',
                'notes':'Fixture judgments exercise routing and state transitions.', **dict.fromkeys(prep.REVIEW_CHECKS,True)}

    def baseline(self, provider='image', mode='text_to_model'):
        if provider=='elevenlabs':
            self.spec['kind']='speech';self.spec['brief']='The gate is open.'
            self.inputs['provider']='elevenlabs';self.inputs['parameters']={'kind':'speech','voice_id':'fixture_voice'}
            self.inputs['routes']=[{'requirement':r['id'],'via':'postprocess','reason':'Synthetic audio review fixture',
                                   'check':'Listen and compare the recorded requirement'} for r in self.spec['requirements']]
        if provider=='tripo':
            self.spec['kind']='model';self.inputs['provider']='tripo';self.inputs['parameters']={'type':mode}
            if mode!='text_to_model':
                (self.root/'reference.png').write_bytes(png((200,40,20)))
                self.spec['references']=[{'id':'front','path':'reference.png','role':'shape','view':'front'}]
                self.inputs['references']=[{'id':'front','send':True}]
                self.inputs['routes']=[{'requirement':r['id'],'via':'reference','references':['front'],
                                       'evidence':'Synthetic reference fixture'} for r in self.spec['requirements']]
        q.write(self.root/'requirements.json',self.spec);q.write(self.root/'inputs.json',self.inputs)
        prepared=prep.prepare(self.root,'requirements.json','inputs.json','initial')
        self.assertEqual(prepared['status'],'ready',prepared['errors'])
        return self.quality('base','initial/preparation.json')

    def quality(self, name, preparation, shape='fail', color='pass', version=None, source=None, confidence='high', alter=None):
        filename=name+'.png'
        if source:
            shutil.copyfile(self.root/source,self.root/filename)
        else:
            picture(self.root,filename,color=(110+sum(name.encode())%100,20,20))
        picture(self.root,name+'-back.png',color='blue')
        plan={'schema_version':1,'asset_id':'crate','kind':'audio' if self.spec['kind'] in ('speech','music','sound_effect') else self.spec['kind'],'use':'Warehouse crate reference',
            'environment':'Synthetic source review','files':[filename], 'preparation':preparation,
            'views':[{'id':'front','path':filename,'set':'result','direction':'front','projection':'orthographic','segmentation':{'alpha':True},'calibration':{'group':'pose','pixels_per_unit':100,'baseline_y':176}},
                     {'id':'back','path':name+'-back.png','set':'result','direction':'back','projection':'orthographic','segmentation':{'alpha':True},'calibration':{'group':'pose','pixels_per_unit':100,'baseline_y':176}}],
            'checks':[{'id':'height','metric':'height','priority':'must','a':'front','b':'back','tolerance':0.03}],
            'required_views':[{'set':'result','directions':['front','back']}],
            'criteria':[{'id':r['id'],'dimension':'structure' if r['id']=='shape' else 'style','priority':'must',
                         'description':r['text'],'requirement':r['id']} for r in self.spec['requirements']]}
        if version:
            _,v=asset_versions.version(asset_versions.load(self.root),version['group'],version['version'])
            plan.update(version=version,files=[f['path'] for f in v['files']])
            plan['views'][0]['path']=plan['files'][0]
        if alter:alter(plan)
        q.write(self.root/(name+'-quality-plan.json'),plan)
        e=q.collect(self.root,name+'-quality-plan.json',name+'-evidence')
        review={'schema_version':1,'reviewer':'synthetic test fixture','criteria':[
            {'id':key,'status':state,'score':3 if state=='pass' else 1 if state=='fail' else None,
             'confidence':confidence if key=='shape' else 'high','expected':self.spec['requirements'][i]['text'],
             'observed':'Synthetic '+state+' fixture for '+key,'evidence':list(e['evidence'])}
            for i,(key,state) in enumerate((('shape',shape),('color',color)))], 'findings':[]}
        q.write(self.root/(name+'-review.json'),review)
        q.assess(self.root,name+'-evidence/evidence.json',name+'-review.json',name+'-assessment')
        return name+'-assessment/quality.json'

    def decision(self, report='base-assessment/quality.json', previous=None):
        plan={'schema_version':1,'report':report,'action':'regenerate','policy':deepcopy(it.POLICY),
              'targets':[{'issue':'criterion:shape','recheck':'criterion:shape'}],
              'changes':[{'kind':'prompt','issues':['criterion:shape'],'reason':'Silhouette requirement failed in the source review.',
                          'expected':'Rectangular outline while preserving red surfaces.','value':'Keep all four corners rectangular and the side panels straight.'}],
              'tasks':[],'review':self.review_flags()}
        if previous:plan['previous']=previous
        return plan

    def create(self, plan=None, output='round1'):
        plan = plan or self.decision()
        q.write(self.root/(output+'-plan.json'),plan)
        return it.create(self.root,output+'-plan.json',output)

    def after(self, name='candidate', shape='pass', color='pass', round_name='round1', **kw):
        return self.quality(name,round_name+'/prepared/preparation.json',shape,color,**kw)

    def test_prompt_revision_preserves_brief_requirements_and_model(self):
        self.baseline('tripo');self.create()
        revised=q.read(self.root,'round1/requirements.json')
        self.assertEqual(revised,self.spec)
        request=q.read(self.root,'round1/prepared/request.json')
        self.assertIn('Keep all four corners',request['parameters']['prompt'])
        for requirement in self.spec['requirements']:self.assertIn(requirement['text'],request['parameters']['prompt'])
        self.assertEqual(request['parameters']['model_version'],q.read(self.root,'initial/request.json')['parameters']['model_version'])
        prep.verify_request(self.root,'tripo',request,{'mode':'api'},fresh=True)

    def test_queue_keeps_iteration_without_running_generation(self):
        self.baseline();self.create();request=q.read(self.root,'round1/prepared/request.json')
        job=asset_workflow.new_job(self.root,'image',request,{'mode':'host'})
        self.assertEqual(job['request']['iteration'],request['iteration'])
        self.assertEqual(job['status'],'queued');self.assertEqual(job['attempts'],[])

    def test_unknown_and_low_confidence_need_evidence(self):
        self.baseline()
        for state,confidence in (('unknown','high'),('fail','low')):
            report=self.quality('uncertain-'+state,'initial/preparation.json',state,confidence=confidence)
            with self.subTest(state=state),self.assertRaisesRegex(ValueError,'Unknown or low-confidence'):
                self.create(self.decision(report),'bad-'+state)

    def test_evidence_handoff_has_no_generation_request(self):
        self.baseline();report=self.quality('uncertain','initial/preparation.json','unknown')
        plan=self.decision(report);plan.update(action='collect_evidence',changes=[],tasks=[{'issues':['criterion:shape'],
            'operation':'Capture a close orthographic view of the corners','expected':'Corners can be inspected without occlusion'}])
        record=self.create(plan)
        self.assertEqual(record['status'],'needs_evidence')
        self.assertFalse((self.root/'round1/prepared/request.json').exists())

    def test_postprocess_handoff_is_not_dispatched(self):
        self.baseline();plan=self.decision();plan.update(action='postprocess',changes=[],tasks=[{'issues':['criterion:shape'],
            'operation':'Straighten source panel vertices in Blender','expected':'Rectangular silhouette with original material preserved'}])
        self.assertEqual(self.create(plan)['status'],'needs_processing')
        self.assertFalse(q.read(self.root,'round1/tasks.json')['executed'])

    def test_accept_requires_a_passing_review_and_does_not_select(self):
        self.baseline();plan=self.decision();plan.update(action='accept',targets=[],changes=[])
        with self.assertRaisesRegex(ValueError,'Cannot accept'):self.create(plan,'invalid')
        plan['report']=self.quality('good','initial/preparation.json','pass')
        self.assertEqual(self.create(plan)['status'],'accepted')
        self.assertFalse((self.root/asset_versions.RECORD).exists())

    def test_stop_is_explicit_and_creates_no_request(self):
        self.baseline();plan=self.decision();plan.update(action='stop',targets=[],changes=[])
        self.assertEqual(self.create(plan)['status'],'stopped')

    def test_image_to_model_text_correction_is_rejected(self):
        self.baseline('tripo','image_to_model')
        with self.assertRaisesRegex(ValueError,'cannot receive'):self.create()

    def reference_changes(self):
        (self.root/'new-reference.png').write_bytes(png((130,20,20)))
        plan=self.decision();plan['changes']=[{'kind':'reference','issues':['criterion:shape'],'reason':'Correct the silhouette in the actual image input.',
            'expected':'New shape reference is sent.','value':{'id':'front','path':'new-reference.png','role':'shape','view':'front',
            'send':True,'observed':'Synthetic corrected red reference; not a production visual judgment.'}}]
        for requirement in self.spec['requirements']:
            plan['changes'].append({'kind':'route','issues':['criterion:shape'],'reason':'Reinspect preserved constraints in the replacement image.',
                'expected':'Shape and red color remain represented.','value':{'requirement':requirement['id'],'via':'reference','references':['front'],
                'evidence':'Both requirements were reviewed against the synthetic replacement fixture.'}})
        return plan

    def test_actual_reference_replacement_and_frozen_source(self):
        self.baseline('tripo','image_to_model');self.create(self.reference_changes())
        request=q.read(self.root,'round1/prepared/request.json')
        self.assertEqual(request['inputs'][0]['sha256'],q.digest(self.root/'new-reference.png'))
        (self.root/'new-reference.png').unlink()
        prep.verify_request(self.root,'tripo',request,{'mode':'api'},fresh=True)

    def test_changed_reference_requires_rechecking_affected_routes(self):
        self.baseline('tripo','image_to_model');plan=self.reference_changes();plan['changes'].pop()
        with self.assertRaisesRegex(ValueError,'every requirement route'):self.create(plan)

    def test_noop_parameter_and_nonexistent_target_rejected(self):
        self.baseline('tripo');plan=self.decision()
        request=q.read(self.root,'initial/request.json')
        plan['changes'][0].update(kind='parameter',value={'key':'model_version','value':request['parameters']['model_version']})
        with self.assertRaisesRegex(ValueError,'does not change'):self.create(plan,'noop')
        plan=self.decision();plan['targets'][0]['issue']='criterion:invented'
        with self.assertRaisesRegex(ValueError,'actual failed'):self.create(plan,'invented')

    def test_passing_item_cannot_be_targeted_as_a_defect(self):
        self.baseline();plan=self.decision();plan['targets']=[{'issue':'criterion:color','recheck':'criterion:color'}]
        with self.assertRaisesRegex(ValueError,'actual failed'):self.create(plan)

    def test_no_generation_from_unreviewed_template(self):
        self.baseline();it.draft(self.root,'base-assessment/quality.json','draft')
        with self.assertRaisesRegex(ValueError,'Agent must review'):it.create(self.root,'draft/plan.json','round1')

    def test_target_cannot_substitute_an_easy_recheck(self):
        self.baseline();plan=self.decision();plan['targets'][0]['recheck']='criterion:color'
        with self.assertRaisesRegex(ValueError,'same criterion'):self.create(plan)

    def test_every_target_needs_a_concrete_change(self):
        self.baseline();plan=self.decision();plan['changes']=[]
        with self.assertRaisesRegex(ValueError,'concrete input'):self.create(plan)

    def test_successful_recheck_completes_external_scope_only(self):
        self.baseline();self.create();after=self.after()
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'complete');self.assertFalse(result['engine_verified'])
        self.assertEqual(result['resolved'],['criterion:shape'])
        self.assertEqual(it.inspect_comparison(self.root,'comparison/comparison.json')['result'],result)

    def test_improvement_cannot_hide_color_regression(self):
        self.baseline();self.create();after=self.after(color='fail')
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'regressed');self.assertEqual(result['recommendation'],'change_method')
        self.assertIn('criterion:color',result['regressions'])

    def test_unknown_previously_passed_requirement_is_regression(self):
        self.baseline();self.create();after=self.after(color='unknown')
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'regressed')

    def test_identical_result_bytes_do_not_claim_generation_progress(self):
        self.baseline();self.create();after=self.after(source='base.png')
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'unchanged_output')
        self.assertNotEqual(result['recommendation'],'complete')

    def test_weakened_rubric_or_other_use_rejected(self):
        self.baseline();self.create()
        for name,alter in [('loose',lambda p:p['checks'][0].update(tolerance=0.9)),('other',lambda p:p.update(use='Another use'))]:
            after=self.after(name,alter=alter)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'same asset'):it.compare(self.root,'round1/iteration.json',after,name+'-comparison')

    def test_unrelated_preparation_cannot_claim_iteration_result(self):
        self.baseline();self.create();after=self.quality('unrelated','initial/preparation.json','pass')
        with self.assertRaisesRegex(ValueError,'produced by this iteration'):it.compare(self.root,'round1/iteration.json',after,'comparison')

    def test_missing_previous_comparison_cannot_reset_round(self):
        self.baseline();self.create();after=self.after(shape='fail')
        with self.assertRaisesRegex(ValueError,'previous comparison'):self.create(self.decision(after),'round2')

    def test_two_stalls_stop_regeneration_and_preserve_previous_rounds(self):
        self.baseline();self.create();after=self.after(shape='fail')
        first=it.compare(self.root,'round1/iteration.json',after,'comparison1')
        self.assertEqual(first['result']['stalled_rounds'],1)
        plan=self.decision(after,'comparison1/comparison.json');plan['changes'][0]['value']='Keep the silhouette broad and eliminate rounded corners.'
        self.assertEqual(self.create(plan,'round2')['round'],2)
        after2=self.after('candidate2',shape='fail',round_name='round2')
        second=it.compare(self.root,'round2/iteration.json',after2,'comparison2')
        self.assertEqual(second['result']['recommendation'],'stop')
        plan=self.decision(after2,'comparison2/comparison.json')
        with self.assertRaisesRegex(ValueError,'stopped regeneration'):self.create(plan,'round3')
        self.assertTrue((self.root/'round1/prepared/request.json').is_file())

    def test_round_limit_stops_even_without_stall_limit(self):
        self.baseline();plan=self.decision();plan['policy']={'max_rounds':1,'max_stalled_rounds':1};self.create(plan)
        after=self.after(shape='fail')
        self.assertEqual(it.compare(self.root,'round1/iteration.json',after,'comparison')['result']['recommendation'],'stop')

    def test_policy_and_previous_report_cannot_be_swapped(self):
        self.baseline();self.create();after=self.after(shape='fail');it.compare(self.root,'round1/iteration.json',after,'comparison')
        plan=self.decision(after,'comparison/comparison.json');plan['policy']['max_rounds']=8
        with self.assertRaisesRegex(ValueError,'chain policy'):self.create(plan,'round2')
        plan=self.decision('base-assessment/quality.json','comparison/comparison.json')
        with self.assertRaisesRegex(ValueError,'exact review'):self.create(plan,'wrong')

    def test_stale_base_evidence_blocks_queue_and_comparison(self):
        self.baseline();self.create();request=q.read(self.root,'round1/prepared/request.json')
        (self.root/'base.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):asset_workflow.new_job(self.root,'image',request,{'mode':'host'})
        self.assertFalse(list(self.root.glob('.openaigame/asset-jobs/*/job.json')))

    def test_preparation_and_request_tampering_rejected(self):
        self.baseline();self.create();request=q.read(self.root,'round1/prepared/request.json')
        bad=deepcopy(request);bad['parameters']['prompt']+=' invent a different creature'
        with self.assertRaises(ValueError):prep.verify_request(self.root,'image',bad,{'mode':'host'})
        bad=deepcopy(request);bad.pop('preparation')
        with self.assertRaises(ValueError):prep.verify_request(self.root,'image',bad,{'mode':'host'})
        (self.root/'round1/requirements.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):it.inspect(self.root,'round1/iteration.json')

    def test_no_overwrite(self):
        self.baseline();self.create()
        with self.assertRaisesRegex(ValueError,'new iteration'):it.create(self.root,'round1-plan.json','round1')

    def test_prepared_lineage_does_not_implicitly_send_parent_image(self):
        self.baseline()
        link=asset_versions.mutate(self.root,{'action':'create','title':'crate','kind':'image','files':['base.png']})
        pin={k:link[k] for k in ('group','version')}
        report=self.quality('pinned','initial/preparation.json',version=pin)
        self.create(self.decision(report))
        request=q.read(self.root,'round1/prepared/request.json')
        self.assertEqual(request['inputs'],[])
        job=asset_workflow.new_job(self.root,'image',request,{'mode':'host'})
        self.assertEqual(job['request']['inputs'],[])
        self.assertEqual(job['request']['lineage']['parent'],pin['version'])

    def test_approval_identity_includes_iteration(self):
        self.baseline('tripo');self.create();request=q.read(self.root,'round1/prepared/request.json')
        with patch.object(generation_approval.api_common,'credential',return_value='synthetic-key'):
            fingerprint=generation_approval.identity(self.root,'fixture-job','tripo',{'mode':'api'},request)
            modified=deepcopy(request);modified.pop('iteration')
            with self.assertRaises(ValueError):generation_approval.identity(self.root,'fixture-job','tripo',{'mode':'api'},modified)
            with patch.object(prep,'verify_request'):
                other=generation_approval.identity(self.root,'fixture-job','tripo',{'mode':'api'},modified)
            self.assertNotEqual(fingerprint,other)

    def test_cli_check_and_stale_exit(self):
        self.baseline();self.create()
        cmd=[sys.executable,'-B','-X','utf8',str(ROOT/'tools/asset_iterate.py'),'--project',str(self.root),'check','--iteration','round1/iteration.json']
        run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8');self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        (self.root/'base.png').write_bytes(b'changed')
        run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8');self.assertEqual(run.returncode,2,run.stdout+run.stderr)

    def test_speech_correction_does_not_rewrite_spoken_words(self):
        self.baseline('elevenlabs')
        with self.assertRaisesRegex(ValueError,'Speech uses the exact brief'):self.create(self.decision(),'bad-speech')
        plan=self.decision();plan['changes'][0].update(kind='parameter',value={'key':'voice_id','value':'another_fixture_voice'})
        self.create(plan)
        self.assertEqual(q.read(self.root,'round1/prepared/request.json')['parameters']['text'],'The gate is open.')

    def test_routing_note_without_payload_change_cannot_regenerate(self):
        self.baseline('tripo','image_to_model');plan=self.decision()
        route=deepcopy(self.inputs['routes'][0]);route['evidence']='A new observation, with identical image input'
        plan['changes'][0].update(kind='route',value=route)
        with self.assertRaisesRegex(ValueError,'Provider input is unchanged'):self.create(plan)

    def test_explicit_default_with_identical_wire_payload_is_not_a_correction(self):
        self.spec['kind']='music';self.inputs.update(provider='elevenlabs',parameters={'kind':'music','music_length_ms':3000})
        self.baseline()
        plan=self.decision();plan['changes'][0].update(kind='parameter',value={'key':'force_instrumental','value':True})
        with self.assertRaisesRegex(ValueError,'Provider input is unchanged'):self.create(plan)

    def test_registered_result_keeps_parent_and_iteration_provenance(self):
        self.baseline();base=asset_versions.mutate(self.root,{'action':'create','kind':'image','title':'Crate','files':['base.png']})
        pin={k:base[k] for k in ('group','version')};report=self.quality('pinned','initial/preparation.json',version=pin)
        self.create(self.decision(report));request=q.read(self.root,'round1/prepared/request.json')
        job=asset_workflow.new_job(self.root,'image',request,{'mode':'host'})
        picture(self.root,'external.png',color='red')
        job.update(status='registered',execution_source='synthetic local fixture; no generation')
        job['artifacts']=asset_workflow.artifacts(self.root,self.root,{'artifacts':[{'path':'external.png'}]},job)
        added=asset_versions.complete_job(self.root,job)
        child={k:added[k] for k in ('group','version')}
        _,version=asset_versions.version(asset_versions.load(self.root),child['group'],child['version'])
        self.assertEqual(version['parent'],pin['version']);self.assertEqual(version['provenance']['iteration'],request['iteration'])
        after=self.after(version=child)
        self.assertEqual(it.compare(self.root,'round1/iteration.json',after,'comparison')['result']['status'],'complete')
        self.assertIsNone(asset_versions.load(self.root)['groups'][pin['group']]['selected'])

    def test_missing_view_can_be_added_without_changing_rubric(self):
        self.baseline()
        def missing(plan):
            plan['views'].pop();plan['checks']=[]
        before=self.quality('missing','initial/preparation.json','unknown',alter=missing)
        plan=self.decision(before);plan.update(action='collect_evidence',changes=[],
            targets=[{'issue':'finding:missing:result:back','recheck':'criterion:shape'}],
            tasks=[{'issues':['finding:missing:result:back'],'operation':'Capture the missing rear view','expected':'Rear silhouette can be assessed'}])
        self.create(plan)
        after=self.quality('added','initial/preparation.json','pass',alter=lambda p:p.update(checks=[]))
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'complete')

    def test_numerical_improvement_counts_before_threshold_pass(self):
        self.baseline()
        def bad(plan):
            picture(self.root,plan['views'][1]['path'],box=(30,90,170,175),color='blue')
        before=self.quality('short','initial/preparation.json','pass',alter=bad)
        plan=self.decision(before);plan['targets']=[{'issue':'check:height','recheck':'check:height'}]
        plan['changes'][0].update(issues=['check:height'],value='Match the full object height across orthographic views.')
        self.create(plan)
        def closer(plan):
            picture(self.root,plan['views'][1]['path'],box=(30,55,170,175),color='blue')
        after=self.after(alter=closer)
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertEqual(result['status'],'improved');self.assertEqual(result['measured_improvements'],['check:height'])
        self.assertEqual(result['unresolved'],['check:height']);self.assertEqual(result['stalled_rounds'],0)

    def test_multiview_cue_disappearance_needs_semantic_reinspection(self):
        self.baseline()
        def duplicate(plan):
            shutil.copyfile(self.root/plan['views'][0]['path'],self.root/plan['views'][1]['path'])
        # Build a real duplicate finding, then explicitly confirm it in the fixture review.
        name='duplicate';filename=name+'.png';picture(self.root,filename)
        source=q.read(self.root,'base-quality-plan.json');source['files']=[filename]
        source['views'][0]['path']=filename;source['views'][1]['path']='duplicate-back.png'
        duplicate(source);q.write(self.root/'duplicate-plan.json',source)
        e=q.collect(self.root,'duplicate-plan.json','duplicate-evidence')
        review=q.read(self.root,'base-review.json');finding=e['findings'][0]
        review['findings']=[{'id':finding['id'],'status':'confirmed','reason':'Deliberately duplicated fixture views','evidence':['front','back']}]
        q.write(self.root/'duplicate-review.json',review);q.assess(self.root,'duplicate-evidence/evidence.json','duplicate-review.json','duplicate-assessment')
        issue='finding:'+finding['id'];plan=self.decision('duplicate-assessment/quality.json')
        plan['targets']=[{'issue':issue,'recheck':'criterion:shape'}];plan['changes'][0].update(issues=[issue])
        self.create(plan);after=self.after(shape='fail')
        result=it.compare(self.root,'round1/iteration.json',after,'comparison')['result']
        self.assertIn(issue,result['unresolved']);self.assertNotEqual(result['status'],'complete')

    def test_evidence_round_can_confirm_defect_then_resume_same_chain(self):
        self.baseline();plan=self.decision();plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        self.create(plan);after=self.after(shape='unknown')
        it.compare(self.root,'round1/iteration.json',after,'comparison1')
        plan=self.decision(after,'comparison1/comparison.json');plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        plan.update(action='collect_evidence',changes=[],tasks=[{'issues':['criterion:shape'],
            'operation':'Inspect obscured corners','expected':'Confirm whether corners are rectangular'}])
        self.create(plan,'round2')
        confirmed=self.quality('confirmed','round1/prepared/preparation.json','fail')
        result=it.compare(self.root,'round2/iteration.json',confirmed,'comparison2')['result']
        self.assertEqual(result['new_failures'],[]);self.assertEqual(result['recommendation'],'continue')
        plan=self.decision(confirmed,'comparison2/comparison.json');plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        plan['changes'][0]['value']='Correct the newly visible sloped corner without changing the red panels.'
        record=self.create(plan,'round3')
        self.assertEqual(record['round'],3)
        self.assertEqual(record['policy'],plan['policy'])
        after=self.after('final',round_name='round3')
        self.assertEqual(it.compare(self.root,'round3/iteration.json',after,'comparison3')['result']['status'],'complete')

    def test_processing_round_can_keep_preparation_and_resume_chain(self):
        self.baseline();plan=self.decision();plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        self.create(plan);after=self.after(shape='fail')
        it.compare(self.root,'round1/iteration.json',after,'comparison1')
        plan=self.decision(after,'comparison1/comparison.json');plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        plan.update(action='postprocess',changes=[],tasks=[{'issues':['criterion:shape'],
            'operation':'Straighten corners locally','expected':'Rectangular silhouette'}])
        self.create(plan,'round2')
        processed=self.quality('processed','round1/prepared/preparation.json','fail')
        it.compare(self.root,'round2/iteration.json',processed,'comparison2')
        plan=self.decision(processed,'comparison2/comparison.json');plan['policy']={'max_rounds':4,'max_stalled_rounds':4}
        plan['changes'][0]['value']='Regenerate the unresolved corner using a straight rectangular edge.'
        self.assertEqual(self.create(plan,'round3')['round'],3)

    def test_comparison_edit_cannot_reset_stall_count(self):
        self.baseline();self.create();after=self.after(shape='fail')
        it.compare(self.root,'round1/iteration.json',after,'comparison')
        report=q.read(self.root,'comparison/comparison.json');report['result']['stalled_rounds']=0
        q.write(self.root/'comparison/comparison.json',report)
        with self.assertRaisesRegex(ValueError,'no longer matches'):it.inspect_comparison(self.root,'comparison/comparison.json')


if __name__=='__main__':unittest.main()

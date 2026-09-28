"""Interval scope, stale conclusions, preserved work and evidence provenance."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import task_state as tasks
import record_evidence as evidence
from record_io import read_json, write_json
from validate_records import check_record


class StageTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root/'design.md').write_text('Actual design artifact',encoding='utf-8')
        (self.root/'run.log').write_text('A fixture command ran',encoding='utf-8')

    def spec(self,start=3,end=3,**kwargs):
        return {'id':'T001','goal':'Validate the requested scope','start_stage':start,'end_stage':end,
                'objects':[{'id':'hero','title':'Hero'}],'deliverables':['Integrated sample and findings'],**kwargs}

    def create(self,**kwargs):
        return tasks.create(self.root,self.spec(**kwargs))

    def operation(self,**op):
        before = tasks.read(self.root,'T001')
        return tasks.update(self.root,'T001',before['revision'],op)

    def proof(self,record_id='E001',objects=None,files=None,dependencies=None,source_type='command'):
        path = evidence.register(self.root,{'id':record_id,'source_type':source_type,
                    'description':'Controlled test fixture observation','observer':'unit-test',
                    'result':'observed','objects':objects or ['hero'],
                    'files':files or ['run.log'],'dependencies':dependencies or []})
        return path.relative_to(self.root).as_posix()

    def ready(self,stage=3):
        return self.operation(action='readiness',stage=stage,status='ready',reason='Existing baseline inspected',evidence=[])

    def complete_reviews(self,stage=3,reference=None,outcome='supported'):
        ref = reference or self.proof()
        for check in next(s for s in tasks.read(self.root,'T001')['stages'] if s['number']==stage)['requirements']:
            self.operation(action='review',stage=stage,check=check['id'],result='passed',
                           reason='Actual fixture evidence reviewed',observer='tester',evidence=[ref],outcome=outcome)
        return ref

    def test_every_interval_is_representable_without_inventing_prior_passes(self):
        seen = 0
        for start in range(1,6):
            for end in range(start,6):
                value = tasks.create(self.root,self.spec(start,end,id=f'T{start}{end}'))
                view = tasks.status(self.root,value)
                self.assertEqual([s['number'] for s in view['stages']],list(range(start,end+1)))
                self.assertEqual(view['outside_scope'],[n for n in range(1,6) if not start<=n<=end])
                self.assertFalse(view['can_close'])
                seen += 1
        self.assertEqual(seen,15)
        self.assertFalse((self.root/'game').exists())

    def test_invalid_interval_and_duplicate_create_preserve_source(self):
        for a,b in [(0,2),(3,2),(1,6),(True,2),(1,3.0)]:
            with self.assertRaises(ValueError): tasks.create(self.root,self.spec(a,b))
        self.create()
        before = tasks.path_for(self.root,'T001').read_bytes()
        with self.assertRaises(FileExistsError): self.create()
        self.assertEqual(tasks.path_for(self.root,'T001').read_bytes(),before)

    def test_numerical_owner_can_plan_in_any_stage_without_changing_scope(self):
        self.assertEqual(tasks.PROFESSIONS, {p.parent.name for p in (ROOT/'skills').glob('*/SKILL.md')})
        for stage in range(1, 6):
            task = tasks.create(self.root, self.spec(stage, stage, id=f'N{stage}'))
            steps = [{'id':'model','stage':stage,'owner':'game-numerical-design','objects':['hero'],
                      'description':'Compare model and actual inputs','depends_on':[]}]
            tasks.update(self.root, task['id'], task['revision'], {'action':'plan','steps':steps})
            saved = tasks.read(self.root, task['id'])
            self.assertEqual(saved['steps'][0]['owner'], 'game-numerical-design')
            self.assertEqual([s['number'] for s in saved['stages']], [stage])
            self.assertEqual(check_record('task', saved, self.root, tasks.path_for(self.root,task['id'])), [])
            before = tasks.path_for(self.root,task['id']).read_bytes()
            steps[0]['owner'] = 'unknown-profession'
            with self.assertRaises(ValueError):
                tasks.update(self.root, task['id'], saved['revision'], {'action':'plan','steps':steps})
            self.assertEqual(tasks.path_for(self.root,task['id']).read_bytes(), before)
        self.assertFalse((self.root/'game').exists())

    def test_single_stage_closes_without_appending_content_production(self):
        self.create()
        self.ready()
        self.complete_reviews()
        self.operation(action='close',reason='Requested stage complete')
        value = tasks.read(self.root,'T001')
        self.assertEqual(value['state'],'complete')
        self.assertEqual([s['number'] for s in value['stages']],[3])
        self.assertEqual(check_record('task',value,self.root,tasks.path_for(self.root,'T001')),[])

    def test_documents_cannot_certify_engine_execution(self):
        self.create()
        self.ready()
        ref = self.proof(source_type='manual',files=['design.md'])
        self.complete_reviews(reference=ref)
        with self.assertRaises(ValueError): self.operation(action='close',reason='Only documents exist')
        self.assertTrue(any('execution' in p for p in tasks.status(self.root,'T001')['stages'][0]['problems']))

    def test_planning_only_task_does_not_require_engine_evidence(self):
        self.create(start=1,end=1)
        self.ready(1)
        self.complete_reviews(1,self.proof(source_type='manual',files=['design.md']))
        self.operation(action='close',reason='Design delivery complete')
        self.assertFalse((self.root/'game').exists())

    def test_changed_dependency_reopens_current_claim_and_keeps_history(self):
        self.create()
        self.ready()
        ref = self.proof(dependencies=['design.md'])
        self.complete_reviews(reference=ref)
        self.operation(action='close',reason='Complete at this version')
        before = tasks.path_for(self.root,'T001').read_bytes()
        (self.root/'design.md').write_text('Changed binding',encoding='utf-8')
        view = tasks.status(self.root,'T001')
        self.assertEqual(view['effective_state'],'needs_revalidation')
        self.assertFalse(view['can_close'])
        self.assertEqual(tasks.path_for(self.root,'T001').read_bytes(),before)
        self.assertEqual(evidence.assess(self.root,ref)['status'],'stale')
        self.assertTrue(list((self.root/'production/tasks/.history/T001').glob('*.json')))

    def test_task_updates_do_not_invalidate_execution_evidence(self):
        self.create()
        ref = evidence.register(self.root,{'id':'E','source_type':'command','description':'Fixture',
                    'observer':'tester','result':'observed','objects':['hero'],'files':['run.log'],
                    'task':'production/tasks/T001.json'}).relative_to(self.root).as_posix()
        self.ready()
        self.assertEqual(evidence.assess(self.root,ref)['status'],'current')

    def test_revision_conflict_and_dependency_cycle_make_no_write(self):
        self.create()
        self.ready()
        with self.assertRaises(ValueError): tasks.update(self.root,'T001',1,{'action':'pause','reason':'old view'})
        step = {'id':'s','stage':3,'owner':'game-technical-design','objects':['hero'],
                'description':'Build','depends_on':['s']}
        before = tasks.path_for(self.root,'T001').read_bytes()
        with self.assertRaises(ValueError): self.operation(action='plan',steps=[step])
        self.assertEqual(tasks.path_for(self.root,'T001').read_bytes(),before)

    def test_one_character_evidence_cannot_cover_two_characters(self):
        self.create(objects=[{'id':'hero','title':'Hero'},{'id':'boss','title':'Boss'}])
        self.ready()
        self.complete_reviews()
        self.assertFalse(tasks.status(self.root,'T001')['can_close'])

    def test_negative_evaluation_is_not_continuation_or_quality_delivery(self):
        self.create(objective='evaluate')
        self.ready()
        self.complete_reviews(outcome='rejected')
        view = tasks.status(self.root,'T001')
        self.assertTrue(view['can_close'])
        self.assertFalse(view['stages'][0]['can_advance'])
        altered = tasks.read(self.root,'T001')
        altered['objective']='deliver'
        self.assertFalse(tasks.status(self.root,altered)['can_close'])

    def test_scoped_issue_invalidates_affected_review_without_rewriting_other_evidence(self):
        self.create(start=2,end=3)
        self.ready(2)
        ref = self.complete_reviews(2)
        self.ready(3)
        self.complete_reviews(3,ref)
        self.operation(action='issue',id='grip',objects=['hero'],stages=[3],state='open',
                       reason='Binding defect observed',evidence=[ref])
        view = tasks.status(self.root,'T001')
        self.assertTrue(view['stages'][0]['complete'])
        self.assertFalse(view['stages'][1]['complete'])

    def test_evidence_is_immutable_and_local(self):
        ref = self.proof()
        before = (self.root/ref).read_bytes()
        with self.assertRaises(FileExistsError): self.proof()
        with self.assertRaises(ValueError): self.proof(record_id='escape',files=['../outside.log'])
        self.assertEqual((self.root/ref).read_bytes(),before)

    def test_legacy_migration_preserves_markdown_and_invents_no_passes(self):
        path=self.root/'production/tasks/T001.md';path.parent.mkdir(parents=True)
        original='# Old task\nStatus: done (historical prose, not current evidence)\n'
        path.write_text(original,encoding='utf-8')
        result=tasks.migrate(self.root,self.spec(2,4))
        self.assertEqual(path.read_text('utf-8'),original)
        self.assertIn('production/tasks/T001.md',result['inputs'])
        self.assertFalse(tasks.status(self.root,'T001')['can_close'])
        self.assertTrue(all(not s['reviews'] for s in result['stages']))

    def test_scope_amendment_preserves_history_and_resets_only_declared_stages(self):
        self.create(start=2,end=3);self.ready(2);ref=self.complete_reviews(2)
        self.ready(3);self.complete_reviews(3,ref)
        before=tasks.read(self.root,'T001')
        result=self.operation(action='amend',reason='User requests new art scope',authorization='Conversation decision',
            changes={'end_stage':4,'constraints':['new style']},affected_stages=[3,4])
        self.assertEqual(result['stages'][0]['reviews'],before['stages'][0]['reviews'])
        self.assertFalse(result['stages'][1]['reviews'])
        self.assertEqual(result['end_stage'],4)
        historical=read_json(self.root/f"production/tasks/.history/T001/{before['revision']}.json")
        self.assertEqual(historical,before)

    def test_recovery_does_not_replay_work_or_erase_unknown_side_effects(self):
        self.create();self.ready()
        self.operation(action='plan',steps=[{'id':'import','stage':3,'objects':['hero'],'owner':'game-technical-art',
            'description':'Import a model','side_effects':'local'}])
        self.operation(action='step',id='import',state='working',reason='Importer started')
        before=tasks.read(self.root,'T001')
        status=tasks.recovery(self.root,'T001')
        self.assertTrue(status['steps'][0]['retry_requires_reconciliation'])
        with self.assertRaisesRegex(ValueError,'side effects'):
            self.operation(action='step',id='import',state='pending',reason='retry')
        self.assertEqual(tasks.read(self.root,'T001'),before)
        ref=self.proof()
        self.operation(action='step',id='import',state='pending',reason='Checked importer and output; no outstanding process',evidence=[ref])

    def test_task_wide_goal_change_requires_all_retained_stages_to_be_reviewed(self):
        self.create(start=2,end=3)
        with self.assertRaisesRegex(ValueError,'every retained stage'):
            self.operation(action='amend',reason='Change experience target',authorization='User decision',
                changes={'goal':'Different experience'},affected_stages=[3])


if __name__ == '__main__':
    unittest.main()

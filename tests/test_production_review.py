"""Board/CLI consistency, optimistic updates and evidence media boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_project_workbench as base
from test_observation import capture
import observation
import task_state


class RuntimeIdentityTests(unittest.TestCase):
    def test_content_change_is_detected_without_reading_local_release_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'tools/workbench').mkdir(parents=True)
            entry=root/'tools/workbench/production_review.py'
            entry.write_text('# original code',encoding='utf-8')
            with patch.object(base.wb.production_review,'__file__',str(entry)):
                initial=base.wb.production_review.diagnostics()
                (root/'VERSION').write_text('local-only',encoding='utf-8')
                (root/'RELEASE_NOTES.md').write_text('private notes',encoding='utf-8')
                self.assertEqual(initial,base.wb.production_review.diagnostics())
                entry.write_text('# updated code',encoding='utf-8')
                changed=base.wb.production_review.diagnostics()
                self.assertNotEqual(initial['version'],changed['version'])
                self.assertNotEqual(initial['files'],changed['files'])
                # Existing manifests stay readable, without exposing internal labels.
                (root/'bundle-manifest.json').write_text(json.dumps(
                    {'bundle_id':'a'*64,'toolkit_version':'local-only'}),encoding='utf-8')
                installed=base.wb.production_review.diagnostics()
                self.assertEqual(installed['distribution'],'installed-bundle')
                self.assertEqual(installed['bundle_id'],'a'*64)
                self.assertNotIn('local-only',json.dumps(installed))


class ProductionReviewTests(unittest.TestCase):
    setUp=base.WorkbenchTests.setUp
    request=base.WorkbenchTests.request
    login=base.WorkbenchTests.login

    def test_board_task_write_is_cli_state_and_stale_write_does_not_replace(self):
        spec={'id':'T1','goal':'Validate a small scene','start_stage':3,'end_stage':3,
              'objects':[{'id':'hero','title':'Hero'}],'deliverables':['Observed representative scene']}
        code,_,data=self.request('/api/production-task',{'action':'create','spec':spec})
        self.assertEqual(code,200,data)
        self.assertEqual(task_state.read(self.root,'T1')['revision'],1)
        payload={'action':'update','id':'T1','revision':1,'operation':{'action':'readiness','stage':3,
            'status':'ready','reason':'Existing scene inspected','evidence':[]}}
        self.assertEqual(self.request('/api/production-task',payload)[0],200)
        self.assertEqual(self.request('/api/production-task',payload)[0],409)
        self.assertEqual(task_state.read(self.root,'T1')['revision'],2)
        self.assertFalse(self.request('/api/production-task?id=T1')[2]['status']['can_close'])
        self.assertEqual(self.request('/api/production-task',payload,headers={'X-CSRF-Token':'bad'})[0],403)

    def register(self):
        data=capture();data['media']=[{'path':'evidence.png','kind':'image','clock':'game','anchors':[[.1,0]],
            'description':'test image','audio_coverage':'not_included'}]
        (self.root/'evidence.png').write_bytes(b'fixture bytes')
        (self.root/'capture.json').write_text(json.dumps(data),encoding='utf-8')
        observation.register(self.root,'capture.json','O1')

    def test_board_exposes_numerical_owner_and_persists_plan_to_cli(self):
        code, _, snapshot = self.request('/api/production')
        self.assertEqual(code, 200)
        self.assertIn('game-numerical-design', snapshot['professions'])
        spec={'id':'N1','goal':'Compare growth costs','start_stage':1,'end_stage':1,
              'objects':[{'id':'growth','title':'Growth'}],'deliverables':['Model comparison']}
        self.assertEqual(self.request('/api/production-task',{'action':'create','spec':spec})[0],200)
        steps=[{'id':'model','stage':1,'owner':'game-numerical-design','objects':['growth'],
                'description':'Compute cumulative costs','depends_on':[]}]
        payload={'action':'update','id':'N1','revision':1,'operation':{'action':'plan','steps':steps}}
        self.assertEqual(self.request('/api/production-task',payload)[0],200)
        self.assertEqual(task_state.read(self.root,'N1')['steps'][0]['owner'],'game-numerical-design')
        self.assertEqual(self.request('/api/production-task?id=N1')[0],200)

    def test_time_position_notes_and_changed_media_keep_version_identity(self):
        self.register()
        note={'id':'N1','observation':'O1','object':'hero','author':'reviewer','text':'late cleanup',
              'anchor':{'kind':'time','clock':'game','time':.25}}
        self.assertEqual(self.request('/api/review-note',note)[0],200)
        self.assertEqual(self.request('/api/observation?id=O1')[2]['notes'][0]['status'],'current')
        self.assertEqual(self.request('/api/observation-media?id=O1&index=0')[0],200)
        (self.root/'evidence.png').write_bytes(b'changed')
        view=self.request('/api/observation?id=O1')[2]
        self.assertEqual(view['status'],'stale');self.assertEqual(view['notes'][0]['status'],'stale')
        self.assertEqual(self.request('/api/observation-media?id=O1&index=0')[0],404)
        self.assertEqual(self.request('/api/observation-media?id=O1&index=-1')[0],404)
        note.update(id='N2',anchor={'kind':'position','position':[1,2,3]})
        self.assertEqual(self.request('/api/review-note',note)[0],409)

    def test_readonly_snapshot_does_not_create_project_records(self):
        self.assertEqual(self.request('/api/production')[0],200)
        self.assertFalse((self.root/'production').exists())
        runtime=self.request('/api/runtime')[2]
        self.assertRegex(runtime['started']['version'],r'^[0-9a-f]{12}$')
        self.assertEqual(runtime['started']['files'],runtime['current']['files'])
        self.assertFalse(runtime['restart_required'])

    def test_note_links_to_actual_scoped_issue_and_retains_evidence(self):
        self.register()
        task_state.create(self.root,{'id':'T1','goal':'Check cleanup','start_stage':3,'end_stage':4,'objects':[{'id':'hero','title':'Hero'}],'deliverables':['Fixed cleanup']})
        note={'id':'N1','observation':'O1','object':'hero','author':'reviewer','text':'late cleanup','anchor':{'kind':'time','clock':'game','time':.25}}
        self.assertEqual(self.request('/api/review-note',note)[0],200)
        payload={'note':'N1','task':'T1','revision':1,'issue':'FX1','stages':[3]}
        code,_,result=self.request('/api/review-note-link',payload)
        self.assertEqual(code,200,result)
        issue=task_state.read(self.root,'T1')['issues'][0]
        self.assertEqual(issue['stages'],[3]);self.assertEqual(issue['state'],'open')
        self.assertEqual(issue['evidence'],[result['evidence']])
        self.assertEqual(self.request('/api/review-note-link',payload)[0],409)


if __name__=='__main__':unittest.main()

"""Board/CLI consistency, optimistic updates and evidence media boundaries."""
import json
import unittest
import test_project_workbench as base
from test_observation import capture
import observation
import task_state


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
        self.assertEqual(runtime['started']['version'],(base.ROOT/'VERSION').read_text().strip())
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

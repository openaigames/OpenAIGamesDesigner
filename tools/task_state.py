"""Versioned stage-interval tasks over the existing project files.

This module records professional decisions; it never makes them or executes a plan.
All writes use optimistic revision checks and keep the previous revision.
"""
from copy import deepcopy
from pathlib import Path
import json
from record_io import identifier, local, now, read_json, write_json, project_lock, changed_files, snapshot_files
import record_evidence

CATALOG = Path(__file__).resolve().parents[1] / 'workflows/stages.json'
PROFESSIONS = {'game-preproduction', 'game-concept', 'game-design', 'game-combat-design',
               'game-level-design', 'game-art-direction', 'game-character-art', 'game-environment-art',
               'game-animation-pipeline', 'game-vfx-design', 'game-audio-design', 'game-ui-ux',
               'game-technical-art', 'game-technical-design', 'game-prototype-validation'}


def stages():
    data = read_json(CATALOG)
    if data.get('schema_version') != 1 or [s['number'] for s in data['stages']] != list(range(1, 6)):
        raise ValueError('Unsupported stage catalog.')
    return data['stages']


def interval(start, end):
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= 5:
        raise ValueError('Stage interval must satisfy 1 <= start <= end <= 5.')
    return list(range(start, end + 1))


def path_for(root, task_id):
    return local(root, 'production/tasks/' + identifier(task_id) + '.json')


def check_fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError('Unexpected fields in ' + label)


def validate(value):
    from validate_records import contract
    errors = contract('task', value)
    if errors:
        raise ValueError('; '.join(errors))
    identifier(value['id'])
    numbers = interval(value['start_stage'], value['end_stage'])
    if [s['number'] for s in value['stages']] != numbers:
        raise ValueError('Stage state must cover exactly the selected contiguous interval.')
    object_ids = [identifier(o['id']) for o in value['objects']]
    if len(set(object_ids)) != len(object_ids):
        raise ValueError('Duplicate object ID.')
    for stage in value['stages']:
        required = next(s['checks'] for s in stages() if s['number'] == stage['number'])
        checks = [identifier(c['id']) for c in stage['requirements']]
        if not checks or len(set(checks)) != len(checks):
            raise ValueError('Stage requirements must be nonempty and unique.')
        if set(stage['reviews']) - set(checks):
            raise ValueError('Review names an unknown requirement.')
        actual_dimensions = {c['id']:c['dimension'] for c in stage['requirements']}
        if any(actual_dimensions.get(c['id']) != c['dimension'] for c in required):
            raise ValueError('Core stage checks cannot be removed or reclassified.')
    known = {}
    for step in value['steps']:
        key = identifier(step['id'])
        if key in known or step['stage'] not in numbers:
            raise ValueError('Duplicate step or step outside the stage interval.')
        if step['owner'] not in PROFESSIONS or not set(step['objects']) <= set(object_ids):
            raise ValueError('Unknown profession or object in plan.')
        known[key] = step
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('Plan dependency cycle.')
        if key in visited:
            return
        visiting.add(key)
        for dependency in known[key]['depends_on']:
            if dependency not in known or known[dependency]['stage'] > known[key]['stage']:
                raise ValueError('Unknown or later-stage dependency.')
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
    for key in known:
        visit(key)
    return value


def read(root, task_id):
    return validate(read_json(path_for(root, task_id)))


def create(root, spec):
    check_fields(spec, {'id','goal','start_stage','end_stage','objects','deliverables','inputs',
                       'constraints','authorization','objective','user_decision_stages'}, 'task specification')
    numbers = interval(spec.get('start_stage'), spec.get('end_stage'))
    task_id = identifier(spec.get('id'))
    decisions = spec.get('user_decision_stages', [])
    if not isinstance(decisions, list) or any(type(n) is not int or n not in numbers for n in decisions):
        raise ValueError('User decisions must refer to stages in this task.')
    states = []
    for item in stages():
        if item['number'] in numbers:
            requirements = deepcopy(item['checks'])
            if item['number'] in decisions:
                requirements.append({'id':'user-decision', 'dimension':'user',
                                     'description':'已有或本轮明确的用户决定及其依据'})
            states.append({'number':item['number'], 'readiness':'pending', 'readiness_reason':'',
                           'prerequisites':[], 'requirements':requirements, 'reviews':{},
                           'outcome':'pending'})
    value = {'schema_version':1, 'id':task_id, 'revision':1, 'created_at':now(), 'updated_at':now(),
             'goal':spec.get('goal'), 'start_stage':spec['start_stage'], 'end_stage':spec['end_stage'],
             'objects':spec.get('objects'), 'deliverables':spec.get('deliverables'),
             'constraints':spec.get('constraints', []), 'authorization':spec.get('authorization', []),
             'objective':spec.get('objective', 'deliver'), 'inputs':snapshot_files(root, spec.get('inputs', [])),
             'stages':states, 'steps':[], 'issues':[], 'state':'active', 'history':[]}
    validate(value)
    with project_lock(root):
        write_json(path_for(root, task_id), value, create=True)
    return value


def evidence_status(root, references, objects):
    errors = []
    records = []
    for ref in references:
        try:
            record = record_evidence.assess(root, ref)
            records.append(record)
            if record['status'] != 'current' or record['result'] == 'not_run':
                errors.append(ref + ': stale or not executed')
            if not set(record['objects']) & set(objects):
                errors.append(ref + ': evidence does not cover a task object')
        except (ValueError, OSError, KeyError, TypeError) as error:
            errors.append(ref + ': ' + str(error))
    return records, errors


def status(root, task):
    value = read(root, task) if isinstance(task, str) else validate(task)
    objects = [o['id'] for o in value['objects']]
    stage_states, earlier_ready = [], True
    for stage in value['stages']:
        problems = []
        if stage['readiness'] != 'ready':
            problems.append('Readiness has not been established: ' + stage['readiness_reason'])
        _, prerequisite_errors = evidence_status(root, stage['prerequisites'], objects)
        problems.extend(prerequisite_errors)
        if not earlier_ready:
            problems.append('An earlier in-scope stage is not ready to advance.')
        for requirement in stage['requirements']:
            review = stage['reviews'].get(requirement['id'])
            if not review or review['result'] not in {'passed', 'not_applicable'}:
                problems.append('Unresolved check: ' + requirement['id'])
                continue
            records, errors = evidence_status(root, review['evidence'], objects)
            problems.extend(errors)
            if not records:
                problems.append('Review lacks source evidence: ' + requirement['id'])
            covered = set().union(*(set(r['objects']) for r in records))
            if set(objects) - covered:
                problems.append('Review evidence misses scoped objects: ' + requirement['id'])
            if requirement['dimension'] == 'technical' and review['result'] == 'not_applicable':
                problems.append('Core execution checks cannot be waived for an execution stage.')
            if requirement['dimension'] == 'technical' and review['result'] == 'passed':
                if not any(r['source_type'] in {'engine', 'command'} and r['result'] in {'passed', 'observed'} for r in records):
                    problems.append('Technical execution check lacks actual engine/command evidence.')
        current_steps = [s for s in value['steps'] if s['stage'] == stage['number']]
        for step in current_steps:
            if step['state'] != 'done':
                problems.append('Unfinished work: ' + step['id'])
            if changed_files(root, step['outputs']):
                problems.append('Step output changed: ' + step['id'])
            _, step_errors = evidence_status(root, step['evidence'], step['objects'])
            problems.extend(step_errors)
        for issue in value['issues']:
            if issue['state'] == 'open' and stage['number'] in issue['stages']:
                problems.append('Open issue: ' + issue['id'])
        if stage['outcome'] not in {'supported', 'rejected'}:
            problems.append('Stage outcome has not been established.')
        if stage['outcome'] == 'rejected' and not (value['objective'] == 'evaluate' and stage['number'] == value['end_stage']):
            problems.append('A rejected result does not satisfy the requested delivery/continuation.')
        complete = not problems
        earlier_ready = complete and stage['outcome'] == 'supported'
        stage_states.append({'number':stage['number'], 'complete':complete, 'can_advance':earlier_ready,
                             'outcome':stage['outcome'], 'problems':problems})
    complete = all(s['complete'] for s in stage_states)
    return {'id':value['id'], 'revision':value['revision'], 'goal':value['goal'],
            'interval':[value['start_stage'],value['end_stage']], 'objects':value['objects'],
            'deliverables':value['deliverables'], 'state':value['state'],
            'effective_state':('needs_revalidation' if value['state'] == 'complete' and not complete else value['state']),
            'stages':stage_states, 'can_close':complete, 'outside_scope':[n for n in range(1,6) if n not in interval(value['start_stage'],value['end_stage'])],
            'changed_inputs':changed_files(root,value['inputs']), 'quality_validation':'recorded_reviews_only'}


def update(root, task_id, expected_revision, operation):
    if type(expected_revision) is not int:
        raise ValueError('An exact task revision is required for mutation.')
    with project_lock(root):
        before = read(root, task_id)
        if before['revision'] != expected_revision:
            raise ValueError('Task changed; read its current revision before writing.')
        value = deepcopy(before)
        apply_operation(root, value, operation)
        value['revision'] += 1
        value['updated_at'] = now()
        value['history'].append({'at':value['updated_at'], 'operation':operation['action'],
                                 'reason':operation.get('reason', ''), 'previous_revision':before['revision']})
        validate(value)
        history = local(root, 'production/tasks/.history/' + task_id + '/' + str(before['revision']) + '.json')
        if history.exists():
            if read_json(history) != before:
                raise ValueError('History conflict; inspect interrupted update before retrying.')
        else:
            write_json(history, before, create=True)
        write_json(path_for(root, task_id), value)
        return value


def apply_operation(root, value, op):
    if not isinstance(op, dict) or not isinstance(op.get('action'), str):
        raise ValueError('A task operation is required.')
    action = op['action']
    object_ids = [o['id'] for o in value['objects']]
    by_stage = {s['number']:s for s in value['stages']}
    if action == 'readiness':
        check_fields(op, {'action','stage','status','reason','evidence'}, action)
        if op.get('status') not in {'ready','pending','blocked'} or not op.get('reason'):
            raise ValueError('Readiness needs status and a concrete reason.')
        stage = by_stage[op['stage']]
        refs = op.get('evidence', [])
        _, errors = evidence_status(root, refs, object_ids)
        if errors:
            raise ValueError('; '.join(errors))
        # Intake may identify absent records; its explanation is separate from prior-stage approval.
        stage.update(readiness=op['status'], readiness_reason=op['reason'], prerequisites=refs)
    elif action == 'plan':
        check_fields(op, {'action','steps','reason'}, action)
        previous = {s['id']:s for s in value['steps']}
        planned = []
        for step in op['steps']:
            check_fields(step, {'id','stage','objects','owner','description','depends_on','side_effects'}, 'plan step')
            new = {**step, 'depends_on':step.get('depends_on', []), 'side_effects':step.get('side_effects','local'),
                   'state':'pending', 'outputs':{}, 'evidence':[], 'execution_refs':[], 'note':''}
            old = previous.get(new['id'])
            if old:
                same = all(old.get(k) == new.get(k) for k in ('stage','objects','owner','description','depends_on','side_effects'))
                if not same and old['state'] != 'pending':
                    raise ValueError('Do not redefine executed work; add a scoped repair step.')
                if same:
                    new = old
            planned.append(new)
        if any(s['state'] != 'pending' and s['id'] not in {p['id'] for p in planned} for s in previous.values()):
            raise ValueError('Executed work must remain in the history and plan.')
        value['steps'] = planned
    elif action == 'amend':
        check_fields(op,{'action','reason','authorization','changes','affected_stages','retire_steps'},action)
        changes=op.get('changes',{})
        check_fields(changes,{'goal','start_stage','end_stage','objects','deliverables','constraints','objective','inputs'},'task amendment')
        if not changes or not op.get('reason') or not op.get('authorization'):
            raise ValueError('Amendment requires concrete changes, reason and existing user authorization.')
        updated={**value,**{k:v for k,v in changes.items() if k!='inputs'}}
        numbers=interval(updated['start_stage'],updated['end_stage'])
        affected=op.get('affected_stages',[])
        if not isinstance(affected,list) or not affected or any(type(n) is not int or n not in set(numbers)|set(by_stage) for n in affected):
            raise ValueError('Declare affected stages so their conclusions can be revalidated.')
        if set(changes)&{'goal','deliverables','objective','objects'} and not set(numbers)<=set(affected):
            raise ValueError('A task-wide goal/scope amendment requires reviewing every retained stage against the new agreement.')
        retired=set(op.get('retire_steps',[]))
        known={s['id'] for s in value['steps']}
        if not retired<=known:raise ValueError('Unknown retired step')
        new_objects={o['id'] for o in updated['objects']}
        retained=[s for s in value['steps'] if s['id'] not in retired]
        if any(s['stage'] not in numbers or not set(s['objects'])<=new_objects or set(s['depends_on'])&retired for s in retained):
            raise ValueError('Explicitly retire affected work/dependants; historical revisions retain their outputs.')
        for key in ('goal','start_stage','end_stage','objects','deliverables','constraints','objective'):value[key]=updated[key]
        if 'inputs' in changes:value['inputs']=snapshot_files(root,changes['inputs'])
        value['authorization'].append(op['authorization'])
        value['steps']=retained
        value['issues']=[i for i in value['issues'] if set(i['stages'])<=set(numbers) and set(i['objects'])<=new_objects]
        revised=[]
        for item in stages():
            if item['number'] not in numbers:continue
            state=deepcopy(by_stage.get(item['number'],{'number':item['number'],'readiness':'pending','readiness_reason':'',
                'prerequisites':[],'requirements':item['checks'],'reviews':{},'outcome':'pending'}))
            if item['number'] in affected:
                state.update(readiness='pending',readiness_reason=op['reason'],reviews={},outcome='pending')
            revised.append(state)
        value['stages']=revised
        value['state']='active'
    elif action == 'step':
        check_fields(op, {'action','id','state','outputs','evidence','execution_refs','reason'}, action)
        step = next((s for s in value['steps'] if s['id'] == op.get('id')), None)
        if step is None or op.get('state') not in {'working','done','blocked','pending'}:
            raise ValueError('Unknown step or state.')
        if not op.get('reason'):
            raise ValueError('Record the actual work or recovery observation.')
        if step['state'] in {'working','blocked'} and op['state']=='pending' and step['side_effects']!='none' and not op.get('evidence'):
            raise ValueError('Inspect actual side effects and record recovery evidence before making this step retryable.')
        if op['state'] in {'working','done'}:
            if by_stage[step['stage']]['readiness'] != 'ready':
                raise ValueError('Establish readiness first.')
            if any(s['state'] != 'done' for s in value['steps'] if s['id'] in step['depends_on']):
                raise ValueError('Step dependencies are unfinished.')
            if any(not s['can_advance'] for s in status(root,value)['stages'] if s['number'] < step['stage']):
                raise ValueError('Earlier stage is not ready to advance.')
        refs = op.get('evidence', step['evidence'])
        _, errors = evidence_status(root, refs, step['objects'])
        if errors:
            raise ValueError('; '.join(errors))
        outputs = snapshot_files(root, op['outputs']) if 'outputs' in op else step['outputs']
        if op['state'] == 'done' and (not refs or not outputs):
            raise ValueError('Completed work needs actual outputs and evidence.')
        execution_refs = op.get('execution_refs', step['execution_refs'])
        snapshot_files(root, execution_refs)
        step.update(state=op['state'], outputs=outputs, evidence=refs, execution_refs=execution_refs, note=op['reason'])
    elif action == 'review':
        check_fields(op, {'action','stage','check','result','reason','observer','evidence','outcome'}, action)
        stage = by_stage[op['stage']]
        if op.get('check') not in {r['id'] for r in stage['requirements']}:
            raise ValueError('Unknown stage check.')
        if op.get('result') not in {'passed','failed','insufficient','not_applicable'} or not op.get('observer') or not op.get('reason'):
            raise ValueError('Review requires a concrete result, reason and observer.')
        refs = op.get('evidence', [])
        _, errors = evidence_status(root, refs, object_ids)
        if errors or not refs:
            raise ValueError('; '.join(errors) or 'Review requires actual source evidence.')
        stage['reviews'][op['check']] = {k:op[k] for k in ('result','reason','observer','evidence')}
        if 'outcome' in op:
            if op['outcome'] not in {'supported','rejected','pending'}:
                raise ValueError('Invalid stage outcome.')
            stage['outcome'] = op['outcome']
    elif action == 'issue':
        check_fields(op, {'action','id','objects','stages','state','reason','evidence'}, action)
        issue_id = identifier(op.get('id'))
        if not op.get('reason') or op.get('state') not in {'open','resolved'}:
            raise ValueError('Issue needs state and explanation.')
        if not op.get('objects') or not set(op['objects']) <= set(object_ids) or not op.get('stages') or not set(op['stages']) <= set(by_stage):
            raise ValueError('Issue must name in-scope objects and stages.')
        _, errors = evidence_status(root,op.get('evidence',[]),op['objects'])
        if errors or not op.get('evidence'):
            raise ValueError('; '.join(errors) or 'Issue needs evidence.')
        issue = {k:op[k] for k in ('id','objects','stages','state','reason','evidence')}
        value['issues'] = [i for i in value['issues'] if i['id'] != issue_id] + [issue]
        if op['state'] == 'open':
            for number in op['stages']:
                by_stage[number]['outcome'] = 'pending'
    elif action in {'pause','resume','cancel','close'}:
        check_fields(op, {'action','reason'}, action)
        if not op.get('reason'):
            raise ValueError('A user decision or completion reason is required.')
        if action == 'close' and not status(root,value)['can_close']:
            raise ValueError('In-scope completion requirements are not satisfied.')
        value['state'] = {'pause':'paused','resume':'active','cancel':'cancelled','close':'complete'}[action]
    else:
        raise ValueError('Unsupported task operation: ' + action)


def snapshot(root):
    tasks, invalid = [], []
    for path in sorted(local(root,'production/tasks').glob('*.json')):
        try:
            tasks.append(status(root,path.stem))
        except (OSError, ValueError, KeyError, TypeError) as error:
            invalid.append({'path':path.relative_to(Path(root).resolve()).as_posix(),'error':str(error)})
    legacy=[{'id':p.stem,'path':p.relative_to(Path(root).resolve()).as_posix(),'status':'unmigrated'}
            for p in sorted(local(root,'production/tasks').glob('*.md')) if not p.with_suffix('.json').exists()]
    return {'tasks':tasks,'invalid':invalid,'stages':stages(),'legacy_tasks':legacy}


def migrate(root,spec):
    """Preserve Markdown verbatim and require an explicit new task contract."""
    value=deepcopy(spec)
    source='production/tasks/'+identifier(value['id'])+'.md'
    if not local(root,source).is_file():raise ValueError('Matching legacy Markdown task was not found.')
    value['inputs']=list(dict.fromkeys(value.get('inputs',[])+[source]))
    return create(root,value)


def recovery(root,task_id):
    task=read(root,task_id)
    rows=[]
    for step in task['steps']:
        refs=[]
        for ref in step['execution_refs']:
            try:
                record=read_json(local(root,ref))
                refs.append({'path':ref,'status':record.get('status','unknown'),'record':record})
            except (OSError,ValueError,TypeError) as error:refs.append({'path':ref,'error':str(error)})
        rows.append({'id':step['id'],'state':step['state'],'side_effects':step['side_effects'],
                     'changed_outputs':changed_files(root,step['outputs']),'executions':refs,
                     'retry_requires_reconciliation':step['state'] in {'working','blocked'} and step['side_effects']!='none'})
    lock=local(root,'.openaigame/task-state.lock')
    return {'id':task_id,'revision':task['revision'],'status':status(root,task),'steps':rows,
            'lock':read_json(lock) if lock.exists() else None,
            'recovery_rule':'Inspect actual side effects. Use the existing engine/session/job recovery entry before retry; never replay unknown imports or publication.'}


def cli(args):
    root = args.project.resolve()
    if not root.is_dir():
        raise ValueError('Project directory does not exist.')
    if args.task_action == 'create':
        result = create(root, read_json(args.spec))
    elif args.task_action == 'migrate':
        result = migrate(root,read_json(args.spec))
    elif args.task_action == 'recover':
        result = recovery(root,args.id)
    elif args.task_action == 'unlock':
        read(root,args.id)
        _,errors=evidence_status(root,args.evidence,[o['id'] for o in read(root,args.id)['objects']])
        if errors:raise ValueError('; '.join(errors))
        from record_io import recover_lock
        result=recover_lock(root,'task-state',args.token,args.reason,args.evidence)
    elif args.task_action == 'update':
        result = update(root,args.id,args.revision,read_json(args.operation))
    elif args.task_action == 'show':
        result = {'task':read(root,args.id),'status':status(root,args.id)}
    else:
        result = snapshot(root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


def add_parser(subparsers):
    parser = subparsers.add_parser('task', help='Five-stage interval task records (does not execute plans)')
    parser.add_argument('--project',type=Path,required=True)
    actions = parser.add_subparsers(dest='task_action',required=True)
    create_parser = actions.add_parser('create')
    create_parser.add_argument('--spec',type=Path,required=True)
    migration=actions.add_parser('migrate');migration.add_argument('--spec',type=Path,required=True)
    recovery_parser=actions.add_parser('recover');recovery_parser.add_argument('--id',required=True)
    unlock=actions.add_parser('unlock');unlock.add_argument('--id',required=True);unlock.add_argument('--token',required=True)
    unlock.add_argument('--reason',required=True);unlock.add_argument('--evidence',action='append',required=True)
    update_parser = actions.add_parser('update')
    update_parser.add_argument('--id',required=True)
    update_parser.add_argument('--revision',type=int,required=True)
    update_parser.add_argument('--operation',type=Path,required=True)
    show = actions.add_parser('show')
    show.add_argument('--id',required=True)
    actions.add_parser('list')

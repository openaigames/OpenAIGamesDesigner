#!/usr/bin/env python3
"""Unity/Unreal production: create, edit, inspect, playback and explicit recovery."""
import argparse
import json
from pathlib import Path
import sys
import uuid
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.engines import sessions as p
from adapters.engines.registry import DRIVERS, production_driver
from game_workflow import load_config, scaffold_project, init_project


def paths(root, inspect=True):
    config = load_config(root)
    driver = production_driver(config['engine'])
    project = p.inside(root, config['engine_root'])
    if inspect:
        driver.inspect(config, project)
    return config, project


def execute(root, request_path, timeout, related=None):
    config, project = paths(root)
    return p.execute(root, project, config, production_driver(config['engine']), request_path, timeout, related)


def recover(root, session_name, restore=False):
    # Recovery must work when the engine descriptor itself needs restoring.
    config, project = paths(root, inspect=False)
    driver = production_driver(config['engine'])
    session = p.recover(root, project, driver, session_name, restore)
    if restore:
        record = p.read(session / 'session.json')
        try:
            record['restored_engine_inspection'] = driver.inspect(config, project)
        except (ValueError, OSError) as error:
            record['restored_engine_inspection_error'] = str(error)
            p.write(session / 'session.json', record)
            raise ValueError('Files restored, but engine inspection still failed: ' + str(error)) from error
        p.write(session / 'session.json', record)
    return session


def create(args):
    root = args.project.resolve()
    project = p.inside(root, 'game')
    if (root / '.openaigame/project.json').exists() or (project.exists() and any(project.iterdir())):
        raise ValueError('Creation requires an unconfigured project and empty game/ directory')
    driver = production_driver(args.engine)
    driver.validate_creation(args)
    p.ensure_idle(project, driver.EDITOR_NAMES)
    if not (root / 'Project Management.md').exists():
        scaffold_project(argparse.Namespace(project=root, brief=args.brief))
    session = root / 'runs' / ('create-' + uuid.uuid4().hex[:12])
    session.mkdir(parents=True)
    record = {'schema_version': 1, 'project': str(project), 'engine': args.engine,
              'operation': 'create', 'owner_pid': os.getpid(), 'status': 'creating',
              'gameplay_validation': 'not_run', 'visual_validation': 'not_run'}
    p.write(session / 'session.json', record)
    try:
        project_file = driver.create_project(args, root, project, session, record)
        init_project(argparse.Namespace(project=root, engine=args.engine, engine_root='game', create_engine=False,
            godot=None, expected_version=args.version, node=None, package_manager_cli=None, editor=args.editor,
            project_file=project_file))
        # Actual native identity + version, not just the descriptor.
        request = session / 'verify.json'
        p.write(request, {'engine': args.engine, 'mode': 'inspect', 'operations': []})
        verification = execute(root, request, args.timeout)
        record['verification'] = (verification / 'session.json').relative_to(root).as_posix()
        record['status'] = p.read(verification / 'session.json')['status']
    except BaseException as error:
        record.update(status='failed', error=str(error))
        raise
    finally:
        p.write(session / 'session.json', record)
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('create')
    c.add_argument('--engine', choices=tuple(DRIVERS), required=True)
    c.add_argument('--editor', type=Path, required=True)
    c.add_argument('--name', required=True)
    c.add_argument('--brief', required=True)
    c.add_argument('--version', default='')
    for name in ['execute', 'status', 'recover', 'restore']:
        s = sub.add_parser(name)
        if name == 'execute':
            s.add_argument('--request', type=Path, required=True)
            s.add_argument('--task', help='Existing project-relative task record')
            s.add_argument('--milestone', help='Existing project-relative milestone record')
        else:
            s.add_argument('--session', required=True, help='Directory name under runs/')
    for s in sub.choices.values():
        s.add_argument('--project', type=Path, required=True)
        s.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    try:
        if not 1 <= args.timeout <= 3600:
            raise ValueError('timeout must be 1..3600 seconds')
        root = args.project.resolve()
        if args.command == 'create': result = create(args)
        elif args.command == 'execute': result = execute(root, args.request, args.timeout,
            {key:getattr(args,key) for key in ['task','milestone'] if getattr(args,key)})
        elif args.command == 'status': result = json.dumps(p.read(p.inside(root / 'runs', args.session) / 'session.json'), ensure_ascii=False, indent=2)
        else: result = recover(root, args.session, args.command == 'restore')
        if isinstance(result, Path):
            record = p.read(result / 'session.json')
            print(json.dumps({'session':str(result), 'status':record['status']}, ensure_ascii=False))
            return 2 if record['status']=='needs_review' else 0
        print(result)
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    sys.exit(main())

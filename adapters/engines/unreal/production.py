"""Unreal production contract, content project creation, commandlet and PIE launch."""
from pathlib import Path
import re
from .. import sessions as p
from ..request_contract import validate, playback_result
from .cli import inspect

TOP_FIELDS = {'engine','mode','scene','operations','seconds','capture_interval','max_p95_ms','actions'}


def input_files(request):
    return [Path(op['source']).resolve() for op in request.get('operations',[]) if op.get('op')=='import']


def validate_creation(args):
    if not args.editor.is_file() or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}',args.name):
        raise ValueError('Provide an existing editor and an ASCII engine project name')


def log_errors(session):
    path=session/'editor.log'
    if not path.exists(): return []
    return [line for line in path.read_text(encoding='utf-8',errors='replace').splitlines()
            if re.search(ERROR_PATTERN,line)]


from .cli import project_file
ENGINE='unreal'
EDITOR_NAMES=('UnrealEditor.exe','UnrealEditor-Cmd.exe')
EVIDENCE_EXCLUSIONS=()
ERROR_PATTERN=r'(?:\bError:|Fatal error:)'
FIELDS={
 'scene':{'op','path','create'},
 'blueprint':{'op','path','parent_class','components'},
 'actor':{'op','target','create','source','class','position','rotation','scale','components','properties'},
 'import':{'op','path','source','replace','skeletal','animations','skeleton'},
 'animation':{'op','target','mesh','component','animation','anim_blueprint','loop'}
}
REQUIRED={'scene':['path'],'blueprint':['path'],'actor':['target'],'import':['path','source'],'animation':['target','mesh']}
ACTIONS={'position':{'op','at','target','position'},'method':{'op','at','target','method','arguments'}}


def validate_request(request):
    validate(request,ENGINE,FIELDS,REQUIRED,ACTIONS,TOP_FIELDS)
    for file in input_files(request):
        if not file.is_file(): raise ValueError('Import requires an existing source file')


def worker_files():
    return [Path(__file__).resolve(),Path(__file__).with_name('production_worker.py')]


def create_project(args, root, project, session, record):
    project.mkdir(parents=True,exist_ok=True)
    filename=args.name+'.uproject'
    p.write(project/filename,{'FileVersion':3,'EngineAssociation':args.version or '', 'Category':'','Description':args.brief,
        'Plugins':[{'Name':'PythonScriptPlugin','Enabled':True},{'Name':'EditorScriptingUtilities','Enabled':True}]})
    (project/'Content').mkdir(exist_ok=True)
    return filename


def launch(config, project, session, request, timeout, record):
    editor=Path(config['editor_executable']).resolve()
    worker=Path(__file__).with_name('production_worker.py')
    flags=['-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-nop4','-nosplash',
           f'-abslog={session / "editor.log"}',f'-OAGDRequest={session / "request.json"}']
    if request.get('mode')=='playback':
        argv=[str(editor),str(project_file(config,project)),f'-ExecutePythonScript={worker}']+flags
    else:
        argv=[str(editor.with_name('UnrealEditor-Cmd.exe')),str(project_file(config,project)),
              '-run=pythonscript',f'-script={worker}']+flags
    p.run(argv,project,session/'process.log',timeout,session,record)
    result=p.native_result(session,project,ENGINE,request['request_id'])
    if request.get('mode')=='playback': playback_result(session,request,p.read)
    return result

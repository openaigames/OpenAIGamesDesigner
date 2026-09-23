"""Unity production contract, project creation, editor helper and standalone player."""
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


ENGINE='unity'
EDITOR_NAMES=('Unity.exe',)
EVIDENCE_EXCLUSIONS=('player',)
ERROR_PATTERN=r'(?:\bError:|\berror CS\d+|Fatal error:)'
FIELDS={
 'scene':{'op','path','create'},
 'object':{'op','target','create','source','primitive','parent','position','rotation','scale','components'},
 'import':{'op','path','source','replace'},
 'model':{'op','path','animation_type','avatar'},
 'animation':{'op','target','controller','states','parameters','transitions','avatar'}
}
REQUIRED={'scene':['path'],'object':['target'],'import':['path','source'],'model':['path'],'animation':['target','controller']}
ACTIONS={'position':{'op','at','target','position'},'message':{'op','at','target','method','argument'}}


def validate_request(request):
    validate(request,ENGINE,FIELDS,REQUIRED,ACTIONS,TOP_FIELDS|{'camera'})
    for file in input_files(request):
        if not file.is_file(): raise ValueError('Import requires an existing source file')


def worker_files():
    return [Path(__file__).resolve(),Path(__file__).with_name('OAGDProduction.cs'),Path(__file__).with_name('OAGDPlayback.cs'),Path(__file__).with_name('OAGDBuild.cs')]


def create_project(args, root, project, session, record):
    p.run([str(args.editor.resolve()),'-batchmode','-quit','-createProject',str(project),
           '-logFile',str(session/'editor.log')],root,session/'process.log',args.timeout,session,record)
    return None


def helper_install(project):
    receipt_path = project / '.oagd-production-helpers.json'
    receipt = p.read(receipt_path) if receipt_path.exists() else {}
    files = []
    for relative in ('Editor/OpenAIGamesDesigner/OAGDProduction.cs', 'OpenAIGamesDesigner/OAGDPlayback.cs', 'Editor/OpenAIGamesDesigner/OAGDBuild.cs'):
        source = Path(__file__).with_name(Path(relative).name)
        target = p.inside(project, 'Assets/' + relative)
        if target.exists() and target.read_bytes() != source.read_bytes() and receipt.get(relative) != p.digest(target):
            raise ValueError('Helper has untracked/user changes; review before replacing: ' + str(target))
        files.append((relative, source, target))
    for relative, source, target in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != source.read_bytes():
            # execute() already checkpointed the engine source. Only recorded unedited helpers can upgrade.
            target.write_bytes(source.read_bytes())
        receipt[relative] = p.digest(source)
    p.write(receipt_path, receipt)


def launch(config, project, session, request, timeout, record):
    helper_install(project)
    argv=[str(Path(config['editor_executable']).resolve()),'-projectPath',str(project),'-batchmode','-quit',
          '-executeMethod','OAGD.Production.Execute','-oagdRequest',str(session/'request.json'),
          '-logFile',str(session/'editor.log')]
    p.run(argv,project,session/'process.log',timeout,session,record)
    result=p.native_result(session,project,ENGINE,request['request_id'])
    if request.get('mode')=='playback':
        player=session/'player/Playback.exe'
        if not player.is_file(): raise ValueError('Playback player build missing')
        argv=[str(player),'-oagdPlayback',str(session/'request.json'),'-screen-width','640','-screen-height','360',
              '-windowed','-logFile',str(session/'player.log')]
        p.run(argv,player.parent,session/'player-process.log',timeout,session,record)
        result=playback_result(session,request,p.read)
    return result

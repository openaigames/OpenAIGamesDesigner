"""Unreal production contract, content project creation, commandlet and PIE launch."""
from pathlib import Path
import re
from .. import sessions as p
from ..request_contract import validate, playback_result
from .cli import inspect
from . import mesh_contract

TOP_FIELDS = {'engine','mode','scene','operations','seconds','capture_interval','max_p95_ms','actions','observe','camera_target','observation_camera','readonly_preview','native_reads','character_exports','inspect_targets','mesh_audit'}


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
 'animation':{'op','target','mesh','component','animation','anim_blueprint','loop'},
 'data_asset':{'op','path','class'},
 'native_patch':{'op','path','expected','values','read_method','write_method'},
 'static_mesh_configure':mesh_contract.CONFIG_FIELDS
}
REQUIRED={'scene':['path'],'blueprint':['path'],'actor':['target'],'import':['path','source'],'animation':['target','mesh'],'native_patch':['path','expected','values'],'data_asset':['path','class']}
ACTIONS={'position':{'op','at','target','position'},'method':{'op','at','target','method','arguments'}}


def validate_request(request):
    validate(request,ENGINE,FIELDS,REQUIRED,ACTIONS,TOP_FIELDS)
    mesh_contract.validate_request(request)
    validate_observation(request)
    validate_native_data(request)
    targets=request.get('inspect_targets',[])
    if not isinstance(targets,list) or len(targets)>256 or any(not isinstance(t,str) or not t for t in targets):raise ValueError('Invalid bounded inspect targets')
    exports=request.get('character_exports',[])
    if not isinstance(exports,list) or len(exports)>100:raise ValueError('Bounded character exports required')
    if exports and request['mode']!='inspect':raise ValueError('Character reference export uses read-only inspect mode')
    ids=set()
    for row in exports:
        if not isinstance(row,dict) or set(row)-{'id','target','component','title','role','previews','actions_exporter'}:raise ValueError('Invalid character export fields')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',row.get('id','')) or row['id'] in ids:raise ValueError('Unique safe character export id required')
        ids.add(row['id'])
        if any(not isinstance(row.get(k),str) or not row[k] for k in ['target','component']):raise ValueError('Explicit character consumer and component required')
        if type(row.get('previews',False)) is not bool:raise ValueError('previews is boolean')
        if row.get('role','shared') not in ('player','boss','shared'):raise ValueError('Invalid character role')
        if row.get('actions_exporter') and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',row['actions_exporter']):raise ValueError('Invalid actions exporter')
    for file in input_files(request):
        if not file.is_file(): raise ValueError('Import requires an existing source file')


def worker_files():
    return [Path(__file__).resolve()]+[Path(__file__).with_name(name+'.py') for name in ['production_worker','observation_worker','native_data','spatial_worker','character_export','pose_worker','mesh_contract','static_meshes']]


def validate_native_data(request):
    import json
    import math
    def method(value):
        return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',value))
    reads=request.get('native_reads',[])
    if not isinstance(reads,list) or len(reads)>128:raise ValueError('native_reads must be a bounded list')
    known=set()
    for read in reads:
        if not isinstance(read,dict) or set(read)-{'id','path','properties','read_method','curve_times'}:
            raise ValueError('Invalid native read fields')
        if any(not isinstance(read.get(k),str) or not read[k] for k in ('id','path')) or read['id'] in known:
            raise ValueError('Native reads require unique id and actual asset path')
        known.add(read['id'])
        props=read.get('properties',[])
        if not isinstance(props,list) or len(props)>128 or any(not method(p) for p in props):raise ValueError('Invalid native property names')
        if 'read_method' in read and not method(read['read_method']):raise ValueError('Invalid native read method')
        if 'curve_times' in read:
            times=read['curve_times']
            if not isinstance(times,list) or not 1<=len(times)<=10000 or any(type(t) not in (int,float) or not math.isfinite(t) for t in times):
                raise ValueError('Curve samples require 1..10000 finite input times')
        if not props and not read.get('read_method') and not read.get('curve_times'):raise ValueError('Native read must select observable data')
    for op in request.get('operations',[]):
        if op['op']!='native_patch':continue
        if not isinstance(op['expected'],dict) or not isinstance(op['values'],dict) or not op['values']:
            raise ValueError('Native patch requires baseline and proposed values')
        if not set(op['values'])<=set(op['expected']):raise ValueError('Patch fields must have a baseline')
        if bool(op.get('read_method'))!=bool(op.get('write_method')):raise ValueError('Project interface requires both read and write methods')
        for key in ('read_method','write_method'):
            if key in op and not method(op[key]):raise ValueError('Invalid native method name')
        json.dumps([op['expected'],op['values']],allow_nan=False)


def validate_observation(request):
    import math
    if request.get('readonly_preview') is not None and type(request['readonly_preview']) is not bool:
        raise ValueError('readonly_preview must be boolean')
    if request.get('readonly_preview') and (request.get('mode')=='edit' or request.get('actions')):
        raise ValueError('Read-only source preview cannot edit assets or execute gameplay actions')
    if request.get('camera_target') is not None:
        if request['mode']!='playback' or not isinstance(request['camera_target'],str) or not request['camera_target']:
            raise ValueError('camera_target requires playback and a nonempty actor target')
    if 'observation_camera' in request:
        from ..request_contract import vector
        c=request['observation_camera']
        if request['mode']!='playback' or request.get('camera_target') or not isinstance(c,dict) or set(c)-{'position','rotation','field_of_view'}:raise ValueError('One explicit runtime observation camera or existing camera target is allowed')
        vector(c['position']);vector(c['rotation'])
        fov=c.get('field_of_view',60)
        if type(fov) not in (int,float) or not math.isfinite(fov) or not 10<=fov<=120:raise ValueError('Observation FOV must be 10..120 degrees')
    if 'observe' not in request:return
    options=request['observe']
    if request['mode']!='playback' or not isinstance(options,dict) or set(options)-{'actors','interval','max_samples','bindings','conditions','queries','animation_capture'}:
        raise ValueError('observe requires playback and supported observation options')
    interval=options.get('interval',0.05)
    if type(interval) not in (int,float) or not math.isfinite(interval) or not .005<=interval<=10:
        raise ValueError('Observation interval must be 0.005..10 seconds')
    limit=options.get('max_samples',2400)
    if type(limit) is not int or not 1<=limit<=10000:raise ValueError('max_samples must be 1..10000')
    if type(options.get('bindings',True)) is not bool:raise ValueError('bindings must be boolean')
    conditions=options.get('conditions',[])
    if not isinstance(conditions,list) or any(not isinstance(c,str) for c in conditions):raise ValueError('conditions must be text list')
    actors=options.get('actors')
    if not isinstance(actors,list) or not 1<=len(actors)<=256:raise ValueError('Observe 1..256 explicitly selected actors')
    ids=set()
    for actor in actors:
        if not isinstance(actor,dict) or set(actor)-{'id','target','kind','properties','markers','event_exporter','attached_actors'}:
            raise ValueError('Invalid observed actor')
        for field in ['id','target']:
            if not isinstance(actor.get(field),str) or not actor[field]:raise ValueError('Observed actor requires id and target')
        if actor['id'] in ids:raise ValueError('Duplicate observed object id')
        ids.add(actor['id'])
        if type(actor.get('attached_actors',False)) is not bool:raise ValueError('attached_actors must be boolean')
        if 'event_exporter' in actor and (not isinstance(actor['event_exporter'],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',actor['event_exporter'])):
            raise ValueError('event_exporter must name the project read-only UFunction')
        markers=actor.get('markers',[])
        if not isinstance(markers,list) or len(markers)>64 or any(not isinstance(m,str) or not m for m in markers):raise ValueError('Invalid observation markers')
        properties=actor.get('properties',[])
        if not isinstance(properties,list) or len(properties)>64:raise ValueError('Invalid observed properties')
        keys=set()
        for prop in properties:
            if not isinstance(prop,dict) or set(prop)-{'id','component','property','unit'} or any(not isinstance(prop.get(k),str) or not prop[k] for k in ['id','property','unit']):
                raise ValueError('Observed property needs id, property, unit and optional component')
            if prop['id'] in keys:raise ValueError('Duplicate property id on actor')
            keys.add(prop['id'])
    queries=options.get('queries',[])
    if not isinstance(queries,list) or len(queries)>64:raise ValueError('At most 64 explicit spatial probes per sample')
    if len(queries)*min(limit,int(request['seconds']/interval)+1)>50000:raise ValueError('Spatial query capture exceeds 50000 results; narrow sampling or queries')
    query_ids=set()
    from ..request_contract import vector
    for query in queries:
        if not isinstance(query,dict) or set(query)-{'id','object','start','end','channel','complex','ignore','purpose'}:raise ValueError('Invalid spatial probe fields')
        if not query.get('id') or query['id'] in query_ids or query.get('object') not in ids or not query.get('purpose'):raise ValueError('Spatial probe needs unique id, observed object and purpose')
        query_ids.add(query['id'])
        for key in ['start','end']:
            point=query[key]
            if isinstance(point,list):vector(point)
            elif isinstance(point,dict) and not set(point)-{'target','offset'} and isinstance(point.get('target'),str) and point['target']:vector(point.get('offset',[0,0,0]))
            else:raise ValueError('Spatial probe endpoint needs xyz or actual actor target/offset')
        if type(query.get('channel',1)) is not int or not 1<=query.get('channel',1)<=32:raise ValueError('Invalid trace channel')
        if type(query.get('complex',False)) is not bool:raise ValueError('complex must be boolean')
        if not isinstance(query.get('ignore',[]),list) or any(not isinstance(v,str) or not v for v in query.get('ignore',[])):raise ValueError('Trace ignores need actor targets')
    pose=options.get('animation_capture')
    if pose is not None:
        if not isinstance(pose,dict) or set(pose)-{'target','component','clip','start','duration','weapon','stage'}:raise ValueError('Invalid animation capture options')
        if any(not isinstance(pose.get(k),str) or not pose[k] for k in ['target','component','clip']):raise ValueError('Explicit animation target, component and clip id required')
        for k in ['start','duration']:
            v=pose.get(k,0)
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid animation window')
        if pose.get('duration',0)<=0 or pose.get('start',0)+pose['duration']>request['seconds'] or pose['duration']/interval>600:raise ValueError('Animation window outside playback or exceeds 600 samples')
        if pose.get('stage','runtime_consumer') not in ('runtime_consumer','unreal_roundtrip'):raise ValueError('Invalid animation capture stage')
        if 'weapon' in pose:
            w=pose['weapon']
            if not isinstance(w,dict) or set(w)-{'component','mesh_asset','attachment','kind'} or any(not isinstance(w.get(k),str) or not w[k] for k in ['mesh_asset','attachment','kind']):raise ValueError('Explicit actual weapon selector required')
            if w['kind'] not in ('bone','socket','component'):raise ValueError('Invalid weapon attachment kind')


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
    culture=config.get('unreal',{}).get('automation_culture')
    if culture:
        if not isinstance(culture,str) or not re.fullmatch(r'[A-Za-z-]{2,16}',culture):raise ValueError('Invalid automation culture')
        flags.append('-culture='+culture)
    if request.get('mode')=='playback':
        argv=[str(editor),str(project_file(config,project)),f'-ExecutePythonScript={worker}']+flags
    else:
        if any(row.get('previews') for row in request.get('character_exports',[])):
            flags.extend(['-AllowCommandletRendering','-RenderOffscreen'])
        argv=[str(editor.with_name('UnrealEditor-Cmd.exe')),str(project_file(config,project)),
              '-run=pythonscript',f'-script={worker}']+flags
    p.run(argv,project,session/'process.log',timeout,session,record)
    result=p.native_result(session,project,ENGINE,request['request_id'])
    if request.get('mode')=='playback':
        playback_result(session,request,p.read)
        if request.get('observe'):
            from observation import validate_capture
            validate_capture(p.read(session/'observation.json'))
            if not p.read(session/'runtime-bindings.json').get('samples'):
                raise ValueError('Playback completed without requested runtime observations')
            if request['observe'].get('animation_capture'):
                validate_pose_result(p.read(session/'animation-capture.json'),request)
    return result


def validate_pose_result(capture,request):
    """Session identity/completeness only; professional diagnostics use animlab /2."""
    import math
    spec=request['observe']['animation_capture']
    if capture.get('schema')!='animlab.capture/2' or capture.get('stage')!=spec.get('stage','runtime_consumer'):
        raise ValueError('Unsupported or mismatched actual pose capture')
    context=capture.get('context',{})
    if context.get('execution_ref')!='runs/'+request['request_id']+'/session.json':raise ValueError('Pose capture is from another session')
    if not context.get('consumer',{}).get('component','').endswith('.'+spec['component']):raise ValueError('Wrong native pose consumer')
    bones=capture.get('bones',[]);clips=capture.get('clips',[])
    if not 1<=len(bones)<=512 or len(clips)!=1 or clips[0].get('id')!=spec['clip']:raise ValueError('Missing requested native skeleton/clip')
    frames=clips[0].get('frames',[])
    if not 2<=len(frames)<=601:raise ValueError('Incomplete or unbounded native pose window')
    previous=-1
    for frame in frames:
        time=frame.get('t')
        if type(time) not in (int,float) or not math.isfinite(time) or time<=previous or time>spec['duration']:raise ValueError('Invalid native pose timestamps')
        previous=time
        if len(frame.get('pose',[]))!=len(bones):raise ValueError('Native pose count differs from skeleton')

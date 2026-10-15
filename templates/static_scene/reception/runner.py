import argparse,json,os,subprocess,time
from pathlib import Path
W=Path(__file__).resolve().parent;settings=json.loads(Path(os.environ['OAGD_ENGINE_CONFIG']).read_text());UE=Path(settings['unreal']);U=UE/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe';G=Path(settings['godot'])
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('--label',required=True);p.add_argument('--render',action='store_true');p.add_argument('--view',default='applied');p.add_argument('--script');a=p.parse_args()
e=W/'evidence'/a.label;e.mkdir(parents=True,exist_ok=False);gd=W/'Godot';up=W/'Unreal';project=up/'OAGDExamples.uproject';env=os.environ.copy()
for name in ('temp','appdata'):(e/name).mkdir()
env['TEMP']=env['TMP']=str(e/'temp');env['APPDATA']=str(e/'appdata');env['PYTHONUTF8']='1';env['OAGD_IMPORT_BATCH']=a.label.replace('-','_');cwd=W
if a.task=='gd-import':cmd=[G,'--headless','--editor','--path',gd,'--import']
elif a.task=='gd-prepare':cmd=[G,'--headless','--path',gd,'--script','res://'+(a.script or 'prepare.gd')]
elif a.task in ('godot','gd-package-run'):
 cmd=[G,'--path',gd] if a.task=='godot' else [W/'packages/Godot/StaticScene.exe']
 if not a.render:cmd+=['--headless']
 cmd+=['--','--report='+str(e/'runtime.json'),'--view='+a.view]
elif a.task=='build':
 cmd=[next((UE/'Engine/Binaries/ThirdParty/DotNet').rglob('dotnet.exe')),UE/'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll','OAGDExamplesEditor','Win64','Development','-Project='+str(project),'-WaitMutex','-NoHotReload','-NoHotReloadFromIDE','-NoUBA','-MaxParallelActions=4']
elif a.task=='ue-script':
 cmd=[U,project,'-run=pythonscript','-script='+str(up/(a.script or 'prepare.py')),'-nullrhi','-unattended','-stdout','-FullStdOutLogOutput','-fastexit']
elif a.task in ('unreal','ue-package-run'):
 scene=(up/'current-map.txt').read_text().strip()
 if a.view=='baseline':scene='/Game/Baseline'
 if a.view=='recovered':scene=scene.replace('/Applied','/Recovered')
 cmd=[U,project,scene,'-game'] if a.task=='unreal' else [W/'packages/Unreal/Windows/OAGDExamples.exe',scene]
 cmd+=['-SceneReport='+str(e/'runtime.json'),'-SceneView='+a.view,'-unattended','-stdout','-FullStdOutLogOutput','-windowed','-ResX=1152','-ResY=720','-RenderOffScreen']
 if not a.render:cmd+=['-nullrhi','-nosound']
elif a.task=='gd-export':cmd=[G,'--headless','--editor','--path',gd,'--export-debug','Windows',W/'packages/Godot/StaticScene.exe']
elif a.task=='ue-export':cmd=[UE/'Engine/Build/BatchFiles/RunUAT.bat','BuildCookRun','-project='+str(project),'-noP4','-platform=Win64','-clientconfig=Development','-build','-cook','-stage','-pak','-archive','-archivedirectory='+str(W/'packages/Unreal'),'-utf8output','-unattended','-nocompileeditor','-UbtArgs=-NoUBA -MaxParallelActions=4 -WaitMutex','-AdditionalCookerOptions=-SkipZenStore -DDC=(Local) -LocalDataCachePath='+settings['ddc']]
else:raise ValueError(a.task)
if cmd[0]==U:cmd+=['-DDC=(Local)','-LocalDataCachePath='+settings['ddc']]
start=time.monotonic()
with (e/'process.log').open('w',encoding='utf8') as log:
 try:code=subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200).returncode
 except subprocess.TimeoutExpired:code=124
r={'command':list(map(str,cmd)),'exit_code':code,'seconds':time.monotonic()-start,'ok':code==0}
if a.task in ('godot','unreal','gd-package-run','ue-package-run'):
 report=json.loads((e/'runtime.json').read_text(encoding='utf-8-sig')) if (e/'runtime.json').exists() else {}
 r.update(checks=len(report.get('checks',[])),failures=report.get('failures','missing report'));r['ok']=r['ok'] and r['checks']>20 and not r['failures']
(e/'execution.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));raise SystemExit(0 if r['ok'] else 1)

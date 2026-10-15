from pathlib import Path
import unreal,json,sys
W=Path(unreal.Paths.project_dir()).parent
sys.path[:0]=[str(W/'toolkit/tools'),str(W/'toolkit/unreal')]
import scene_replacement_import as R
from static_scene import fingerprint
checks=[]
def check(ok,name):checks.append(name);assert ok,name
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level('/Game/Baseline')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
plan,resources=R.prepare_resources(W/'transactions/unreal','/Game/Reception/Assets')
def state():return {a.get_actor_label():fingerprint(R.snapshot(a)) for a in R.actors().get_all_level_actors() if type(a)==unreal.StaticMeshActor}
before=state();original=R.importer.assemble;count=0
def fail_stage(*args):
 global count
 count+=1
 if count==3:raise RuntimeError('Injected third-group staging failure')
 return original(*args)
R.importer.assemble=fail_stage
try:R.apply(plan,resources)
except RuntimeError:checks.append('staging failure raised')
else:raise AssertionError('Missing staging failure')
finally:R.importer.assemble=original
check(state()==before,'staging failure leaves every native actor identical')
original_state=R.state;count=0
def fail_hide(*args):
 global count
 count+=1
 if count==2:raise RuntimeError('Injected second-target failure')
 return original_state(*args)
R.state=fail_hide
try:R.apply(plan,resources)
except RuntimeError:checks.append('partial target mutation failure raised')
else:raise AssertionError('Missing target failure')
finally:R.state=original_state
check(state()==before,'partial failure restores all targets and removes replacements')
receipt=R.apply(plan,resources);checks.append('apply after recovery')
bad=json.loads(json.dumps(receipt));bad['roots']['DoorA']='wrong'
after=state()
try:R.rollback(bad)
except ValueError:checks.append('wrong receipt refused')
else:raise AssertionError('Wrong receipt accepted')
check(state()==after,'wrong receipt leaves all actors intact')
a=R.lookup()['Unrelated'];a.set_actor_location(a.get_actor_location()+unreal.Vector(0,75,0),False,True)
check(unreal.EditorLoadingAndSavingUtils.save_map(world,'/Game/Reception/Applied'),'save combined scene')
(W/'Unreal/receipt.json').write_text(json.dumps(receipt,indent=2));(W/'Unreal/current-map.txt').write_text('/Game/Reception/Applied')
(W/'Unreal/prepare-report.json').write_text(json.dumps({'checks':checks,'failures':[]},indent=2))

from pathlib import Path
import unreal,json,sys
W=Path(unreal.Paths.project_dir()).parent
sys.path[:0]=[str(W/'toolkit/tools'),str(W/'toolkit/unreal')]
import scene_replacement_import as R
from static_scene import fingerprint
checks=[]
def check(ok,name):checks.append(name);assert ok,name
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level('/Game/Reception/Applied')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unrelated=fingerprint(R.snapshot(R.lookup()['Unrelated']))
receipt=json.loads((W/'Unreal/receipt.json').read_text());check(R.rollback(receipt)['ok'],'restart rollback')
baseline=json.loads((W/'Unreal/baseline.json').read_text())
for key,row in baseline['objects'].items():check(fingerprint(R.snapshot(R.lookup()[key]))==row['fingerprint'],'baseline restored '+key)
check(fingerprint(R.snapshot(R.lookup()['Unrelated']))==unrelated,'unrelated edit preserved')
try:R.rollback(receipt)
except ValueError:checks.append('duplicate rollback rejected')
else:raise AssertionError('Duplicate rollback')
# Reuse independently imported native resources; no second import or author path.
plan=R.read_plan(W/'transactions/unreal');resources={}
for aid,item in plan['assets'].items():
 p=R.importer.read_plan(W/'transactions/unreal'/item['revision']);meshes={};collision={}
 for m in p['meshes']:
  paths=unreal.EditorAssetLibrary.list_assets('/Game/Reception/Assets/'+aid+'/Mesh_'+str(m['id']),recursive=True)
  meshes[m['id']]=next(unreal.load_asset(path) for path in paths if isinstance(unreal.load_asset(path),unreal.StaticMesh))
  path='/Game/Reception/Assets/'+aid+'/Collision_'+str(m['id'])
  if unreal.EditorAssetLibrary.does_asset_exist(path):collision[m['id']]=unreal.load_asset(path)
 resources[aid]={'plan':p,'meshes':meshes,'collision':collision}
R.apply(plan,resources);checks.append('restart reapply')
check(unreal.EditorLoadingAndSavingUtils.save_map(world,'/Game/Reception/Recovered'),'save recovered scene')
(W/'Unreal/rollback-report.json').write_text(json.dumps({'checks':checks,'failures':[]},indent=2))

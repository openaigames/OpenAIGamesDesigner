from pathlib import Path
import unreal,json,sys
W=Path(unreal.Paths.project_dir()).parent
sys.path[:0]=[str(W/'toolkit/tools'),str(W/'toolkit/unreal')]
import scene_replacement_import as R
spec=json.loads((W/'case.json').read_text())
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not unreal.EditorAssetLibrary.does_asset_exist('/Game/Baseline');assert levels.new_level('/Game/Baseline')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Script/OAGDExamples.SceneGame'))
cube=unreal.load_asset('/Engine/BasicShapes/Cube');ids=[]
for row in spec['grayboxes']:
 x,y,z=row['center'];sx,sy,sz=row['size']
 a=R.actors().spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(-z*100,x*100,y*100),unreal.Rotator(pitch=0,yaw=90-row['yaw'],roll=0));a.tags=['OAGD_ID_'+row['id']];a.set_actor_label(row['id']);a.set_actor_scale3d(unreal.Vector(sx,sz,sy));a.static_mesh_component.set_static_mesh(cube);a.static_mesh_component.set_collision_profile_name('BlockAll')
 if row['managed']:ids.append(row['id'])
light=R.actors().spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,1000),unreal.Rotator(pitch=-40,yaw=-35,roll=0));light.light_component.set_editor_property('intensity',3.0)
assert levels.save_current_level()
(W/'Unreal/baseline.json').write_text(json.dumps(R.capture(ids),indent=2))

from pathlib import Path
import sys,json,copy
"""Persist generated triangles and nav bounds; refuse to overwrite an existing map."""
import unreal
for name in ('Tint','Vertex'):
    if unreal.EditorAssetLibrary.does_asset_exist('/Game/Scene/'+name):continue
    m=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,'/Game/Scene',unreal.Material,unreal.MaterialFactoryNew())
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    if name=='Tint':
        e=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionVectorParameter,-300,0)
        e.set_editor_property('parameter_name','Tint');e.set_editor_property('default_value',unreal.LinearColor(.1,.75,1,1))
    else:e=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionVertexColor,-300,0)
    unreal.MaterialEditingLibrary.connect_material_property(e,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m)
if unreal.EditorAssetLibrary.does_asset_exist('/Game/Example'):raise RuntimeError('Existing map is project-owned. Generate the new revision in a new project or migrate edits explicitly.')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.new_level('/Game/Example'):raise RuntimeError('Could not create map')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Script/OAGDExamples.ExampleGame'))
if not unreal.ExampleMapTools.build_generated_scene(world):raise RuntimeError('Could not instantiate generated collision and bounds')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,1500),unreal.Rotator(-70,-20,0))
light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
if not levels.save_current_level():raise RuntimeError('Could not save generated map')
unreal.log('OAGD_SCENE_MAP_SAVED')

root=Path(unreal.Paths.project_dir());sys.path.insert(0,str(root))
from static_replacement import prepare,apply,rollback,lookup
folder=root/'Content/generated/static';plan=json.loads((folder/'plan.json').read_text());baseline=json.loads((folder/'baseline.json').read_text())
assets,reports=prepare(plan,folder,'/Game/Static')
checks=[]
bad=copy.deepcopy(plan);bad['replacements'][0]['targets'][0]='missing'
count=len(actors.get_all_level_actors())
try:apply(bad,baseline,assets);raise AssertionError('Bad mapping accepted')
except ValueError:pass
assert count==len(actors.get_all_level_actors());checks.append('missing target leaves scene untouched')
target=lookup()[plan['replacements'][0]['targets'][0]];target.set_actor_location(unreal.Vector(10,0,0),False,False)
try:apply(plan,baseline,assets);raise AssertionError('Edited target accepted')
except ValueError:pass
assert target.get_component_by_class(unreal.ProceduralMeshComponent).get_editor_property('visible');checks.append('edited target rejected before mutation')
target.set_actor_location(unreal.Vector(0,0,0),False,False)
receipt=apply(plan,baseline,assets);checks.append('apply succeeds')
try:apply(plan,baseline,assets);raise AssertionError('Duplicate apply accepted')
except ValueError:pass
checks.append('duplicate application rejected')
rollback(receipt)
component=target.get_component_by_class(unreal.ProceduralMeshComponent)
assert component.get_editor_property('visible') and component.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION and count==len(actors.get_all_level_actors());checks.append('rollback restores visibility collision and object count')
receipt=apply(plan,baseline,assets);checks.append('reapply after rollback')
assert levels.save_current_level();checks.append('replacement map saved')
(root/'static-build.json').write_text(json.dumps({'checks':checks,'failures':[],'resources':reports,'plan_id':plan['plan_id']},indent=2))
unreal.log('OAGD_STATIC_MAP_SAVED')

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

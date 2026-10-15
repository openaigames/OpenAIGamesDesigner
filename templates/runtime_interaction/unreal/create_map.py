"""Create only this example's persistent map; gameplay creates its scoped room objects."""
import unreal
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Interaction/Tint'):
    material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('Tint','/Game/Interaction',unreal.Material,unreal.MaterialFactoryNew())
    material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    tint=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionVectorParameter,-300,0)
    tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',unreal.LinearColor(.05,.6,1,1))
    unreal.MaterialEditingLibrary.connect_material_property(tint,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material);unreal.EditorAssetLibrary.save_loaded_asset(material)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Example'):
    if not levels.new_level('/Game/Example'):raise RuntimeError('Could not create map')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Script/OAGDExamples.ExampleGame'))
    if not levels.save_current_level():raise RuntimeError('Could not save map')
unreal.log('OAGD_INTERACTION_MAP_SAVED')

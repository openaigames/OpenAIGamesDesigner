"""Run inside UE 5.8 editor after compiling this isolated project."""
import unreal
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/ExampleTint'):
    material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('ExampleTint','/Game',unreal.Material,unreal.MaterialFactoryNew())
    tint=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionVectorParameter,-300,0)
    tint.set_editor_property('parameter_name','Tint')
    tint.set_editor_property('default_value',unreal.LinearColor(.6,.68,.75,1))
    unreal.MaterialEditingLibrary.connect_material_property(tint,'',unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(tint,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if unreal.EditorAssetLibrary.does_asset_exist('/Game/Example'):
    unreal.log('OAGD map already exists; preserving edits')
else:
    subsystem.new_level('/Game/Example')
    mode=unreal.load_class(None,'/Script/OAGDExamples.ExampleGame')
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_world_settings().set_editor_property('default_game_mode',mode)
    subsystem.save_current_level()
    unreal.log('OAGD_MAP_CREATED')

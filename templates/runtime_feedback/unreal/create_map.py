"""Run once in the built UE 5.8 example; preserve any existing project maps."""
import unreal
from pathlib import Path
source=Path(unreal.Paths.project_content_dir())/'OAGDData/audio'
for name in ('door','ui','action','zone'):
    path='/Game/Feedback/'+name
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        task=unreal.AssetImportTask();task.set_editor_property('filename',str(source/(name+'.wav')));task.set_editor_property('destination_path','/Game/Feedback');task.set_editor_property('destination_name',name);task.set_editor_property('automated',True);task.set_editor_property('save',True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        sound=unreal.load_asset(path)
        if not sound:raise RuntimeError('Audio import failed '+name)
        sound.set_editor_property('looping',name=='zone');unreal.EditorAssetLibrary.save_loaded_asset(sound)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Feedback/FeedbackTint'):
    material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('FeedbackTint','/Game/Feedback',unreal.Material,unreal.MaterialFactoryNew())
    material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    tint=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionVectorParameter,-300,0)
    tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',unreal.LinearColor(.1,.6,1,1))
    unreal.MaterialEditingLibrary.connect_material_property(tint,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material);unreal.EditorAssetLibrary.save_loaded_asset(material)


levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
cube = unreal.load_asset('/Engine/BasicShapes/Cube')
for room in ('a', 'b'):
    path = '/Game/Room_' + room
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.log('Preserving existing ' + path)
        continue
    if not levels.new_level(path):
        raise RuntimeError('Could not create ' + path)
    for label, position, size in [('Floor', (0, 0, -50), (20, 20, 1)), ('Door', (400, 0, 150), (.4, 3, 3))]:
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*position))
        actor.set_actor_label(label + '_' + room)
        component = actor.static_mesh_component
        component.set_static_mesh(cube)
        component.set_collision_profile_name('BlockAll')
        actor.set_actor_scale3d(unreal.Vector(*size))
        if label == 'Door':
            actor.set_editor_property('tags', [unreal.Name('door-' + room)])
    if not levels.save_current_level():
        raise RuntimeError('Could not save ' + path)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/InvalidRoom'):
    if not levels.new_level('/Game/InvalidRoom') or not levels.save_current_level():
        raise RuntimeError('Could not save invalid-scene fixture')
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Example'):
    if not levels.new_level('/Game/Example'):
        raise RuntimeError('Could not create persistent level')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', unreal.load_class(None, '/Script/OAGDExamples.ExampleGame'))
    if not levels.save_current_level():
        raise RuntimeError('Could not save persistent level')
for path in ('/Game/Example', '/Game/Room_a', '/Game/Room_b'):
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError('Missing saved map ' + path)
unreal.log('OAGD_STATE_MAPS_SAVED')

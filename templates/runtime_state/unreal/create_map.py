"""Run once in the built UE 5.8 example; preserve any existing project maps."""
import unreal

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

"""Persist native collision, nav bounds and original calibration tint for this example."""
import unreal
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Navigation/Tint'):
    m=unreal.AssetToolsHelpers.get_asset_tools().create_asset('Tint','/Game/Navigation',unreal.Material,unreal.MaterialFactoryNew())
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    e=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionVectorParameter,-300,0)
    e.set_editor_property('parameter_name','Tint');e.set_editor_property('default_value',unreal.LinearColor(.05,.7,1,1))
    unreal.MaterialEditingLibrary.connect_material_property(e,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Example'):
    if not levels.new_level('/Game/Example'):raise RuntimeError('Could not create map')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Script/OAGDExamples.ExampleGame'))
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cube=unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
    for pos,size in [((0,0,-50),(2000,1600,100)),((0,0,100),(100,800,200)),((1400,0,-50),(400,400,100))]:
        a=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos));a.static_mesh_component.set_static_mesh(cube)
        a.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC);a.static_mesh_component.set_collision_profile_name('BlockAll')
        a.set_actor_scale3d(unreal.Vector(*(v/100 for v in size)))
    light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,1000),unreal.Rotator(-70,-20,0))
    light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    unreal.ExampleMapTools.create_navigation_bounds(world)
    if not levels.save_current_level():raise RuntimeError('Could not save map')
unreal.log('OAGD_NAVIGATION_MAP_SAVED')

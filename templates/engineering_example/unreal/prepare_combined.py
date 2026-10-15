"""Create project-owned streamed rooms, assets and the persistent combined entry."""
import unreal as u
import json,sys
from pathlib import Path
root=Path(u.Paths.project_dir());sys.path.insert(0,str(root))
from static_replacement import prepare,apply
tools=u.AssetToolsHelpers.get_asset_tools();levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
for name in ('Vertex','FeedbackTint'):
    folder='/Game/Scene' if name=='Vertex' else '/Game/Feedback'
    if u.EditorAssetLibrary.does_asset_exist(folder+'/'+name):continue
    m=tools.create_asset(name,folder,u.Material,u.MaterialFactoryNew());m.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
    kind=u.MaterialExpressionVertexColor if name=='Vertex' else u.MaterialExpressionVectorParameter
    expression=u.MaterialEditingLibrary.create_material_expression(m,kind,-300,0)
    if name!='Vertex':expression.set_editor_property('parameter_name','Tint')
    u.MaterialEditingLibrary.connect_material_property(expression,'',u.MaterialProperty.MP_EMISSIVE_COLOR);u.MaterialEditingLibrary.recompile_material(m);u.EditorAssetLibrary.save_loaded_asset(m)
for name in ('door','ui','action','zone'):
    if u.EditorAssetLibrary.does_asset_exist('/Game/Feedback/'+name):continue
    task=u.AssetImportTask();task.filename=str(root/'Content/OAGDData/audio'/(name+'.wav'));task.destination_path='/Game/Feedback';task.destination_name=name;task.automated=True;task.save=True;tools.import_asset_tasks([task])
    sound=u.load_asset('/Game/Feedback/'+name)
    if not sound:raise RuntimeError('Audio import failed '+name)
    sound.set_editor_property('looping',name=='zone');u.EditorAssetLibrary.save_loaded_asset(sound)
folder=root/'Content/generated/static';plan=json.loads((folder/'plan.json').read_text());baseline=json.loads((folder/'baseline.json').read_text())
assets,reports=prepare(plan,folder,'/Game/Static')
for room in ('a','b'):
    path='/Game/Combined/Room_'+room
    if u.EditorAssetLibrary.does_asset_exist(path):raise RuntimeError('Existing room is project-owned: '+path)
    if not levels.new_level(path):raise RuntimeError('Could not create room')
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if not u.CombinedMapTools.build_generated_scene(world):raise RuntimeError('Generated geometry failed')
    apply(plan,baseline,assets)
    if not levels.save_current_level():raise RuntimeError('Could not save room')
# This one-time setup explicitly updates the generated playback entry to the combined consumer.
if not levels.load_level('/Game/Playback/Example'):raise RuntimeError('Missing playback entry')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode',u.CombinedGame)
if not u.CombinedMapTools.build_bounds(world):raise RuntimeError('Navigation bounds failed')
if not levels.save_current_level():raise RuntimeError('Could not save combined entry')
(root/'combined-build.json').write_text(json.dumps({'ok':True,'engine':u.SystemLibrary.get_engine_version(),'static_resources':reports,'rooms':['a','b']},indent=2))

"""Runs INSIDE Unreal Python. Native editing and bounded PIE playback, no MCP emulation."""
import csv
import json
import math
from pathlib import Path
import re
import time
import traceback
import unreal


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def package(value):
    if not isinstance(value, str) or not re.fullmatch(r'/Game/[A-Za-z0-9_/]+', value) or '//' in value:
        raise ValueError('Writable asset must be a /Game/ package path: ' + str(value))
    return value


def asset(value):
    obj = unreal.load_asset(value)
    if obj is None:
        raise ValueError('Missing engine asset: ' + value)
    return obj


def vector(value):
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
        raise ValueError('Expected finite xyz vector')
    return unreal.Vector(*value)


def cls(name):
    value = unreal.load_class(None, name) if name.startswith('/Script/') else getattr(unreal, name, None)
    if value is None:
        raise ValueError('Unknown Unreal class: ' + name)
    return value


def value(data):
    if not isinstance(data, dict):
        return data
    if set(data) == {'asset'}:
        return asset(data['asset'])
    if set(data) == {'vector'}:
        return vector(data['vector'])
    if set(data) == {'enum'}:
        group, item = data['enum'].split('.')
        return getattr(getattr(unreal, group), item)
    if set(data) == {'class'}:
        loaded = unreal.load_class(None, data['class'])
        if not loaded:
            raise ValueError('Class asset missing: ' + data['class'])
        return loaded
    raise ValueError('Unsupported typed property: ' + str(data))


def properties(obj, values):
    for key, data in values.items():
        obj.set_editor_property(key, value(data))
        # Native readback; representation is included for both primitives and object references.
        obj.get_editor_property(key)


def find_actor(name, world=None):
    actors = (unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world
              else unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    matches = [a for a in actors if a.get_actor_label() == name]
    if len(matches) != 1:
        raise ValueError('Actor must resolve uniquely: ' + name + ' matches=' + str(len(matches)))
    return matches[0]


def component(actor, description):
    matches = actor.get_components_by_class(cls(description['type']))
    if description.get('name'):
        matches = [c for c in matches if c.get_name() == description['name']]
    if len(matches) != 1:
        raise ValueError('Component must resolve uniquely; add persistent components through blueprint operation: ' + str(description))
    return matches[0]


def apply(op):
    kind = op['op']
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if kind == 'scene':
        path = package(op['path'])
        if op.get('create'):
            if unreal.EditorAssetLibrary.does_asset_exist(path):
                raise ValueError('Scene already exists')
            success = level.new_level(path)
        else:
            success = level.load_level(path)
        if not success:
            raise ValueError('Scene create/load failed: ' + path)
    elif kind == 'blueprint':
        path = package(op['path'])
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            raise ValueError('Blueprint already exists; do not replace existing graphs')
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', cls(op.get('parent_class', 'Actor')))
        parent, name = path.rsplit('/', 1)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, parent, unreal.Blueprint, factory)
        if not bp:
            raise ValueError('Blueprint creation failed')
        subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        handles = subsystem.k2_gather_subobject_data_for_blueprint(bp)
        for spec in op.get('components', []):
            params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=cls(spec['type']), blueprint_context=bp)
            handle, failure = subsystem.add_new_subobject(params=params)
            if str(failure):
                raise ValueError('Component creation failed: ' + str(failure))
            if not subsystem.rename_subobject(handle, unreal.Text(spec['name'])):
                raise ValueError('Component rename failed')
            data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
            obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object_for_blueprint(data, bp)
            properties(obj, spec.get('properties', {}))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        if not unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False):
            raise ValueError('Blueprint save failed')
    elif kind == 'actor':
        if op.get('create'):
            actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            if any(a.get_actor_label() == op['target'] for a in actors.get_all_level_actors()):
                raise ValueError('Actor label already exists')
            source = asset(op['source']) if op.get('source') else cls(op.get('class', 'Actor'))
            location = vector(op.get('position', [0, 0, 0]))
            if isinstance(source, unreal.Blueprint):
                actor = actors.spawn_actor_from_class(source.generated_class(), location)
            else:
                actor = (actors.spawn_actor_from_object(source, location) if op.get('source')
                         else actors.spawn_actor_from_class(source, location))
            if not actor:
                raise ValueError('Actor spawn failed')
            actor.set_actor_label(op['target'])
        else:
            actor = find_actor(op['target'])
        if 'position' in op:
            actor.set_actor_location(vector(op['position']), False, False)
        if 'rotation' in op:
            actor.set_actor_rotation(unreal.Rotator(*op['rotation']), False)
        if 'scale' in op:
            actor.set_actor_scale3d(vector(op['scale']))
        properties(actor, op.get('properties', {}))
        for spec in op.get('components', []):
            properties(component(actor, spec), spec.get('properties', {}))
    elif kind == 'import':
        source = Path(op['source'])
        if not source.is_file():
            raise ValueError('Source file missing')
        destination = package(op['path'])
        if unreal.EditorAssetLibrary.does_asset_exist(destination) and not op.get('replace'):
            raise ValueError('Import destination exists; replace must be explicit')
        parent, name = destination.rsplit('/', 1)
        task = unreal.AssetImportTask()
        for key, data in {'filename': str(source), 'destination_path': parent, 'destination_name': name,
                          'automated': True, 'replace_existing': op.get('replace', False), 'save': True}.items():
            task.set_editor_property(key, data)
        if source.suffix.lower() == '.fbx':
            options = unreal.FbxImportUI()
            # Explicit legacy FBX importer offers skeleton/animation binding; do not guess skeletons.
            options.set_editor_property('automated_import_should_detect_type', False)
            skeletal = op.get('skeletal', False)
            options.set_editor_property('import_as_skeletal', skeletal)
            options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
            options.set_editor_property('import_animations', op.get('animations', False))
            if op.get('skeleton'):
                options.set_editor_property('skeleton', asset(op['skeleton']))
            task.set_editor_property('options', options)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = list(task.get_editor_property('imported_object_paths'))
        if not paths:
            paths = [a.get_path_name() for a in task.get_objects()]
        if not paths:
            raise ValueError('Importer produced no engine objects')
        for path in paths:
            asset(path)
        return {'imported': paths, 'source': str(source)}
    elif kind == 'animation':
        actor = find_actor(op['target'])
        mesh_component = component(actor, {'type': 'SkeletalMeshComponent', **op.get('component', {})})
        mesh = asset(op['mesh'])
        if not isinstance(mesh, unreal.SkeletalMesh):
            raise ValueError('Character mesh must be a SkeletalMesh')
        skeleton = mesh.get_editor_property('skeleton')
        mesh_component.set_skeletal_mesh_asset(mesh)
        if op.get('animation'):
            animation = asset(op['animation'])
            if animation.get_editor_property('skeleton') != skeleton:
                raise ValueError('Animation and mesh skeleton differ; retarget explicitly first')
            mesh_component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            # AnimationData is serialized; a runtime-only play_animation call is insufficient.
            data = mesh_component.get_editor_property('animation_data')
            data.set_editor_property('anim_to_play', animation)
            data.set_editor_property('saved_looping', op.get('loop', True))
            data.set_editor_property('saved_playing', True)
            mesh_component.set_editor_property('animation_data', data)
        elif op.get('anim_blueprint'):
            bp = asset(op['anim_blueprint'])
            if bp.get_editor_property('target_skeleton') != skeleton:
                raise ValueError('Animation Blueprint skeleton differs; retarget explicitly first')
            mesh_component.set_animation_mode(unreal.AnimationMode.ANIMATION_BLUEPRINT)
            mesh_component.set_anim_instance_class(bp.generated_class())
        else:
            raise ValueError('Choose animation or anim_blueprint')
    else:
        raise ValueError('Unsupported Unreal operation: ' + kind)
    return {'op': kind, 'target': op.get('target', op.get('path'))}


def inspect_scene():
    output = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        components = []
        for c in actor.get_components_by_class(unreal.ActorComponent):
            detail = {'name': c.get_name(), 'class': c.get_class().get_path_name(), 'references': {}}
            for key in ['static_mesh', 'skeletal_mesh_asset', 'anim_class', 'override_materials', 'animation_data']:
                try:
                    data = c.get_editor_property(key)
                    detail['references'][key] = data.get_path_name() if isinstance(data, unreal.Object) else str(data)
                except Exception:
                    pass  # Not every component exposes these optional reference properties.
            components.append(detail)
        transform = actor.get_actor_transform()
        output.append({'label': actor.get_actor_label(), 'class': actor.get_class().get_path_name(),
                       'position': [transform.translation.x, transform.translation.y, transform.translation.z],
                       'scale': [transform.scale3d.x, transform.scale3d.y, transform.scale3d.z],
                       'rotation': str(actor.get_actor_rotation()), 'components': components})
    return output


class Playback:
    def __init__(self, request, result):
        self.request, self.result = request, result
        self.directory = Path(request['session'])
        (self.directory / 'frames').mkdir(exist_ok=True)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.started = time.monotonic()
        self.first = None
        self.last_world_time = None
        self.deltas = []
        self.step = 0
        self.capture = 0
        self.next_capture = 0
        self.finish_at = None
        self.screenshot_tasks = []
        self.busy = False
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.level.editor_request_begin_play()

    def finish(self, error=None):
        if self.finish_at is not None:
            return
        self.finish_at = time.monotonic()
        self.level.editor_request_end_play()
        ordered = sorted(self.deltas)
        p95 = ordered[math.ceil(len(ordered) * .95) - 1] if ordered else None
        report = {'request_id': self.request['request_id'], 'scope': 'PIE world delta sampled once per observed world time from editor Slate tick; not GPU profiling',
                  'recording_scope': 'active PIE viewport PNG sequence; includes capture overhead',
                  'frames': len(ordered), 'actions_completed': self.step, 'captures': self.capture, 'error': error,
                  'mean_ms': sum(ordered)/len(ordered) if ordered else None, 'p95_ms': p95,
                  'max_ms': max(ordered) if ordered else None,
                  'success': not error and bool(ordered) and self.step == len(self.request.get('actions', []))}
        if self.request.get('max_p95_ms', 0) > 0 and (p95 is None or p95 > self.request['max_p95_ms']):
            report.update(success=False, error='PIE p95 exceeded configured budget')
        with (self.directory / 'frame-times-ms.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f); writer.writerow(['sample', 'world_delta_ms'])
            writer.writerows(enumerate(self.deltas))
        save_json(self.directory / 'playback.json', report)
        self.result.update(success=report['success'], error=report['error'])
        save_json(self.request['report'], self.result)

    def tick(self, delta):
        # Screenshot loading may pump Slate recursively. Never execute a timed action twice.
        if self.busy:
            return
        self.busy = True
        try:
            self.tick_once(delta)
        finally:
            self.busy = False

    def tick_once(self, delta):
        try:
            if self.finish_at is not None:
                if time.monotonic() - self.finish_at > 3 and not self.level.is_in_play_in_editor():
                    unreal.unregister_slate_post_tick_callback(self.handle)
                    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
                    unreal.SystemLibrary.quit_editor()
                return
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not world or not self.level.is_in_play_in_editor():
                if time.monotonic() - self.started > 60:
                    self.finish('PIE startup timed out')
                return
            if self.first is None:
                self.first = time.monotonic()
            elapsed = time.monotonic() - self.first
            world_time = unreal.GameplayStatics.get_time_seconds(world)
            if world_time != self.last_world_time:
                dt = unreal.GameplayStatics.get_world_delta_seconds(world) * 1000
                if dt > 0:
                    self.deltas.append(dt)
                self.last_world_time = world_time
            actions = self.request.get('actions', [])
            while self.step < len(actions) and actions[self.step]['at'] <= elapsed:
                action = actions[self.step]
                actor = find_actor(action['target'], world)
                if action['op'] == 'position':
                    actor.set_actor_location(vector(action['position']), False, False)
                elif action['op'] == 'method':
                    actor.call_method(action['method'], tuple(action.get('arguments', [])))
                else:
                    raise ValueError('Unsupported gameplay action: ' + action['op'])
                with (self.directory / 'actions.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps({'action': action, 'time': elapsed, 'position': str(actor.get_actor_location())}) + '\n')
                self.step += 1
            pending = any(not t.is_task_done() for t in self.screenshot_tasks)
            if (self.request.get('capture_interval', 0) > 0 and elapsed >= self.next_capture
                    and elapsed < self.request['seconds'] and not pending):
                filename = str(self.directory / 'frames' / ('frame-%06d.png' % self.capture))
                task = unreal.AutomationLibrary.take_high_res_screenshot(640, 360, filename)
                if not task or not task.is_valid_task():
                    raise ValueError('Screenshot task could not be started')
                self.screenshot_tasks.append(task)
                self.capture += 1
                self.next_capture = elapsed + self.request['capture_interval']
            if elapsed >= self.request['seconds'] and not any(not t.is_task_done() for t in self.screenshot_tasks):
                self.finish()
            elif elapsed > self.request['seconds'] + 30:
                self.finish('Screenshot task did not finish')
        except Exception:
            self.finish(traceback.format_exc())


def main():
    match = re.search(r'-OAGDRequest=(?:"([^"]+)"|(.*?)(?=\s+-|$))', unreal.SystemLibrary.get_command_line())
    if not match:
        raise ValueError('Missing -OAGDRequest')
    request = json.loads(Path(match.group(1) or match.group(2)).read_text(encoding='utf-8-sig'))
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).parent.resolve()
    result = {'engine': 'unreal', 'request_id': request['request_id'], 'project': str(project),
              'version': unreal.SystemLibrary.get_engine_version(), 'success': False, 'completed': []}
    try:
        if project != Path(request['project']).resolve():
            raise ValueError('Project identity mismatch')
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if request.get('scene') and not level.load_level(package(request['scene'])):
            raise ValueError('Failed to load requested scene')
        if request['mode'] == 'playback':
            if not request.get('scene'):
                raise ValueError('Playback requires an explicit scene')
            global playback
            playback = Playback(request, result)
            return
        if request['mode'] == 'inspect' and request.get('operations'):
            raise ValueError('Inspect cannot execute mutations')
        for operation in request.get('operations', []):
            result['completed'].append(apply(operation))
        if request['mode'] == 'edit':
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            path = world.get_path_name().split('.')[0]
            package(path)
            if not level.save_current_level():
                raise ValueError('Scene save failed')
            if not level.load_level(path):
                raise ValueError('Saved scene reload failed')
        result['objects'] = inspect_scene()
        result['success'] = True
    except Exception:
        result['error'] = traceback.format_exc()
        unreal.log_error(result['error'])
    save_json(request['report'], result)
    if not result['success']:
        raise RuntimeError(result['error'])


main()

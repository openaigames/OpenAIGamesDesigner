# Runtime and Spatial Observation

[English](observations.md) | [简体中文](observations.zh-CN.md)

The shared protocol is [observation.schema.json](../../schemas/observation.schema.json); registration uses [observation.py](../../tools/observation.py). Raw captures and registration records remain separate; registration never edits evidence. Dependency changes affect historical applicability rather than carrying old passes forward.

```sh
python tools/observation.py --project MyGame register --capture runs/R001/observation.json --id O001 --dependency game/Content/Map.umap
python tools/observation.py --project MyGame show --id O001
python tools/observation.py --project MyGame elapsed --id O001 --start hero:cancel-1 --end hero:cleanup-1
```

Dependencies include actual consumed rules, assets, configuration, and execution records. Do not infer consumers from matching filenames; include sources affecting the conclusion. Engines record exact clocks, objects, input modes, assistance, and sampling costs. The protocol does not contain all engine state or provide deterministic replay.

## Godot 2D

Add [OAGDObservation.gd](godot/OAGDObservation.gd) under a test scene. register_object(id, actual_node, kind), then call mark_event(id, name, details) from actual rule branches. Mark requests, acceptance/rejection, commits, hits, feedback layers, cancellation, and cleanup separately. Missing events cannot be filled with invented hits.

sample_parameter reads live properties. capture(scene, context) reads Node2D world positions, collision bounds/polygons, and Camera2D data. save_capture writes only a new project-local file. Game time accumulates process delta and follows time scale. Shape2D rectangles are boundary proxies, not proof of passage/visibility. Code-created scenes can be read from active nodes; projects explicitly supply IDs/events for extra semantics.

Source fixture tests/fixtures/godot-observation deliberately delays cleanup after cancellation to test observation. Do not copy it as correct combat logic.

## Unreal 3D

Uses Playback from [engine sessions/recovery](sessions.md). Example request:

```json
{
  "engine":"unreal","mode":"playback","scene":"/Game/Map",
  "seconds":3,"capture_interval":0.5,"camera_target":"ReviewCamera",
  "observe":{"interval":0.05,"bindings":true,"max_samples":2400,
    "conditions":["Describe the actual conditions of this run"],
    "actors":[{"id":"hero","target":"Hero","kind":"player",
      "markers":["weapon_r","hand_r"],
      "properties":[{"id":"speed","component":"CharacterMovement","property":"max_walk_speed","unit":"cm/s"}],
      "event_exporter":"ExportObservationEvents"}]}
}
```

event_exporter names an explicitly read-only project UFunction returning a JSON array string. Entries contain id, time, event, optional data; time uses that PIE world's GetTimeSeconds. IDs remain stable within a run; repeated queries may return accumulated records but cannot rewrite events. The tool neither invokes nonexistent universal attack APIs nor infers feedback timing from health/state changes. Projects must guarantee exporter read-only behavior.

Actions are scheduled in **game seconds since first sampling**. Screenshot overhead is not simulated progress; a wall-clock watchdog still bounds stalls. position actions teleport and method actions invoke components; neither is human input. readonly_preview:true rejects edits/actions, but normal game startup logic still runs. Read-only means source assets are unchanged, not a frozen game.

Outputs include observation.json, runtime-bindings.json, frames, frame times, and session records. Binding readback includes real mesh/animation references, parent components, attachments, relative/world transforms, marker existence, and creation methods where exposed. Single-node clips and existing AnimBP references can be read; an unsampled action is not necessarily unavailable to the character.

Spatial records use actual Actor positions/bounds and CameraComponent projection. Bounds are not exact terrain/navmeshes; use collision/navigation queries and real routes for passage/occlusion/reachability. Cameras are not physical obstacles; editor icon bounds are not spatial dimensions. Rotation requests use [pitch,yaw,roll] degrees and named conversion arguments.

camera_target locks screenshots to a specific CameraActor. PNG timestamps record request-world time; completion may be later. Frames contain no audio and capture affects timing, so they are not overhead-free performance measurements. Parameter/binding sample caps explicitly record gaps.

Startup errors retain needs_review even with a successful exit. unreal.automation_culture can pin process language for reproduction; do not suppress unknown errors merely to clean logs.

Native references: [SceneComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SceneComponent), [AutomationLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary).

## Record Review

The workbench has no separate runtime-review page. Use observation.py show/elapsed for records/intervals, inspect original media, or generate comparisons. Capture, revision checks, and annotation APIs remain available.

Records retain independent clocks. Align two observed events with an explicitly chosen time shift rather than assuming shared device clocks. Video interpolation is limited to supplied anchor intervals; register pause/rate segments separately. Image request/capture times do not prove subframe latency.

For spatial analysis, generate XY top views, XZ/YZ sections, or route comparisons from real samples. Position annotations require complete measured 3D coordinates; do not infer an unprojected axis. Check object/time before saving. Comparisons require matching coordinate conventions, units, and scope; matching units alone do not imply matching origins.

Annotations record observations/anchors, not stage approval or issue closure. The same game_workflow task entry and compatible APIs manage tasks; link evidence after professional assessment.

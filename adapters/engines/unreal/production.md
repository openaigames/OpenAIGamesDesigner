# Unreal Production Interface

[English](production.md) | [简体中文](production.zh-CN.md)

## Creation and Startup

[production.py](production.py) maintains Unreal request rules, project descriptors, plugin requirements, and launch commands. The production runner uses the actual Unreal Editor on Windows.

```powershell
python tools/engine_workflow.py create --project "D:/Games/MyUEGame" --engine unreal --editor "D:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --name MyUEGame --version 5.8 --brief "Agreed project scope"
```

Creation produces a content project, explicitly enables PythonScriptPlugin and EditorScriptingUtilities, and loads the project for verification. Add C++ Targets and modules according to the project's technical design; no gameplay framework or sample project is added by default. edit/inspect use Python commandlets. playback uses PIE in a separate editor with asynchronous Python kept alive.

Frame capture and sampling incur editor/capture overhead and do not include synchronized audio. Disable capture_interval for separate performance measurements. Installed plugins do not prove that MCP is connected; record MCP evidence separately.

Shared entry points and recovery: [session management](../sessions.md). Implementation: [production_worker.py](production_worker.py), executed in the real Unreal Python environment, rather than an external Python simulation or native MCP call.

| Operation | Required fields and purpose |
| --- | --- |
| scene | `/Game/...` `path`; `create: true` creates, otherwise opens |
| blueprint | New `path`, `parent_class` (Actor by default), and components (name/type/properties) |
| actor | Exact, unique Actor Label in `target`; creation selects `class` or Blueprint/asset `source` and requires `create: true` |
| import | Absolute source file `source` and target `/Game/...` path; replacement requires `replace: true` |
| animation | target, mesh, and animation or anim_blueprint; optional component name |
| static_mesh_configure | source, new path, asset_role, strategy; derived automatic LOD or Nanite assets, see [mesh resources](mesh-resources.md) |

Actor position/rotation/scale use world XYZ (UE centimeters), Pitch/Yaw/Roll (degrees), and scale. Locate existing components in actor.components by type and optional name. Persistent new components are written into a new Blueprint through SubobjectDataSubsystem, then instantiated; temporary new_object components are not treated as persistent. Existing Blueprint paths are not overwritten, preserving hand-authored graphs.

Properties use actual `set_editor_property` names. Values accept JSON scalars and `{"asset":"/Game/..."}`, `{"vector":[x,y,z]}`, `{"enum":"ComponentMobility.MOVABLE"}`, or `{"class":"/Game/..._C"}`. Extend the interface for complex structures, arrays, or special properties; unsupported types must not be silently ignored. After saving, read back objects, components, and common mesh/material/animation references.

With `mode: inspect`, `mesh_audit` reads static meshes, LOD, Nanite, collision, materials/textures, and instancing candidates in the loaded scene. Configuration creates derived assets only. Verify them in a separate inspect session after saving; the interface does not automatically replace map references or treat asset readback as performance acceptance.

Import uses AssetTools / AssetImportTask and checks actual imported_object_paths. FBX requests can specify skeletal, animations, and skeleton. Format support depends on installed UE import plugins. A successful import does not validate units, materials, bones, or appearance. Use returned paths to track renamed assets and dependencies.

Characters use SkeletalMeshComponent, supporting single-node looping AnimSequences on the same skeleton or binding an existing Animation Blueprint. Skeleton mismatches fail; no implicit retargeting or automatic clip selection occurs. Animation Blueprint authoring, complex retargeting, Montage/Notify, and Motion Matching require project-specific implementation.

Examples: [level and Blueprint components](examples/scene.json), [automated PIE actions](examples/playback.json). Automation operates on the actual PIE world copy and does not save test movement back into the editor scene. Actions support `position`, or `{at,op:"method",target,method,arguments:[]}` to call reflected project methods. They do not send OS keyboard/mouse input or verify Enhanced Input coverage.

PIE uses EditorPythonScripting's keep-alive setting and Slate ticks, explicitly starts and stops play, then closes the editor launched for this session. Recording captures the active PIE viewport as PNGs. World delta sampling includes editor/capture overhead and is not a GPU or complete CPU profile. UE APIs vary by version; retain raw logs and versions for each session. Formal performance tests should use target-platform builds and Unreal Insights.

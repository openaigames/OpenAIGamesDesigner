# Asset Processing and Procedural Generation

[English](README.md) | [简体中文](README.zh-CN.md)

| Task | Tool and contract |
| --- | --- |
| Format conversion, static assembly, decimation | Blender convert / assemble / optimize below |
| Parametric parts, terrain, roads, rooms, scattering | [PROCEDURAL](PROCEDURAL.md), procedural_assets.py |
| Skeleton inspection, retargeting, root/pelvis policies, bounded repair | [MOTION](MOTION.md), motion_workflow.py |
| Reusable character profiles, reference poses, contact budgets | [CHARACTER_PROFILE](CHARACTER_PROFILE.md), motion_profile.py |
| Actual bone sampling after engine import | [Native sampling](../engines/motion/README.md), motion_native.py |
| In-game playback, root motion, foot/hand constraints | [Playback](../engines/motion_playback/README.md), native components |
| Existing Blender scene measurement, baking, export, rendering | [Environment tools (Chinese)](../../skills/game-environment-art/references/environment-tools.md) |

Each tool defines its accepted inputs, outputs, and limitations. Static decimation does not support skinned characters. Preserve source assets, write new revisions, and use asset handoff records to link them to the game objects that use them and to their validation results.

## Blender Conversion, Static Assembly, and Decimation

Uses [asset jobs](../assets/README.md) for submit/run/retry, input snapshots, and artifact registration. Configure the absolute Blender executable. Processing runs separately with --factory-startup --background --disable-autoexec, without connecting to or clearing an open user scene.

## Operation Limits

| operation | Input/use | Output |
| --- | --- | --- |
| convert, default | First GLB/glTF/FBX/OBJ and sidecars, using import/export | processed.glb, processed.blend, or both |
| assemble | Explicit instances referencing main models by inputs index | Movable parent nodes retaining imported hierarchy and requested layout |
| optimize | First static main model and explicit decimate_ratio | Decimated copy plus before/after statistics |

Assembly can use one global decimate_ratio, default 1. Range (0,1] is a target ratio, not an exact count/quality guarantee. Assembly/optimization reject skeletons, object animation, shape keys, and non-Mesh/Empty objects. Characters can use convert with separate skeleton/animation checks; static decimation cannot process skinning.

This interface does not provide automatic retopology, rigging, baking, texture resizing, LOD, collision, or navigation. Edited .blend scenes are not inputs; use dedicated recipes rather than assuming arbitrary scene edits survive.

[blender_environment.py](blender_environment.py) handles existing editable scenes with read-only surface/UV measurement, explicit-mesh standard material baking, static GLB export/readback, and fixed-camera rendering. It reads .blend and writes a new directory without saving the source. See [environment tools (Chinese)](../../skills/game-environment-art/references/environment-tools.md). This does not change convert/assemble/optimize contracts.

These limits apply to this Blender processor. Native UE StaticMesh can use [mesh resources](../engines/unreal/mesh-resources.md) for audits, multi-LOD generation, or derived Nanite configuration, followed by reopen/readback and scene validation.

## Example Request

With both source files already in the game project, save this JSON as a project-local request:

```json
{
  "inputs": ["assets-source/column.glb", "assets-source/wall.glb"],
  "parameters": {
    "operation": "assemble",
    "format": "both",
    "decimate_ratio": 0.65,
    "instances": [
      {"id": "column_north", "input": 0, "position": [2, 5, -0.4], "rotation_degrees": [0, 12, 35], "scale": [1, 1, 1]},
      {"id": "wall_west", "input": 1, "position": [-4, 3, -0.2], "rotation_degrees": [0, 0, 90], "scale": [0.8, 0.8, 0.8]},
      {"id": "column_broken", "input": 0, "position": [-2, 1, -0.7], "rotation_degrees": [65, 0, 15], "scale": [0.6, 0.6, 0.6]}
    ]
  }
}
```

Run `python tools/asset_workflow.py --project "GAME_PROJECT" submit --provider blender --request "PROJECT_RELATIVE_REQUEST"`, then run the returned job ID. Requests use project-relative paths; workers receive absolute immutable snapshot paths. Include glTF/OBJ textures, MTL, bin, and other sidecars in inputs, preserving relative directories. Sidecar indices are not main models.

Stable instance IDs accept letters/digits/underscore/hyphen, length 1–80; requests allow 1–512 instances. position uses meters in **Blender right-handed Z-up coordinates**. rotation_degrees is XYZ Euler; scale is three positive values, default 1. All numbers must be finite. GLB export converts to glTF Y-up; engines must explicitly convert layout coordinates.

Transforms act on parent nodes while retaining imported hierarchy, not flattening children to the origin. Author mirrors in a defined-axis processing step; negative scale is rejected. Repeated assets can vary angle, size, and burial depth. The interface executes explicit layouts rather than randomizing art direction.

## Sources and Evidence

Each run rebuilds from a clean scene into an empty/new output directory. Old artifacts remain intact. Parent nodes use instance IDs and imported objects receive prefixes; reruns do not stack onto prior scenes. Pack eligible texture dependencies before saving blend; reopen checks remain necessary.

processing-report.json records Blender version, all input/sidecar hashes, layout, ratio, per-instance before/after and overall mesh/vertex/triangle/material counts. quality_validation remains not_checked. Mesh statistics do not replace engine draw calls, transparent overdraw, texture, or frame-time measurements.

## Validation

From source root, run `python -B -m unittest discover -s tests -p test_blender_recipes.py -v`. Full maintenance tests are not distributed in runtime bundles. Without Blender, parameter/failure checks run and native round trips skip. Set OAGD_BLENDER to the actual executable to test temporary original models: assembly, decimation, texture packing, both-format reopen, layout/source preservation, repeat execution, and shape-key protection. Tests do not read real game assets.

For Blender integration, set OAGD_BLENDER and run `python tools/run_tests.py`. Retain version, inputs, outputs, and raw logs. Skipped CI tests are not native passes. Fixture geometry/dependency checks are not art acceptance; review real assets in project cameras, terrain, and target runtime.

# Static Asset Integration

[English](STATIC_ASSETS.md) | [简体中文](STATIC_ASSETS.zh-CN.md)

For Godot and UE 5.8. Projects choose assets, replacement targets, and collision policies; tools provide mappings, derived resources, native replacement, and rollback.

## Inputs and Limits

Accepts static GLB 2 with one mesh, one node, and applied transforms. Supports up to eight uniquely named opaque, single-sided, nonemissive scalar PBR materials. Color, roughness, and metallic values map by material-slot name. Textures, transparent/two-sided materials, extensions, skeletons, animation, multiple nodes, and nonuniform scaling are explicitly rejected. Arbitrary off-the-shelf assets are not guaranteed to work directly.

The calibration doorframe is an original project asset. Its recipe is `templates/runtime_static/make_source.py`; exported GLB and provenance are in `templates/runtime_static/assets/`. It tests openings, materials, and LOD, not final art. The example replaces three entrances: flat ground, a ramp, and one retaining graybox collision.

## Create and Run the Example

```powershell
python tools/runtime_components.py create --engine godot --scenario static --project C:/Trials/StaticGodot
python tools/runtime_components.py create --engine unreal --scenario static --project C:/Trials/StaticUE --ue-root D:/UE_5.8
```

For Godot, import first, generate resources/save the scene, then launch:

```powershell
Godot.exe --headless --editor --path C:/Trials/StaticGodot --quit
Godot.exe --headless --path C:/Trials/StaticGodot --script res://build_assets.gd
Godot.exe --path C:/Trials/StaticGodot
```

For UE, compile `OAGDExamplesEditor Win64 Development`, run project `create_map.py`, then run `/Game/Example`. See [runtime components](README.md) for compilation commands. Generation rejects existing maps and derived directories. Failed outputs remain for inspection; retry in a new directory rather than overwriting manual edits.

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/StaticGodot --executable C:/Tools/Godot.exe --visual
python tools/runtime_validation.py --engine unreal --project C:/Trials/StaticUE --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe --visual
```

Godot validation imports and prepares native resources for new examples. UE validation requires compilation and map creation first. Each default case has 64 checks: 24 replacement-resource checks plus 40 traversal checks. Read `failures`; the UE game process may still exit with code 0.

## Integrate with Your Project

Generate or select a `scene.json` baseline. Create a project manifest specifying source hashes, baseline hash, and stable object IDs:

```json
{
  "schema": "oagd.static-assets/1",
  "scene_sha256": "SHA256 of the actual scene.json",
  "assets": [{"id":"portal","source":"assets/portal.glb","sha256":"SHA256 of the actual GLB"}],
  "replacements": [{
    "id":"entry_portal","targets":["entry_wall_left","entry_wall_right","entry_lintel"],
    "asset":"portal","position":[0,0,0],"yaw_degrees":0,"scale":1,"collision":"source_mesh"
  }]
}
```

```powershell
python tools/static_assets.py --project C:/Games/MyGame --scene generated/scene.json --manifest static-assets.json --output C:/Games/MyGame/revisions/static-r01
```

Preparation validates everything before creating a new revision directory. Changed source/baseline, duplicate or missing targets, escaping paths, and unsupported inputs are rejected. The directory contains source copies, original manifest, baseline, target fingerprints, and derived settings. `static_assets.read_plan(folder)` detects modifications to the frozen revision. Prepare a new revision to change settings.

Godot uses `OAGDStaticAssets.prepare_asset` to create `.res`, `apply(plan, baseline, lookup, parent, asset_root)` to replace, and `rollback(receipt)` to undo. `lookup` comes from `OAGDGeometry.load_scene`. UE editor calls `prepare`, `apply`, and `rollback` in `adapters/engines/unreal/static_replacement.py`, depending on `static_meshes.py`, `mesh_contract.py`, and the project's OAGDCore plugin. All target positions, normals, colors, indices, and transforms are checked before application; Godot vertex colors use native 8-bit precision. Mappings must pass preparation; low-level functions do not interpret arbitrary JSON.

Replacement retains original graybox entities and stable IDs, hides their visuals, and assigns replacement IDs to new entities. `source_mesh` uses LOD0 triangle collision and disables old collision. `retain_graybox` replaces visuals while preserving old collision. Originals are not deleted. Receipts support rollback within the current engine session. For cross-session recovery, reopen the preserved baseline; arbitrary editor changes are not automatically merged.

## Native Processing and Checks

Godot [ImporterMesh](https://docs.godotengine.org/en/stable/classes/class_importermesh.html) generates automatic LOD and saves ArrayMesh/PackedScene. Checks read native surfaces, materials, LOD indices, and collision. glTF colors are linear; Godot `albedo_color` stores sRGB, so validation converts accordingly.

UE mesh tools create derived copies, disable Nanite on them, and generate conventional 100%/50%/20% LODs with thresholds 1/0.35/0.12. Full meshes provide complex static collision, not guaranteed dynamic rigid-body simulation. UE 5.8 command-line editors must explicitly load StaticMeshEditor, wait for mesh building, and use native threshold setters before reading back. Imported source assets remain unchanged; their Nanite fallback counts are not original GLB triangle counts.

Source scenes use right-handed Y-up meters; UE scenes use `(-Z,X,Y)*100`. Native UE GLB mesh-local coordinates are `(X,Z,Y)*100`. Replacement Actors add 90° yaw to align with the scene, then project yaw. Bounds readback uses mesh-import coordinates; scene positions, openings, and pillar collisions are checked separately.

Recheck materials, dimensions, LOD, collision, and routes after save/reopen and in packaged builds. LOD data alone proves neither seamless switching nor improved performance. Final art, exact cross-engine appearance, frame-rate benchmarks, manual playtests, arbitrary platforms, and independent handoff require separate validation.

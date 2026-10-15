# Static Scene Integration

[English](README.md) | [简体中文](README.zh-CN.md)

## Workflow Navigation

| Stage | Tool and guide |
| --- | --- |
| Freeze multi-node GLB/glTF and import natively | static_scene; this page |
| Graybox mapping, collision, traversal, persistent rollback | scene_replacement; [replacement](REPLACEMENT.md) |
| Combined cases, dependency packaging, reception in a new directory | scene_handoff; [reception](RECEPTION.md) |

Import freezes dependencies and creates native resources. Replacement handles explicit collision, graybox mapping, and rollback. Handoff verification checks input integrity and the declared entry points.

For graybox replacement, collision, traversal checks, and rollback after import, see [replacement](REPLACEMENT.md). This page covers freezing and native import.

Freeze existing static glTF 2 scenes into traceable revisions and import them as native Godot/UE 5.8 resources. Games own their scenes, models, and materials. Generated outputs do not require OAGDCore, character, or motion components at runtime.

## Inputs and Limits

| Item | Scope |
| --- | --- |
| Files | GLB 2 or glTF 2 with external buffer/PNG/JPEG inside the same directory tree; freezes geometry, UVs, and image bytes into self-contained GLB |
| Scenes | Multiple meshes, empty nodes, hierarchy, instances, duplicate names in the active scene; stable IDs use source node indices, display names remain metadata |
| Transforms | Translation, normalized quaternions, positive uniform scale, equivalent shear-free matrices; nonuniform/mirrored/sheared transforms require explicit baking |
| Geometry | Indexed triangles, floating-point POSITION/NORMAL, optional UV0/TANGENT; textures require UV0; up to two million triangles per mesh |
| Materials | Opaque standard metallic-roughness PBR, base-color/normal/MR/emissive textures, double-sided, KHR_materials_emissive_strength; linear repeat sampling |
| Color | Base-color/emissive are sRGB; normal/MR linear; glTF normals use +Y and UE flips green on import; MR uses G for roughness and B for metallic |
| Rejected | Skeletons, animation, morphs, cameras, vertex colors, UV1, transparency/AO, unknown extensions/compressed textures, remote/data URIs, missing/escaping dependencies, hierarchy cycles, invalid indices |
| Outside import scope | Automatic graybox replacement, collision policies, navigation, LOD, Nanite, custom HLSL/shader/GI migration. Imported instances have no collision |

The single-mesh scalar-material contract of [static replacement](../runtime_components/STATIC_ASSETS.md) is unchanged. Single-mesh and multi-node formats are not interchangeable. Outputs must not overwrite sources, and resource destinations must be new directories. Existing games are not automatically upgraded.

## Freeze and Check

Run from the source root or installed `game-preproduction/runtime`, using absolute project paths.

```sh
python tools/static_scene.py prepare --source SOURCE.glb --output NEW_REVISION
python tools/static_scene.py prepare --source SOURCE.gltf --nodes 3 25 --output NEW_SUBSET
python tools/static_scene.py check NEW_REVISION
```

`--nodes` selects source indices from the active scene, retaining their subtrees and necessary ancestors; names are not guessed. Frozen packages contain `plan.json`, complete `scene.glb`, and unique-mesh `meshes/*.glb`. Plans record dependency hashes, selection, local/world matrices, measured vertex bounds, and triangle counts. Validation reads actual vertices/indices instead of trusting accessor min/max.

Run `check` before copying the complete revision into the target project. Checks neither require sources at their original locations nor write to the original project. Prepare a new revision after file/plan changes. Hashes identify changes; they are not licenses or digital signatures.

## Godot

Copy `godot/static_scene.gd` into the project and place the frozen directory at a location such as `res://assets/revision01/`. In a native Godot import script:

```gdscript
var result = preload("res://static_scene.gd").prepare(
    "res://assets/revision01", "res://assets/native01.scn")
assert(result.ok, str(result))
```

The adapter rechecks frozen hashes, uses GLTFDocument to create a real scene, checks source nodes/local transforms/hierarchy, and saves a PackedScene. `.scn` can embed compressed resources; then use ordinary `load(...).instantiate()`. Projects can find pivots through `source_node_index` metadata and apply their own door rules. The Python entry point validates the full plan; do not skip `check`.

## Unreal 5.8

In a UE 5.8 editor with PythonScriptPlugin / EditorScriptingUtilities, add runtime `tools` and this module's `unreal` directory to Python's search path:

```python
from static_scene_import import prepare, assemble
plan, meshes, readback = prepare(revision_path, "/Game/MyNewImport01")
root, nodes = assemble(plan, meshes, "MyImport01")
# Save into a new level created by the caller; do not overwrite game maps.
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
```

`prepare` uses the native glTF importer in a new content directory and returns actual dimensions, material parameters, texture bindings, and color-space readback. Each source mesh is imported once; instances share it. `assemble` preserves empty pivots and hierarchy as editable Actor attachments, all Movable / NoCollision. Projects choose later static optimization and collision. Failed assembly removes only its newly created Actors; interrupted imports remain in the new output directory for diagnosis. Retry in another directory.

glTF uses Y-up meters. UE mesh-local coordinates and nodes use `(X,Z,Y)*100`; an outer root adds +90° yaw, producing scene coordinates `(-Z,X,Y)*100`. Do not scale meshes by 100 again or apply source node transforms twice.

## Validation and Provenance

Check hierarchy, pivots, materials, and textures after import, after save/reopen, and in target builds.

Original numerical fixtures are generated by `templates/static_scene/make_fixtures.py`. `create(new_directory, color_path, normal_path)` generates geometry and copies supplied textures. Without textures it uses single-pixel fixtures for technical tests only. Tests are in `tests/test_static_scene.py`. Third-party art used in the Clockhill and FPS examples must be supplied separately. Register project assets through `asset_handoff`, preserving sources, dependencies, and actual consumers.

Technical checks establish correct resource consumption, not reconstruction of source-engine custom materials, complete map migration, or human art acceptance.

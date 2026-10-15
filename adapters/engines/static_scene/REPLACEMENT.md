# From Graybox to Multi-Node Static Assets

[English](REPLACEMENT.md) | [简体中文](REPLACEMENT.zh-CN.md)

First freeze/check assets with [static scene import](README.md), then map and replace grayboxes. See [reception](RECEPTION.md) for signed-zero fingerprint compatibility. Both engines share mapping semantics but capture separate native baselines; baselines are not interchangeable. Project coordinates are right-handed Y-up meters. Position/yaw act on the outer asset root while retaining the asset's own root transform.

## Supported Objects

- Godot 4: direct `MeshInstance3D` children of the scene root, identified by `stable_id` metadata, optionally with script-free collision subtrees. Custom scripted nodes are outside this transaction.
- UE 5.8: unattached native `StaticMeshActor` with exactly one `StaticMeshComponent`, identified by `OAGD_ID_<ID>` Actor Tags. Blueprints, custom components, and ProceduralMeshActors retain their project interfaces and are not automatically managed as grayboxes.
- Assets must be checked static GLB/glTF revisions. Skeleton and animation import, runtime destruction, arbitrary shaders, and complete map migration are outside scope.

## Mapping and Collision

See the [door replacement configuration](../../../templates/static_scene/replacement.example.json). Its node indices refer to `make_fixtures.py`; project assets need their own indices and actual `plan_id`. `targets` may include several grayboxes, but each target belongs to one group only. Targets remain present; only visibility/collision change.

| policy | Behavior | Use |
| --- | --- | --- |
| `retain_graybox` | Hide originals, retain collision; new assets have none | Decorative replacement over tuned playable dimensions |
| `source_mesh` + `nodes` | Explicit fixed-mesh triangle collision; disable corresponding old collision | Static buildings, map fragments, fixed boxes |
| `boxes` + `boxes` | Local center/full dimensions per source node, following that node | Door pivots/leaves and regular parts |

Godot source_mesh uses static concave shapes; UE uses ComplexAsSimple on separately copied meshes. Neither is for dynamic rigid bodies or moving doors. Door leaves use boxes in meters. Original mesh collision settings are unchanged. With retain_graybox, visual/collision sizes may differ; choose deliberately and check passage.

## Freeze a Transaction

Capture a native baseline JSON with the adapter's `capture`, then run:

```sh
python tools/scene_replacement.py prepare --project <project> --baseline baseline.json --manifest mapping.json --output <new-transaction-directory>
python tools/scene_replacement.py check <new-transaction-directory>
```

Input paths are project-relative. Output must be a new directory containing frozen `plan.json` and actual dependencies. `check` verifies fingerprints, node tables, asset plans, and file bytes. Original assets need not be overwritten.

## Godot Usage

Keep `godot/scene_replacement.gd` beside `static_scene.gd`. Generate each native PackedScene with `Importer.prepare`. Pass plans to native adapters only after Python `check` succeeds.

```gdscript
var baseline = Replacement.capture(scene_root, ["GrayDoor"])
# Save baseline, freeze/check the transaction, then load plan.
var result = Replacement.apply(scene_root, plan, {"door": load("res://native/door.scn")})
if result.ok:
    var packed = PackedScene.new()
    packed.pack(scene_root)
    ResourceSaver.save(packed, "res://revisions/applied.scn")
# Also available after loading applied.scn in a new process:
var rollback_result = Replacement.rollback(scene_root)
```

Receipts are stored in scene-root `oagd_replacement_receipt` metadata. Saving gives the current scene ownership of imported hierarchy nodes so added collision reloads at the same paths. Each root allows one active transaction; successful rollback permits reapplication.

## UE 5.8 Usage

Add `tools` and `adapters/engines/static_scene/unreal` to editor Python paths. Save grayboxes and their meshes/materials/textures before capturing the baseline.

```python
baseline = replacement.capture(['GrayDoor'])
# After saving baseline and running prepare above:
plan, resources = replacement.prepare_resources(transaction_directory, '/Game/Revisions/NewImport')
receipt = replacement.apply(plan, resources)
# Save a new map revision with EditorLoadingAndSavingUtils.save_map and save receipt JSON.
# Load the map in a new process, then read its receipt:
replacement.rollback(receipt)
```

Resource destinations must be new. Receipt and map are paired files, without a cross-filesystem crash-atomic guarantee. Native state includes physical `.uasset` files and recursive dependency fingerprints, with Asset Registry synchronization before reads. Unsaved edits prevent capture/rollback. Do not rewrite receipts to bypass conflicts.

## Passage Checks and Manual Edits

Call Godot `Replacement.passage(world, start, finish, radius, height)` on a physics frame after collision registration. In a running UE world, include `unreal/ScenePassage.h` and call `OAGDScene::Passage(World, Start, Finish, Radius, Height)`. Both use vertical capsules, start-overlap checks, and full-segment sweeps, not center rays. They do not generate navmeshes or plan detours. Check closed/open doors, frames, headroom, building entrances, and exterior routes separately.

Application validates every managed graybox; rollback validates hidden originals and added hierarchies. Changed position, hierarchy, visibility, material, geometry, or collision rejects the entire operation. Unmanaged objects remain editable. On conflicts, preserve the scene and choose whether to keep edits, create a revision, or restore changed objects; there is no default force overwrite.

Fingerprints normalize transforms to 1e-5 engine units for state comparison, not full project version control. Maps, scripts, global illumination, and project settings are outside rollback scope. Retain native saves and operation reports in project version records.

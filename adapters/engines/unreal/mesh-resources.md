# Static Mesh Audits, Automatic LOD, and Nanite

[English](mesh-resources.md) | [简体中文](mesh-resources.zh-CN.md)

Uses [production sessions](../sessions.md) for project identity, checkpoints, logs, and recovery. Supports native UE StaticMesh assets. Editing creates new `/Game/` assets without replacing scenes or source models. Implemented in [mesh_contract.py](mesh_contract.py) and [static_meshes.py](static_meshes.py).

## Read-Only Audits

The [example](examples/mesh-audit.json) uses `mode: inspect` and `mesh_audit.paths` to select up to 512 package paths, without `.AssetName` suffixes. You can also specify a top-level `scene` and `mesh_audit.include_scene: true` to collect static mesh components in the loaded world. This does not load every partition or run the game.

Results appear under `mesh_audit` in the session's `result.json`:

- Render triangles, vertices, sections, screen thresholds, Nanite settings, material slots, and collision for each mesh and LOD.
- Effective material blend mode, two-sided settings, base-material textures, and instance override texture dimensions. Dependencies may include textures unused by the active shader branch; this is not resident VRAM measurement.
- Consumers and instance counts in the loaded scene, plus instancing candidates sharing mesh/material/mobility/shadow/collision settings. Candidates are not proof that merging is safe; check interaction and independent state.
- Optional `warning_limits: {"triangles":50000,"material_slots":8,"texture_dimension":2048}` are example project filters. No universal thresholds apply when omitted. Single-LOD warnings do not misclassify Nanite meshes as missing LODs.

Conventional LOD triangles on Nanite models are explicitly identified as fallback render data; Nanite source triangles remain unknown. Report DCC source data and per-frame visible geometry separately. Unreadable optional fields return `null` and specific `unavailable_fields`, not zero.

## Derived Configuration

The [configuration example](examples/mesh-configure.json) uses `mode: edit`. Each `static_mesh_configure` entry requires `source`, a nonexistent destination `path`, `asset_role`, and `strategy`. Roles are building/prop/foliage/ground. A request can contain several explicit operations, but is not atomic. After a partial failure, inspect `completed` and the destination directory before continuing.

**Conventional LOD:** use `strategy: lod` and list 2–8 `lods`, including a full-geometry LOD0. `percent_triangles` and `screen_size` must decrease strictly within 0–1; triangle percentages must be positive. Both values are 1 for LOD0. UE StaticMeshEditorSubsystem performs reduction and Nanite is disabled on the derived copy. Percentages are requested targets; actual readback determines triangle counts. Existing hand-authored LODs are replaced only on the copy.

**Nanite:** use `strategy: nanite` and explicitly declare `platform_supports_nanite: true`. This declaration reflects the project's platform decision; the tool does not certify hardware. Materials must be Opaque/Masked. Optional `nanite` settings:

- `preserve_area`: defaults to true for foliage and false otherwise; only foliage can enable it.
- `keep_percent_triangles`: positive and at most 1; `trim_relative_error`: nonnegative.
- `fallback_target`: auto / percent_triangles / relative_error. A corresponding `fallback_percent_triangles` or `fallback_relative_error` requires the matching target so saved parameters actually take effect.

Unspecified Nanite settings and existing conventional LODs are preserved. The operation does not change RHI, engine version, or shared materials. A supported blend mode does not establish acceptance of WPO, wind animation, two-sided overdraw, or target-device performance. Other engine versions require native testing.

If materials do not declare Nanite usage, results include `nanite_material_usage_requires_render_check`. Perform a real render check and follow the project's material workflow. Mesh configuration does not automatically rewrite shared materials.

Optional `lod_for_collision` selects an existing LOD; it does not generate or simplify collision shapes. Changes to fallback or collision LOD can affect collision uses; retest doorways, steps, and shooting occlusion.

## Execution and Acceptance

```powershell
python tools/engine_workflow.py execute --project "D:/Games/MyGame" --request "D:/Games/MyGame/requests/mesh-audit.json" --timeout 600
```

Requests use the existing configuration. After `derived_asset_saved`, start a separate inspect session for the derived path and verify saved LOD counts, actual triangle counts, and settings. Source assets should remain unchanged across sessions. Reusing an existing destination is rejected; failed copies remain for inspection. Record technical checks separately from visual and frame-time acceptance.

This module does not perform automatic instancing or level-reference replacement, texture baking/resizing, HLOD, collision generation, or hardware performance sampling. Use appropriate project tools and retain separate evidence.

Implementation references: [UE automatic LOD](https://dev.epicgames.com/documentation/en-us/unreal-engine/static-mesh-automatic-lod-generation-in-unreal-engine?application_version=5.4), [UE Nanite](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine?application_version=5.4), and StaticMeshEditorSubsystem headers. For native test steps, see `tests/fixtures/unreal-mesh-resources/README.md` in the source root or installed runtime.

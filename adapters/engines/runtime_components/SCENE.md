# Scene Generation and Traversal

[English](SCENE.md) | [简体中文](SCENE.zh-CN.md)

Generate `scene.json` / GLB with `procedural_assets.py`, then connect native navigation. Each game owns its specifications, generated files, rules, and component copies.

## Creation and Execution

```text
python tools/runtime_components.py create --engine godot --scenario scene --project NEW_PROJECT
python tools/runtime_components.py create --engine unreal --scenario scene --project NEW_PROJECT --ue-root UE_5.8_ROOT
python tools/runtime_validation.py --engine godot --project NEW_PROJECT --executable GODOT_EXE --visual
```

Godot imports and runs directly. For UE 5.8, compile OAGDExamplesEditor, run `create_map.py` with editor Python to save meshes, collision, materials, and navigation bounds, then run `/Game/Example`. Use UnrealEditor-Cmd.exe for `runtime_validation.py --engine unreal`. Map creation rejects existing maps; migrate edited maps explicitly or compare specifications in a new project.

Buttons select detours, ramps, narrow doors, low lintels, broken bridges, steep slopes, and isolated rooms. Run route submits a movement request. This is a traversal graybox, not a complete level/menu. Project scripts are in `templates/runtime_scene/`. Godot builds native triangle collision from `generated/scene/scene.json`; UE saves ProceduralMeshComponents from `Content/generated/scene/scene.json` and reads vertices back in tests. Both use the same source; UE converts `(-Z,X,Y)*100`.

## Specification

Add `--scene-spec YOUR_SPEC.json` to `runtime_components.py create` to copy/generate an independent specification and write agent dimensions into that project's UE navigation configuration. The full specification is checked before creation. Traversal examples require at least one query; use `procedural_assets.py build` for query-free static scenes.

`templates/procedural/scene.json` is an editable example. Use `kind: scene`, schema_version 1, meters, Y-up, and counterclockwise source triangles.

| Field | Meaning and constraints |
| --- | --- |
| agent | radius_m/height_m are capsule radius/full height; clearance_m/headroom_m are navigation margins; max_slope_degrees/max_step_m define slope/step limits. Height must be at least the diameter |
| rooms | 1–64 open-top axis-aligned rooms; globally unique id; position is interior floor center; size is interior width/height/depth. XZ footprints cannot overlap |
| ports | Doorways with globally unique id, east/west/north/south side, clear width/height, and offset along the wall. Overlaps and corner-crossing openings are rejected |
| paths | Up to 128 connections between ports of different rooms; each port has at most one connection. width is clear surface width; segments is 4–128 |
| controls | Two cubic Bézier control points; omitted means straight. Horizontal endpoint tangents must follow outward doorway normals. Cusps, degeneracy, and width-induced local folding are rejected |
| gap_segments | Optional missing segment indices for broken/incomplete bridges; no collision or structural connectivity is generated there |
| queries | Start/end room pairs; generate center test points and structural expectations. Native reports supply actual results; expectations are not proven reachability |

Paths become thick triangle meshes and can form ramps. Reported slopes come from generated triangles. Room floors meet path endpoints exactly at interior boundaries to avoid small floor-overhang steps. Lintels and side walls have real collision rather than tag-based passage blocking.

## Reports and Changes

`procedural_assets.py build --spec SPEC --output NEW_DIRECTORY` emits the four standard files. Asset jobs can use the `procedural` provider with `parameters.spec`, retaining existing registration. `validation.json` / `scene.json.navigation` include agent parameters, port positions, path lengths, sampled slopes, clear width/height, failures, and connectivity groups, with native_status not_run.

Native checks use matching agent dimensions, bake Godot NavigationMesh / UE Recast, then query through components. Positive cases must physically move to the target. Negative cases check navigation surfaces at both endpoints but no complete path. Reports include spec_sha256, agent parameters, queried paths, timing, and trajectories. Delivery tools hash project sources separately; a specification hash alone does not identify binary or geometric outputs.

Object IDs are independent of list order. Editing one path preserves other objects, and identical specifications generate identical bytes. Three-way merges preserve nonconflicting local edits at stable-object boundaries; conflicting edits/deletions are rejected. Merges remove specification hashes and old navigation because geometry changes require new traversal checks. Engine/DCC edits not written back into scene.json are invisible to JSON merging.

## Limits

Structural reports inspect declared ports, paths, and dimensions, but do not solve every path intersection, third-room crossing, or extra obstacle. Native baking/movement checks expose those differences. Arbitrary building design, automatic multi-story stairs, open-world streaming, jump links, dynamic terrain rebaking, and avoidance are outside scope. Step settings constrain baking; they do not give the Godot mover arbitrary automatic step-up behavior. Examples use continuous ramps. See [static assets](STATIC_ASSETS.md) for final asset replacement, materials, and LOD.

Default example capsule: radius 0.35 m, height 1.8 m. Navigation: radius 0.5 m, height 1.9 m, slope 35 degrees, step 0.25 m. Reachability applies only to the tested specification, engine geometry, and movement parameters. Technical passes do not replace manual level or art acceptance.

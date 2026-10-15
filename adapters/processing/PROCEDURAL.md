# Specification-Driven Static Models and Small Scenes

[English](PROCEDURAL.md) | [简体中文](PROCEDURAL.zh-CN.md)

The `procedural` provider generates deterministic geometry locally without Blender or a paid service. Use it alongside Blender conversion, assembly, and decimation. It creates static geometry and does not replace a full 3D authoring application.

## Supported Generation

Part specifications support box, ramp, and cylinder, metric dimensions, colors, collision flags, translation-only hierarchy, bounding-box surface attachment, and mirroring. parent references a part ID; attach: "+y" places a part's bottom on the parent's top bound, with position as extra translation. Mirrors use origin-aligned x/y/z planes. Hierarchies propagate translation only; no rotation, booleans, joints, or mechanical solver.

The [parts example](../../templates/procedural/parts.json) includes ground, walls, ramp, platform, and symmetric capped columns. Changing column height moves attached caps. Checks reject cycles/missing parents, duplicate IDs, nonfinite coordinates, tiny dimensions, degenerate faces, triangle-budget overflow, and mirror naming conflicts. Geometry tests cover winding/mirrored normals.

The [terrain example](../../templates/procedural/terrain.json) supports flat/hills/basin/canyon heightfields, straight Z-axis road flattening, rectangular platforms/clearance zones, and seeded scatter with gaps/slope limits. Road edges transition over one grid cell. If the requested count cannot fit, generation fails with the count found rather than silently reducing it. Terrain mode has no curved-road flattening, river erosion, or ecosystems. Separate scene mode provides rooms, ports, and curved road surfaces for dual-engine navigation checks.

Road/platform boundaries subdivide the mesh so coarse grids retain narrow roads. Flat interior regions take precedence over transition bands; overlapping interiors use later-defined regions, with roads after clearance zones. cells sets base resolution; boundary refinement can increase triangles within the budget.

Scatter height/max_slope use final triangles. Slope is rise per horizontal meter, the tangent of the angle; 0.5 is about 26.6°. Height/slope samples use bottom centers, not complete footprint fitting. They do not replace navigation or full grounding checks.

## Generate and Record

Generate independently into a new directory:

```powershell
python tools/procedural_assets.py build --spec templates/procedural/parts.json --output C:/Trials/Generated/v1
```

Outputs are scene.glb, scene.json, spec.json, and validation.json. GLB works with existing browsing/import/Blender workflows; JSON feeds Godot/UE native loaders. Output directories must be empty.

For jobs, revisions, and handoff, use the existing asset interface with the same specification in parameters.spec and empty inputs:

```json
{"parameters":{"spec":{"schema_version":1,"kind":"parts","parts":[{"id":"crate","size":[1,1,1]}]}},"inputs":[]}
```

Save request.json inside the project, then run:

```powershell
python tools/asset_workflow.py --project C:/Games/MyGame submit --provider procedural --request request.json
python tools/asset_workflow.py --project C:/Games/MyGame run --job RETURNED_JOB_ID
```

The provider uses local Python without keys. Four files register as one asset revision; the request freezes the specification and existing handoff handles registration. Structural checks do not prove engine import or audiovisual acceptance. Continue selection/application/validation through asset revisions and handoff.

## Regenerate while Preserving Manual Edits

Generate a new revision, then merge the original baseline, new generation, and manually edited scene.json:

```powershell
python tools/procedural_assets.py merge --baseline C:/Trials/v1/scene.json --generated C:/Trials/v2/scene.json --current C:/Trials/edited/scene.json --output C:/Trials/merged
```

Merging compares complete objects by stable ID. Generator-only changes adopt new results; manual-only changes survive; identical changes merge. Different edits and delete/edit conflicts list IDs and stop without overwriting output. Results retain three input fingerprints and no longer claim to be a complete output of one specification. Blender/engine edits not written back to JSON are invisible.

See [runtime components](../engines/runtime_components/README.md) for engine integration/examples.

## Modular Scenes

kind: scene supports interior room dimensions, ports, cubic paths, and agent clearance/slope analysis through the same four files and asset jobs. See [SCENE.md](../engines/runtime_components/SCENE.md) for fields, engine execution, and limits. Three-way merges remove old navigation/spec_sha256 to prevent reuse of pre-edit traversal conclusions.

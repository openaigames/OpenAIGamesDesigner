# Character Retargeting and Motion Repair

[English](MOTION.md) | [简体中文](MOTION.zh-CN.md)

Use these offline tools to retarget and repair animation for Godot and UE 5.8. Each project defines its bone mappings, contact windows, thresholds, and asset revisions. Existing characters, controllers, AnimBPs, state machines, weapons, and rules are not automatically replaced.

[Character profiles](CHARACTER_PROFILE.md) provide explicit local reference poses, forward/auxiliary-bone diagnostics, fixed calibration of allowed translation bones, controller-velocity-aware support repair, and per-frame scope/total-budget audits. Existing explicit mappings remain compatible.

FBX uses COPY paths and embedded images for supported textures. Reimport and inspect complex material nodes, missing external images, and different material models.

Processed controller-owned animation can use [playback integration and examples](../engines/motion_playback/README.md) with Godot AnimationTree / UE 5.8 AnimBP. Playback has its own save/replacement/runtime-evidence workflow. Offline passes do not imply game-runtime passes.

## Supported Operations

| Feature | Implementation and limits |
| --- | --- |
| Skeleton inspection | Blender reads .blend/FBX/GLB and lists actual Armatures, hierarchy, reference transforms, skinned objects, Action ranges, imported scene frame rate |
| Mapping suggestions | Names/limited aliases produce drafts; ambiguity is unresolved. process requires complete explicit target→source mapping and checks ancestry |
| Retargeting | Transfer reference-relative global rotations in aligned character space, then convert to target-parent local space; preserve target joint distances/bone axes; unmapped bones follow their target parents |
| Root/pelvis translation | Preserve explicitly scaled root motion or zero it. translation_bones explicitly permits nonroot translation; other channels fail rather than being silently removed |
| Isolated rotation spikes | On specified bones, detect a middle frame far from two similar neighbors and repair by quaternion interpolation; no whole-clip smoothing or multi-frame gap filling |
| Support-foot repair | Explicit three-bone chain, support window, pole, and budget; two-bone IK fixes endpoint origin/orientation with fades outside support. Unreachable or over-budget changes fail |
| Loop seams | Smooth only selected nonroot local rotations toward first frame over the tail interval; no travel-zeroing or whole-body/cross-clip naturalness guarantee |
| Revision evidence | New directory per run with an editable `.blend` file in meters, Godot .glb, UE .fbx, evaluated source/before/after captures, repair events, hashes, logs. Failed revisions remain; sources are preserved |

Support points are declared endpoint-bone origins, not inferred soles, ground, or terrain. Without declared contact windows, the tool cannot assess foot sliding. Numerical budgets are project settings, not art-quality standards.

Inputs must be self-contained, skinned export rigs. Targets support standard inheritance and positive uniform Armature scale, not constraints/drivers, negative/nonuniform scale, shear, or animated scaling. Bake source Armature object motion onto a real root bone. Target meshes should belong directly to that Armature. Export/bake representative clips from complex control rigs first. Automatic rigging, penetration cleanup, finger grip, arbitrary style rewriting, and dynamic terrain IK are outside scope.

Targets use linear blend skinning. Preserve Volume dual-quaternion skinning is rejected because GLB/FBX may deform differently. Target mesh-object Action/NLA/drivers are also rejected; clean them explicitly in an export copy rather than silently removing them.

Each source clip reloads the same file's initial state so unkeyed sparse-Action channels do not inherit previous clips. Unkeyed channels retain saved values, not assumed rest pose. Set neutral values explicitly when required. Fractional frame-rate GLB uses explicit timeline conversion; UE FbxFactory accepts integer sampling rates only.

Known compatibility limitation: Blender's tested fractional-rate FBX reimport path extends 29.97 fps durations by about 0.1% despite correct file timestamps. It is not accepted for round trips. Use an explicitly resampled integer-rate export copy or separately validate the timeline before further FBX processing. The corresponding 29.97 fps GLB path supports native Godot reload checks.

FBX loading removes importer-inferred use_connect constraints while retaining hierarchy/reference transforms, allowing child translation keys to evaluate. Otherwise pelvis channels may contain keys without affecting poses. This normalization applies only to loaded FBX copies, not originals or authored .blend settings. Nonroot translation still requires translation_bones. Blender's default importer may retain the original limitation.

## Usage

Run from source root. Installed tools live in game-preproduction/runtime/tools, with adapters/templates beside them. Verify the selected Blender installation locally before production use.

```text
python tools/motion_workflow.py inspect --blender BLENDER_EXE --input source.blend --output inspect-source
python tools/motion_workflow.py inspect --blender BLENDER_EXE --input target.glb --output inspect-target
python tools/motion_workflow.py suggest --source-inventory inspect-source/report.json --target-inventory inspect-target/report.json --source-armature SourceRig --target-armature TargetRig --output mapping-draft.json
python tools/motion_workflow.py process --blender BLENDER_EXE --spec motion.json --output revisions/r01
python tools/motion_workflow.py verify --output revisions/r01
```

Fill the [configuration template](../../templates/motion/retarget-repair.json) with actual files, inspected SHA-256, bone names, and Actions. It is not a universal mapping. alignment_xyzw is a unit quaternion from source Blender world orientation to target, without mirror/scale/translation. Both use world meters, Z-up, object transforms included, and scale_length=1. Clip fps explicitly defines selected source-frame timing; inspect imported frame rate first, particularly GLB keyframes reconstructed at a scene's 24 fps.

Disabled repairs do not run. root_motion.owner=controller requires translation=in_place; animation ownership retaining displacement uses owner=animation, translation=scaled. This defines outputs; game consumers still implement extraction/movement.

Contact start_s/end_s are relative to selected clip start. Leave at least blend_s before/after full support. max_correction_m limits endpoint displacement; max_joint_rotation_deg defaults to 60° and limits each joint relative to the unrepaired pose. Unreachable chains are not stretched or hidden by moving the whole character. Revise settings or author manually, then create a new revision.

## Godot Native Import and Checks

```text
python tools/motion_native.py prepare --revision revisions/r01 --clip walk --engine godot --output native/godot-r01
GODOT_EXE --headless --path GODOT_PROJECT --script ABSOLUTE_RUNTIME/adapters/engines/motion/godot/import_capture.gd -- ABSOLUTE_PATH/native/godot-r01/job.json
python tools/motion_native.py audit --revision revisions/r01 --clip walk --capture native/godot-r01/capture.json --output native/godot-r01/audit.json
```

Creates an independent PackedScene and evaluates real AnimationPlayer/Skeleton3D global poses. Checks frame count, times, duration, root, per-bone positions, rotation changes relative to first frame, and declared foot windows. GLB time origin is explicitly zeroed. Resources retain target skinning and can be adopted into project structure without automatically replacing players.

## UE 5.8 Native Import and Checks

Prepare an import job:

```text
python tools/motion_native.py prepare --revision revisions/r01 --clip walk --engine unreal --destination /Game/Motion/WalkR01 --output native/ue-r01
```

Set child-process OAGD_MOTION_JOB to the absolute job.json path, then run:

```text
UnrealEditor-Cmd.exe PROJECT.uproject -run=pythonscript -script=ABSOLUTE_RUNTIME/adapters/engines/motion/unreal/import_motion.py -nullrhi -unattended
```

Enable PythonScriptPlugin and EditorScriptingUtilities. The script accepts only new /Game/ destinations, imports SkeletalMesh/Skeleton/AnimSequence, and saves dependencies. Reference round trips use DefaultRecorderBoneCompression and record the actual compressor; resample after choosing game compression. FBX uses an Armature wrapper removed by UE, preserving root topology. A temporary centimeter export copy transforms rig, skin, and translation keys together so importer wrapper scaling does not cancel motion. Editable metric sources/GLB remain unchanged. Default neutral materials do not establish material integration.

For independent sampling, copy [OAGDMotion](../engines/motion/unreal/OAGDMotion) into Plugins/OAGDMotion of an authorized test project, enable, and compile for UE 5.8. This is an optional test consumer, not a required game dependency.

```text
python tools/motion_native.py capture-job --revision revisions/r01 --clip walk --import-record native/ue-r01/import.json --output native/ue-r01/capture-job.json
UnrealEditor-Cmd.exe PROJECT.uproject /Engine/Maps/Entry?game=/Script/OAGDMotion.OAGDMotionCapture -game -MotionJob=ABSOLUTE_PATH/native/ue-r01/capture-job.json -nullrhi -unattended
python tools/motion_native.py audit --revision revisions/r01 --clip walk --capture native/ue-r01/capture.json --import-record native/ue-r01/import.json --output native/ue-r01/audit.json
```

Sampling seeks a real game-world SkeletalMeshComponent to each time, calls TickAnimation/RefreshBoneTransforms, and reads back. It verifies native evaluation/round-trip precision, not human input, natural-time playback, AnimBP blending, root extraction, cancellation rules, or packaged games. Existing consumers still use engine_workflow.py Playback and animlab /2; independent scenes cannot replace their acceptance.

## Results and Handoff

report.json.ok covers processing and configured numerical checks only. verify checks unchanged input/output revisions. motion_native audit additionally verifies native readback and asset hashes, with default 2 mm positional and 0.2° rotation-change residuals. These are round-trip tolerances, not contact or art thresholds.

Changed sources/imports invalidate old evidence. Before production integration, register source, target, configuration, outputs, engine consumers, and playback evidence through asset revision/handoff records. oagd.motion-capture/1 is offline comparison, not animlab /2 runtime sampling. Generate fresh /2 evidence from actual consumers for existing pipeline gates.

References: [Blender bone spaces](https://docs.blender.org/api/4.5/bpy.types.Bone.html), [Godot GLTFDocument](https://docs.godotengine.org/en/stable/classes/class_gltfdocument.html). UE integration follows native FbxMainImport, SkeletalMeshEdit, and SkeletalMeshComponent behavior and requires actual engine verification.

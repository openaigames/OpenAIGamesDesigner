# Character Profiles and Retargeting

[English](CHARACTER_PROFILE.md) | [简体中文](CHARACTER_PROFILE.zh-CN.md)

Character profiles define bone mappings, reference poses, orientation, and contact calibration for offline processing and runtime playback. They belong to game projects. Shared tools parse, retarget, and perform bounded repairs without a global character database or attack/quest/damage rules.

## Entry Points

tools/motion_workflow.py process accepts existing oagd.motion/1 explicit mappings and configurations referencing oagd.character-profile/1. Existing configurations need no migration. Examples: templates/motion/character-profile.json and profile-motion.json. Replace files, rigs, hashes, and calibration values first.

```sh
python tools/motion_workflow.py validate --spec project/motion.json
python tools/motion_workflow.py process --blender BLENDER --spec project/motion.json --output NEW_REVISION
python tools/motion_workflow.py verify --output NEW_REVISION
```

validate checks configuration/file identity; process reads/evaluates actual rigs. Output directories cannot be overwritten; failed revisions remain. Update referenced SHA-256/revision after changes and obtain fresh engine/game evidence.

## Profile Contents

| Field | Meaning |
| --- | --- |
| id, revision | Project-owned identity and positive integer revision |
| source, target | Profile-relative assets, SHA-256, explicit Armature names |
| roles | Source/target names for 16 humanoid roles; no renaming to template bones required |
| coordinates | Actual processing-copy units, up, anatomical forward; meters/Z-up with horizontal ±X/±Y forward and computed alignment |
| reference_pose | Local xyzw quaternions relative to original bind rest and calibration evidence; no changes to bind matrices, meshes, lengths, or weights |
| unmapped_bones | Explicit source ignore / target inherit_rest for every extra bone; unknown bones cannot disappear silently |
| root_motion | Ownership, in-place policy, translation scale, allowed translating roles |
| clip_policies | Repair windows/chains/poles/budgets and optional fixed translation calibration, such as pelvis |
| repair_budget | Whole-clip world-position/local-rotation/change-frame limits, separate from individual contact budgets |

Roles are root, hips, spine, head, and left/right thigh, shin, foot, upperarm, forearm, hand. This convenience format targets the specified humanoid structure. Nonhumanoids can retain explicit motion configurations. Names use ASCII for the Godot/UE examples; case-colliding names are rejected.

Source ignore means no direct target track. If it is an ancestor of a mapped bone, its motion still affects that bone's evaluated global pose. Target inherit_rest follows the real parent with original local rest transform. Automatic twist distribution, finger inference, and weight repair are not provided; prepare an explicit export rig or dedicated workflow.

## Reference Poses and Calibration

Reconstruct reference poses from original rest plus declared local rotations. For each mapping, source-current global rotation × inverse source-reference gives relative motion. Align character coordinates, apply to target-reference rotation, then recover target-parent local rotation. Target lengths/bind rest remain unchanged.

translation_offsets_m provides constant target-character-space meter offsets by role, only for nonroot bones permitted by translation_roles, such as pelvis. This is reference calibration before the repair baseline, not dynamic IK/terrain adaptation. Repair comparisons exclude declared calibration; configuration and profile-diagnostics.json retain its evidence separately.

Checks verify actual bones, ancestry, shoulder/hip sidedness against forward, and complete extra-bone policies. Inspect poses/forward on real meshes: skeleton positions do not prove that faces/toes point correctly.

## Contact Coordinates for In-Place Locomotion

Contact rules may declare controller_velocity_mps: [x,y,0], the clip's calibrated constant speed in target Blender world meters. Nonzero values require controller-owned in-place motion.

```
Target ankle(t) = first actual support position - controller velocity × (t - first sample time)
Contact drift = actual ankle position + accumulated controller displacement - first sample position
```

The solver changes only declared three-bone chains, windows, and fade edges, preserving lengths and using explicit poles. Repairs fail if their targets are unreachable or exceed the configured limits. Rules without velocity retain fixed world anchors. Projects supply support windows; automatic fits/suggestions are not approvals.

tools/motion_playback.py::profile_settings reads observation-bone maps and walk/run contact speeds from processed results. checked_bindings rejects inconsistent bones/speeds, preventing offline/runtime speed mismatches. Playable templates require Blender -Y anatomical forward; normalize other orientations in copies. Generic offline retargeting does not share that template restriction.

This is constant-speed, flat-ground offline calibration over declared support intervals. See [locomotion](../engines/motion_playback/LOCOMOTION.md) for runtime turns/blends and [constraints](../engines/motion_playback/CONSTRAINTS.md) for terrain contacts.

## Repair Scope and Evidence

Each clip outputs evaluated before/after/source captures and *-repair-scope.json. The audit reconstructs local changes from actual transforms and checks undeclared bones/times, translations, world changes, and changed-frame ratios. Descendant world changes caused by ancestors are listed separately. Solver targets alone do not replace post-bake evaluation.

Native Godot/UE captures independently read imported assets using the same contact coordinates. Runtime checks separately measure world feet; an offline curve with assumed controller displacement is not runtime evidence. Inspect skinning, sole gaps, and arm-lift direction visually.

Fractional rates such as 29.97 use explicit offline/GLB timeline handling. UE FbxFactory sampling rejects noninteger rates, and playable templates require 30/60 fps. Perform and record real resampling; changing the FPS label is insufficient.

# Optional Foot Contacts and Grip

[English](CONSTRAINTS.md) | [简体中文](CONSTRAINTS.zh-CN.md)

The audit scripts referenced below are maintained in the source repository and are not included in installation bundles.

Use `constraints.mode = contacts_v1`. feet and grip are independently optional and do not require root motion. Supports native Godot and UE 5.8 playback.

## Integration Points

- Godot: oagd_constraints.gd is a SkeletonModifier3D child of Skeleton3D, modifying bones after source animation. With manual animation, set the skeleton's manual callback, call prepare, advance animation, then Skeleton3D.advance. Read final bones at modification_processed.
- UE: UOAGDConstraintsComponent manages inputs, physics queries, and props. FAnimNode_OAGDConstraints follows the source pose; UAnimGraphNode_OAGDConstraints is editable. Existing AnimBPs can use it without changing movement frameworks. Queries run on the main thread in PreUpdate; Evaluate reads snapshots. Props attach and results publish after final bone refresh.
- motion_playback.py create validates bone names/parameters and creates independent Contacts examples from constraints_main.gd / ConstraintsGame.*. stage replaces assets only, not project code.
- Examples require eight base clips plus hold/carry. Existing games can use their own clips, input, and contact windows.

## Data and Responsibilities

feet specifies pelvis, continuous three-bone left/right chains, sole_offset_m, probe_up_m, probe_down_m, max_step_m, max_slope_deg, max_pelvis_m, blend_s, and knee_pole in character-local [forward,right,up]. Probes use world up. Calibrate contact goals to actual ankle-to-sole distance. Pelvis compensation is bounded downward motion; two-bone IK never stretches bones.

grip specifies main_hand, a three-bone offhand chain, blend_s, and elbow_pole. sockets.godot/unreal explicitly provide main/support position and rotation_xyzw. Positions are local socket values in Godot meters or UE centimeters. Importer bone axes differ; do not copy quaternions directly. main describes prop relative to main hand; support describes support hand relative to prop. Socket frames remove bone scale, preserving prop geometry dimensions.

Each frame projects supply grounded, left/right stance weights, and offhand contact. Components do not infer which clip is planted or holding. Examples derive windows from actual clip clocks: both feet in standing, declared support phases in walking. hold/carry already place hands in front of the body; IK only closes contact differences.

Godot: `configure(actor, settings, excluded_rids)`, `prepare(dt, grounded, Vector2(left,right), contact)`, `take(prop, both)`, `release()`, `reset()`.

UE: `Configure(mesh, json)`, `Prepare(dt, grounded, contacts, contact)`, `Take(prop_component, both)`, `Release()`, `Reset()`. Submit frame inputs before native mesh animation updates.

Normal windows blend over blend_s. Explicit cancel, release, or target loss removes hand constraints immediately. Props retain world pose on release; dropping physics/inventory rules belong to the game. Retaking creates fresh constraints. Single-hand mode does not enable support-hand IK.

## Results and Limits

Foot states: disabled, contact, swing, airborne, no_ground, slope_limit, step_limit, unreachable. Hand states: released, attached, single_hand, window_closed, contact, missing_target, unreachable. Rejection never stretches chains. Ground/support loss or airborne state releases foot contact. Inspect weights, pelvis_offset / Result.Pelvis, goals, and actual bones; goals alone do not prove contact.

Scope includes static planes, bounded slopes/steps, biped three-bone chains, and main-hand-attached one/two-hand props. UE probes previous-frame foot XY for a local plane, then projects the current source pose, introducing one-frame edge-query latency. Fast terrain-boundary crossings, moving platforms, nonuniform skeleton scaling, quadrupeds, finger fitting, self-collision elimination, and network prediction are unsupported.

step_down / foot_reach use fixed-height fixtures. steep / high_step use surfaces visible to foot rays but nonblocking to capsules, isolating fallback checks. air_land uses real movement jumps/landings. These do not establish stair climbing. Root-motion examples keep their movement ownership; composition must define ownership explicitly. See the [combined example](../../../templates/engineering_example/README.md).

## Reproduction

`python tools/motion_playback.py create --project NEW_DIRECTORY --engine godot|unreal --revision VERIFIED_REVISION --bindings BINDINGS_JSON [--ue-root UE58_ROOT]`

Run generated native prepare, then launch. E takes, Q releases, Space jumps, WASD moves. Report arguments run fixed cases. `tests/scenarios/motion_constraints_audit.py REPORT BINDINGS --output AUDIT` checks bones, segment lengths, contact error, release, and fallback. Record native visual review separately; scripts do not establish finished animation or human acceptance.

Godot evaluation/readback follows [SkeletonModifier3D](https://docs.godotengine.org/en/stable/classes/class_skeletonmodifier3d.html). UE uses native AnimNodeBase, BoneContainer, and SkeletalMeshComponent APIs.

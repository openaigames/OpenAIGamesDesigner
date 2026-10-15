# Ground Root Motion

[English](ROOT_MOTION.md) | [简体中文](ROOT_MOTION.zh-CN.md)

The audit scripts referenced below are maintained in the source repository and are not included in installation bundles.

Optional `planar_v1` mode gives animation root translation to native character physics. Ordinary in-place clips remain controller-driven. Each game owns its components, graph, character, and rules.

## Contract and Scope

```json
"root_motion": {
  "mode": "planar_v1",
  "vertical": "physics",
  "rotation": "controller",
  "transition_s": 0.0
}
```

Animation-owned entries explicitly use `motion_owner: "animation"`, `in_place: false`, and `loop: false`; controller entries retain controller / true. Checks cover processing reports, all root samples, and a shared target reference skeleton. Root height changes, root rotation, zero displacement, looping root clips, layers, and continuous locomotion graphs are rejected. Planar motion can point in any direction; projects choose facing before starting.

The example switches states immediately to avoid residual blend-tail displacement. Roll body rotation is on the hips; root supplies the ground trajectory, while physics/gravity control height. This is not arbitrary 3D root transforms, Motion Warping, networking, or foot IK. Other graphs can integrate native systems after verifying extraction/collision semantics.

## Generation and Integration

1. Use `motion_workflow.py process` to create an independent revision with `owner=animation, translation=scaled`, retaining the actual root trajectory.
2. `motion_root.py --base IN_PLACE_REVISION --rooted ROOT_REVISION --output NEW_COLLECTION` combines verified results on the same target skeleton. Originals remain unchanged; clips retain their policies/dependencies.
3. Add the policy and root clips to complete bindings, then use `motion_playback.py create --engine godot|unreal --project NEW --revision NEW_COLLECTION --bindings BINDINGS [--ue-root UE_5.8]`. The template also requires the original eight clips plus animation-owned dash/roll. These names are sample conventions, not shared component restrictions.
4. Native prepare creates AnimationTree/editable AnimBP. Templates select Godot root_main.gd / UE RootGame. Asset upgrades still use stage → prepare → activate, but stage cannot silently switch movement consumers between root and older modes. Create a new example or explicitly adapt game code.

`author_root_sample.py` is a reproducible recipe for the CesiumMan example character, not a universal generator. It preserves meshes/weights, writes dash/roll trajectories and poses on the source skeleton, and calibrates hip height from evaluated skinning's lowest point. Preserve character provenance/license with the project.

## Godot

`prepare.gd` finds the common root position track and sets `AnimationTree.root_motion_track`. `OAGDPlayback.configure(tree, clips, {}, root_policy)` checks immediate transitions; advance evaluates natively. Final nonlooping frames are capped to remaining time so speed changes do not overextract distance.

`oagd_root_motion.gd` exposes `configure(playback, CharacterBody3D, Skeleton3D)`, `start(id, restart=false)`, `cancel()`, `prepare_step()`, and `step(dt, controller_velocity)`. Each physics frame calls prepare_step, chooses controller input, then calls step once. Do not also move through another motor. Root delta is in Skeleton3D space, including imported rotation/scale, not just the model wrapper transform. See [AnimationMixer](https://docs.godotengine.org/en/stable/classes/class_animationmixer.html).

## UE 5.8

Root sequences enable bEnableRootMotion and first-frame root lock; AnimInstance uses RootMotionFromEverything. CharacterMovement extracts/consumes delta; projects must not additionally translate Actors. UOAGDRootMotionComponent manages ownership, cancellation caches, and final-frame handback. Its post-conversion callback reads actual extraction and constrains it to the plane; Configure rejects an occupied callback.

RootGame explicitly sets bTickBeforeOwner=false. Movement depends on character input Tick; mesh retains native post-movement evaluation. Call PrepareStep before input each frame, and do not AddMovementInput while Active. Completion does not cancel immediately: the next PrepareStep cleans up after physics consumes the final displacement. Cancellation clears old root caches, velocity, and input. Reentry starts a new generation without resetting character position.

## Validation and Delivery

Templates accept Godot `--report=... --fps=60` or UE `-MotionReport=... -UseFixedTimeStep -FPS=60`. Fourteen cases cover both actions, diagonals, wall impact/sliding, slow/fast/changing rates, pause, cancel, reentry, restart, movement after completion, and takeover while moving. E dashes, F rolls, Q cancels, WASD moves. Programmatic input is not OS input or human playtesting.

`tests/scenarios/motion_root_audit.py` checks actual capsule positions, extracted delta, bones, and events with 167 assertions. Run source, packaged, and received projects separately; an output file alone is insufficient. Technical samples do not establish production animation quality, arbitrary character adaptation, all-pose penetration freedom, or capsule shrinking during rolls.

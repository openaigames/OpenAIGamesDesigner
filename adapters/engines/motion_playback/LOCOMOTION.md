# Continuous Locomotion Blending

[English](LOCOMOTION.md) | [简体中文](LOCOMOTION.zh-CN.md)

Optional Godot AnimationTree and UE 5.8 AnimBP implementations. Projects own input, speeds, acceleration/deceleration, turning, jumping/landing, and assets. Shared components receive actual horizontal speed and evaluate animation. Existing oagd.playback/1 bindings without locomotion retain discrete playback.

## Configuration and Prerequisites

Explicitly add to project bindings:

```json
"locomotion": {
  "mode": "speed_phase",
  "acceleration_mps2": 3.0,
  "deceleration_mps2": 4.0,
  "turn_speed_deg_s": 240.0,
  "transition_s": 0.18,
  "contact_phase": {"L": [0.16666666666666666, 0.3333333333333333], "R": [0.6666666666666666, 0.8333333333333334]}
}
```

These phase windows belong to the technical examples and must not be copied onto unknown clips. Phase is clip time divided by full-cycle duration. motion_playback create/stage checks that walk/run processed contact intervals, excluding repair fades, both cover each foot's declared window. Missing/reversed support is rejected. It neither discovers phases nor rearranges frames automatically. Calibrate source motion before building the graph.

idle/walk/run must loop without clip events. Walk speed must be below run speed, using calibrated character-profile values. Assets remain in-place and controller-owned; all processed samples are checked for root translation/rotation. locomotion is a reserved generated state name. The original eight clips remain independently playable.

## Runtime Behavior

Components compute idle/movement and walk/run weights, then derive cycle frequency from blended stride length. Each clip's rate scales with its duration so a 1-second walk and 0.6-second run share foot phase. Low speeds blend idle; higher speeds blend run. Releasing input does not instantly select idle: actual deceleration reduces movement weight.

- Godot: configure_locomotion(speeds), set_locomotion_speed(actual_speed), select locomotion, then advance(delta). Nested Blend2 nodes use sync=true so zero-weight clips update. TimeScale aligns cycles; locomotion_times returns native child clocks.
- UE: UOAGDPlaybackSet stores enablement/calibrated speeds. Call SetLocomotionSpeed after OnCharacterMovementUpdated. Editable TwoWayBlend/SequencePlayer sync groups retain zero-weight updates; WalkTime/RunTime are read after evaluation. Playback is not simulated with per-frame SetPosition.
- Examples use real CharacterBody3D/CharacterMovement collision. Project code handles horizontal acceleration and limited turning. Characters face movement; side input turns them, without separate strafe/backward clips.
- Jump/fall/land/full interaction remain outer states with configured transitions. Rapid speed changes stay in locomotion without resetting cycles. Full-body interaction locks movement; see [layers](LAYERS.md) for upper-body overlays.
- P pauses/resumes the whole example, freezing bones, blends, and movement. E interacts, Q cancels, R restarts. Playback rate alone affects animation; projects must freeze physics separately if needed.

Existing graphs are not replaced automatically. Use create for new templates, or stage → native prepare → activate for projects already using them, preserving old graphs/bindings. Integrate complex existing graphs through these interfaces rather than overwriting them.

## Checks and Limits

Native records include child clocks, weights, horizontal speed, bone world transforms, facing, pause state, and actual timestep. Measure drift separately for steady walking/running/intermediate speed, starts/stops, speed changes, and turns. Category changes do not reset the anchor within one contact window. Check pose continuity in character space and separately exclude explicit restart teleports.

This is not foot locking or motion warping. Foot-slide conclusions apply only to declared flat-ground contact windows. Sharp turns may slide; dedicated starts/stops, 180-degree turns, strafing, backward movement, and moving landings are not supplied here. Technical sample steady-state quality does not establish transition quality. Loose turn-diagnostic budgets are not final animation acceptance criteria.

Locomotion uses in-place clips and explicit support windows. See the corresponding modules for root motion, terrain IK, and hand constraints.

# Optional Stepping Turns

[English](TURNING.md) | [简体中文](TURNING.zh-CN.md)

The audit scripts referenced below are maintained in the source repository and are not included in installation bundles.

The example decelerates, performs left/right 45°/90°/180° stepping turns on flat ground, and restarts. Editable clips are authored from the calibrated character's real idle pose. Controllers own displacement/facing; native animation graphs evaluate skeletal poses. It uses no runtime foot IK and does not require existing games to replace movement systems.

## Authoring and Integration

```powershell
python tools/motion_turns.py --base VERIFIED_PROFILE_REVISION --output NEW_TURN_REVISION --blender BLENDER_EXE
```

Input must be a verified character-profile revision with Blender -Y forward, hips/thigh/shin/foot mappings, and a real skinned idle. Outputs retain eight base clips and add six turns with .blend, GLB, FBX, evaluated captures, turns.json contact intervals, and an authoring report. Use a new directory; originals remain unchanged. The recipe authors clips directly on the calibrated target skeleton. Other rigs require their own calibration and validation.

Each 45° uses 0.6 seconds with two foot changes plus 0.2-second entry/exit: 45° takes 1 second, 90° 1.6 seconds, 180° 2.8 seconds. Offline baking preserves support-foot world position/orientation with a 7.5 cm swing arc. Authoring checks actual bone drift, pose steps, and skinned minimum height; native validation remains necessary.

Add six nonlooping, event-free clips and explicitly configure:

```json
"turning": {"mode":"step_turn_v1","trigger_deg":30,"settle_s":0.2,"recover_s":0.2},
"turn_observation_bones": {
  "dst_hips":"Actual hip bone", "dst_thigh_L":"Left thigh", "dst_shin_L":"Left shin",
  "dst_thigh_R":"Right thigh", "dst_shin_R":"Right shin"
}
```

This policy depends on locomotion. CLI checks all six clips, durations, mappings, and verified authoring manifests. Use motion_playback.py create/stage. Existing projects must explicitly upgrade their copies, run native import, and activate; toolkit installation does not rewrite games.

## Project Runtime Rules

- At least 30° input/body deviation triggers deceleration along current facing, a 0.2-second wait, then the nearest 45°/90°/180° turn. Smaller angles use ordinary turning.
- Translation stops while turning. Facing follows actual clip position: after AnimationTree advance in Godot, or native progress at world-frame end in UE. No separate accumulated clock substitutes for animation time.
- Changed/released input waits until both feet settle in the current step before resuming/reselecting direction. Pause freezes movement, animation, and turning; restart clears turn state.
- The template blocks full-body interaction/jumping during turns. Games may choose different rules but must revalidate contact evidence after timing/rotation changes.
- Both engines retain 60 fps turn sampling. Convert Blender/engine rotation signs using character forward so support feet do not circle the wrong way.

## Validation and Limits

motion_turning_audit.py in tests/scenarios measures real support drift, including entry blend, foot orientation, knees, pause, and input recovery. motion_turning_roundtrip.py compares source/native poses after blending. Retain consumer hashes and runtime reports; offline target trajectories are not engine evidence.

This flat-ground technical example responds more slowly than direct rotation because it decelerates and steps. It does not provide high-speed curved runs, sprint stops, strafing, backward motion, terrain IK, motion warping, or production animation quality. Drift thresholds are case-specific; tune for body size, camera, and game feel.

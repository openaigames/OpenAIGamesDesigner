# Multi-Source Animation Regression

[English](motion_regression.md) | [简体中文](motion_regression.zh-CN.md)

motion_regression_audit.py reuses motion_layers_audit.py coordinate/report adapters. It is a defined technical-case auditor, not a universal animation-quality score.

## Inputs and Actual Consumers

- Two skinned characters, CesiumMan and RiggedFigure, with original assets, target rigs, weights, and explicit profiles.
- Source one: original technical clips. Source two: a 1.9-second interior segment of CesiumMan's public animation, evaluated at 24 Hz subframes and resampled to 30 Hz. It is neither a complete seamless loop nor a newly acquired mocap library.
- Retargeted external_gait has 58 frames; nonlooping full_external binds it with start=0, pulse=0.65, finish=1.9-second markers.
- Project scripts explicitly verify rig/profile/dependencies/exports/hashes when combining processed results for one target.
- Run native Godot AnimationTree and UE 5.8 AnimBP in editable projects and packaged Windows programs.

## The 12.4-Second Scenario

| Time | Action |
| --- | --- |
| 0.5 s | Full-body clip at normal rate |
| 3.5–5.9 s | Controller moves forward |
| 3.6 s | Same clip on upper body while moving |
| 7 s | Full body at half rate |
| 11 / 11.25 s | Full-body request / cancel |

Independent baselines use matching steps/controller/path without action layers. Run fixed 60 Hz and actual alternating 30/60 Hz. Baselines must match sampling times and cannot be copies of tested records.

```text
python tests/scenarios/motion_regression_audit.py runtime.json baseline.json external-revision bindings.json
```

At full weight, compare native bones to DCC capture with 2 mm position and 0.2° rotation-change magnitude tolerances. Outside upper masks, require below 0.1 mm / 0.02°. Matching magnitudes alone do not prove rotation axes or skin quality; inspect front/side views. Emit adjacent audit.json and nonzero failure exits.

Check four accepted requests, one cancellation, event order/duplicates/times, final cleanup, aliases, and variable steps. Deliberately corrupted timestamps/events/weights/bones test auditor rejection and are counted separately from real pipeline negatives.

## Replacement and Negative Cases

Run old aliases first, then stage the new collection, import, activate, and repackage. Verify rejection of activation before import, changed bindings after import, and changed exports after import, with current bindings preserved. Retain old directories/failure evidence.

Processing negatives include swapped sides, incorrect forward, nonuniform scale, and missing target dependencies. Binding negatives include out-of-range events. This project's skinned-height contract is 1.8 ± 0.036 m; use it to detect 100× scaling without inventing universal human-height limits. Include captures with deliberately reversed arm motion as negative fixtures.

## Cost and Actual Input

Predefine 1/16 characters, two runs each in order 1/16/16/1, rendered at 1152×720. Warm up 5 seconds, sample 15. Disable screenshots/large bone reports; use real wall time, records identifying the actual native instances, and process CPU/memory. Check counts, unique animation objects, staggered phases, and clock errors. Report percentiles/tails/build/hardware/renderer. Different engine render configurations cannot be ranked directly.

Run window-input checks separately from cost sampling. Identify assistant versus human input, taps versus holds versus replay, and only count observed actions. Automated cancellation/turning checks supplement but do not replace window operations.

Input tools may report logical keys correctly but physical identities incorrectly. Diagnose both before changing tests; isolated tests may use explicit logical bindings while production keeps physical mappings. Test holds/releases through Godot Input.parse_input_event and UE APlayerController::InputKey rather than directly setting movement wishes/calling action handlers. Positive jump cases must start in a jump-eligible state, not during turn locks. Label OS pulses and engine injection separately.

## Scope

Public gait tests verify transfer/playback, not foot contacts, seamless loops, or final game-specific quality. Root motion and constraints use their own validation entry points.

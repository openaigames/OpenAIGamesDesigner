# Native Locomotion Cases

[English](motion_locomotion.md) | [简体中文](motion_locomotion.zh-CN.md)

Uses two calibrated characters with shared windows L=[1/6,1/3], R=[2/3,5/6]. This is a case contract, not a gait detector. motion_locomotion_audit.py audits only the 22-second native example timeline, using standard-library code without starting/simulating engines.

Create with motion_playback, add explicit locomotion bindings, prepare natively, and activate. For Godot, use `-- --report=<absolute.json> --scenario=locomotion --fps=30`; add `--variable-fps` to alternate physics updates between 30 and 60 Hz. For UE or its packaged build, use `-MotionReport=<absolute.json> -MotionScenario=locomotion -UseFixedTimeStep -FPS=30`; add `-MotionVariableFps` to alternate update rates. Programmatic input is not human playtesting.

`python tests/scenarios/motion_locomotion_audit.py <runtime.json>` reads actual bones, clocks, facing, displacement, and events into adjacent audit.json. It checks steady walk/run/intermediate speeds, starts/stops, speed changes, turns, jump/land, pause, rapid reversal, cancellation, fade reentry, restart, and forward movement of the shoulder and elbow independently. Insufficient native samples fail. Contact anchors cannot reset during speed/turn changes within one window.

The 20 cm turning limit is a technical diagnostic budget, not final foot-slide quality. Use dedicated assets/constraints for drift exceeding project tolerance. Inspect actual thresholds, per-window residuals, and failure times, not only top-level ok.

# Optional Native Playback Examples

[English](README.md) | [简体中文](README.zh-CN.md)

tools/motion_playback.py copies templates into new projects. Projects own assets, mappings, speeds, input, and rules. Existing projects replace assets through stage → native prepare → activate; update component code through [installation/migration](../../docs/INSTALLATION.md).

| Example | Configuration/behavior |
| --- | --- |
| [Basic playback](../../adapters/engines/motion_playback/README.md) | Controller movement; project-driven states/events |
| [Locomotion](../../adapters/engines/motion_playback/LOCOMOTION.md) | Acceleration, turn speed, gait phases, jump/land transitions; P pauses |
| [Stepping turns](../../adapters/engines/motion_playback/TURNING.md) | Flat-ground turn authoring, stop/restart calibration |
| [Layers](../../adapters/engines/motion_playback/LAYERS.md) | E upper gesture, F grounded full-body gesture, Q cancel |
| [Ground root motion](../../adapters/engines/motion_playback/ROOT_MOTION.md) | Explicit policy selects root_main.gd / UE RootGame; animation supplies trajectory |
| [Foot IK and grip](../../adapters/engines/motion_playback/CONSTRAINTS.md) | constraints selects constraints_main.gd / UE ConstraintsGame; feet/grip configured independently |

Each path needs matching clips, bindings, and graph. Grip uses hold/carry source poses and sockets calibrated after engine import. FBX can embed supported images; inspect complex materials natively.

## Character Configuration

Merge observation_bones and movement_speeds_mps from [character_profile.example.json](character_profile.example.json) into complete bindings. Values belong to one CesiumMan example, not arbitrary characters.

- Eleven dst_* observation keys are stable report roles; values are actual unique bone names. All are required and root must match processing. Creation/staging checks sampled bones; runtime checks native rigs and fails on missing bones.
- movement_speeds_mps explicitly sets walk/run controller speed in m/s. Calibrate actual retargeted support tracks rather than assuming the original character's speed prevents sliding.
- Omitting both retains sample mannequin names and 1/2.5 m/s compatibility defaults, unsuitable for other skeletons.
- The eight clips/events/root-ownership fields remain required. These two fields do not replace full retargeting configuration; separately validate reference-pose differences, contacts, and skinning.

## Production Notes

Preserve original assets, licenses, editable sources, and processing reports. Godot source directories may use .gdignore to avoid .blend import. Export presets must reference matching local Windows templates. UE targets 5.8; record the actual runtime environment in project evidence.

Import, numerical round trips, natural playback, deformed-mesh visuals, and human playtesting are separate scopes. Project notes should state contact residuals, uninspected poses, and source-style limits.

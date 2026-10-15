# Native Motion Import and Sampling

[English](README.md) | [简体中文](README.zh-CN.md)

Imports offline processing results into actual Godot / UE 5.8 projects and reads native bone transforms for unit, axis, root/pelvis trajectory, and mapping checks. This is separate from [in-game animation playback](../motion_playback/README.md).

| Implementation | Purpose |
| --- | --- |
| godot/import_capture.gd | Native import and bone capture |
| unreal/import_motion.py | UE import, save, and sampling-resource preparation |
| unreal/OAGDMotion/ | Native UE evaluation and capture plugin |

Prepare jobs through tools/motion_native.py after reading the [motion processing contract](../../processing/MOTION.md). Supply an actual processed revision and matching configuration, with fresh project/report locations. Handwritten results cannot substitute for native sampling.

Sampling and numerical round trips do not establish skinning quality, game feel, or arbitrary skeleton compatibility. After preparing native resources, use the playback workflows for game time, state selection, root motion, or foot/hand constraints.

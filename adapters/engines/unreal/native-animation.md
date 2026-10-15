# Native Character, Animation, and Weapon Observation

[English](native-animation.md) | [简体中文](native-animation.zh-CN.md)

Uses `tools/engine_workflow.py execute`. In `inspect`, `character_exports` reads the mesh, Skeleton, and Single Node or AnimBP static dependencies from actual SkeletalMeshComponents. It can also call an explicitly provided read-only project action-collection function. Static references, declared available actions, and observed runtime behavior are labeled separately. Collection functions must return `actions:[{id,label,asset}]` and nonempty `source_assets`; bindings must not be guessed from filenames. FBX export supports same-Skeleton AnimSequences under project `/Game` paths. External plugin mounts, Montage blends, and custom resources require project adapters and cannot be represented as verified single-file clips.

```json
{"engine":"unreal","mode":"inspect","scene":"/Game/Demo/Map","inspect_targets":["name:SkeletalMeshActor_8"],"character_exports":[{"id":"hero","target":"name:SkeletalMeshActor_8","component":"SkeletalMeshComponent0","role":"player","previews":true}]}
```

After execution, run `tools/engine_characters.py --project PROJECT --session SESSION`. Synchronization checks the session, project, source hashes, and exported FBX hashes before updating existing `.asset-browser/characters.json` / `previews.json`. Each character keeps independent version evidence; other characters are not implicitly revalidated. Derived previews are stored in `previews/engine/SESSION/`, without adding candidate stages or registration barriers. Browser FBX previews support browsing, not verification of engine blending, attachments, materials, or input.

Runtime observation requests can set `attached_actors:true` on an actor to read independent weapon Actors created during BeginPlay. `observe.animation_capture` includes `target`, `component`, `clip`, `start`, and `duration`, plus optional `weapon:{mesh_asset,attachment,kind,component}`. Weapons are found by actual parent component and asset path; ambiguity fails rather than falling back to `hand_r`. The session produces `animation-capture.json` (`animlab.capture/2`) for the animation diagnostic tool. Observation intervals are relative to the first PIE sample and contain actual world poses and available native animation time; they do not establish replay from clip frame zero.

Use `camera_target` for existing cameras. For read-only source observation, `observation_camera:{position:[x,y,z],rotation:[pitch,yaw,roll],field_of_view:60}` creates a temporary in-memory editor camera, copies it into PIE, and removes it afterward without saving the original level. `readonly_preview:true` rejects asset edits and gameplay action calls. Results explicitly record the temporary camera. Check source before/after hashes, the PIE world, actual pose changes, and images; process exit or bone count alone does not prove animation playback.

Off-screen animation may be affected by the project's visibility Tick policy. Bring the object into the observation camera first; do not silently change character Tick rules. Screenshots add sampling overhead. Binding, grip, foot, and hit-contact checks cover only explicitly declared, actually sampled intervals. Projects without authored contact markers do not receive invented contact passes.

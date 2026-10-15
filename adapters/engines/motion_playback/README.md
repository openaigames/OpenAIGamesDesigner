# Optional Animation Playback and Contact Constraints

[English](README.md) | [简体中文](README.zh-CN.md)

| Path | Guide |
| --- | --- |
| Prepare characters, clips, and observation bones | [Offline processing](../../processing/MOTION.md), [character profiles](../../processing/CHARACTER_PROFILE.md), [templates](../../../templates/motion_playback/README.md) |
| Basic playback, states, and events | Creation, replacement, and integration below |
| Speed-driven locomotion blending | [LOCOMOTION](LOCOMOTION.md) |
| Stepping turns on flat ground | [TURNING](TURNING.md) |
| Upper/full-body layers and markers | [LAYERS](LAYERS.md) |
| Ground root motion and physics consumption | [ROOT_MOTION](ROOT_MOTION.md) |
| Terrain foot IK, pelvis compensation, main/support-hand grip | [CONSTRAINTS](CONSTRAINTS.md) |

Each path has its own graph, asset, and consumer contract. Select modes for the project rather than enabling all together. Godot uses native animation trees; UE targets 5.8. Record automated checks separately from physical devices and human visual review.

Connect processed character clips to actual game time, skeletal blending, and character movement. Godot uses AnimationTree. UE 5.8 uses an editable Animation Blueprint with Sequence Players and Blend Poses by Int. Files belong to each project; existing games can adopt just the adapter without the sample state machine.

## Responsibilities and Scope

- Shared adapters validate bindings, select clips/rates, identify playback runs, dispatch markers from actual sequence time, and notify completion/interruption/reset.
- Projects own input, state selection, movement, jumping, interaction outcomes, cancellation, and cameras. Animation events provide timing, not damage or win/loss rules.
- The default accepts **controller-owned in-place motion**. Explicit `root_motion` enables limited animation-owned ground displacement. CLI checks processing configuration and complete root tracks; adapters check bindings/graphs. Displacing clips cannot be mislabeled as in-place.
- Basic-layer events apply only to nonlooping clips, once per name per run. Cancellation invalidates old run IDs. Rate 0 pauses; forward rates are 0..4. Reverse, arbitrary seek, and network authority are unsupported. Optional layers support once-per-cycle markers; basic locomotion footsteps need separate integration.
- Selecting the same action is idempotent; use reset for a full restart. Completion callbacks can choose the next action. Recursive selection during interruption/reset notifications is rejected to avoid reentering exit callbacks.

## Creation and Execution

Process and verify a motion revision with [offline processing](../../processing/MOTION.md), then supply `oagd.playback/1` bindings. Entries declare `id`, processed `clip`, `duration_s`, `loop`, `motion_owner=controller`, `in_place=true`, and optional `markers=[{name,at_s}]`. The sample requires idle, walk, run, jump, fall, land, action, and action_v2; these are sample rules, not universal component requirements.

Cross-engine binding IDs and markers use lowercase letters, digits, and underscores, starting with a letter. UE FName comparisons are case-insensitive; packaged display spelling may come from existing engine names. Sample reports normalize to lowercase. Processed `clip` names retain source spelling.

```text
python tools/motion_playback.py create --engine godot --project NEW_PROJECT --revision REVISION --bindings bindings.json
python tools/motion_playback.py create --engine unreal --project NEW_PROJECT --revision REVISION --bindings bindings.json --ue-root UE58
```

Godot: run `Godot --headless --path PROJECT --script PROJECT/prepare.gd`, then open `project.godot`. Import creates a PackedScene with a merged animation library, shared skeleton, and editable tree. Runtime loads this saved resource, not Blender/FBX.

UE: compile `MotionPlayEditor`, then run `UnrealEditor-Cmd PROJECT/MotionPlay.uproject -run=pythonscript -script=PROJECT/prepare.py -nullrhi -unattended`. The script imports AnimSequences to one Skeleton and saves a Bindings DataAsset, ABP_Player, and Example map. The editor module builds graphs; standalone packages contain only runtime modules.

New UE examples explicitly use D3D12 / Shader Model 6. First launch may require lengthy shader compilation. Automated capture can use native `-RenderOffScreen`, which still renders on the GPU. `-nullrhi` supports bone/rule checks only, not visual acceptance. Automated tests can use separate caches; normal project launches need no off-screen flags.

WASD moves, Shift runs, Space jumps, E gestures, Q cancels, and R restarts. Characters/gestures are original technical samples, not final art. `templates/motion_playback/author_sample.py` creates editable Blender sources, explicit mappings, processing configuration, and bindings. Process through motion_workflow before project creation. A deliberate single-frame action defect exercises real automatic repair.

## Replace Clips

```text
python tools/motion_playback.py stage --project PROJECT --revision NEW_REVISION --bindings NEW_BINDINGS
# Run the engine prepare script again to save the new native resources.
python tools/motion_playback.py activate --project PROJECT
```

stage validates processing evidence, copies inputs to a new revision directory, and writes `bindings.pending.json`; the game retains old bindings. prepare creates new native resource directories/scenes only. activate checks bindings, source files, and native output hashes before switching, retaining old bindings and UE settings in `.openaigame/playback-history`. Activation requires successful import evidence but does not establish runtime acceptance. Restart and record actual states, poses, and events.

`status` compares the creation snapshot with the project. Explain rule/configuration/asset differences in project records; local edits are not overwritten automatically. Keep original `.blend` files and all processing revisions in production records; stage does not copy the full history into runtime packages.

## Integrate with Existing Projects

Godot can copy only `godot/oagd_playback.gd`, configure an existing AnimationTree state machine, and select project nodes. The example uses 0.12-second transitions. configure does not create/overwrite graphs. Trees use manual processing and one project-owned advance call per frame with actual delta. This performs normal evaluation/blending, not per-frame seek. Maintain a unique, fixed update order.

UE can copy only OAGDPlayback and use UOAGDPlaybackComponent, UOAGDPlaybackSet, and a derived UOAGDPlaybackAnimInstance. Graph indices must match Bindings.Clips; connect PlayRate to PlaybackRate and reset newly activated Sequence Players. The builder initializes engine nodes and registers property input bindings. Sampling after NativePostEvaluateAnimation reads real clocks and checks request generations/active blend weights, preventing stale inactive-node end times from reemitting events. Existing Montages, complex layers, and asynchronous/parallel updates require specific adapters.

## Evidence and Limits

Examples can run a fixed schedule through input handlers and record engine state, character/bone trajectories, clocks, and events. This is reproducible programmatic testing, not manual playtesting. Report paths must be new writable files.

```text
Godot --path PROJECT -- --report=REPORT_JSON --fps=60
UnrealEditor-Cmd PROJECT/MotionPlay.uproject MAP -game -MotionReport=REPORT_JSON -UseFixedTimeStep -FPS=60 -unattended
```

Fixed steps support repeatability, not performance benchmarks. Windows packages must actually launch; compilation/export is insufficient. Basic in-place example conclusions apply to flat ground, matched speeds, and declared support windows. Root motion and constraints follow their own guides. The basic example does not establish networking or final art quality.

Sample anatomical forward is Blender -Y, marked by toes, nose, and a white chest panel. Use Godot `--view=side` / `--view=front`, or UE `-MotionView=side` / `-MotionView=front`, for close inspection. Reports contain shoulder/elbow/hand and forward vectors. Direction checks must assess intended upper-arm lift and elbow bend alongside events/displacement, not merely that a hand bone moves.

UE records bones, animation clocks, and positions after `OnWorldPostActorTick` to avoid mixing previous poses with current movement. This observation callback does not drive/correct poses. Side/front views use soft fill lighting to reveal body orientation.

References: [Godot AnimationTree](https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html), [UE blend nodes](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprint-blend-nodes-in-unreal-engine).

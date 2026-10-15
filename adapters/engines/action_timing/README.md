# Action Timing Records

[English](README.md) | [简体中文](README.zh-CN.md)

Records and compares action events across engines. For retargeting, see [motion processing](../../processing/README.md); for states, blending, and constraints, see [animation playback](../motion_playback/README.md).

Inspect the actual relationship between input, rules, animation, and audio requests. Interaction, movement, climbing, spells, melee, shooting, vehicles, and UI feedback can share this interface without predefined game rules.

| Engine | Installation path within the project | Native integration |
| --- | --- | --- |
| UE5 | `Plugins/ActionTiming` | Actor Component, Blueprint functions, Anim Notify, Insights Bookmark |
| Unity | `Assets/ActionTiming` | MonoBehaviour, Animation Event, rule callbacks |
| Godot 4 | `addons/action_timing` | Node, AnimationPlayer method tracks, rule callbacks |
| Three.js | `src/action-timing` | ES Module, AnimationMixer finished / loop |
| Phaser | `src/action-timing` | ES Module, Sprite animationstart / animationcomplete, Scene shutdown |
| Other web frameworks | Project script directory | Renderer-independent ES Module; record from real event callbacks |

```text
python tools/action_workflow.py install --engine unreal --out <UE_PROJECT>/Plugins/ActionTiming
python tools/action_workflow.py install --engine unity --out <UNITY_PROJECT>/Assets/ActionTiming
python tools/action_workflow.py install --engine godot --out <GODOT_PROJECT>/addons/action_timing
python tools/action_workflow.py install --engine threejs --out <WEB_PROJECT>/src/action-timing
```

Installation copies recorder source only. Existing same-name files with different contents are preserved and produce errors. UE requires plugin enablement/compilation and an ActionTiming dependency in consumer C++ modules. Unity/Godot require attaching components to actual action objects. Release builds do not record by default; there is no background reporting.

## Integrate with Real Actions

1. Start recording at the tested action's beginning, supplying action name, project revision, source, input mode, and input-script description.
2. Record separately at input callbacks, actual rule changes, animation events, and audio-play requests. Each call uses a monotonic clock, including real waits from pause/time scaling.
3. On normal completion, call StopAndSave / stop_and_save / stop. The test defines whether cancellation is expected completion: a reload-cancel test may complete, while an unexpected scene close saves incomplete.
4. Export JSON into the game project and register it through the CLI below.

UE/Unity: `StartRecording(action, revision, source, inputMode, inputDescription)`, `RecordEvent(track, eventName, uncertaintySeconds)`, `StopAndSave(complete)`. Godot uses snake_case equivalents; start/record return Error and must be checked. Call native interfaces on the main thread.

UE Record Action Event Anim Notify finds the recorder on the Mesh owner's Actor. Set its track/event names. Notify delivery depends on weights, blends, and engine configuration; record rule effects where rules execute. Animation Insights/Rewind Debugger can inspect poses/states. The recorder also emits Insights Bookmarks when bookmark tracing is enabled; it does not create custom Rewind tracks.

Unity Animation Events call RecordAnimationEvent with an event name on the recorder's object. Project Animator state callbacks call RecordEvent on actual entry/exit. Disabling the component saves an incomplete record.

Godot AnimationPlayer method tracks target record_animation_event. Record AnimationTree transitions where actual state decisions occur. Tree exit saves incomplete. Default output is user://action-timing; output_directory can point to a development project. Exported games must not write read-only res://.

Web example:

```javascript
import {ActionRecorder, observeThreeMixer} from './action-timing/action-recorder.mjs';
const recording = new ActionRecorder({
  engine: 'threejs', engine_version: THREE.REVISION,
  action: 'interaction', revision: buildRevision, source: 'player interaction callbacks',
  input_mode: 'software', input_description: 'interaction-check-v1'
}).start();
recording.record('input', 'activate');
const detach = observeThreeMixer(recording, mixer, 'character');
// In the callback that actually commits the rule:
recording.record('logic', 'commit');
const capture = recording.stop(true); // Also removes listeners registered for this run
recording.download();                 // Or pass capture to the project save interface
```

Phaser uses observePhaserSprite(recording, scene, sprite, track); shutdown stops incomplete and removes listeners. Other frameworks can use ActionRecorder alone. Focus loss/page suspension may delay callbacks; records show actual times. Distinct Actors, Sprites, or animation instances need separate tracks/recorders. A Mixer observer records all its completion/loop events and cannot distinguish unidentified instances.

## Files and Checks

UE saves `Saved/ActionTiming/*.json`; Unity saves `Application.persistentDataPath/ActionTiming/*.json`; Godot prints its path; web uses download/project saving. JSON is action-events/1 in seconds with zero_s=0. Preserve engine version, action, project revision, input description, completion, and dropped counts.

Track/event names accept letters, digits, and `_ . : / -`, up to 120 characters. Occurrences start at 1 each run, such as commit#1/commit#2; specifications reference these qualified names. New runs reset counts; duplicate start fails. Each run allows 10,000 events; overflow increments dropped_events and cannot pass. Use response sampling for per-frame values, not this discrete-event recorder.

```text
python tools/action_workflow.py import --project <GAME_PROJECT> --capture production/timing/capture.json --spec production/timing/spec.json --title "Interaction after editing"
python tools/action_workflow.py compare --project <GAME_PROJECT> --a <OLD_RUN_ID> --b <NEW_RUN_ID>
```

See [action timelines (Chinese)](../../../skills/game-animation-pipeline/references/action-timeline.md) for specification format. Captures can be imported without criteria; results explicitly remain unchecked. Measurements never generate their own passing thresholds. Event checks can run without video, but cannot establish visual quality. Audio request time is not audible output time.

The workbench stores event/spec copies, original paths, and SHA-256. Optional project-local MP4/WebM includes the action's video zero time and requires player review. Video references/hashes are retained; changed files cannot play as historical footage. Results are `.openaigame/action-runs/<id>/run.json`. Import/filter/compare/export does not edit engine action settings. APIs retain session, same-origin, and CSRF checks; there is no cross-origin game upload endpoint.

Comparisons check action name, clock, input mode, and description. Declarations do not prove identical manual input, hardware, or network conditions. Multi-machine clocks require explicit synchronization evidence and real network tests.

## Native Editing and Debugging

- UE: [Rewind Debugger](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-rewind-debugger-in-unreal-engine?application_version=5.4) for native pose/state inspection.
- Unity: [realtimeSinceStartupAsDouble](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Time-realtimeSinceStartupAsDouble.html) for real time; Animator/Animation remain the editing tools.
- Godot: [Time](https://docs.godotengine.org/en/stable/classes/class_time.html) for monotonic clocks; AnimationPlayer/AnimationTree handle motion/blends.
- Three.js: [AnimationMixer](https://threejs.org/docs/#api/en/animation/AnimationMixer).
- Phaser: [animation events](https://docs.phaser.io/api-documentation/4.0.0/namespace/animations-events).

Editor time, simulation time, elapsed real time, and audio/video time are different clocks. Test new engine/platform integrations in a small local scene before production actions.

## Custom Configuration and Preview Clients

The shared workbench has no action-inspection or clip-editing page. [Editing and engine integration](EDITING.md) documents protocols/scheduling for custom clients. Recorders and CLI retain actual runtime results.

# Action Configuration and Scheduling

[English](EDITING.md) | [简体中文](EDITING.zh-CN.md)

For developers integrating tools. The shared workbench contains asset libraries, generation services, and generation jobs, but no clip editor. Configuration, draft validation, and apply interfaces remain available. Inspect actions with native engine tools and the [recording CLI](README.md).

## Integration Order

1. Read real asset durations, track bindings, and gameplay parameters; have project components consume the same action-sequence/1 configuration.
2. Register only implemented editable fields. GET /api/action-editor reads configuration, POST /api/action-draft saves drafts, and POST /api/action-apply applies them. Keep session, same-origin, and CSRF validation.
3. Check draft/live versions. Preserve pre-apply configuration in project history. On conflict, reread/compare instead of overwriting automatically.
4. Rerun in-engine and check repeated input, interruption, audio, and released restrictions against fresh captures. Old videos do not update with configuration.

## Project Integration

Registration file: `.openaigame/action-editor.json`.

```json
{
  "schema":"action-editor/1",
  "actions":[{
    "id":"landing",
    "title":"Landing action",
    "engine":"godot",
    "file":"game/config/landing.json",
    "editable":{"pose":["start_s","source_in_s","source_out_s","rate","blend_in_s","blend_out_s"],"footstep":["start_s","volume"],"recover":["time_s"]},
    "consumer_note":"The landing component reads this configuration.",
    "references":[{"label":"Original capture","run":"IMPORTED_RUN_ID","start_s":2.1}]
  }]
}
```

editable lists only fields the actual consumer uses. Engine values are unreal, unity, godot, threejs, phaser, and web. The workbench does not execute commands from registration or expose arbitrary script execution.

See [landing-sequence.json](landing-sequence.json). Times are seconds. Each clip references one asset with actual duration, type, and project binding. Audio additionally declares a project-local WAV preview and SHA-256. Configuration cannot replace registered bindings with arbitrary resources or change skeletons.

Clip duration is `(source_out_s - source_in_s) / rate`. blend_in_s starts at clip start; blend_out_s precedes clip end. Their sum cannot exceed duration. Audio rate changes pitch too; scheduling provides no pitch-preserving time stretch.

Projects interpret windows/events, such as interaction eligibility, hit cancellation, landing recovery, or ammo commit. No weapon/gameplay type is prescribed. Window ends and commit events are independently editable; projects validate their relationships.

## Engine Consumers

| Engine | Scheduler | Project bindings |
| --- | --- | --- |
| UE5 | FActionSequenceRuntime::Load/Start/Advance/Stop | Animation instances, audio, rules; call from C++ and expose project Blueprint interfaces |
| Unity | ActionSequencePlayer | Animator/Playables, AudioSource, rules; pass elapsed game time from Update |
| Godot | ActionSequencePlayer | AnimationPlayer/AnimationTree, AudioStreamPlayer, rules; advance in _process or fixed project updates |
| Three.js | ActionSequence / bindSequence | AnimationMixer/Action, audio, rules |
| Phaser | Same web interface | Sprite animation, audio, rules; do not expose skeletal transitions without implementing blending |
| Other web frameworks | Same web interface | Framework animation, audio, and rule objects |

Schedulers emit clip_start, clip_exit, clip_end, clip_cancel, windows, and instantaneous events. Start animation at source in-point/rate; project blending implements transitions. Audio uses in-point/rate/volume, gain transitions, and stops at end/cancel. Scheduler callbacks do not prove correct visual blending.

Advance once per game time. Skipped frames dispatch crossed events in order; backward time does not replay. Restart/seek requires stopping and reinitializing. Cancellation stops clips and emits window_cancel; projects release restrictions. Cancellation differs from completion. Callbacks may stop an action but must defer restarting the same scheduler to the next update.

Engines retain control of overrides, layers, root motion, weapon contact, and network prediction. Verify bindings before exposing parameters. Overlapping same-track clips require explicit consumer blending. Configuration edits registered clips only; it does not add layers or rewrite native animation assets.

## Validation Scope

Configuration checks/schedulers cover the listed engines but are not universal character controllers. Record configuration scheduling, real animation/audio bindings, device video, and listening separately. One project's results do not validate other projects/engines.

Browser previews play exported audio; check final mixing, engine latency, spatialization, and concurrency in-game. Sample timestamps do not establish sample-accurate synchronization or network acceptance.

Native test scenes can receive drafts and return real frames, versions, and events through [live preview](PREVIEW.md). A Godot bridge is bundled; custom clients connect to registered online scenes. Preview is separate from applying live configuration. Other engines need their own bridges or apply/rerun/video workflows.

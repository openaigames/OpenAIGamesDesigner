# Native Action Preview API

[English](PREVIEW.md) | [简体中文](PREVIEW.zh-CN.md)

The action-preview/1 protocol connects custom clients. The shared workbench has no native action-preview page. Live configuration, drafts, and history remain separate; frames must come from actual engine rendering.

Godot 4 includes godot/action_preview_bridge.gd and optional godot/action_preview_consumer.gd. UE, Unity, and web projects implement/validate their own bridges or use apply/rerun/video checks.

## Integration Workflow

1. Create a separate test scene using project characters, weapons, animation drivers, audio, and attachments, isolated from live matches, AI, and damage commits.
2. Start it, then query `GET /api/action-preview-status?id=<action-id>` and send drafts/controls through `POST /api/action-preview-command`, with workbench session, same-origin, and CSRF checks.
3. Wait for engine-confirmed run ID/configuration digest before showing associated frames/events. Sent does not mean applied. Pause/rate/view controls affect the test scene, not live configuration.
4. POST /api/action-preview-record saves an actual run. Returned images are not automatically assembled into video; engines must record/link playback files.
5. Apply formally through [configuration APIs](EDITING.md), then rerun movement, repeated input, interruption, and state restoration checks.

Audio comes from the local Godot process; consumers handle pause/rate consistently. Frames return at roughly 8 fps without a low-latency audiovisual-sync guarantee. Final quality requires watching and listening.

## Registration

Add to an action entry in `.openaigame/action-editor.json`:

```json
"preview": {"protocol":"action-preview/1", "consumer":"player_lab"}
```

Retain file, engine, editable, and other existing fields. consumer is a stable test-scene ID matching the bridge. Registration contains no executable commands/paths or arbitrary script entry points. Existing project tools launch the engine.

Before adding the bridge, set project_root (containing .openaigame), consumer_id, action_ids, views, host, and optional capture viewport. Do not include the bridge in release scenes.

## Consumer Interface

| Method | Responsibility |
| --- | --- |
| preview_load(sequence) -> Dictionary | Cancel previous action, actually load/bind draft; return {ok:true, sequence:loaded configuration} or {ok:false,error:reason} |
| preview_advance(delta) | Advance action time once and drive real animation, audio, and test rules |
| preview_state() -> Dictionary | Return actual elapsed_s, duration_s, complete; optionally animation, position, audio state, IK, or weapon measurements |
| preview_cancel() | Cancel action, stop audio, release windows/temporary state |
| preview_transport(paused, speed) | Update independent clocks such as audio; bridge controls only action advancement |
| preview_view(id) -> bool | Select a real scene camera and acknowledge only success |

Call bridge.record_event(track, name) where playback, audio, and rules actually trigger. Loading confirmation does not validate poses, IK, or blending. The bridge transports/records; the consumer implements behavior.

The optional consumer supports one AnimationPlayer per track, with bindings track-id:animation-name. Projects explicitly set animation_players, rest_animations, audio_streams, and cameras. Same-track overlaps are rejected because blending is not implemented there. Use project consumers for complex AnimationTrees, root motion, two-hand IK, and gameplay. Edit skeletal motion, fingers, skinning, and models in source tools/engines.

## Sessions and Results

Exchange files live in `.openaigame/action-preview/<consumer>/`:

- ready.json identifies the engine instance, supported actions/views/controls; stale after 4 seconds.
- request.json holds the latest instance/client/action/operation command with unique request/run IDs.
- client.json is a heartbeat; disconnect or 7 seconds without heartbeat cancels preview.
- status.json contains engine-confirmed run/configuration SHA-256, state, events, pose readback, and frame number.
- `runs/<run>/sequence.json` freezes the draft; capture.json stores native events/configuration. Two PNGs alternate for live frames.

Restarted instances reject old commands. Old frames/runs and other actions cannot confirm a new draft. One client controls a consumer at a time; others receive explicit feedback. External live-configuration changes require reload; stale drafts cannot overwrite them directly.

Historical events use monotonic real time, including pause/rate effects. Controls are stored separately in preview_controls. Different conditions are not automatically comparable. Snapshots identify configuration versions, not provenance or visual/audio acceptance.

Restart API services after code updates. This protocol does not alter asset-library pages or model-preview controls.

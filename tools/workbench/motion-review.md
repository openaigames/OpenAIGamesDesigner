# Legacy Clip Selection API

[English](motion-review.md) | [简体中文](motion-review.zh-CN.md)

The shared model preview has no clip-selection form. This document preserves the data protocol and client interaction contract for reading, saving, and exporting older records. Existing project records and backups are retained. Animation playback controls remain available, but the workbench has no separate animation-review page.

The compatibility API stores asset-level `undecided`, `keep`, and `reject` decisions and distinguishes candidate from game sources. It does not move, delete, import, or accept assets for a project stage. Art Direction initialization is optional. Technical asset IDs come from scanned paths and can link to existing art IDs; unknown provenance, licenses, and tags remain unknown.

## Preview, Context, and Revisions

`POST /api/motion-context` is a read-only description request that uses session and CSRF checks:

```json
{"path":"game/attack.fbx","context":{"character_id":"player","role":"player","use":"general","rig_path":null}}
```

The response includes `source.fingerprint` for the source and dependencies, `revision`, and `entries`. Use the character's displayed animation path, not its model path. Context fields `role`, `use`, `character_id`, and `rig_path`, together with the version's `clip_index`, identify a decision. Duplicate clip names are not identities. Several characters may share a clip and save independent decisions.

Fetch the fingerprint before loading the preview. After loading, append `observation: {fingerprint, clips: [{name, duration}]}` when describing or saving. GLTF names are checked against the local file. FBX metadata comes from an actual FBXLoader load and is stored as `browser_fbx_observation`. It is not a native engine observation or proof of texture, material, or final-result quality. An observation with an old fingerprint cannot be saved after the source changes.

Fingerprints cover the animation source, valid associated preview, external glTF buffers and images, declared mapping dependencies, selected character model and binding subrecord/dependencies, and a temporary FBX preview character. Changes to other characters do not invalidate this character's decision. Global legacy dependencies in a character manifest still apply to their declared scope; use per-character `dependencies` for finer invalidation.

FBX contains skeleton and animation tracks. Declare external FBX dependencies in the character binding or preview manifest to include them in version checks. Temporary character pairing for animation-only files checks matching bone names and hierarchy; it does not retarget. `mirror` and `root_motion` are production requirements, not transformations of the displayed preview.

## Saving, History, and Export

`POST /api/motion-review` accepts `{revision, preview, clip_index, fingerprint, choice}`, where `preview` is the description request above. `choice` contains `decision`, `role`, `semantic`, `mirror`, `root_motion`, and `note`. `keep` requires a specific role and semantic. Character use must match the preview context. HTTP 409 indicates a version conflict: retain the draft and require an explicit reload.

`GET /api/motion-review` returns the latest decisions with `current`, `stale`, or `unavailable` status. History lives in `.asset-browser/motion-review.json`, schema 2. Before the first write to a v1 record, a byte-identical `motion-review.v1.<revision>.json` backup is saved. Older records retain asset-level uses and require review; migration does not infer a character. Corrupt or unknown schemas cannot be read or overwritten. GET requests do not initialize files.

Writes use `record_io.project_lock`, path checks, atomic replacement, and revision validation. For a lock left after interruption, inspect the original process and evidence with the shared recovery tools; do not automatically delete another process's lock.

`GET /api/motion-handoff` exports current kept and excluded items; `?character=player` limits the export to a character. It includes record IDs, animation paths, clip indices, context, `source.files` and fingerprint, provenance, the original choice, and revision. `runtime_validation` is always `not_checked`.

For an explicit handoff, save the export JSON in the project's evidence directory. An `asset_fit` capability's evidence can reference it; also register its `source.files` as evidence dependencies for the combination. Selection establishes only the observed preview scope. Use observations and evidence for actual engine quality, explicitly linking objects, stages, or issues through the task tools. Saving `keep` does not close issues, overwrite `asset_fit`, or pass Production Validation.

Clients must protect unsaved drafts when switching assets, clips, characters, game animations, or temporary FBX characters, and during refresh, navigation, and export. Canceling retains the previous selection, time, and pause state. Prevent switching while saving, preserve drafts on errors, and use the native `beforeunload` prompt when closing the browser.

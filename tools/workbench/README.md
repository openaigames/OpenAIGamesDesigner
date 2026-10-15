# Project Asset Workbench

[English](README.md) | [简体中文](README.zh-CN.md)

The workbench lets you browse project assets, preview models and animation, inspect generation jobs, and configure generation services. See the [tool guide](../README.md#project-workbench-and-asset-audit) for startup commands and the [documentation index](../../docs/README.md) for character and scene tools.

The three pages are the asset library (`#assets`), generation services (`#services`), and generation jobs (`#tasks`). Filter assets by purpose, file type, tags, and candidate/game scope; scope follows actual file locations and project configuration. Legacy `#review`, `#production`, `#observation`, and `#actions` links and their `--view` options redirect to the asset library. Project stages, observations, and review records remain accessible through the CLI and data APIs. A directory location does not establish a binding or a quality result.

`GET /api/assets` returns each asset's location (`candidate`/`game`), `previewCopy`, `characters`, and `characterBindingError`. Derived previews are not listed as separate candidates. Select a bound model and use the animation selector in its details to play a bound action; choose a character first when several share the model. Invalid bindings show a reason, while the original files remain browsable.

The asset-plan sidebar reads `fits` and `fit_errors` from the same response. It shows capabilities, requirement coverage, gaps, tradeoffs, provenance, and stale versions. Plans can be inspected before downloading; local members can open in the preview. Maintain plans with `asset_library.py fit/fits`; the page does not add registration or promotion steps.

For FBX animation, the preview-model selector checks actual bone names, hierarchy, and valid skinning, and offers only structurally matching models. Static props, incompatible skeletons, and unreadable files are excluded. Without a matching model, playback uses the original skeleton. This choice lasts only for the browser session and does not change game bindings. A skeleton match does not supply synchronized animation for separate magazines, weapon attachments, or other objects. Inspect mesh deformation: a moving timeline alone does not demonstrate a complete preview.

Generation settings are grouped into 2D, 3D, video, and audio sections, with a key-management link on each model card and sidebar shortcuts. Tripo AI and Hunyuan 3D provide 3D generation; ElevenLabs provides sound effects, music, and dialogue. Each uses its own key and the existing generation authorization flow.

Seedream provides 2D generation and Seedance provides video generation. Their cards use the same logo, status, password field, and encrypted-storage layout as Tripo AI, with the original ByteDance Seed icon. Both share `ARK_API_KEY`: saving, updating, or removing it from either card updates the other. Environment variables take precedence.

New generation jobs support Seedream text-to-image and editing with one reference image, plus Seedance text-to-video and first-frame-to-video. Configure the model ID, image size or video duration, resolution, aspect ratio, audio, and watermark, and select a reference image from the project. Each saved job requires authorization before the Agent executes it; downloaded results appear in the asset library. The default models are Seedream 5.0 Pro and Seedance 2.5 and require access in the Volcengine Ark account.

Reference selection shows a thumbnail. Job details display the saved input snapshot, link to the original image, and distinguish an editing reference from a video's first frame. Generation uses that snapshot, so later changes to the original do not alter the job input; changes to the snapshot itself stop preview and submission. Image inputs accepted by the Tripo and Hunyuan adapters can also be inspected in job details. A reference image is an input, not a generated result.

Seedream and Seedance link to [Ark API Key management](https://ark.volcengine.com/region:cn-beijing/apiKey). This is an account page; adapters make model calls through the official API endpoints. A saved key does not verify account access, quota, or output quality. See [Seedream and Seedance integration](../../adapters/assets/ark-generation.md) for supported requests and the different recovery behavior of synchronous images and asynchronous video.

## Asset Categories and Tags

Choose the asset scope in the sidebar, then filter by category and purpose tags. Cards and details show a primary category, with supplementary audio-kind and animation tags. Shared purpose tags come from Art Direction. Classification does not change file formats, locations, bindings, or acceptance results.

Automatic classification is read-only. Reviewed classifications are saved in `.openaigame/asset-taxonomy.json` with the current file SHA-256. A saved classification takes precedence for the matching file version. Changed files and older records without a version require review. A unique move candidate with identical content and extension can be confirmed in the details; copies do not inherit classifications automatically. Legacy topic data is retained without topic-editing controls.

`asset_audit.py --classify <category> --paths <project-relative paths...>` shares the workbench's save logic. Use `--audio-kind music|sfx|speech` for audio purpose and `--reset-classification` to restore automatic classification. These operations do not require Art Direction initialization. Scan fields `taxonomy.needsReview` and `missingRecords` identify records to review; `classification.version` validates a save. POST `/api/asset-classification` accepts a `versions` map from paths to current hashes and returns 409 for stale versions. A single-file move confirmation may include `previousPath`; the server rechecks the unique match and absence of the original before updating.

## Game Content Roots

Use `.asset-browser/catalog-config.json` to limit the library display. Optional `includePaths` lists project-relative files: omission includes all files allowed by scanning rules, while an empty list displays none. `excludePrefixes` excludes subdirectories. These filters affect display and inventory checks within the selected scope; they do not move or delete files, establish bindings, or verify assets. When a version group's primary file is filtered out, eligible companion files still appear.

`tools/content_roots.py` determines scope from `.openaigame/project.json`. Keep the existing `engine_root` and engine configuration; using the workbench does not require moving the project.

| Configuration | Default game content scope |
| --- | --- |
| No project configuration | `game/` under the project root, matching a complete directory segment |
| Unreal | `engine_root/Content` and Content directories in project plugins |
| Unity | `engine_root/Assets` |
| Godot / Three.js / Phaser | `engine_root` |

Explicit `content_roots` override these defaults and must remain inside the configured engine root. `asset_exclude_roots` excludes supporting directories. Both use paths relative to the game project root. For example, merge these fields into an existing Unreal configuration:

```json
{
  "engine": "unreal",
  "engine_root": "UEProject",
  "content_roots": ["UEProject/Content", "UEProject/Plugins/Combat/Content"],
  "asset_exclude_roots": ["UEProject/Content/SourceReferences"]
}
```

This example shows scope fields only; retain the project's engine version, editor, and run configuration. Scanning still excludes build caches, derived previews, and designated project-record directories. Invalid configuration reports the reason and stops game-scope inference instead of silently falling back. Supported ordinary assets outside the game content roots are candidates.

## Character Binding Manifest

Example `.asset-browser/characters.json` (replace SHA-256 placeholders with actual hashes):

```json
{
  "version": 1,
  "characters": [{
    "id": "player", "title": "Player", "role": "player",
    "model": "game/Content/Hero.uasset",
    "actions": [{"label": "Sword combo", "path": "game/Content/Attack.uasset"}]
  }],
  "dependencies": {
    "game/Content/Hero.uasset": "MODEL_SHA256",
    "game/Content/Attack.uasset": "ANIMATION_SHA256",
    "game/Content/CharacterConfig.uasset": "BINDING_SHA256"
  },
  "evidence": "Read from the actual engine character configuration"
}
```

Export the manifest from actual engine bindings rather than inferring them from names or neighboring files. All models and actions must lie within the configured game content roots and have hash coverage. Changed or missing dependencies and invalid paths stop binding display and report the reason. Several characters may share a model. The manifest records project facts; it does not import assets or rewrite the game.

The Unreal preview map `.asset-browser/previews.json` uses version 1. Its `path` accepts a standalone GLB or binary FBX; `source_sha256`, `sha256`, and `dependencies` are validated. Character action previews must include a mesh so the character remains visible when switching animation. The bundled FBXLoader handles embedded animation and the source skeleton. Animation-only candidates can use a matching character for session-local preview.

## Legacy Review API

Records live in `.openaigame/asset-review/registry.json` with `schemaVersion` 1. GET `/api/asset-review` returns records, computed `effectiveStage`, invalidated checks, and `revision`. POST accepts `revision` and an `action`: `create`, `edit`, `start`, `check`, `qualify`, `return`, `new_version`, or `archive`. Requests require the workbench session cookie, a same-origin Origin, and a CSRF token.

Local automation can add `tools/` to Python's module path and call `workbench.asset_review.load(root)` or `mutate(root, request)` to retain file locks, revision checks, and atomic writes. Do not edit stage values directly in JSON. See [asset_review.py](asset_review.py).

Each record covers one use or clip at one version. The first `files` entry is the preview subject; the remainder includes related sources, derived files, and dependencies, all project-relative. A `sourceUrl` alone can create a candidate. `start` requires files, `use`, `testPlan`, and `environment`. Character `role` is separate from the Art Direction `objectId`; the art inventory owns tags.

A `check` uses gate `source`/`external`/`engine`/`game`, status `pass`/`fail`/`blocked`/`na`, and fields `method`, `reviewer`, `conclusion`, and `evidence`. Evidence uses `[{"path":"reports/review.md","type":"run_report"}]`, with types `report`, `run_report`, `video`, `image`, or `license`. Passing requires real evidence. Dynamic assets need video or a run report for engine/game checks; only `external` may be marked not applicable with a reason. Run reports must describe observations; assertions alone do not establish visual quality or game feel.

`qualify` succeeds only when all four applicable checks pass for the current version, evidence and dependency hashes remain valid, and there are no issues. Qualification does not establish a binding. Check actual references through `.asset-browser/usage.json`; a review record cannot replace the engine reference inventory. Detected changes make `effectiveStage` show `testing`, while preserving history.

`new_version` requires a different version name, clears checks, and returns to candidate status; `supersedes` and `lineageId` connect history. `archive` requires a reason and is reversible. `return` also requires a reason and clears effective checks while retaining operation history. After a 409 conflict, reload and review rather than automatically overwriting concurrent edits.

Plans are connected through the `plan` field, purpose descriptions, and specification links. This API does not build dependency graphs, batch-promote assets, download files, edit animation, or execute engines. Qualification is the reviewer's recorded acceptance decision, not an automatic assessment of artistic quality.

Model previews provide an animation list, playback, speed, timeline, and skeleton display. The shared workbench has no clip-selection form or separate animation-review page. Use the [legacy clip-selection API](motion-review.md) to read older records.

## Version History and Generation References

Versions of the same deliverable appear as one asset card, preserving scope, category, and filters. Version history shows parent versions, reference purposes, actual files, provenance, and selection history. It supports comparing two images, selecting an older version, archiving, and continuing from any version. Companion views and files stay together; distinct deliverables such as concepts, models, and animations use separate groups. The selected version, latest result, and actual game files are shown separately. Selecting a version does not copy it into the game or change engine bindings.

Adding existing files to version history saves independent copies of those files and explicitly selected companions. Older projects need no bulk migration. The store is `.openaigame/asset-versions`; a hash mismatch prevents preview, selection, and use as generation input. Archiving retains files and collapses archived entries by default. Art records own objects and tags; classification is saved per file.

The generation form defaults to a built-in image tool, executed by the Agent using an available tool. The page itself does not call a model. Select a base image, reference purposes, change instructions, and project images. Linked image versions become actual input snapshots, subject to adapter count and format limits. Unsupported references cause an explicit error instead of being silently dropped. Paid cloud generation retains its authorization flow.

POST `/api/asset-versions` supports `create`, `add`, `select`, and `archive`, using the GET response's `revision` to prevent concurrent overwrites. `select` requires a `reason`; `archive` accepts an `archived` boolean. GET includes immutable files, reference-review prompts, and game files whose hashes match the original paths. File access requires a session, explicit registration, and integrity validation. See the [CLI guide](../README.md#asset-versions-and-built-in-tool-results).

## Action Recording API

`GET /api/action-runs` lists project records. `GET /api/action-run?id=...` reads events, a specification snapshot, and checks. `GET /api/action-compare?a=...&b=...` compares two records. `GET /api/action-video?id=...` validates the file version before playing an associated recording. `POST /api/action-import` accepts a project-local capture and optional spec, title, video, and `video_zero_s`, with session, same-origin, and CSRF checks.

Relative intervals, track synchronization, fixed times, and uncertainty use the animation pipeline's shared analysis tools. See [cross-engine action recording](../../adapters/engines/action_timing/README.md) for adapters, paths, and formats. If a standalone project lacks the animation pipeline, only this feature reports the missing dependency; other workbench pages remain usable.

The action-editing protocol can connect registered native test scenes, isolate drafts, confirm applied revisions, and return actual viewport images and runtime events. The package includes a Godot bridge and an optional AnimationPlayer consumer. The workbench does not load the action frontend; clients implement their own UI. Existing records and adapters remain available. See [native preview](../../adapters/engines/action_timing/PREVIEW.md) for the protocol, scene interface, and limitations.

## Asset Production Handoff

`asset_handoff.py apply` and the shared production entry write Art Direction file mappings and art-lifecycle records. `check` verifies registration, integration, or recorded validation within the specified asset scope. Purpose tags use the same source; scanning does not adopt assets automatically. See [asset production registration and delivery checks (Chinese)](../../skills/game-preproduction/references/asset-handoff.md) for integration and legacy mappings.

Structured [asset quality reports](../../adapters/assets/quality-review.md) can publish to the external review gate. A previous pass becomes stale when its referenced source, image, mask, capture metadata, or review changes. Engine and game gates remain independent.

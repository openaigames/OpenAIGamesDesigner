# Tripo and Hunyuan3D APIs

[English](generation-api.md) | [简体中文](generation-api.zh-CN.md)

See [generation modes](generation-capabilities.md), generated from the same definitions used by workbench/submission checks. Tripo image-to-multiview produces images; subsequent model generation is a separate job. Both services support query/download/recovery. Python 3.10+ standard library is sufficient; no local GPU, weights, or SDK is required. Rigging, animation, topology optimization, and engine import are separate tasks.

## Tripo API Compatibility

Tripo model generation and image-to-multiview image generation use `https://openapi.tripo3d.ai/v3`. H3.1 is the geometry model; V3 is the API protocol. These are separate choices.

Local requests retain `parameters.type` and `model_version`. The adapter selects the dedicated `/generation/…` endpoint, sends `model_version` as `model`, and omits `type` from the HTTP body. Uploads use `/files`; polling uses `/tasks/{task_id}`. Existing V2 task IDs can be queried through V3 without submitting another generation. See the [official migration guide](https://developers.tripo3d.ai/en/docs/migration-v2-to-v3).

New H3.1 jobs with textures pin `texture_version` to `v3.5-20260815`. Explicit texture choices, queued jobs, and retries retain their original parameters. Geometry-only jobs do not acquire a texture model. Texture quality remains an explicit choice: selecting the latest model does not automatically enable Ultra geometry or 8K textures. Unsupported legacy fields such as `text_seed`, `style`, and `render_image` are rejected before submission.

## Model Generation and Rigging

Adapters call model-generation APIs, not platform auto-rigging, and do not accept arbitrary skeleton files/dimension JSON as constraints. Verify platform features separately from implemented interfaces. Unknown parameters cannot simulate missing integration. GLB/FBX extensions do not prove skeletons, skinning, or usable animation; inspect/play in DCC/engine tools.

For animated models, retain or confirm the chosen production route: model first then rig/animate, or author to existing animation/rig proportions. See game-technical-art references/rig-aware-asset-production.md. Dimensions may inform text or reference images, but only actual payload fields are sent. Verify joint image/text support. Do not silently discard requested inputs; honor an explicitly selected image-only route. Unsent dimensions remain post-generation calibration, not claimed service constraints. Existing route decisions do not replace the paid-job authorization below.

Unspecified new jobs use Tripo H3.1 / v3.1-20260211 and Hunyuan 3.1. Model IDs are frozen in requests/authorization digests. See [model policy](model-defaults.md). Sketch/LowPoly require explicit compatible 3.0; modes never silently downgrade models.

## Configuration

Open [local settings](local-settings.md) with `python tools/settings_server.py`. Saved Tripo/Hunyuan-compatible API keys enable default configurations without manual mode/auth fields. Tools read local credentials without exposing them to the model.

For project-specific settings, Tencent TC3, or existing local wrappers, add entries to .openaigame/asset-providers.json while retaining others. Project entries take precedence:

```json
{
  "tripo": {"mode": "api", "api_key_env": "TRIPO_API_KEY", "poll_seconds": 5},
  "hunyuan3d": {
    "mode": "api", "auth": "tc3", "region": "ap-guangzhou",
    "secret_id_env": "TENCENTCLOUD_SECRET_ID",
    "secret_key_env": "TENCENTCLOUD_SECRET_KEY", "poll_seconds": 5
  }
}
```

Create Tripo keys at its [API platform](https://platform.tripo3d.ai/). Saved Hunyuan API keys use API-key authentication; explicit TC3 uses SecretId/SecretKey and an account-supported region. Replace example regions appropriately. Temporary credentials can set token_env, default TENCENTCLOUD_TOKEN.

For the Hunyuan API-key endpoint, use:

```json
{"mode": "api", "auth": "api_key", "api_key_env": "HUNYUAN3D_API_KEY"}
```

This targets Tencent's api.ai3d.cloud.tencent.com/v1/ai3d, not every hosted Hunyuan service. Confirm the endpoint available to your account during platform migration; TokenHub/other protocols need separate adapters.

Tripo/Hunyuan keys can use encrypted settings or process environment. Environment changes require restarting the terminal/agent process; settings-page saves apply to subsequent calls immediately. TC3 remains environment-based. Configuration stores variable names only; environment values win. Never put secrets in chat, requests, repositories, or arguments. Check locally without generating:

```sh
python tools/asset_workflow.py --project "MyGame" doctor --provider tripo
python tools/asset_workflow.py --project "MyGame" doctor --provider hunyuan3d
```

ready_to_attempt means local configuration/credentials exist, not verified quota, permissions, or connectivity.

## Submit and Download

Save production/asset-request.json in the project. Tripo text-to-model:

```json
{"parameters": {"prompt": "A stylized wooden supply crate", "model_version": "v3.1-20260211", "texture_version": "v3.5-20260815", "pbr": true}, "inputs": []}
```

Hunyuan text-to-model:

```json
{"parameters": {"Prompt": "Stylized wooden supply crate", "Model": "3.1", "EnablePBR": true}, "inputs": []}
```

For explicitly image-only modes, omit unsupported prompt/Prompt and use inputs: ["assets-source/reference.png"]. Only snapshots are read. Tripo local uploads accept PNG/JPEG up to 20 MiB per image; export WebP references as PNG/JPEG before creating the job. The generation API also documents WebP URL inputs, but this adapter uses the file-upload endpoint, whose documented image formats are PNG/JPEG. Hunyuan single-image accepts PNG/JPEG/WebP; multiview accepts PNG/JPEG, dimensions strictly between 128 and 5000 pixels, up to 6 MiB each and 8 MiB total Base64. Oversized inputs fail before queuing; no automatic resizing/omission. Set supported parameters explicitly without automatic service/model substitution.

### Hunyuan Multiview and Text

```json
{
  "parameters": {"Model":"3.1", "GenerateType":"Normal", "EnablePBR":true, "FaceCount":1000000},
  "inputs": [
    {"path":"assets-source/object-front.png", "view":"front"},
    {"path":"assets-source/object-left.png", "view":"left"},
    {"path":"assets-source/object-back.png", "view":"back"}
  ],
  "brief":"Local brief: show the intended style and proportions in the reference images. This text is not uploaded."
}
```

front maps to ImageBase64; other views use MultiViewImages ViewType/ViewImageBase64. Exactly one front and one file per direction are required. Do not use a composite sheet as separate views or repeat one image under several labels. Left/right are object-relative. 3.0 supports front/left/right/back; 3.1 adds top/bottom/left_front/right_front. Check consistent object, proportions, pose, and construction; genuine side-view occlusion is valid.

Ordinary image modes do not accept Prompt simultaneously. Image+Prompt fails explicitly, never silently dropping text. Text mode sends Prompt; local brief is review-only. Only the 3.0 single-image Sketch route supports image+Prompt here, and must be deliberately selected. Unknown negative_prompt, dimension JSON, or rig files are not supported constraints.

Workbench modes allow text/multiview, direction-specific previews, model, face count, and PBR. Details show actual inputs and Prompt transmission. Views, image digests, and brief bind to one authorization and survive retry. A sanitized transmission.json is saved before submission and marked accepted after a cloud ID is received. Offline validation does not establish account-level cloud success.

Reference: [Tencent professional API](https://cloud.tencent.com/document/api/1804/123447). Do not turn one character design/view count into a universal asset default.

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider tripo --request production/asset-request.json
python tools/settings_server.py --project "MyGame" --approve-job JOB_ID
```

Users review service, prompts, inputs, and potential fees in the browser and personally authorize. Authorization lasts one hour, applies to one request/current account, and is consumed once. Reuse an existing valid authorization. Key storage, queuing, or an agent's written approval is not authorization. Then run:

```sh
python tools/asset_workflow.py --project "MyGame" run --job JOB_ID --timeout 900
python tools/asset_workflow.py --project "MyGame" status --job JOB_ID
```

Use provider hunyuan3d for Hunyuan. submit creates a local queue; run and workers check authorization before generation. Without it, jobs stay queued and no generation process starts. Parameter/input/project/job/key changes require renewed confirmation. Failures never automatically switch services or regenerate.

There is no live price quote or server-side spending cap. Set provider-account/project limits for hard budgets. This gate covers normal toolkit entry points, not arbitrary local code, custom wrappers, or direct SDK calls.

Snapshots, attempt logs, remote.json, results, and files live in `.openaigame/asset-jobs/<job-id>/`. Checks record nonempty files, sizes, and SHA-256. Model ZIP extraction preserves texture/material paths and rejects escaping paths/code files. Unknown formats remain failed rather than qualified models.

## Interrupted Jobs

Cloud IDs persist before polling/downloading. After timeout, network failure, or local cancellation:

```sh
python tools/asset_workflow.py --project "MyGame" resume --job JOB_ID --timeout 900
```

resume queries the same cloud job into a new attempt directory without resubmitting. If records remain running after process exit, confirm it stopped and use mark-interrupted --job JOB_ID --confirm-stopped. If submission response/ID was lost, find the job in the provider console, then use resume --job JOB_ID --remote-job CLOUD_JOB_ID. Do not automatically repeat POST when the job cannot be located.

cancel stops local waiting/download only; **it does not cancel cloud generation or guarantee refunds**. Resume before cloud results expire. For explicit regeneration after expiry/failure, use retry --job JOB_ID --new-generation and run the new job. Changed parameters require submit.

New generation needs new authorization. Query/download resume does not consume a new generation authorization. After a consumed authorization and lost response, recover the cloud ID; do not reuse authorization to submit again.

Register results/provenance/licenses through [asset acquisition](asset-sources.md) from-job, then inspect models, adapt rigs/animation, and import. A generated 3D file does not include a working controller or animation module.

References: [Tripo H3.1](https://developers.tripo3d.ai/en/models/v3-1), [file upload](https://developers.tripo3d.ai/en/docs/files), [task query](https://developers.tripo3d.ai/en/docs/task-query), [Hunyuan submit](https://cloud.tencent.com/document/product/1804/123447), [query](https://cloud.tencent.com/document/product/1804/123448), [API-key endpoint](https://cloud.tencent.com/document/product/1804/126189).

### Tripo Multiview

Use parameters.type=multiview_to_model and input objects with view. Include front plus at least one of left/back/right: 2–4 distinct files, no duplicate images. Present views are uploaded in front/left/back/right order and sent as named entries, for example `inputs: [{"front":"file-token-a"},{"back":"file-token-b"}]`. Missing views are omitted, never mirrored or copied. Files/hashes are checked before consuming authorization.

The V3 route supports H3.1 with explicit geometry_quality, texture_quality, texture_version, pbr, and face_limit. Image modes send no prompt/negative_prompt; brief is local. Calibrate dimensions/rigs afterward. Workbench details show directions/text transmission; create these jobs through CLI/structured requests, not an assumed multiview form.

See [multiview generation parameters](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard). Offline payload tests do not establish account success; record returned job IDs and actual models separately.

## Constraint Prompts and Joint Inputs

Prepare a constraint prompt describing object, style, front/back construction, pose, proportions, and materials. Persist an explicit user requirement to send text even with references as a personal/project preference, not a universal character design.

Personal policy: %LOCALAPPDATA%/OpenAIGamesDesigner/generation-policy.json, or ~/.local/share/OpenAIGamesDesigner/generation-policy.json elsewhere. Project policy: .openaigame/generation-policy.json. Contents: {"version":1,"require_3d_prompt":true}. Project false cannot silently override personal true; change only when the user changes preference. Unconfigured users retain compatible behavior.

When enabled, creation/authorization/execution checks actual parameters.prompt / parameters.Prompt and mode support. brief is insufficient. Unsupported image+text combinations are blocked with a reason, without inventing fields, silently storing text locally, dropping images, or changing models. Existing cloud query/download can continue; history is preserved.

The supported joint-input route is Hunyuan Model=3.0, GenerateType=Sketch, one front sketch, and Prompt. Workbench exposes Sketch separately and requires explicit 3.0 selection. Tripo H-series image/multiview and Hunyuan Normal/Geometry image routes lack confirmed image+Prompt support and cannot submit under strict policy. SDK passthrough alone does not prove service consumption; additions need official contracts, payload tests, and output checks.

Workbench shows original prompts, images, compatibility reasons, and saved transmission status. Pending, accepted, and constraint-compliant outputs are separate evidence. Preserve payload records and inspect front/back structure, pose, and volume before rigging. Direct SDK calls are outside the gate, but agents must still honor user requirements.

## Inspect Settings and Failure Reasons

Tripo/Hunyuan service cards expose a settings check showing project/default configuration, authentication, environment/encrypted credential source, key-management page, and generation/query endpoints. Management pages issue keys; they do not receive generation requests. doctor exposes the same information without secrets.

Checks are local, without verifying account rights/quota or generating. Actual failures classify authentication, permissions, parameters, quota, rate limits, cloud jobs, or output files. Insufficient evidence remains unresolved rather than blaming every failure on keys.

Prefer query/download when an ID exists. If submission is uncertain without an ID, inspect the provider console first. Reuse valid single-job confirmation rather than adding duplicate steps.

After mode/auth/image-field changes, run offline tests for payload fields, directions, errors, and recovery. Offline passes do not establish account access or quality.

After capability changes, regenerate the English and Chinese capability guides with tools/generation_capabilities.py so documentation and submission rules remain aligned.

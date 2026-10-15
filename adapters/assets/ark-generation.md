# Seedream Images and Seedance Video

[English](ark-generation.md) | [简体中文](ark-generation.zh-CN.md)

Both providers use official Volcengine Ark APIs with shared local credentials, project jobs, per-job authorization, downloads, and asset registration. No extra SDK is required; networking uses host proxy settings.

## Configuration and Accounts

Save a Volcengine Ark API key on either Seedream/Seedance service card. Both share ARK_API_KEY; updates/removal affect both. Environment values override encrypted local storage. Configured status does not verify model access or balance.

- [Ark key management](https://ark.volcengine.com/region:cn-beijing/apiKey)
- [Account funding](https://console.volcengine.com/finance/fund/recharge)
- [Model pricing (Chinese)](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)

Key-management pages are not API URLs. Adapters use https://ark.cn-beijing.volces.com/api/v3 and do not send credentials to arbitrary custom endpoints. Projects can explicitly name environment variables:

```json
{
  "seedream": {"mode": "api", "api_key_env": "ARK_API_KEY"},
  "seedance": {"mode": "api", "api_key_env": "ARK_API_KEY", "poll_seconds": 5}
}
```

Save this in .openaigame/asset-providers.json without actual secrets. Project configuration wins, so custom variables may select a different account from the shared card key.

## Supported Inputs and Outputs

| Provider | Input/output | Parameters |
| --- | --- | --- |
| Seedream | Text-to-single-image or editing with one local reference image; PNG/JPEG/WebP named from actual headers | Model ID, size tier, watermark, prompt |
| Seedance | Text-to-video or one local first frame; asynchronous query/download to MP4 | Model ID, integer duration, resolution, ratio, audio, watermark, prompt |

Configured defaults are doubao-seedream-5-0-pro-260628 and doubao-seedance-2-5-260628; enable them in the account first. Supported families: Seedream 4.0/4.5/5.0 Pro/Flash/Lite and Seedance 2.0/Fast/Mini/2.5. Use Model IDs, not Endpoint IDs with undeclared capabilities. Size checks: Seedream 5.0 Pro/Flash 1K/1.5K/2K; 4.5 2K/4K; 5.0 Lite 2K/3K/4K; 4.0 1K/2K/4K. Seedance 2.5 accepts 4–30 seconds, 2.0 families 4–15. Fast/Mini use 480p/720p; others support up to 1080p.

Inputs allow one project-local PNG/JPEG/WebP up to 10 MiB, snapshotted/hashed on save and rechecked before submission. Seedance 2.5 first-frame jobs require ratio: adaptive; image selection adjusts the UI. Official APIs apply finer image/content constraints. Multiple references, video editing, layers, image sets, and automatic resubmission are unsupported. Rendered video is not skeletal animation.

## Workbench and CLI

Choose the service in generation jobs, enter parameters/reference, and save a pending job. Users review prompts, snapshots, and fees before authorization; agents then execute. Effective size/duration defaults are recorded. Open outputs in the library or register provenance with asset_library.py from-job.

Seedream request:

```json
{
  "parameters": {"prompt": "Front-view concept art of a stylized stone gate for a game", "model": "doubao-seedream-5-0-pro-260628", "size": "2K", "watermark": true},
  "inputs": []
}
```

Seedance request:

```json
{
  "parameters": {"prompt": "The camera slowly pushes into a castle courtyard as flags move in the wind", "model": "doubao-seedance-2-5-260628", "duration": 5, "resolution": "720p", "ratio": "16:9", "generate_audio": true, "watermark": true},
  "inputs": []
}
```

```sh
python tools/asset_workflow.py --project "MyGame" doctor --provider seedream
python tools/asset_workflow.py --project "MyGame" submit --provider seedream --request production/image-request.json
python tools/settings_server.py --project "MyGame" --approve-job JOB_ID
# After the user authorizes the job in the page:
python tools/asset_workflow.py --project "MyGame" run --job JOB_ID --timeout 600
```

For video, use provider seedance and its request file. Choose an appropriate timeout, such as 1800 seconds. doctor is local and consumes no generation quota. Authorization binds project/provider/parameters/input hashes/actual key; changing the shared key invalidates old authorization.

## Recovery, Download, and Acceptance

- Seedance persists its ID immediately after submission. Stopping locally does not cancel cloud generation. Use resume --job JOB_ID after failure/interruption/download failure to query/download the same job, not POST another. Explicit regeneration requires a new job/authorization.
- Seedream is synchronous with no resumable cloud job ID. After response/download loss, inspect local remote.json and provider records. Request IDs are not job IDs; do not automatically retry. Explicit regeneration uses retry --new-generation and renewed authorization. Inspect/register saved files separately.
- Downloads use restricted HTTPS without API keys. Temporary signed URLs stay out of logs/job JSON. Outputs go to attempt-N/output with paths, sizes, hashes, and provenance.
- Headers/container checks establish basic format only. Verify actual dimensions/duration, playback, visual quality, and game import separately. Some 1080p outputs use HEVC; browser playback depends on available decoders.

References: [image generation (Chinese)](https://docs.volcengine.com/docs/ark/image-generation-api?lang=zh), [create video (Chinese)](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh), [query video (Chinese)](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh), [authentication](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=en). Verify account permissions, regions, billing, and new capabilities against official documentation.

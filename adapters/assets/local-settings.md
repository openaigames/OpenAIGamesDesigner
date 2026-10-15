# Local Services and Credentials

[English](local-settings.md) | [简体中文](local-settings.zh-CN.md)

Open settings without creating a game project. From toolkit root:

```sh
python tools/settings_server.py
```

The tool starts a temporary service bound only to 127.0.0.1 and opens a browser. Installed path: game-preproduction/runtime/tools/settings_server.py. Agents managing the browser can use --no-open, then open the complete returned startup URL. The URL is single-use for that session; existing pages can refresh, but service restarts require a new URL.

## Natural-Language Entry

You can ask:

> Open the OpenAIGamesDesigner local service settings so I can configure Tripo AI and Hunyuan 3D.

After configuration:

> Check whether the Tripo AI and Hunyuan 3D settings are saved. Report configuration status only, without reading or displaying keys or submitting generation jobs.

For generation:

> Prepare a Hunyuan 3D job for a stylized wooden crate in this project. Show the prompt and parameters, open the confirmation page, and wait for my confirmation before submitting.

## Enter Credentials

1. Paste the corresponding API key into the Tripo AI, Hunyuan 3D, ElevenLabs, Seedream, or Seedance card.
2. Save it and check the locally saved status.
3. Tell the agent which service/asset to use; do not send keys in chat.

Seedream/Seedance share ARK_API_KEY. Saving/updating/removing either affects both. Obtain it from [Ark key management](https://ark.volcengine.com/region:cn-beijing/apiKey) and enable the model. See [image/video generation](ark-generation.md).

Hunyuan keys come from [Tencent's key page](https://console.cloud.tencent.com/ai3d/api-key) and target its **OpenAI-compatible API-key interface**, not OpenAI-issued keys. That console issues keys; generation/query use https://api.ai3d.cloud.tencent.com/v1/ai3d/submit and /v1/ai3d/query. The page supplies mode: api and auth: api_key. Use [project configuration](generation-api.md) for SecretId/SecretKey, regions, or other hosted providers.

Settings support updates, deletion, and status refresh. Saving neither validates online nor submits/consumes generation quota; locally saved means encrypted storage succeeded. Actual jobs verify access/results. Finish and close the service through its page or terminal; it also stops after 60 minutes idle. Closing a browser tab alone does not immediately stop it.

## Confirm Each Generation

The agent queues a job, then opens its request:

```sh
python tools/settings_server.py --project "MyGame" --approve-job JOB_ID
```

The confirmation section shows project, service, job, prompt, and input digests. The user reviews fees and personally confirms; agents cannot check/click on their behalf. Saving credentials and authorizing generation are separate actions.

Before providing the URL, the service checks access to the current user's authorization directory and encrypted storage without creating authorization or contacting providers. Failure exits with a reason. Resolve launch permissions before reopening. Restricted environments need access to the user's local settings directory through their normal permission mechanism or an ordinary user terminal; no administrator rights are required. Do not move credentials/authorizations into projects to bypass restrictions.

If confirmation is disabled, read its reason. Existing authorization needs no repeat. Check missing credentials or a job no longer queued; for record-access failures, verify service identity/directory permissions and refresh/restart. Multiple pages have independent sessions. Retry a transient confirmation error safely: the backend rechecks the same job/account without submitting automatically.

Authorization lasts one hour, binds request/account, and is single-use. Without it, asset_workflow run starts no generation; the worker rechecks/consumes it before submission. Changed requests/keys or retry jobs need new confirmation. Reuse valid authorization. Tripo/Hunyuan/Seedance query/download do not require new-generation authorization. See [Ark recovery](ark-generation.md#recovery-download-and-acceptance) for synchronous Seedream and [audio recovery](elevenlabs-audio.md#outputs-calibration-and-recovery) for saved ElevenLabs originals; request IDs do not provide remote resume.

Windows authorization uses DPAPI too. Other platforms use environment secrets and private-user nonsecret authorization records. Pages do not set provider spending caps; use provider quotas. Normal entry-point checks are not a sandbox against arbitrary local code.

A no-generation check can save keys, queue a job, and verify unauthorized run rejection. Changed requests require renewed review. Actual confirmation followed by run may incur charges.

## Credential Resolution

| Item | Rule |
| --- | --- |
| Windows storage | %LOCALAPPDATA%/OpenAIGamesDesigner/credentials.dpapi.json for the current user |
| Protection | User-level DPAPI; no plaintext project/toolkit/repository storage |
| Project providers | Matching .openaigame/asset-providers.json entries win; otherwise saved credentials supply default provider settings |
| Key selection | Explicit/default environment variables win; missing default variables may use local storage. Custom variable names do not fall back to another account |
| Activation | Subsequent calls reread immediately; settings-page saves need no agent restart |
| Agent-visible information | Configured status, source, missing items; status/doctor never return secret values |

Agents must explicitly select providers in submit; available keys do not authorize changing a user's service choice. Queues store nonsecret settings/variable names, while execution reads local keys. If accounts change after queuing, confirm access to any existing cloud job.

Check local status without a project:

```sh
python tools/settings_server.py --status
```

Delete removes only toolkit-stored keys, not environment variables or provider credentials. If environment values take priority, update/remove them and restart that process.

Encrypted settings support Windows. Other systems use environment variables, never plaintext fallback. DPAPI binds to the current user; reconfigure after moving account/machine. It protects trusted local credential storage, not against malicious programs under the same user. Reference: [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).

Pages load no third-party scripts or saved-key plaintext into forms. APIs check local Host, origin, session, and write token. Generation tools send authentication only to the selected provider when executing requests.

## Project Workbench Entry

With a project, use `python tools/project_workbench.py --project "GAME_ROOT" --view services`, or `--approve-job JOB_ID` for the selected job. Both reuse the same storage/authorization. Agents execute after confirmation; confirmation itself does not generate. Without a project use standalone settings. See [Project Workbench](../../tools/README.md#project-workbench-and-asset-audit).

## Host Proxy Settings

Generation providers and asset downloads share networking. Windows reads current-user system proxy settings per request and resolves PAC/WPAD per destination, including manual proxies/bypass rules. Changes affect the next request, not an active transfer.

HTTPS_PROXY/https_proxy takes precedence, then ALL_PROXY/all_proxy; an explicit empty value means direct. NO_PROXY/no_proxy matches bypass proxies. Other targets use explicit/system settings. macOS/Linux use environment and Python-readable host settings; the toolkit does not add PAC parsing there.

Proxy connections use curl for HTTP/HTTPS/SOCKS and streaming. Windows supplies curl; other systems need it on PATH. Proxy resolution failures are reported without silently connecting directly. No proxy means direct service access. Tools do not alter host settings or store proxy addresses/secrets in projects. Browser-extension proxies are not system settings.

TLS verification remains enabled. Credentials pass through process memory, not command arguments/logs. Upload bodies use temporary files cleaned on completion/cancel. Connection failures do not automatically resubmit generation. Authenticated API requests do not follow redirects; ordinary downloads recheck URLs/proxies on redirects.

Saved credentials do not prove connectivity. If browser pages work but APIs time out, inspect host/system/environment proxies, then use read-only calls to check connection/authentication without generating. References: [Windows auto proxy](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpgetproxyforurl), [Python proxies](https://docs.python.org/3/library/urllib.request.html).

## Inspect Effective Project Settings

Tripo/Hunyuan workbench cards show configuration/authentication/key sources and request endpoints. Project overrides/environment values may take priority over freshly saved keys; inspect these before replacing credentials.

Locally saved, configuration complete, and service accepted are distinct states. Settings checks do not generate or consume quota. See [implemented generation modes](generation-capabilities.md).

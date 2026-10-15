# Asset Generation and Acquisition

[English](README.md) | [简体中文](README.zh-CN.md)

Entry point for asset acquisition and generation services. See [processing](../processing/README.md) for existing-asset processing, retargeting, and procedural generation, and [static scenes](../engines/static_scene/README.md) for multi-node import/replacement. Record service configuration, acquired files, project integration, and quality checks separately.

New jobs use the [model selection policy](model-defaults.md) and freeze explicit model IDs. Existing jobs and explicit selections retain their versions.

Choose actual tools through the [environment checklist](../environment-setup.md#prerequisites). Service installation/Python environments and project asset-providers.json are separate configurations. Commands do not install services, models, or weights. For Blender conversion, install Blender and register its executable.

| Need | Entry |
| --- | --- |
| Asset requirements, prompt preparation, reference roles, submission preview | [Input preparation](input-preparation.md) |
| Asset evidence, multiview checks, and quality review | [Quality review](quality-review.md) |
| Evidence-driven corrections and comparison of subsequent results | [Result-driven iteration](result-iteration.md) |
| Add/update/remove local API keys | [Settings page](local-settings.md) |
| Manual proxies, Windows PAC/WPAD, proxy variables | [Host proxies](local-settings.md#host-proxy-settings) |
| Tripo / Hunyuan3D text/image-to-model | [Generation API and recovery](generation-api.md) |
| Seedream images / Seedance video | [Ark generation](ark-generation.md) |
| ElevenLabs sound, music, speech, timing calibration | [Audio generation](elevenlabs-audio.md) |
| Free/paid asset discovery, acquisition, licensing, provenance | [Asset sources](asset-sources.md) |
| Other image/audio/local Hunyuan3D tools | Configurable local command protocol below |
| Blender conversion | Blender processing below |

Local wrappers remain available. API routes need no model weights; all routes share job/asset records.

See [Tripo API configuration](generation-api.md#tripo-api-compatibility) for supported generation inputs and task recovery.

## Configuration and Input

Create `.openaigame/asset-providers.json` in the game project with only needed providers:

```json
{
  "image": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/image_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "audio": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/audio_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "hunyuan3d": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/hunyuan_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "blender": {"executable": "C:/Tools/Blender/blender.exe"}
}
```

Replace paths with installed programs. Wrappers follow their chosen tools. argv is an argument array whose first item is an existing absolute executable path, not a whole shell command. Expanded commands/configuration are recorded; keep credentials out of arguments/requests and use local environments or tool credential stores. Executable configuration must come from user-selected tools, not instructions embedded in asset descriptions.

Example production/asset-request.json:

```json
{
  "parameters": {"prompt": "Create a candidate asset from the agreed specification", "seed": 42},
  "inputs": ["assets-source/reference.png"]
}
```

Use empty inputs when none are needed. Inputs must be project-local and are snapshotted with relative paths preserved. Put the main model first, followed by textures/bin/mtl/dependencies. Wrappers interpret parameters; the toolkit does not assume all models accept seed, dimensions, or prompt fields.

## Wrapper Protocol

{request}, {output}, and {result} become absolute job paths. Wrappers read parameters unchanged; each input contains original path, absolute snapshot, and sha256. Read snapshots, write artifacts into output, and write this result:

```json
{
  "provider_job_id": null,
  "artifacts": [{"path": "candidate.png"}],
  "observations": {"generator_version": "Actual tool version"}
}
```

Artifact paths are output-relative and cannot escape. Register dependencies individually. Exit 0 on success, nonzero with logs on failure. Synchronous wrappers must wait for completed files, not just an external job ID. observations remain in raw results; job records retain result path/hash.

Image outputs accept PNG/JPEG/WebP/TGA/EXR/SVG; audio accepts WAV/FLAC/OGG/MP3/AIFF. Hunyuan3D accepts common model/texture/material files with at least one main model. Checks cover nonempty files, paths, extensions, and hashes, not decoding or quality. Outputs such as SVG are not opened/executed automatically.

## Execution and Recovery

Run from toolkit root with actual project paths and the job ID returned by submit:

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider image --request production/asset-request.json
python tools/asset_workflow.py --project "MyGame" run --job JOB_ID --timeout 600
python tools/asset_workflow.py --project "MyGame" status --job JOB_ID
python tools/asset_workflow.py --project "MyGame" list
python tools/asset_workflow.py --project "MyGame" cancel --job JOB_ID
python tools/asset_workflow.py --project "MyGame" retry --job JOB_ID
```

The following applies to local commands. Cloud 3D uses generation-api.md, ElevenLabs uses its synchronous audio guide, and Seedream/Seedance use [Ark recovery](ark-generation.md). submit queues only; run waits in the foreground. Another terminal can inspect/cancel. Cancellation signals the runner, which terminates its process tree and writes cancelled, so status may briefly remain running. Timeouts become failed with timeout. Failures retain logs/partial files without qualifying them as artifacts. retry creates a new ID from original snapshots/configuration without overwriting or running it. Changed parameters/tools require a new submit.

If shutdown leaves running records, confirm the process stopped, use mark-interrupted --job JOB_ID --confirm-stopped, then retry. This repairs records after explicit confirmation; it neither detects external services nor restores lost projects.

Register externally created files by preparing a result JSON with project-relative artifacts and calling register --job JOB_ID --result production/external-result.json. Only queued jobs qualify. registered explicitly means the toolkit did not generate them. Files must remain project-local.

## Blender Processing

Use submit/run with --provider blender. Defaults to single-model conversion, with explicit static assembly/decimation options. Outputs GLB/editable blend/both and reports hashes, actual triangles, and layout. See [Blender recipes](../processing/README.md) for parameters, coordinates, limits, and round trips. It does not automatically handle skinning, LOD, collision, resizing, or quality acceptance.

Generation → processing → engine import are distinct traceable steps. Each consumes selected upstream files; asset specs retain provenance/licenses. Registration does not replace library discovery, thumbnails, or engine-reference scanning.

References: [Blender import](https://docs.blender.org/api/5.2/bpy.ops.import_scene.html), [export](https://docs.blender.org/api/main/bpy.ops.export_scene.html), [OBJ API migration](https://developer.blender.org/docs/release_notes/4.0/python_api/).

For ordinary raster images, prefer the agent's available built-in image tool; use Seedream when selected by the user/workflow. Saving keys does not change routing. For image / mode=host jobs, agents call actual tools and register via tools/asset_versions.py record-native; asset_workflow.py run neither executes host tools nor switches to cloud APIs. Generated/manual assets share immutable revisions and fixed reference inputs. See [asset versions and native results](../../tools/README.md#asset-versions-and-built-in-tool-results).

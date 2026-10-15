# Asset Requirements and Input Preparation

[English](input-preparation.md) | [简体中文](input-preparation.zh-CN.md)

Use [asset_prepare.py](../../tools/asset_prepare.py) to compile asset requirements into a reviewable generation request. Preparation reads local files, checks the selected adapter, freezes references, and writes a submission preview. It does not contact providers, read API credentials, approve payment, or generate assets.

## Requirements and plans

Keep the original brief in an [asset requirements document](../../schemas/asset-requirements.schema.json). Each requirement has a stable ID, text, category (identity, appearance, technical), and priority (must, preference). Optional attribute/value fields detect different required values for the same named attribute; they cannot detect arbitrary contradictions in prose. References have project-relative paths and roles such as shape, material, or style. Label 3D views relative to the object.

The Agent writes an [input plan](../../schemas/asset-input-plan.schema.json), preserving user choices and assigning one route to every requirement:

| Route | Meaning |
| --- | --- |
| prompt | Append the requirement verbatim to the base prompt, when the adapter accepts text |
| reference | Send selected images and record what the Agent actually observed |
| postprocess | Retain a pending operation and acceptance check; generation does not guarantee it |
| unresolved | Record the gap and block queuing |

Decide whether to send every reference and explain exclusions. Requirements cannot rely on unsent references. Reference roles and observations are local metadata, not provider control parameters. When the distinction matters to a text-capable service, express it in the actual prompt too.

The Agent may supply rewrite.text and rewrite.reason. The original brief and a readable diff are retained; prompt-routed requirements are still appended verbatim. Without a rewrite, the original brief is used. Preserve language, style, explicit models, and inputs. Semantic review must account for the entire brief, preserved requirements, additions, and reference roles. Record the reviewer and reasoning. This is an Agent declaration, not a computed quality score or user approval.

For a door, describe material in the prompt and assign clear opening dimensions to a later mesh/collision check. A texture description does not establish working hinges or passage width.

## Prepare, inspect, and queue

Copy a matching pair from [the examples](../../templates/asset_preparation/README.md) into the game project, adapt it, and complete the Agent review. Example checks intentionally remain false. Paths in both documents are relative to the game project.

```sh
python tools/asset_prepare.py --project "MyGame" prepare --spec production/crate.spec.json --plan production/crate.plan.json --output production/prepared-crate
python tools/asset_prepare.py --project "MyGame" check --request production/prepared-crate/request.json
python tools/asset_workflow.py --project "MyGame" submit --provider tripo --request production/prepared-crate/request.json
```

Outputs:

- preparation.json: frozen specification/plan, source hashes, coverage, Agent review, resolved parameters, and intended payload.
- request.json: an existing asset-job request with a preparation path/hash.
- preview.md: prompt diff, requirement routes, reference decisions, pending checks, and submission preview.
- references/: copies of all declared references, including local-only references.

Exit codes: 0 ready; 1 report with unresolved checks; 2 invalid documents/files or failed verification. Existing output directories are never overwritten. Use a new directory for revised inputs.

The preview uses adapter payload builders, replacing image data and upload tokens with hash labels. It describes intended transmission, not provider receipt. Host-image previews describe prompt/references; the Agent maps them to the available host tool.

Queuing checks the record, provider settings, prompt, parameters, references, and original source hashes before creating a job. Queued jobs and explicit retries keep frozen inputs when working files change. Preserve the preparation directory with the job: execution, record validation, approval fingerprints, and asset-version provenance retain its link. API execution still uses existing per-job approval.

## Supported routes and limits

Supported: installed Tripo/Hunyuan3D API modes, Seedream images, Seedance videos, ElevenLabs sound effects/music/speech, and host images. Project asset-providers.json takes precedence; otherwise cloud providers use API settings and image uses host mode. Configure Hunyuan authentication explicitly when needed. Command wrappers remain available through the existing asset workflow, without a preparation capability contract.

Image-only 3D routes cannot receive rewritten text. Use actual reference evidence or explicit pending operations; unresolved requirements block queuing. Existing user/project prompt policies still apply. Generated multiview references are image deliverables and need visual review before model generation.

Speech keeps the exact brief as spoken text and rejects rewriting/appended instructions. Timing-linked audio continues through the [audio-window workflow](elevenlabs-audio.md); this tool does not compile those requests.

Checks cover schemas, explicit attribute conflicts, routing, image signatures/dimensions, adapter limits, and hashes. They do not fully decode every image or establish silhouette consistency, style, geometry, licensing, or Godot/Unreal readiness. Deferred checks remain pending; output quality is unverified.

After generation or acquisition, use [evidence and quality review](quality-review.md) to check the actual output against these requirements.

For confirmed defects, [result-driven iteration](result-iteration.md) prepares targeted corrections while preserving this baseline and the actual provider route.

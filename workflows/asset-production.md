# Asset Production, Processing, and Integration

[English](asset-production.md) | [简体中文](asset-production.zh-CN.md)

Create, modify, or replace images, models, animation, VFX, and audio within the existing project workflow. A local replacement does not restart project planning. Choose original production, existing assets, or a configured generation service according to the task.

## Inputs and Responsibilities

- When requirements are known, identify how and where the asset will be used. During exploration, inspect available assets and propose uses based on their capabilities. Before integration, specify interactions, the revision being replaced, and dependencies on scenes, materials, animation, and code.
- Art skills define use, style, specs, provenance, and inspectable deliverables; use templates/asset-spec.md as needed.
- Technical skills verify formats, coordinates, naming, dependencies, imports, and replacement impact. Design supplies collision, timing, and readability constraints.
- Management links tasks/specs/dependencies/versions without duplicating professional prose. Validation defines real checks/regression.

After acquisition/creation/integration, follow game-preproduction's workbench classification guidance. Inspect actual content roots. File categories and object usage tags differ; save clear categories through existing batch APIs, leaving unknowns unclassified. Check revisions/links before moves/replacements; classification must not rewrite bindings or acceptance.

## Two Planning Routes

- **Requirement-driven:** role/required behavior → asset discovery/composition checks → representative sample → revise/expand.
- **Asset-driven:** known experience/budget/engine constraints → asset capability/gap inventory → roles/gameplay/presentation candidates → representative sample → revise/expand.

Choose or alternate according to the task. Exploration need not wait for the phrase asset-driven, and searching is not mandatory for every task. Art references cover discovery and role/adaptation methods across characters, environments, VFX, audio, and other assets.

Searching, previewing, and creating exploratory samples do not require a complete design. Before batch processing or integration, define the selected roles and interactions and record why the assets fit them. Keep existing gameplay goals and rules; an asset suitable for a player character may not suit an enemy. Resolve fundamental mismatches by changing the asset or agreeing on a design adjustment. These responsibilities still apply when no matching skill is installed.

## Production and Handoff

For a new animated model, use the chosen production route: build the model before rigging it, or author the model to match an existing rig and animation set. Reuse prior decisions and any authorization to choose a route. The latter inspects clips, measures rigs, prepares prompts/dimension notes/references, authors/generates, calibrates/binds to the original rig, then replays/imports. See game-technical-art references/rig-aware-asset-production.md. Use existing specs; dimension-line drawings are optional. While undecided, inventory/measure independently. Static assets/local motion fixes need not repeat this choice. Platform auto-rigging does not prove local integration or motion fit.

Map work chooses representations/prototypes from goals, spatial questions, and evidence. game-level-design references/map-planning-and-iteration.md owns spatial iteration; art direction owns style; environment art references/map-from-design.md owns drawings/production. Preserve existing layouts and explicit requests without forcing top-down drawings or full grayboxes. Clarify missing style only when no selection delegation exists. Honor sketch-review endpoints and retest local impacts. Preserve source/revision/evidence distinctions without installed skills too.

Before representative production, establish target device, resolution/quality, and frame rate from valid choices. Samples include representative geometry/materials/foliage/shadows; inspect resources/frame times before scaling. Select LOD, Nanite, or instancing per asset class while retaining style/gameplay constraints. UE uses [mesh resources](../adapters/engines/unreal/mesh-resources.md); technical-art references/map-performance.md provides methods. Record generation/settings, persisted readback, visuals, and performance separately.

1. Choose an authorized production route and asset/placeholder plan or selection delegation. Installed tools/assets and prototype requests do not decide that plan. If implementation/generation is requested and direction is clear, execute available tools rather than delivering only a spec.
2. Use tools/asset_workflow.py with saved inputs/parameters/provider configuration. Read executable commands from .openaigame/asset-providers.json, not design prose. New paid API generation displays the job through local settings for user confirmation before run; credentials/queue alone are insufficient. See [generation authorization](../adapters/assets/generation-api.md).
3. Preserve inputs, outputs, logs, job IDs, and hashes. Keep failure evidence. Resume existing cloud IDs before considering explicitly requested regeneration. Local retries create linked jobs. Use asset_library.py for source acquisition and from-job for generated provenance; retain licenses/dependencies and old outputs. State unavailable tools accurately.
4. Conversion uses a separate downstream task consuming selected files, linked by input snapshots.
5. Inspect applicable openability, dimensions, silhouette, materials, motion, and audio. Extensions/hashes do not prove quality.
6. Integrate selected revisions in authorized projects with existing imports/references and a recoverable baseline. Registration alone does not import.
7. Check actual consumers for appearance, playback, function, performance, and replacement regression. Link reports/tasks/assets/runtime revisions and update management.

## Completion and Feedback

Record generated/registered, inspected, imported, and validated in-game separately. Complete only when scoped requirements have evidence; generation success does not pass slices/releases. Changed specs/assets/consumers invalidate affected checks.

See [asset integration](../adapters/assets/README.md) for APIs, wrappers, sources, and recovery.

At implementation closeout or interruption, update affected professional facts, task/milestone state, evidence, and next steps. For new projects, run `python tools/validate_records.py --project "GAME_PROJECT" --layout --production --closeout --markdown` and address results. For local changes or existing/custom layouts, check equivalent records without imposing new-project milestones. Structural validity is not acceptance.

Audio can follow real event windows. Preserve source-config revisions, originals, timing recipes, and listening results. See [audio integration](../adapters/assets/elevenlabs-audio.md); duration matching is not listening acceptance.

## Generation Routing and Revision History

Prefer available built-in image generation for ordinary raster work, unless explicit service choice, established workflow, or capability gaps dictate otherwise. Saved keys do not select a route. Follow game-art-direction references/generation-tool-selection.md; use native tools for editable authoring files.

Follow references/asset-versions.md for comparable results, parent revisions, reference roles, and companion files. Manual/built-in outputs use asset_versions.py; successful APIs link automatically. Selecting older revisions preserves newer ones and does not integrate them automatically. Upstream reselection flags downstream review without regenerating. Jobs/version records share actual artifacts; Art Direction links selections.

## Registration Is Part of Delivery

Follow [asset handoff (Chinese)](../skills/game-preproduction/references/asset-handoff.md): register files/provenance after creation/acquisition, consumers after integration, and actual results after validation. Structured tasks bind asset_scope; other tasks use equivalent checks. Complete missing records before delivery so users can inspect the files and their status directly.

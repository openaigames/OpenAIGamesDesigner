# Tools and Task Index

[English](README.md) | [简体中文](README.zh-CN.md)

Run commands from the source root or the installed `game-preproduction/runtime` directory, using Python 3.10+. Set `--project` to the absolute path of the actual game project; keep game outputs outside the toolkit installation. See [environment setup](../adapters/environment-setup.md) and the [documentation index](../docs/README.md).

| Task | Tools and documentation |
| --- | --- |
| Asset evidence, multiview checks, and quality review | `asset_quality.py`; [Quality review](../adapters/assets/quality-review.md) |
| Review-driven input corrections and bounded iteration | `asset_iterate.py`; [Result-driven iteration](../adapters/assets/result-iteration.md) |
| Project setup, stage tasks, and engine execution | `game_workflow.py`, `engine_workflow.py`; common workflows below |
| Core input, state, feedback, interaction, navigation, and scenes | `runtime_components.py`, `runtime_validation.py`; [runtime components](../adapters/engines/runtime_components/README.md) |
| Part, terrain, road, and room specifications | `procedural_assets.py`; [procedural generation](../adapters/processing/PROCEDURAL.md) |
| Multi-node static integration, replacement, and handoff | `static_scene.py`, `scene_replacement.py`, `scene_reception.py`, `scene_handoff.py`; [static scenes](../adapters/engines/static_scene/README.md) |
| Retargeting, constrained repair, character profiles, and native sampling | `motion_workflow.py`, `motion_profile.py`, `motion_native.py`; [asset processing](../adapters/processing/README.md) |
| Playback, locomotion blending, turning, layers, root motion, and foot/hand constraints | `motion_playback.py`, `motion_turns.py`, `motion_root.py`, `motion_constraints.py`; [playback integration](../adapters/engines/motion_playback/README.md) |
| Combined consumers and game component migration | `engineering_example.py`, `runtime_migration.py`; [combined example](../templates/engineering_example/README.md) |
| Asset sourcing, jobs, versions, and production handoff | `asset_library.py`, `asset_workflow.py`, `asset_versions.py`, `asset_handoff.py`; [asset integration](../adapters/assets/README.md) |
| Workbench and generation settings | `project_workbench.py`; [workbench](workbench/README.md) |
| Environment production and delivery | `environment_workflow.py`; [environment tools (Chinese)](../skills/game-environment-art/references/environment-tools.md) |
| Numerical data, audio, and action events | `numeric_workflow.py`, `audio_workflow.py`, `action_workflow.py`; instructions below and in their modules |
| Packaging, integrity checks, and installation upgrades | `package_skills.py`, `check_installation.py`, `bundle_upgrade.py`; [installation and migration](../docs/INSTALLATION.md) |

Describe the goal to the Agent; you do not need to enter every command yourself. Tools do not place game rules, assets, or saves in the shared runtime. Inspect an existing project before selecting the interfaces it needs.

## Start with a Natural-Language Request

Open the Agent in the game project and describe a goal, such as “Build an exploration puzzle game” or “Add a charged attack to this Unreal project.” The Agent reads the available material, resolves important unknowns, selects professional methods, and maintains project files. Existing projects continue from the requested change without restarting project definition. Open the workbench as needed.

For documentation-only work, use templates directly or generate a specific task. The default new-project [layout](../workflows/README.md) places professional entry documents at the game root and the native project in `game/`, creating other directories as needed. Establish and link six nonempty entry documents, progressively recording known and undecided details before major implementation. Discussion-only requests do not require saving files.

The Agent can use these entry points; users need not enter commands or name a skill:

```sh
python tools/game_workflow.py scaffold --project "MyGame" --brief "The user's actual game requirements"
python tools/validate_records.py --project "MyGame" --layout --markdown
```

`scaffold` creates six nonempty entry documents and a management index. It does not select an engine or generate gameplay and refuses to overwrite existing entry files. Before major implementation, save the GDD or local specification, technical entry, prototype milestone, and task, with links from management. Check them with `--layout --production --markdown`. Existing projects retain equivalent files and layouts and omit `--layout`. File and link checks do not establish design quality or user approval.

```sh
python tools/game_workflow.py document --project "MyGame" --kind task --id T001 --title "Validate the core interaction"
python tools/game_workflow.py document --project "MyGame" --kind feature-spec --id F001 --title "Charged attack"
```

Eight document kinds are supported: `prototype`, `vertical-slice`, `content-production`, `task`, `feature-spec`, `asset-spec`, `validation-report`, and `decision`. Use `content-production` for a content-production milestone. Create management through `scaffold`, `init`, or manual editing. New asset specifications use `design/assets/`; existing `assets/specs/` layouts remain valid. Existing targets are not overwritten; edit existing documents in place.

## Stage Tasks and Evidence

`document --kind task` creates a Markdown task description. Use the `task` subcommands to record plans, status, dependencies, and reviews across a continuous interval of the five stages. Creating Markdown does not create a stage-state record.

```sh
python tools/game_workflow.py task --project "MyGame" create --spec production/task-request.json
python tools/game_workflow.py task --project "MyGame" show --id T001
python tools/record_evidence.py --project "MyGame" --register production/evidence-request.json
```

Fill request files with the actual goal using the [task schema](../schemas/task.schema.json) and [evidence schema](../schemas/evidence.schema.json). See [stage execution](../workflows/stage-execution.md) for scope, progression, and recovery, and [runtime observations](../adapters/engines/observations.md) for event and spatial records. Small changes may reuse an existing task without creating a complete stage archive.

## Modify an Existing Project

Describe the change, such as “Add an economy system.” The Agent reads the existing design and implementation, clarifies what is needed, saves rules in the relevant GDD section or `design/features`, and links art requirements, technical interfaces, and validation in the same change or task record. Retain established formats and edit affected areas. Record design, implementation, and validation separately; leave undecided details explicit.

The management entry links the active change and summarizes progress. Update the project overview only when positioning or core experience changes. A design-only request does not trigger implementation; authorized implementation continues through changes and verification. Structural checks cannot establish semantic agreement across disciplines.

## Configure Engine Execution

Use [engine_workflow.py](engine_workflow.py) for Unity/Unreal project creation and production operations: native projects, scenes and components, imports and bindings, character animation, timed play recordings, and session recovery. See [engine production and sessions](../adapters/engines/sessions.md) for requests, requirements, and evidence scope. `game_workflow.py init/run` configures and runs existing projects, tests, and builds.

For new Godot projects and execution, see the [Godot workflow](../adapters/engines/godot/README.md). For existing Unity and Unreal projects:

```sh
python tools/game_workflow.py init --project "MyGame" --engine unity --engine-root game --editor "C:/Tools/Unity/Editor/Unity.exe"
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "C:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
```

These commands are alternatives for different projects. `init` preserves an existing `.openaigame/project.json`. Unity and Unreal require an existing native project. `--create-engine` supports Godot, Three.js, and Phaser; see [web games](../adapters/engines/web.md) for web initialization and builds. Edit existing configurations while preserving project-specific commands.

```sh
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action test --task production/tasks/T001.md --timeout 600
python tools/game_workflow.py status --project "MyGame"
```

Confirm the task's real path first. Unity/Unreal `doctor` checks executable paths and declared project versions, not the editor binary's actual version. Unity `prepare` performs a batch import and `play` opens the editor. Unreal `prepare` loads and records the actual project and version; `play` launches with `-game`. See [engine execution](../adapters/engines/execution.md) for native smoke, test, build, and export scenes, targets, helpers, and dependencies. Existing commands may override defaults.

## Asset Jobs and Record Checks

Use [asset_prepare.py](asset_prepare.py) to compile requirements, account for reference roles, and inspect the intended provider payload before queuing. See [input preparation](../adapters/assets/input-preparation.md) for examples and checks.

Configure a generation API or local command and request file using [asset integration](../adapters/assets/README.md):

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider image --request production/asset-request.json
python tools/asset_workflow.py --project "MyGame" run --job JOB_ID --timeout 600
python tools/asset_workflow.py --project "MyGame" status --job JOB_ID
python tools/validate_records.py --project "MyGame" --markdown
```

Submission and execution are separate: submitting does not start generation. The Agent can execute sequentially within the user's authorization without repeated manual steps. Checks report the number of records inspected; zero records do not demonstrate a run. Markdown checks cover local links. Professional content, visuals, gameplay, and asset permissions need their own checks.

See the [validation guide](../tests/README.md) for an end-to-end trial and the evidence needed for each step.

## Numerical Table Round Trip

`game-numerical-design` owns numerical modeling and table methods; system or combat design owns rules, and engineering handles write-back. Older `game-design` numerical references retain navigation.

Requests can be natural language: “Export editable weapon parameters,” “Set heavy-attack damage to 60 and compare the effect,” or “Apply my Excel changes to the project and verify them.” The Agent reads the design and technical references and performs the relevant operations. The CLI is a reproducible file interface, not a requirement for users to operate manually.

`numeric_workflow.py` works with existing, explicitly bound JSON record arrays. It exports a CSV working copy, reads a plain numeric CSV or XLSX sheet, produces a diff, and updates specified fields in existing records. Without an engine project, the Agent first prepares candidate tables and specifications. The tool does not derive balanced values from a gameplay description or create engine loaders. Keep established Unreal, Unity, or Godot data formats and importers rather than converting them solely for this tool.

Save a binding in the game project, for example `design/numerics/combat-binding.json`:

```json
{
  "version": 1,
  "target": "game/data/combat.json",
  "records_key": "attacks",
  "id_field": "id",
  "fields": {
    "damage": { "type": "integer", "unit": "HP/hit", "min": 0, "max": 1000 },
    "cooldown": { "type": "number", "unit": "seconds", "min": 0.01, "max": 10 }
  }
}
```

Fields and ranges here illustrate the format; derive actual values from the project and specification. A target may look like `{"attacks":[{"id":"LIGHT","damage":30,"cooldown":0.5,"animation":"LightAttack"}]}`. Omit `records_key` for a root array. Top-level array keys are supported, arbitrary JSONPath is not. IDs must be stable strings and editable fields numeric. Unbound fields such as `animation` remain unchanged.

```sh
python tools/numeric_workflow.py --project "MyGame" export --binding design/numerics/combat-binding.json --session design/numerics/exchange-01
python tools/numeric_workflow.py --project "MyGame" plan --session design/numerics/exchange-01 --table design/numerics/exchange-01/parameters.csv --out design/numerics/exchange-01/plan.json
python tools/numeric_workflow.py --project "MyGame" apply --plan design/numerics/exchange-01/plan.json
```

`export` creates `parameters.csv` and `baseline.json` without overwriting an existing session. After editing the CSV, `plan` reports IDs, fields, old/new values, and units without writing the game. Review the diff against project rules, then use `apply` within the authorized scope; planning adds no separate approval requirement. After further table edits, use a fresh `--out` for a new plan.

For Excel, point `--table` to a project-local `.xlsx` and select `--sheet Parameters` or the actual sheet name. Its first row must match the CSV field names; include only the ID and bound fields, without decorative titles, notes, or total rows. Other sheets may contain formulas, curves, and explanation. XLSX reading optionally requires `openpyxl`; CSV does not. The tool does not create XLSX files; the Agent can use available spreadsheet tools. Copy external files into the game project under a new name, retaining originals, rather than importing values paraphrased in chat.

The tool rejects blank or invalid numbers, duplicate or unknown IDs, missing rows, out-of-range values, changed fields, formula/error cells, and bindings or configuration changed since export. It does not fill blanks with zero or add/delete records. Row order does not affect ID matching. Recalculate and inspect formulas with a trusted spreadsheet tool before exporting plain values; do not apply stale cached results. Run project-specific cross-field and reference checks separately.

`apply` rechecks the table, baseline, and plan; saves the original and `.openaigame/numeric-imports/<id>/receipt.json`; and atomically replaces the target. Pause competing writers or editor exports during application. If the project has changed, export again and merge the user's edits. There is no automatic three-way merge, file watcher, or concurrency lock. `configuration_written` means the file was written; `engine_validation` remains `not_run`. Follow with actual engine import/reload, configuration checks, gameplay tests, and separate evidence.

After interruption, inspect the receipt's `prepared`/`failed` state, target, and before/after hashes to establish whether writing occurred. Restore from `before.json` only after confirming no later edits, and save a recovery record. Merge later changes instead of overwriting them. The technical skill's numerical-exchange reference describes recovery. Numerical imports have their own records; generate runtime or engine-session records when actually executing those tools. See the [schemas](../schemas/README.md) for data contracts.

## Update Records After Implementation

Before delivery, record actual engine, architecture, project, and run entry points; used placeholder art, provenance, and limitations; validation results, untested areas, and interruption reasons; task and milestone status and evidence; and management links, stage, goal, and next steps. An unfinished stage is valid, but an existing project or milestone must not still be described as absent. Future choices may remain undecided; recording completed work needs no new approval.

After new-project implementation, including failure or interruption, run `validate_records.py --project <project-root> --layout --production --closeout --markdown`. Read and address the report. Do not claim management is complete when structural checks fail or change status to success merely to pass. Retain unresolved failures and next steps. For custom or existing layouts, check equivalent content without forcing a new directory structure.

Closeout checks the six entry documents, real indexes, leftover initial placeholders, and evidence links. Management, risk/validation, the active task, and milestone should link actual `runs/<id>/manifest.json`, `runs/engine-*/session.json`, `runs/create-*/session.json`, or reports under `tests/reports/` or `production/validation/`. Use `--report-root <project-relative-directory>` for custom reports. Direct engine-call reports should include input versions, commands, exit codes, logs/output paths, and observation limits. These checks validate structure and references, not the truth or completeness of every statement.

## Engine Helper Scripts

`python tools/engine_setup.py --project "MyGame"` explicitly installs Unity Editor helpers and refuses to overwrite modified files. See [engine execution](../adapters/engines/execution.md) for Unity/Unreal native testing and builds, and web browser smoke configuration.

## Installation Integrity and Maintenance Tests

Each distribution stores content metadata and file hashes in `game-preproduction/runtime/bundle-manifest.json`. Run `python <runtime>/tools/check_installation.py --skills-root <installed-skills-parent>` to report `missing`, `changed`, and `extra` files within toolkit skill directories. Other skills and personal files at the root are excluded. The check does not overwrite customizations or delete extras; compare, back up, and merge actual differences before updating. An older installation without a manifest needs a newly packaged distribution and synchronization; a missing manifest is not a successful integrity check.

In the source repository, `python tools/run_tests.py` runs root tests and skill script tests, including `game-animation-pipeline` protocol checks. Use `--group game-animation-pipeline` to run that group alone. The maintenance runner and CI are source-only tools.

Build distributions from source with `tools/package_skills.py`; do not upload a personal installation directory. Packaging excludes local keys, environment configuration, logs, project records, caches, and work outputs. `.gitignore` also excludes these from ordinary Git staging. `.env.example` and `.env.template` are for credential-free examples only. Keep private release drafts and execution records outside the repository or in ignored local directories.

Schemas define data formats, the packaged manifest verifies installation integrity, and third-party licenses remain included.

### Asset Sources and Registration

`asset_library.py sources` filters independently by asset type, pricing (`--pricing free|mixed|paid|unknown`), login requirement, and acquisition method. Pricing filters match source-level categories; check the selected resource's actual price on mixed sites. Commands also provide live Poly Haven `search`/`files`, download or local-copy `acquire`, generated-job `from-job`, and `list`/`verify`/`index`. See [asset sourcing](../adapters/assets/asset-sources.md) and [generation integration](../adapters/assets/generation-api.md) for API `doctor`/`resume` and credentials.

### Local Key Settings

Run `python tools/settings_server.py` to configure Tripo, the Tencent Hunyuan compatible API, ElevenLabs, and Volcengine Ark keys (shared by Seedream and Seedance), without a game project. `--status` reports configuration presence; `--no-open` lets the Agent open the returned startup URL. See [local settings](../adapters/assets/local-settings.md).

## Project Workbench and Asset Audit

```sh
python tools/project_workbench.py --project "MyGame"
python tools/project_workbench.py --project "MyGame" --view services
python tools/project_workbench.py --project "MyGame" --approve-job JOB_ID
python tools/asset_audit.py --project "MyGame"
```

Replace `MyGame` with the absolute game root. The shared interface binds to that project on an automatically allocated local port. Use `--no-open --ready-file <new-temporary-file>` when the Agent opens the returned URL. Browsers on the same computer can use the same address and establish a session automatically. The server listens only on `127.0.0.1`, with Origin and CSRF checks on writes. It exits after 120 idle minutes by default; closing a page does not stop it immediately. Game assets stay in the game project; web files and Three.js live in the shared runtime. Redistributable, toolkit-authored fixtures are included under runtime `tests/fixtures/`; real user projects and assets are excluded. Full maintenance tests and packaging scripts remain source-only.

The workbench supports local 3D, images, audio, video, particle demonstrations, and engine-file indexing. Real-time 3D supports GLB/glTF, OBJ with project-local MTL/textures, and FBX models, skeletons, and animation. Missing textures and incompatible skeletons show specific limitations. The browser does not execute Niagara, AnimBP, collision, or final engine materials. Animation previews can follow the character or show its full trajectory without changing the source. Tags come from art records; unregistered assets remain browsable.

Export actual engine character consumers and synchronize through `engine_characters.py` into `.asset-browser/characters.json` and `previews.json`. Select a character to choose associated actions, distinguishing direct component bindings, static AnimBP references, and project-declared available sets. Preview exports support FBX and GLB. Source, derived, and declared dependency files are pinned by SHA-256; changes invalidate old previews. Content roots determine candidate/game scope, excluding runtime backups and derived previews from candidate rescans. Browser playback and final game behavior need separate evaluation; see [Unreal native animation](../adapters/engines/unreal/native-animation.md) for export limitations.

See [game content roots](workbench/README.md#game-content-roots) for scope and exclusions. Model previews retain playback controls. The [legacy clip-selection API](workbench/motion-review.md) supports querying, saving, and exporting older decisions; the workbench has no such form. Historical decisions neither move files nor replace engine validation.

For numerical predictions, use `numeric_workflow.py --project <project> model --request <relative-request.json> --out production/numeric-models/<revision>.json`. Models support explicit expression trees, piecewise-linear curves, and stepped thresholds. Parameters and measured values reference actual JSON pointers, authoritative files, and execution records. Outputs include JSON and a standalone HTML comparison report. `model-check --report <relative-report>` checks dependency freshness. Predictions do not overwrite authoritative game parameters or establish measured behavior or optimal feel.

For initial records in older projects, `asset_audit.py --project "MyGame" --init-art` preserves existing prose; `--register-missing` registers file facts only. The Agent then completes objects and tags from the existing inventory, retaining stable IDs and unknown uses. Configure a custom art entry through the project-relative `art_document` in `.openaigame/workbench.json`. The professional skill's workbench reference defines marked sections and legacy mappings.

The services page uses local encrypted storage; saving settings does not generate assets. The jobs page reads actual `asset-jobs`, creates API text requests, and lets users inspect existing requests. Following authorization, the Agent runs `asset_workflow`; the UI does not simulate progress or call providers itself. Standalone settings also work without a game project.

## Image and Video Generation

`asset_workflow.py --provider seedream` supports single-image text generation and editing with one reference image. `--provider seedance` supports text-to-video and first-frame-to-video, polling a task ID before downloading results. The workbench exposes the corresponding parameters, references, and per-job authorization. Seedance resumes an existing task; Seedream does not automatically resend a synchronous request. See [Ark image and video integration](../adapters/assets/ark-generation.md).

## Audio Generation and Timing

`asset_workflow.py --provider elevenlabs` uses the same key settings, authorization, and asset registration flow. Workbench jobs support effects, music, and character dialogue. `audio_workflow.py` measures local WAV files, decodes MP3, and crops to gameplay windows, preserving originals and writing a new revision and recipe. See [ElevenLabs game audio](../adapters/assets/elevenlabs-audio.md). Decoding requires FFmpeg. Matching duration does not establish listening quality or engine validation.

### Browse Assets by Purpose

The library starts with all assets and provides categories for characters, weapons/equipment, props, maps/environments, animation, VFX, materials/textures, music/audio, 2D art/UI, plugins/code, and Blueprints/gameplay templates, plus unclassified assets. Audio filters include music, effects, and speech. Select scope first, then category and purpose tags; directory, search, and favorites filters remain independent. Legacy topic data is retained for compatibility.

Classification first uses saved records matching the current file version, then existing character bindings, registered engine types, file content/format, and directory suggestions. An ordinary FBX or `.uasset` is not classified as a character or Blueprint solely by extension. Insufficient information leaves it unclassified. Models containing clips also appear under animation, so counts may overlap without copying files or implying compatibility or quality.

Cards and details show category labels. In details, edit the primary category and audio kind or restore automatic classification. Bulk classification covers all filtered results across pages, shows the count before saving, and accepts at most 500 items. Overrides persist in `.openaigame/asset-taxonomy.json` with each file's SHA-256. Replacements and moves require review; concurrent edits and corrupt records are not silently overwritten. This file stores classification only; Art Direction owns shared tags and objects, while content directories determine scope.

Plugin descriptors, common source files, and shaders can be listed and classified without executing or installing them. Preview support still depends on format; a category does not make an unsupported engine asset previewable.

## Asset Versions and Built-In Tool Results

`asset_versions.py --project <project> list` reads history; `apply --request request.json` performs explicit operations. Request paths are project-relative and files must be inside the project. Operations are `create` (`title`, `kind`, `files`), `add` (`group`, `files`), `select` (`group`, `version`, `reason`), and `archive` (`group`, `version`, `archived`). File entries can be paths or `{ "path": "...", "sha256": "...", "role": "front" }`. Optional fields include `parent`, `references`, and `note`. Store alternative versions of one deliverable separately; put companion views and textures in the same version's `files`. `revision` enables optimistic concurrency checks.

`record-native --request native-result.json` registers files actually created and saved by an Agent's built-in tool; it does not call a model or cloud service. For example:

```json
{
  "prompt": "Keep the armor structure and adjust the colors",
  "tool": "builtin:imagegen",
  "inputs": ["concepts/hero-base.png"],
  "outputs": ["concepts/hero-front.png", "concepts/hero-side.png", "concepts/hero-alternative.png"],
  "output_sets": [["concepts/hero-front.png", "concepts/hero-side.png"], ["concepts/hero-alternative.png"]]
}
```

Set `tool` to the tool actually used; an example name is not execution evidence. For an existing built-in workbench job, supply `job` to reuse its snapshots and parameters. Read the snapshots and run the actual tool before registering outputs. Multiple images become separate versions by default. Use `output_sets` to group companion files for one alternative, with each output appearing exactly once. Alternatives share the original base; they do not automatically form an edit chain.

For edits or references to registered versions, add `lineage: { "group": "GROUP_ID_OR_NULL", "parent": "VERSION_ID_OR_NULL", "note": "Change description", "references": [{ "group": "REFERENCE_GROUP_ID", "version": "REFERENCE_VERSION_ID", "role": "Color reference" }] }`, using actual IDs from `list` and JSON `null` when absent. Image jobs include the associated primary images in actual input snapshots. Manual inputs must also match the files really passed to the tool. Built-in jobs prepare at most five images and reject excess or unsupported formats. References for non-image generation record provenance; they do not imply images were uploaded.

API/local-command jobs save versions after `succeeded`, and external registrations after `registered`; inspect `asset_version` in the job. Registration failures preserve outputs and record `version_registration_error`. `link-job --job <job-id>` retries registration without regenerating. Re-registering the same outputs does not duplicate versions.

Records and immutable copies live in `.openaigame/asset-versions`; Art Direction summaries link the selected and latest results. Selecting changes the record, not game files. Snapshot storage, readability, selection, integration, and quality acceptance remain separate facts. Copies use disk space; archiving collapses display without deleting originals.

## Input, Focus, and Pause

Core provides action configuration, rebinding, contexts, multiple pause reasons, and input preferences. It merges left/right Shift, Ctrl, and Alt keys and supports wheel-up/down events. Wheel input is discrete: switch weapons or pages through action callbacks rather than polling sustained strength. Projects define sprint, crouch, and weapon rules. See [input](../adapters/engines/runtime_components/INPUT.md).

```sh
python tools/runtime_components.py create --engine godot --scenario input --project NEW_PROJECT
python tools/runtime_components.py create --engine unreal --scenario input --project NEW_PROJECT --ue-root UE58_ROOT
```

Use a new directory for each creation. Select `state`, `feedback`, `interaction`, `navigation`, `scene`, `static`, `training`, or `puzzle` for the corresponding standalone case. See [runtime components](../adapters/engines/runtime_components/README.md) for configuration and validation. The runner saves a fresh report, exit code, and actual assertions; standalone packages require a separate launch.

## Action Timing Checks

`action_workflow.py` records and compares input, rules, animation, and sound triggers. The [event recorder](../adapters/engines/action_timing/README.md) can be used independently. The shared workbench has no separate action-check page; CLI records and compatibility APIs remain available.

Use [motion_workflow.py](../adapters/processing/MOTION.md) for character processing and [motion_playback.py](../adapters/engines/motion_playback/README.md) for playback. Optional paths cover [locomotion](../adapters/engines/motion_playback/LOCOMOTION.md), [turning](../adapters/engines/motion_playback/TURNING.md), [layers](../adapters/engines/motion_playback/LAYERS.md), [root motion](../adapters/engines/motion_playback/ROOT_MOTION.md), and [foot/hand constraints](../adapters/engines/motion_playback/CONSTRAINTS.md). Existing graphs, assets, and game rules are not converted automatically.

## Distribution and Combined Examples

`engineering_example.py` creates a combined consumer from a checked character revision and bindings. `runtime_migration.py plan/apply/rollback` explicitly migrates project-local core/playback copies while protecting customizations. See [combined project integration](../templates/engineering_example/SUPPORT.md).

Multi-node static workflows proceed through `static_scene` → `scene_replacement` → `scene_handoff`. `scene_reception.py` creates a combined reception example for its specific input contract. See [project reception](../adapters/engines/static_scene/RECEPTION.md) for inputs and resource boundaries. This workflow does not expand the single-mesh input contract of `static_assets.py`.

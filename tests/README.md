# Tests and Validation

[English](README.md) | [简体中文](README.zh-CN.md)

Validate code, native-tool integration, and the game experience separately. For each case, record the input revisions, commands, outputs, logs, and observations in a validation report.

## Module Test Entry Points

Run tests for the affected modules from the source repository root:

```sh
python -m unittest discover -s tests -p test_runtime_upgrade.py
python -m unittest discover -s tests -p test_runtime_migration.py
python -m unittest discover -s tests -p test_engine_packages.py
python -m unittest discover -s tests -p test_project_contract.py
```

| Scope | Tests and native examples |
| --- | --- |
| Asset input preparation | `test_asset_preparation.py`; offline routing, missing/conflicting constraints, file changes, payload previews, and queue/version integration |
| Core installation, migration, and input | `test_runtime_upgrade.py`, `test_runtime_migration.py`; [native core examples](../adapters/engines/runtime_components/README.md) |
| Feedback, interaction, and navigation | `test_feedback.py`, `test_interaction.py`, `test_navigation.py`; native engine scenario runners |
| Generated scenes, static assets, and handoff | `test_scene_generation.py`, `test_static_assets.py`, `test_static_scene.py`, `test_scene_replacement.py`, `test_scene_handoff.py` |
| Character animation | `test_motion_workflow.py`, `test_motion_profile.py`, `test_motion_playback.py`, `test_motion_layers.py`, `test_motion_root.py`, `test_motion_constraints.py`, `test_motion_handoff.py` |
| Documentation, distribution, and rollback | `test_project_contract.py`, `test_engine_packages.py`, `test_bundle_upgrade.py`; source and package links, execution after relocation, and protection of source files |

Maintenance tests, scenario runners, native test fixtures, and skill script tests stay in the source repository. Installation bundles contain runtime tools and editable examples under `templates/` and skill assets. Run tests from source and point CLI scenarios at a separate installation with `--runtime PATH_TO_GAME_PREPRODUCTION_RUNTIME` to verify it without copying tests into the bundle. Keep generated logs, reports, and machine-specific trial scripts outside the public source; fixture READMEs describe reproducible setup.

```sh
python tests/scenarios/asset_iteration_audit.py --runtime "SKILLS_ROOT/game-preproduction/runtime" --output NEW_ITERATION_DIRECTORY
python tests/scenarios/asset_quality_audit.py --runtime "SKILLS_ROOT/game-preproduction/runtime" --output NEW_QUALITY_DIRECTORY
```

## Native and Human Validation

Use real engines and isolated projects to check import, runtime behavior, saving and reopening, and target builds. Automated input, physical-device testing, visual and audio review, and human playtesting answer different questions.

| Order | Target | Procedure and criteria | Evidence to retain |
| --- | --- | --- | --- |
| 1 | Tools and distribution | Run unit tests, check source and package links, validate all sixteen skills, and execute the CLI after relocation | Source revision, command results, package inspection, and execution logs |
| 2 | Skill behavior | Start from an idea, then change an existing project; check that questions and documents fit the task without restarting project definition or creating an unrequested dashboard | Original request, conversation, files, and observations |
| 3 | Local generation tools | Submit and run a job through the configured wrapper; check status, open outputs, and exercise failure and retry | Tool and model identifiers, job records, outputs, and quality review |
| 4 | Blender | Import a textured model, convert it, reopen it, and inspect scale, materials, animation, and dependencies | Input and output files, logs, and reopen checks |
| 5 | Godot prototype | Implement the specification, run tests, play the game, export, and launch the standalone build | Specification, test reports, observations, and build/runtime results |
| 6 | Unity and UE | Connect an existing project, run `doctor`, configure native actions or overrides, package, and launch | Engine and project identifiers, raw XML/JSON reports, logs, and build results; see [execution](../adapters/engines/execution.md) |
| 6a | Three.js and Phaser | Initialize, install dependencies, build, serve the export over HTTP, and interact with it | Lockfiles, install/build logs, browser errors, and input results; a blank canvas is insufficient |
| 6b | MCP | Verify project identity, read and edit a test object, save, reopen, and run; inspect state after a disconnect | Provider and tool list, raw responses, and persistence checks |
| 7 | Vertical slice | Agree on experience and quality targets, integrate content, measure and playtest, then deliver an editable project | Goals, revisions, performance measurements, feedback, and acceptance decisions |

Numerical collaboration also needs a complete round trip: export configuration → edit CSV or Excel → compare and validate → apply → reload in the engine → verify effective values. Automated tests cover conflicts, ranges and types, unbound fields, backups, failures, and optional XLSX support. Native DataTable and GAS integration need engine tests.

Use a project copy of the [validation-report template](../templates/validation-report.md) or an equivalent report to record scope, revisions, execution, observations, failures, and next steps. Link reports from project management and update conclusions only where the evidence supports them. Choose engine checks according to the game's needs.

```sh
python tools/run_tests.py
python tools/package_skills.py --output dist/NEW_VALIDATION_BUNDLE
python tools/validate_records.py --project "ACTUAL_GAME_PROJECT" --markdown
```

The source-only runner executes root tests and each skill's `scripts/tests` in separate processes and aggregates failures. Use `--list` to list groups and `--group core`, `--group game-art-direction`, or `--group game-animation-pipeline` to select one. A selected group does not cover the full suite.

Maintenance tests require Python 3.10+ and Node.js. CI uses Node 22 on Windows with Python 3.10 and 3.12. Pass `--node <executable>` when Node is not on `PATH`. Install YAML and Excel dependencies with `python -m pip install -r tests/requirements.txt`. Set `OAGD_BLENDER` for native Blender regressions; a skipped native test means that check was not run. Inspect the actual CI logs for results.

Source-only behavioral evaluation sets include `ability-system-choice-scenarios.md`, `character-animation-scenarios.md`, `combat-design-scenarios.md`, `production-method-scenarios.md`, and `numerical-design-scenarios.md`. The ability-system cases cover GAS selection, retaining custom implementations, and distinguishing animation packs, controllers, and full frameworks. These files provide evaluation inputs; record actual evaluations separately. Task tests should also verify that discipline assignments persist and unknown disciplines are rejected.

## Workbench and Asset Services

Workbench regressions cover the asset library, generation jobs, service settings, legacy launch routing, and retained record APIs. Browser checks cover redirects, asset plans and gaps, character/action selection, and service/job pages without paid generation. Backend, migration, and browser-control tests use the same runner.

Asset API tests use controlled responses and subprocesses to check authorization, job-ID recovery, file and ZIP handling, provenance, and license records without paid requests. Validate a provider separately with `doctor` → a small authorized job → query, download, and open → resume the same job ID where supported. Catalog entries and search plans do not establish API connectivity.

## ElevenLabs Audio Regression

`test_elevenlabs_audio.py` covers parameters, single-use authorization, stale snapshots, protection against credential leaks through redirects, interrupted synchronous responses, MP3 decoding, and PCM cropping with local test audio. FFmpeg or imageio-ffmpeg provides the codecs. `test_audio_brief.mjs` and HTTP tests cover forms, timing windows, and notices about changed source files. Account access, generated audio quality, and in-game effects require separate checks.

## Host Proxy Regression

`test_host_proxy.py` covers environment-variable priority, `NO_PROXY`, manual proxies, Windows PAC outcomes, redirect routing, binary requests, headers, streaming, interruption cleanup, and secret protection. It simulates Windows and network processes without real credentials. Use official read-only APIs for separate host and account connectivity checks.

## Asset Classification Regression

`test_rig_compatibility.mjs` checks FBX skinning, hierarchy, duplicate-name conflicts, and deformation. Browser tests use real FBX files for model selection, missing matches, and different poses. An animation containing only a gun or attachment cannot show the character's complete reload motion.

`test_asset_taxonomy.py` covers category and format separation, suggestions, character-motion links, audio types, legacy topics, unknown resources, overrides and recovery, replacements, moves, duplicates, shared tags, atomic batches, conflicts, corruption, and sessions. `test_asset_categories.mjs` covers filters, animation labels, deduplicated totals, and legacy functions. Browser tests verify editing, persistence after refresh, pagination, and preview entry points.

## Ark Image and Video Regression

`test_ark_generation.py` uses synthetic keys and controlled responses to check shared-key storage and removal, defaults, limits, snapshots, authorization, lost image responses, video polling, recovery with the same job ID, output formats, and duplicate-submit prevention. `test_project_workbench.py` covers job creation, parameter readback, authorization, and shared keys. These tests consume no cloud quota; account access and generated image/video quality need separate validation.

Asset revision tests run with `python -m unittest discover -s tests -p test_asset_versions.py` and `node tests/test_asset_versions.mjs`. They cover selection, branches, immutable snapshots, references, concurrency, companion files, alternatives, host jobs without cloud execution, authorization, grouping, and production briefs, using isolated files without paid models.

Asset quality behavior is covered by `test_asset_quality.py`. Run `python tests/scenarios/asset_quality_audit.py --output NEW_DIRECTORY` for isolated CLI cases with network access denied. The scenarios use declared synthetic judgments, not production art approvals; see [quality review](../adapters/assets/quality-review.md).

`test_asset_iteration.py` checks targeted changes, preserved requirements, actual payload differences, reference snapshots, provenance, regression detection, and bounded retries. Run `python tests/scenarios/asset_iteration_audit.py --output NEW_DIRECTORY` for isolated CLI cases with socket connections denied and jobs queued only. Synthetic judgments exercise the workflow, not cloud generation quality. See [result-driven iteration](../adapters/assets/result-iteration.md).

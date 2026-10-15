# Result-Driven Asset Iteration

[English](result-iteration.md) | [简体中文](result-iteration.zh-CN.md)

Turn a reviewed defect into a targeted input correction, then compare the next result against the same requirements. The Agent interprets visual evidence and writes the correction; the tool preserves the brief, compiles the actual provider input, verifies evidence freshness, and tracks progress. It does not call a language model or dispatch generation.

Use this after [input preparation](input-preparation.md) and [quality review](quality-review.md). Python 3.10+ and Pillow are required. Keep all records inside the game project and use a new output directory for each command.

## Choose the Next Action

| Action | Appropriate use | Output |
| --- | --- | --- |
| `regenerate` | A confirmed defect can be addressed through supported generation inputs | Frozen requirements, references, prepared request, and preview |
| `postprocess` | Local editing is more appropriate, such as fixing a pivot or simplifying geometry | Explicit tasks and expected results; no generated request |
| `collect_evidence` | Missing views, uncertain scale, or low-confidence observations | Evidence tasks; no speculative correction |
| `accept` | The source review passes | Acceptance record for that scope |
| `stop` | Further attempts are not justified | Stop record with the reviewer's explanation |

Acceptance never selects an asset version, replaces a game file, or approves engine/game behavior. Processing and evidence tasks remain unexecuted until the Agent uses the appropriate tools.

## Prepare a Correction

```sh
python tools/asset_iterate.py --project MyGame draft --report evidence/base-assessment/quality.json --output production/revision-draft
python tools/asset_iterate.py --project MyGame prepare --plan production/revision-decision.json --output production/revision
python tools/asset_iterate.py --project MyGame check --iteration production/revision/iteration.json
```

Inspect `issues.json`, copy the draft plan to the decision path, and fill it using actual observations. The draft has incomplete review flags and cannot be dispatched. Every selected issue needs a concrete change or task. Record why it should help and what the next inspection should observe.

Issue IDs are namespaced: `criterion:opening`, `check:triangles`, or `finding:...`. Criteria and measurements must be rechecked under the same ID. A multiview finding also needs an existing semantic criterion: removing a duplicate-pixel warning alone cannot prove coherent geometry.

The [plan schema](../../schemas/asset-iteration-plan.schema.json) and [examples](../../templates/asset_iteration/README.md) describe four changes:

- `prompt`: append a targeted instruction to the previous prompt. The original brief and requirement definitions remain intact.
- `reference`: add or replace an image with explicit role, direction, observed content, and whether to send it. New bytes are copied into the iteration. Reinspect every requirement route that used a replaced reference.
- `parameter`: change a supported provider parameter with a key/value pair. Existing model and settings remain frozen unless explicitly adjusted through supported inputs.
- `route`: update how an existing requirement is realized and checked. Requirements themselves cannot be removed or weakened.

Inspect `preview.md` and `prepared/preview.md`. The latter shows the actual provider payload. Tripo image-to-model cannot use a text-only correction where that route does not send a prompt: change its input reference and affected routes, or choose another method. An unchanged transmitted payload is rejected even if explanatory notes changed. Speech corrections cannot rewrite literal spoken words through a prompt addition.

## Generate and Reassess

Queue the prepared request through the existing asset workflow:

```sh
python tools/asset_workflow.py --project MyGame submit --provider tripo --request production/revision/prepared/request.json
```

Queuing does not execute a provider. Run through the existing per-job authorization flow when generation is authorized; retain job recovery and duplicate-submission protections. The request and authorization fingerprint include the iteration link. If the baseline pins an asset version, registration retains its parent and iteration provenance. A parent link does not implicitly upload its image.

Collect the actual output with a new quality plan. Keep the asset, use, environment, criteria, tolerances, deferred requirements, and required directions unchanged; link `production/revision/prepared/preparation.json`. Existing view IDs retain their set and direction; extra views may be added. Reinspect previously passing requirements as well as the target defect.

```sh
python tools/asset_iterate.py --project MyGame compare --iteration production/revision/iteration.json --report evidence/candidate-assessment/quality.json --output evidence/revision-comparison
python tools/asset_iterate.py --project MyGame check --comparison evidence/revision-comparison/comparison.json
python tools/asset_iterate.py --project MyGame draft --report evidence/candidate-assessment/quality.json --previous evidence/revision-comparison/comparison.json --output production/next-draft
```

For processing or additional evidence, retain the prior input preparation. Keep source files, renders, references, decisions, and reports: checks follow their dependencies, and stale evidence blocks reuse. Hashes prove content consistency, not authorship or that a reviewer actually inspected a file.

## Progress and Stopping

`comparison.json` lists resolved/unresolved targets, numerical movement toward or away from tolerances, mandatory regressions, new failures, and preference regressions. An improved total score cannot hide a previously passing requirement that now fails or becomes unknown. Identical output bytes cannot count as generation or processing progress. Supplemental evidence may resolve an unknown without changing the source.

Recommendations are `continue`, `collect_evidence`, `change_method`, `complete`, or `stop`. Defaults allow at most three rounds and two consecutive rounds without progress; set both before the first round, within the supported limit of eight. Subsequent plans must link the previous comparison and retain the policy. Regressions require changing method. A stopped or completed chain cannot dispatch further regeneration. A new strategy needs an explicit new baseline and an explanation; do not discard history to reset counters.

`complete` means the fixed source-review scope passed. It does not prove performance, animation, collision, or readability in Godot or Unreal. Those remain separate project checks.

Exit codes: 0 for draft, ready, accepted, stopped, complete, or improved; 1 for evidence/processing handoffs and comparisons needing work; 2 for invalid inputs or stale evidence. Reproducible offline cases remain in the source repository under `tests/scenarios/asset_iteration_audit.py`; their synthetic judgments test the workflow, not a provider's artistic quality.

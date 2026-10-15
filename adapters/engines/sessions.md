# Engine Production and Sessions

[English](sessions.md) | [简体中文](sessions.zh-CN.md)

[engine_workflow.py](../../tools/engine_workflow.py) dispatches requests to the project's explicitly chosen engine and initializes the associated project records. Engines own operations, dependencies, parameters, and launch methods.

| Location | Responsibility |
| --- | --- |
| [Unity production.py](unity/production.py) / [guide](unity/production.md) | Creation, requests, C# helpers, Editor/standalone Player launch |
| [Unreal production.py](unreal/production.py) / [guide](unreal/production.md) | Creation, requests, Python worker, commandlet/PIE launch |
| [registry.py](registry.py) | Explicit engine registration/selection, not guesses from installed software |
| [sessions.py](sessions.py) | Locks, process ownership, checkpoints, logs, states, recovery |
| [request_contract.py](request_contract.py) | Shared JSON, numeric, timing, and capture checks; engine-supplied operations/fields |

The shared layer neither defines Actor/GameObject/animation/import fields nor constructs native commands. registry.production_driver(engine) selects implementations; shared checkpoint/recovery operations come from sessions.

## Usage

Users describe goals; agents produce requests using project design and the selected engine. See engine guides for creation/native operations. Relevant skills and project documents retain professional decisions for prototypes, slices, and feature changes.

```powershell
python tools/engine_workflow.py execute --project "D:/Games/MyGame" --request "D:/Games/MyGame/production/request.json" --task production/tasks/T001.md --timeout 600
python tools/engine_workflow.py status --project "D:/Games/MyGame" --session engine-SESSION_ID
```

`create` initializes the six main project documents before native project creation, preserving existing records. Adopt existing projects with game_workflow.py init rather than rebuilding. --task / --milestone link actual project documents. CLI arguments, edit/inspect/playback modes, directories, and session format retain their contracts; fields belonging to another engine fail explicitly.

## State and Evidence

Each execution writes runs/engine-*/ with session.json, exact request.json, before/ checkpoint, native result.json, and process/engine logs. Automation also saves playback.json, actions.jsonl, frame-time CSV, and enabled captures. Checkpoints preserve sources and Unity .meta files while excluding regenerable Library/Saved/Binaries directories. Reserve space for large projects.

Requests, import sources, and native workers retain hashes. validate_records.py --project ... checks session format, checkpoints, and output evidence. Native implementations handle save/reopen readback. Failed batches can contain saved partial results and must not be described as atomic.

CLI returns 0 for complete, 1 for failed, 2 for needs_review. Native results accompanied by engine errors require review. Timeouts, nonzero engine exits, wrong identity, or missing reports are not complete. Record interface execution, game-rule tests, gameplay, and visuals separately.

## Concurrency, Interruption, and Recovery

Before running, inspect editor processes for the target project. If already open, reject another batch writer without closing the user's editor. Engines specify process names. Toolkit locks prevent concurrent toolkit work on one project, not external editors/manual changes.

```powershell
python tools/engine_workflow.py recover --project "D:/Games/MyGame" --session engine-INTERRUPTED_ID
python tools/engine_workflow.py restore --project "D:/Games/MyGame" --session engine-RESTORE_ID
```

recover confirms the session process ended, records observed state, and releases its old lock while retaining needs_review/exit code 2. It does not replay operations with unknown outcomes. Inspect again, identify completed work, then request the remainder.

restore verifies identity, checkpoint, and post-run file hashes, rejecting later edits. Changed/new files move to displaced-* before baseline restoration. If recovery itself is interrupted, inspect state/backups. Failed creation before configuration writing retains directories/logs; inspect and continue as an existing project.

Use [MCP integration](mcp.md) when suitable tools exist; Python/C# operations do not imply MCP connectivity. Engine guides define performance sampling, capture limits, animation scope, and dependencies.

## Creation Records and Recovery Checks

Creation uses engine-session records: runs/create-*/session.json contains schema_version, operation=create, and state, then links the native identity-validation session. Record validation scans create and engine sessions. Missing fields in older records are reported, not invented retrospectively.

Recovery checks configuration/session identity, processes, and checkpoints without requiring a damaged project to pass normal structure checks first. Validate the engine entry after restoration. Later user edits, corrupt backups, other sessions, or live processes still block restoration. If files restore but the entry remains invalid, retain restored state plus errors without claiming that the project runs successfully.

Tasks/management can link real session.json evidence. Closeout accepts manifest.json, engine-session, and reports under tests/reports or production/validation. Declare custom report roots with `--report-root <project-relative-directory>`. Record structure and game acceptance remain separate.

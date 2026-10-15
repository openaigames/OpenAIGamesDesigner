# Project Workflows and Documentation Ownership

[English](README.md) | [简体中文](README.zh-CN.md)

Use six main documents to organize a new project. Keep specialist decisions in their relevant documents, link detailed specifications, and summarize progress in Project Management. Each rule or configuration has one authoritative source. A shared change record connects design, art, engineering, tasks, and validation, showing what has been designed, implemented, and tested. Update the concept when the game's direction, core experience, audience, or pillars change. The agent maintains these links as it works; changes are not synchronized automatically.

This local game-development toolkit supports editable design files, native projects, and actual evidence without requiring a database, persistent server, or dashboard. Sixteen skills cover production, concept, systems, numerical design, combat, levels, art direction, characters, environments, animation, VFX, audio, UI/UX, technical art, engineering, and validation. Combine methods as needed without restricting game genres.

## Toolkit Responsibilities

| Layer | Maintains | Limits |
| --- | --- | --- |
| skills | Professional judgment, clarification, handoff methods | Documents are not implemented games |
| workflows | Five stages/ranges, content production, and reusable intake/prototype/slice/change/asset/delivery flows | No duplicated workflow per engine/genre |
| templates | Management, milestones, tasks, specs, configuration, editable native examples | Existing projects need not migrate/fill every template |
| tools | Documents, engine execution, asset jobs, numerical exchange, record checks, packaging | No automatic task/stage approval |
| adapters | Commands, optional runtime/motion/scenes, generation services, Blender | Not every editor capability or generation model |
| schemas | Project/run/session/job/artifact contracts; see [schemas](../schemas/README.md) | Not a separate task database |
| tests | Tools, protocols, file protection, native cases/evidence | Not substitutes for real integration or acceptance |

adapters/engines has Godot, Unity, Unreal, Three.js, and Phaser entries; web engines share web_common.py. adapters/assets covers cloud APIs and local generation wrappers; adapters/processing covers Blender and procedural/motion processing. Shared helpers stay with their domains.

## Game Project Layout

```
MyGame/
├── Project Management.md           Goals, stages, entry points, blockers, next action
├── Game Concept.md                 Professional documents developed as needed
├── Game Design Document.md
├── Art Direction.md
├── Technical Design.md
├── Risk & Assumption List.md
├── production/                     Milestones, tasks, decisions, asset requests
├── design/                         Detailed features, asset specs, numerical attachments
├── tests/                          Project tests and reports
├── game/                           One continuously edited native project
├── assets-source/                  Original assets and provenance
├── .openaigame/
│   ├── project.json                Engine location and execution settings
│   ├── asset-providers.json        Selected provider configuration
│   ├── asset-jobs/<id>/            Snapshots, state, logs, artifacts
│   └── numeric-imports/<id>/       Numerical changes and source backups, as needed
├── runs/<id>/                      Execution records, input snapshots, logs
└── builds/<id>/                    Exports
```

Use this layout for new projects unless another location or structure has been chosen. Existing projects keep their established layout. Start each main document with known facts, open questions, and the conditions for completing the work, then add directories as needed. Keep durable project records with the game rather than relying on temporary agent logs. An existing engine root can be configured as `.`; a new one defaults to `game/`. Markdown captures decisions and explanations, while JSON records structured tasks, commands, files, and evidence. A Markdown document can share a task ID to add detail without duplicating its status.

Before major gameplay implementation, retain current rules, technical entry, task, and prototype goals. New layouts use validate_records.py --layout --markdown and --production for handoff. Existing/custom layouts omit layout checks but retain equivalent evidence. Validators cannot determine professional quality or user acceptance.

A change connects request/decision → feature/asset spec → task → native edits → execution record → observation/playtest → stage/next step. Commands prove their own technical conditions, not gameplay, visual quality, or user approval.

For asset jobs, `succeeded` means the generation or processing step completed and its outputs were registered. `registered` identifies externally produced files. Both retain `quality_validation: not_checked` until reviewed. Snapshots, hashes, and retry links provide traceability; keep separate version control and backups.

Numerical work stays in the same workflow: GDD/specs own rules and link the editable source, numerical design owns models, engineering owns mappings/overrides/import, validation checks effective values, and management summarizes. JSON exchange supports file round trips; native resources use project importers. configuration_written is not runtime/balance validation. Exchange is neither background sync nor a separate end-to-end scheduler.

## Distribution and Scope

Source is the maintained repository; dist contains builds; personal skill directories are installed copies; game directories contain work results. Bundles place workflows/templates/tools/adapters/schemas and portable guides in game-preproduction/runtime, alongside the sixteen skills' references. The packager includes the runtime resources and public guides needed for installation.

Unity/Unreal provide identification, native execution, test parsing, and builds; see [execution](../adapters/engines/execution.md). Production drivers create/edit/import/play with shared [checkpoints/recovery](../adapters/engines/sessions.md). Exact operations follow engine guides; implement project features through real code, available MCP, or project tools. Local wrappers and cloud generation share asset jobs; see [asset integration](../adapters/assets/README.md). Model weights are not bundled.

Start with [tools](../tools/README.md); see [validation guidance](../tests/README.md).

## Module Guides

Workflows organize work; choose tools by task. [Documentation](../docs/README.md) indexes modules, [templates](../templates/README.md) indexes documents/project recipes, and [installation](../docs/INSTALLATION.md) explains source, shared runtime, and game copies.

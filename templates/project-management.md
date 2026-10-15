# {{name}} — Project Management

[English](project-management.md) | [简体中文](project-management.zh-CN.md)

## Goals and Stage

- Project stage: determine from the existing project and user goal.
- Task goal: to define.
- Milestone: not established.
- Project entry: locate the actual project; record absent projects as not created rather than assuming an engine/configuration exists.
- Layout: new projects keep professional indexes at root and native code in game/, with design/, production/, assets-source/, runs/, builds/ as needed. Existing projects record their actual locations.

## Professional Document Index

Link the five actual concept, GDD, art, technical, and risk entries for new projects; content may be pending. Existing projects use equivalent records without filling every document for local changes.

State whether each is an early draft, updated to implementation, awaiting review, or missing specific content. File existence is not completion. Detailed rules, assets, and evidence retain their authoritative owners.

| Responsibility | Actual file | Content needed for this task |
| --- | --- | --- |

## Milestones and Tasks

Store milestones/tasks under production/ as needed. Maintain links/priorities here, not duplicate detailed state. Project stage and new-feature maturity are separate.

## Changes and Dependencies

Link one change record/task and summarize affected disciplines, completed/open work, blockers, and next steps. Do not maintain another status table. Record whether positioning changes; local rules/assets do not automatically change the concept.

## Decisions and Blockers

Record decision source, date, and scope. Suggestions are not user approval. Preserve history and affected records.

## Execution and Validation

Link actual records. Toolkit entries may include `runs/<run-id>/manifest.json`, `runs/engine-*/session.json`, `runs/create-*/session.json`, and .openaigame/project.json, only when they exist. Other projects retain native records. Distinguish command completion, function, experience, visuals, and milestone decisions. Preserve failures; hashes are not backups.

## Next Steps

Define the question, necessary design inputs, and inspectable deliverable, then execute.

At closeout/interruption, update actual stage/goals/entry/task states/evidence instead of leaving initial placeholders. State which professional records were compared against which project/configuration/report, what was filled, and what remains. Do not claim completeness without review. New projects run closeout checks; existing ones verify equivalents. Report structural checks separately from content review.

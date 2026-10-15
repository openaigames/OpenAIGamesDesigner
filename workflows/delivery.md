# Delivery and Subsequent Updates

[English](delivery.md) | [简体中文](delivery.zh-CN.md)

Identify whether delivery means a native project, in-engine demonstration, or standalone build, plus platform/configuration/scope. Engineering verifies actual build tools/dependencies/export settings and records real outputs. Engine references/adapters own commands and limits.

Verify launch and key flows in the receiving environment, with sources/licenses/issues documented. Publication, signing, and store upload require applicable authorization/tools; these tools do not perform them.

Retain revisions, dependencies, builds, and checks. Hash manifests are not recovery systems; use actual version control/backups preserving manual edits. Feedback becomes tasks linked to the delivered revision and the [feature-change workflow](feature-change.md).

For playable-project delivery, compare affected documents with implementation: rules/boundaries, assets, modules/configuration, run steps, risks, and evidence must be findable. Skills define handoff depth. Record checked scope/gaps in existing tasks/management. Early summaries, file existence, and structural passes do not establish completeness; never pad with invented design/tests.

At implementation closeout or interruption, update affected professional facts, task/milestone state, evidence, and next steps. For new projects, run `python tools/validate_records.py --project "GAME_PROJECT" --layout --production --closeout --markdown` and address results. For local changes or existing/custom layouts, check equivalent records without imposing new-project milestones. Structural validity is not acceptance.

Asset delivery also follows [registration and handoff checks (Chinese)](../skills/game-preproduction/references/asset-handoff.md). validate_records.py --asset-scope can run independently on older projects. Distinguish recorded/integrated/verified against the task endpoint. Verify that the project remains runnable while completing missing records. Resolve the underlying handoff requirements rather than merely dismissing workbench notices.

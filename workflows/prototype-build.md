# Design → Prototype → Playtest

[English](prototype-build.md) | [简体中文](prototype-build.zh-CN.md)

1. Extract the question to test from user goals/design. Clarify only unknowns changing the experiment; incomplete documentation is not a reason to refuse implementation, and genre alone does not define all gameplay.
2. Create/reuse a prototype milestone from templates/milestones/prototype.md and tasks from templates/task.md. Specify local rules, placeholder boundaries, input revisions, observation methods, and dependencies. New projects save/link these before major implementation without finishing all design documents. Engine choice does not confirm core interaction. Record authorized provisional defaults. For visible output, establish asset choices or a selection delegation, including key objects/motion sources and limits; prototype does not automatically mean whitebox. Continue independent work while choices remain open. Select frameworks and presentation assets separately according to rules/maintenance and action/readability needs.
3. Inspect the actual project, engine, and recovery baseline. New engine-specific work needs a concrete choice/delegation; candidate lists, installed software, and default-gameplay authorization are insufficient. Continue independent design/read-only work during ambiguity. Implement in the native project; execution tools do not automatically turn GDDs into games. Report missing tools accurately.
4. Run appropriate build/resource checks, startup, and tests using actual project tools, linking tasks/milestones/input versions. Inspect failures before fixing and create new execution records rather than overwriting history.
5. Observe/play according to the experiment. Automation proves only covered behavior. Exit codes do not prove feel, fun, or art; absent playtest evidence remains unverified.
6. Update tasks/milestones with real entries, run steps, evidence, and limits. Compare rules/assets/implementation and revise affected professional records to handoff depth. Early concise drafts do not justify omitting facts already established. Continue authorized changes/retests and never invent user approval.

Deliver actual changes, reproducible run steps, and executed checks. Distinguish standalone exports from editor-runnable projects. Unsupported mechanics return to relevant design rather than restarting all documents.

For bulk parameters/curves, create numerical attachments only when useful and link specs. Mark provisional assumptions, use technical exchange/validation, and check actual loaded values. Without loaders/mappings, tables remain candidates, not an integrated tuning system.

Use game_workflow.py run with --task, --milestone, and --input when available. Direct engine calls retain equivalent versions, commands, exit codes, logs, artifacts, and state links beyond temporary agent logs. New-project handoff uses validate_records.py --layout --production --markdown; existing projects use equivalent records. Structure does not validate gameplay/milestones.

At implementation closeout or interruption, update affected professional facts, task/milestone state, evidence, and next steps. For new projects, run `python tools/validate_records.py --project "GAME_PROJECT" --layout --production --closeout --markdown` and address results. For local changes or existing/custom layouts, check equivalent records without imposing new-project milestones. Structural validity is not acceptance.

Use game-numerical-design directly for quantitative models, probability/supply-demand, and candidate comparisons. Retain the same specs/sources/workflow without a separate numerical stage. Systems/combat disciplines retain rule ownership.

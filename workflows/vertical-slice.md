# Prototype → Vertical Slice → Production Review

[English](vertical-slice.md) | [简体中文](vertical-slice.zh-CN.md)

Use templates/milestones/vertical-slice.md for representative experience, target quality, constraints, and existing evidence. Resolve missing mechanics first; authorized exploratory production can proceed with explicit risks rather than invented approval gates.

Evolve the same native project. Tasks cover only needed gameplay loops, levels, imports, animation/VFX/audio, UI, and performance. Art provides specs/provenance/visual checks; engineering implements/integrates; validation links goals to operations/evidence. Distinguish placeholders from target-quality assets.

Check that representative rules, controls, animation/feedback, and evidence connect. A working framework, complete animation pack, or damage-dealing attack alone does not establish slice quality. Judge against agreed experience/quality without imposing a framework.

Reuse prototype execution tools for continuous running/regression. First confirm that the project runs, then assess the player experience, audiovisual presentation, behavior on the target platform, and production cost. Launch checks and screenshots cover only part of this evaluation.

Record actual time, rework, and dependencies rather than converting estimates into results. Link editable projects, applicable builds, quality evidence, issues, and tradeoffs. Clearly record any exports or acceptance checks that have not been performed.

Mechanic issues return to experiments; quality issues to assets/integration; cost issues to scope. If a slice is the endpoint, deliver it without expanding into full production.

At implementation closeout or interruption, update affected professional facts, task/milestone state, evidence, and next steps. For new projects, run `python tools/validate_records.py --project "GAME_PROJECT" --layout --production --closeout --markdown` and address results. For local changes or existing/custom layouts, check equivalent records without imposing new-project milestones. Structural validity is not acceptance.

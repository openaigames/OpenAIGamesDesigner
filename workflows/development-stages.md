# Five Development Stages

[English](development-stages.md) | [简体中文](development-stages.zh-CN.md)

Use these stages to define the scope and completion criteria for a task. [stages.json](stages.json) contains their machine-readable names and minimum checks. A stage describes the work on the relevant features or content; it is not determined by the number of files created.

| Stage | Work | Exit evidence |
| --- | --- | --- |
| 1 Project Definition | Interpret ideas/references/existing work; define goals, scope, constraints, design, experiments | Direction, rules, interfaces, and validation plans at agreed handoff depth. Planning can end here without claiming proven gameplay |
| 2 Gameplay Validation | Prepare environment, implement core mechanics, tune, replace assets, playtest | Operable mechanics and observations supporting retention/change/rejection. Compilation alone is insufficient |
| 3 Production Validation | Build representative quality samples and integrate outputs to test specs, methods, cost, performance | Evidence for target quality/feasibility/limits. A vertical slice is one complete-experience form, not every sample |
| 4 Content Production | Produce/assemble agreed content, evaluate full experience, fix, prepare release | Complete usable content with quality/experience evidence. Samples do not automatically validate new content |
| 5 Final Delivery | Verify native project, builds, sources/dependencies, instructions, receiving environment | Recipient can obtain/use the agreed revision. Publication/external sending stays within authorization |

Start at any stage and complete one stage or a sequence of consecutive stages. Ideas, projects, assets, and references do not automatically determine endpoints. Users need not know stage numbers.

Technical checks record facts; professional reviews interpret quality; user decisions record matters requiring their choice. Existing authorization remains valid without requesting the same approval again. Negative research conclusions can be valid deliverables without establishing target quality or readiness for the next stage.

Reuse valid prior work, fill only necessary gaps, and return failures to their causes while preserving unrelated evidence. Clarify changes beyond agreed goals/authority rather than silently reducing scope. See [stage execution](stage-execution.md).

# Start or Take Over a Game Project

[English](project-intake.md) | [简体中文](project-intake.zh-CN.md)

Use the six main documents for management, concept, game design, art, engineering, and risks as ongoing project records. For later changes, follow [feature change](feature-change.md) and update the affected documents in place. Link detailed specifications from these entry points, and retain equivalent documents in existing projects.

When creating a new project, establish its location and save the six main documents before major implementation. Record known facts, open questions, and completion criteria; `game_workflow.py scaffold` can create the initial files. The native project defaults to `game/`; add `design/`, `production/`, `assets-source/`, `runs/`, and `builds/` as needed. See the [project layout](README.md#game-project-layout), and keep any structure already chosen for the project.

Choose the starting stage from the goal and available project files. Resolve the unknowns that affect the next step. For a new game, establish the intended player experience; for an existing game, inspect its design and implementation. Reuse `Project Management.md` or its equivalent and expand the relevant specialist documents as work proceeds.

The overall project stage can differ from the maturity of a particular feature. Advance when the required work and evidence are complete.

Identify real project paths, engines/tools, dependencies, runnable baseline, and recovery revision. Before engine-specific work on a new game, obtain a concrete engine choice or authorization to select an engine. Delivery form, multiple candidates, and installed tools are not selections. Resolve remaining ambiguity while continuing engine-independent design/records; record pending choice and actual environment separately. Reuse existing target projects/prior decisions without asking again or rebuilding/migrating merely for intake.

Read the engine-specific technical references and verify adapter/project-tool capabilities. That layer owns environment, commands, and asset operations; no one engine command is a universal prerequisite. Continue to prototype/slice/change as needed. File intake alone does not establish runtime success.

For MCP, distinguish installed, connected, and specifically verified capabilities. Record target identity, provider versions, actual operations, and evidence in Technical Design. See [engine integration](../adapters/engines/mcp.md). Keep engine-specific instructions in adapters and continue using the same project/records.

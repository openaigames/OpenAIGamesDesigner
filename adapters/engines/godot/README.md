# Godot Execution

[English](README.md) | [简体中文](README.zh-CN.md)

## Choose an Integration Route

This page covers project commands, setup, and editor integration. Reusable in-game functions are separate modules; they do not replace the project's main scene, character, or rules automatically.

| Task | Guide |
| --- | --- |
| Input, state, feedback, interaction, navigation, basic scenes | [Core components](../runtime_components/README.md) |
| Import and sample processed character animation | [Motion](../motion/README.md) |
| Playback, root motion, foot/hand constraints | [Playback](../motion_playback/README.md) |
| Multi-node static assets, graybox replacement, and scene handoff | [Static scenes](../static_scene/README.md) |
| Component updates and rollback | [Installation and migration](../../../docs/INSTALLATION.md) |

These modules use native Godot resources. Exporting requires official export templates matching the engine.

## Project Execution

The [command adapter](cli.py) uses Godot's CLI. Discover and verify editor tools through [MCP integration](../mcp.md). [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) is a candidate whose actual tool list must be checked. Confirm the project.godot path, then test scene read/write and save/reopen. CLI smoke does not replace those checks. Commands work without MCP.

A real Godot 4 executable is required. The adapter does not migrate existing projects. Run examples from the toolkit root and replace MyGame with the actual game path.

## Environment Setup

| Component | Configure | Check |
| --- | --- | --- |
| Project's Godot 4 | Install/extract locally; set godot_executable or GODOT_BIN | Query --version, import, and run a scene |
| Export templates | Editor → Manage Export Templates | Match the engine version |
| Platform preset and SDK | Export dialog and platform-specific SDK installation | Export and launch the output independently |
| MCP, optional | Provider Node/npm environment, Godot path, [agent configuration](../../environment-setup.md#mcp-setup-across-three-layers) | Discover tools, confirm project, read/write and save |

Follow the [Godot MCP requirements](https://github.com/Coding-Solo/godot-mcp), not UE's C++ plugin procedure. See [Godot export documentation](https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html) for templates. .NET projects need their own .NET environment; the minimal example uses GDScript.

## Command Examples

```sh
python tools/game_workflow.py init --project "MyGame" --engine-root game --godot "C:/Tools/Godot/Godot.exe" --create-engine
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action prepare
python tools/game_workflow.py run --project "MyGame" --action smoke --frames 60
python tools/game_workflow.py run --project "MyGame" --action play --timeout 600
```

`--create-engine` creates a minimal Node2D project, not complete gameplay; omit it for existing projects. Doctor queries --version, prepare imports, smoke runs a bounded headless session, and play opens an interactive window and waits for it to close. Timeout stops the process.

After editing scripts, scenes, and configuration within the agreed scope, run tests for actual game rules:

```sh
python tools/game_workflow.py run --project "MyGame" --action test --script tests/test_game.gd --timeout 120
```

The script must execute assertions and print `OAGD_TEST_PASS count=N` with N > 0 when successful. Inspect what the tests mean; a marker alone is not acceptance evidence, and exit/log errors affect the result. The source repository includes an original integration fixture under `tests/fixtures/godot-2d/`; copy it to an independent test project. Maintenance fixtures are excluded from installation bundles; editable game examples are provided under `templates/runtime_examples/`.

Export requires an existing preset and matching templates:

```sh
python tools/game_workflow.py run --project "MyGame" --action export --preset "Windows Desktop" --timeout 600
```

Build/export use the preset and record output hashes. Defaults are game.exe and debug; configure other targets or release in the godot section, as shown in [execution configuration](execution.md). Launch standalone builds on the target environment and inspect resources/logs; simulated tests cannot prove that they work.

Each run records input snapshots, command, versions, logs, and state. Changes during execution require review; hashes are not backups. Command success does not certify controls, visuals, performance, or milestones.

See [runtime observations](../observations.md#godot-2d) for events, parameters, space, and media. The observation fixture is available in the source repository under `tests/fixtures/godot-observation/`.

Reference: [Godot command line](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html).

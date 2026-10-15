# Engine Execution Configuration

[English](execution.md) | [简体中文](execution.zh-CN.md)

Confirm the engine, existing project, and target platform, then configure the game's `.openaigame/project.json`. Merge these sections into existing settings without overwriting engine_root or design records. Replace all example paths.

## Supported Actions

| Action | Godot | Unity | Unreal | Three.js / Phaser |
| --- | --- | --- | --- | --- |
| doctor | Query executable version | Check project and declared version | Check project and declared version | Check framework declaration and local dependencies |
| prepare | Import resources | Batch import and compile | Load through Python commandlet and record actual engine version | Restore npm/pnpm dependencies |
| smoke | Bounded headless run | Timed Play Mode in a selected scene | Timed NullRHI game process in a selected map | Real headless browser loading a selected build |
| test | Project GDScript assertions | Unity Test Framework XML | Automation JSON | Project behavior-test command |
| play | Run the game | Open editor; enter Play separately | Editor -game | Local Vite server |
| build | Export preset | BuildPipeline.BuildPlayer | UBT compilation of an explicit target | Vite build |
| export | Build and register outputs | Build and register outputs | UAT build, cook, stage, archive | Build and register outputs |

These are executable interfaces, not proof of compatibility with every engine/platform. Preserve blocked/failed evidence when scenes, targets, modules, licenses, or test frameworks are missing. Games must supply their own tests; engine tests alone do not validate game rules.

## Unity

See [Unity execution](unity/execution.md) for configuration, defaults, and limits.

## Unreal

See [Unreal execution](unreal/execution.md) for configuration, defaults, and limits.

## Three.js / Phaser

See [web execution](web.md#browser-check-configuration) for configuration, defaults, and limits.

## Godot

See [Godot execution](godot/execution.md) for configuration, defaults, and limits.

## Runs and Evidence

```sh
python tools/game_workflow.py run --project "MyGame" --action smoke --timeout 180
python tools/game_workflow.py run --project "MyGame" --action test --timeout 600
python tools/game_workflow.py run --project "MyGame" --action export --timeout 3600
```

Each run stores commands, logs, input hashes, and results. Engine errors, missing reports, and absent outputs cannot pass. Timeout terminates only that run's process tree. Supply actual --script / --preset arguments for Godot.

`commands.<action>` overrides the default for all supported engines. Doctor always uses built-in environment/configuration checks. Custom tests must produce real results using the [report protocol](../README.md). Editor changes and asset production use [MCP](mcp.md) or project scripts; command configuration does not establish an MCP connection. Record stage acceptance, gameplay, and visual judgments separately.

## Authoring Operations

Use [engine_workflow.py](../../tools/engine_workflow.py) for Unity/UE project creation, scene/component editing, import and binding, animation setup, automated play/capture, and checkpoint recovery. See [sessions](sessions.md). game_workflow run handles running, testing, and building. Do not send creation/import requests through smoke or describe Python/C# execution as a native MCP connection.

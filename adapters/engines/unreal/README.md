# Unreal Engine

[English](README.md) | [简体中文](README.zh-CN.md)

## Choose an Integration Path

This page covers project commands, environment setup, and editor integration. Use the independent modules below for reusable in-game features. They do not automatically replace the project's main scene, character, or rules.

| Task | Guide |
| --- | --- |
| Input, state, feedback, interaction, navigation, and basic scenes | [Core runtime components](../runtime_components/README.md) |
| Importing and sampling processed character motion | [Motion](../motion/README.md) |
| Animation playback, root motion, and foot/hand constraints | [Playback](../motion_playback/README.md) |
| Multi-node static assets, graybox replacement, and project handoff | [Static scenes](../static_scene/README.md) |
| Upgrading and rolling back installed components | [Installation and migration](../../../docs/INSTALLATION.md) |

Runtime components, animation playback, and static scene modules target UE 5.8. Source plugins require a matching C++ build environment. Execution interfaces for existing projects use the project's own engine configuration.

## Project Execution

The [command adapter](cli.py) handles project identification, running, testing, compilation, and export. The [production interface](production.md) handles project creation, native Python scene/asset/animation setup, and PIE operations. Choose an editor compatible with the target project. If suitable MCP tools are available in the agent environment, follow [MCP integration](../mcp.md).

## Environment Setup

The following uses Windows as an example. Existing projects retain their engine and dependencies; no automatic upgrade occurs.

| Component | Used for | Configuration | Verification |
| --- | --- | --- | --- |
| Unreal Editor | Opening, editing, and running projects | Unreal Engine → Library in Epic Games Launcher, or an existing source build | Open `.uproject` with the matching editor and check the actual version |
| C++ toolchain and Windows SDK | C++ projects, source plugins, or platform compilation | Visual Studio Installer → Modify → Game development with C++, selecting components compatible with the target UE | Build the actual Editor or game target; VS Code does not supply a compiler |
| PythonScriptPlugin / EditorScriptingUtilities | Toolkit Python production interface | Project plugin configuration; see [production](production.md) | Script loads the project, executes the request, and produces native results |
| Third-party MCP and required engine plugins, optional | Agent-driven editor operations | Provider instructions for plugins, services, and [agent connection](../../environment-setup.md#mcp-setup-across-three-layers) | Discover tools, verify the target project, then make a read-only query |

A content-only project's need for C++ tools depends on its plugins and build targets. Use `vswhere -all -products '*' -format json` to include standalone Build Tools when locating Visual Studio installations. Verify compatibility against actual build logs and the target UE requirements.

Reference: [Epic's Visual Studio setup guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine).

## Projects and Commands

Run from the toolkit root, substituting actual paths. Existing projects can be integrated in place:

```sh
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "D:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
python tools/game_workflow.py run --project "MyGame" --action doctor
```

doctor checks editor files and project declarations. prepare loads the project for inspection; smoke runs a specified map; test runs selected Automation tests; build uses UBT; export uses UAT. See [execution configuration](execution.md) for maps, test filters, targets, and dependencies.

## Editing and Persistence

| Task | Entry point |
| --- | --- |
| Create and verify a content project | [Creation and startup](production.md#creation-and-startup) |
| Scenes, Blueprint components, Actors, imports, and animation bindings | [Production requests and scope](production.md) |
| Automated PIE actions, frame sequences, and timing samples | [Playback and sampling](production.md) |
| Session state, checkpoints, and recovery | [Session management](../sessions.md) |
| Runtime events, parameters, attachments, and spatial readback | [Shared runtime observations](../observations.md) |
| Native DataAsset / CurveFloat readback and guarded writes | [Native parameters](native-data.md) |
| Static mesh, material/texture, and instance audits; derived LOD / Nanite settings | [Mesh resources](mesh-resources.md) |
| Character consumers, associated animation, derived previews, and bone sampling | [Native animation](native-animation.md) |

Python production, MCP tools in the agent environment, and game runtime logic provide different capabilities. Follow each interface's defined scope. Check scene persistence, engine execution, gameplay behavior, and performance separately.

## Verifying MCP Integration

Configure plugins, services, and the agent connection for the provider's supported versions; see [candidate providers](../mcp.md#candidate-providers). This toolkit neither bundles nor automatically installs third-party MCP servers.

1. In a separate test project, verify plugin compilation, loading, and service startup. Pin the versions and dependencies used.
2. Discover actual tools and verify the editor project path, instance, and current scene. A listening port does not establish project identity.
3. Start with a read-only object listing. For write checks, use a uniquely named test object, modify it, and read it back.
4. Save and reopen the project to check persistence. Remove the test object, save, and check again. If a tool is unavailable, use an actual editor method rather than inventing an interface.
5. Retain calls, logs, and results in the test project before applying verified capabilities to the target. Inspect the current state after interruption to avoid duplicate operations.

Provider compatibility and tool coverage depend on actual results with the target versions. Project commands, source code, and the toolkit's native production interface remain available without MCP.

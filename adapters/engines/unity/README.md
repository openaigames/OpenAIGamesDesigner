# Unity

[English](README.md) | [简体中文](README.zh-CN.md)

This page covers project configuration and execution. For collecting and comparing animation events, see [action timing](../action_timing/README.md).

The [command adapter](cli.py) works with real projects containing `Assets/` and `ProjectSettings/ProjectVersion.txt`. Set `editor_executable` after selecting an editor. Verify the project's declared version and the installed editor's actual version separately.

For project creation, scene and component editing, asset and animation setup, and automated standalone playback, see the [production interface](production.md).

## Environment Setup

| Component | Where to configure it | Verification |
| --- | --- | --- |
| Matching Unity Editor | Installs in Unity Hub | Project import completes and scripts compile without errors |
| Target platform build modules | Module management for the editor in Unity Hub | Select the target platform and produce a build; install any platform-specific SDKs |
| Project package dependencies | Unity Package Manager, using the project's Packages configuration | Restore dependencies and verify in Play Mode |
| MCP editor package, if needed | Package Manager, following the provider's instructions | Package loads and identifies the intended editor instance |
| MCP service and agent connection, if needed | Provider's Python / uv environment and [agent configuration](../../environment-setup.md#mcp-setup-across-three-layers) | Tools are available; save and reopen a test object |

Installation references: [Unity Hub](https://docs.unity.com/en-us/hub), [candidate MCP provider](https://github.com/CoplayDev/unity-mcp). Install MCP packages, services, and project dependencies separately; they are not distributed with this toolkit. Menu names depend on the installed Hub and Editor.

## Commands

| Action | Default behavior | Project requirements |
| --- | --- | --- |
| doctor | Checks files and declared version | Verify actual editor version, render pipeline, and packages |
| prepare | Imports in batchmode and exits | Project-specific import and package restoration |
| play | Opens the editor | Enter Play Mode, interact, and observe shutdown |
| smoke | Timed Play Mode through helper scripts | An actual scene and explicit helper installation |
| test | Unity Test Framework | Test platform and real cases; inspect raw XML |
| build / export | BuildPipeline.BuildPlayer | Helpers, scene list, target platform, and modules |

Initialize with `game_workflow.py init --engine unity`; see [tools](../../../tools/README.md) for other arguments. Command arguments, project wrappers such as `executeMethod`, and report formats follow the [adapter contract](../../README.md). See [execution configuration](execution.md) for helpers, installation, and action settings. Existing project methods can override `commands`.

Editor operations follow [MCP integration](../mcp.md). The candidate [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) provides an editor package and service. Pin compatible versions and discover the tool groups actually enabled. With multiple editors, identify the target session first; installation alone does not establish a connection. Verify read → modify a test object → save and reopen, then asset import, Play Mode, and test reports as needed. A successful tool response does not replace Console, persistence, or gameplay checks.

Use the existing project architecture and asset approach. An installed Unity editor does not imply that the user selected Unity. If a service is unavailable, use project scripts; do not install another engine automatically.

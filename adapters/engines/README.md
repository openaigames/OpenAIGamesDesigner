# Engine Integration

[English](README.md) | [简体中文](README.zh-CN.md)

## Capabilities and Guides

| Layer | Implementation and entry |
| --- | --- |
| Execution, editing, and observation | Separate entries for five engines/frameworks below; authoring interfaces differ |
| Shared runtime components | [runtime_components](runtime_components/README.md): input, state, feedback, interaction, navigation, and more for Godot / UE 5.8 |
| Native sampling of processed animation | [motion](motion/README.md): reads imported bones; does not own a game state machine |
| Animation runtime | [motion_playback](motion_playback/README.md): locomotion, root motion, and contact constraints for Godot / UE 5.8 |
| Static scenes | [static_scene](static_scene/README.md): multi-node import, replacement, and relocatable project reception |
| Event recording | [action_timing](action_timing/README.md): independently usable recording interfaces for all five engines/frameworks |

Runtime components and playback have Godot and UE 5.8 implementations. Unity, Three.js, and Phaser provide their own execution and recording interfaces; consult their guides for scope.

## Project Command Entries

Start with [environment setup](../environment-setup.md), then follow the selected engine:

| Engine/framework | Entry | Guide |
| --- | --- | --- |
| Godot | [godot/cli.py](godot/cli.py) | [Godot](godot/README.md) |
| Unity | [unity/cli.py](unity/cli.py) | [Unity](unity/README.md) |
| Unreal | [unreal/cli.py](unreal/cli.py) | [Unreal](unreal/README.md) |
| Three.js | [threejs/__init__.py](threejs/__init__.py) | [Web 3D](threejs/README.md) |
| Phaser | [phaser/__init__.py](phaser/__init__.py) | [Web 2D](phaser/README.md) |

Prefer an available, suitable MCP connection for editor operations; these adapters execute commands. Both routes share designs, tasks, and evidence, but MCP calls are not implicit in `game_workflow.py run`. The CLI does not discover, install, or proxy MCP services. See [MCP integration](mcp.md).

Public imports use forms such as `from adapters.engines import unreal`. Each cli.py handles execution, testing, and delivery. Unity/Unreal production.py handles creation and editing; both entry types coexist.

## Shared Files

| File | Responsibility |
| --- | --- |
| common.py | Executable checks and custom command argument expansion |
| native_support.py | Configuration checks, evidence registration, normalized test reports; engine parsers are unity/reports.py and unreal/reports.py |
| registry.py | Explicit Unity/Unreal authoring-driver selection, not a universal capability registry |
| sessions.py / sessions.md | Execution, checkpoints, process ownership, interruption recovery |
| request_contract.py | Shared request, numeric, and result validation |
| web_common.py | Three.js/Phaser initialization, dependencies, server, and builds |
| browser_smoke.cjs | Browser loading, screenshots, and error checks |
| execution.md | Execution protocol and engine configuration navigation |
| [observations.md](observations.md) | Godot/UE events, parameters, attachments, and spatial capture |
| [unreal/native-animation.md](unreal/native-animation.md) | UE characters, animation, and linked preview export |
| [unreal/native-data.md](unreal/native-data.md) | UE parameter readback and protected writes |
| mcp.md | Host MCP integration and evidence conventions, not a server implementation |
| web.md | Shared web-game usage and browser check configuration |

Read unity/production.py or unreal/production.py for authoring, and sessions.py for shared execution/recovery. Import Godot from adapters.engines.godot and web frameworks from adapters.engines.threejs or adapters.engines.phaser.

Add modules only for implemented, testable functions, such as assets, animation, or playtesting. Do not create empty capability directories, bundle third-party MCP source, or assume every provider exposes identical tool names.

Defaults, configuration, and evidence requirements are in [execution configuration](execution.md). Unity/UE creation, scene/component editing, import, character animation, automated capture, and recovery are covered by [sessions](sessions.md). Keep evidence for these routes separate from run/build/export and MCP.

## Action Timing and Events

[Cross-engine recording](action_timing/README.md) provides Unreal, Unity, Godot, Three.js, Phaser, and generic web interfaces, with CLI capture and comparison. Record real engine events; the components do not replace animation editors or require a separate IPC service.

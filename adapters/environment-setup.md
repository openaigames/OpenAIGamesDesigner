# Configure the Environment by Task

[English](environment-setup.md) | [简体中文](environment-setup.zh-CN.md)

Select the functions your task needs and configure only their prerequisites. Existing projects retain their engines and tools. Installing skills does not install engines, MCP servers, generation models, or assets.

The project files, Python tools, and engine configuration can be used by different agents. The host needs file access and command execution. Follow that host's requirements for skill discovery and MCP connections.

## Connect an Agent

1. Give the agent the actual toolkit and game paths. Ask it to read the README and the skills relevant to the task.
2. If the host supports skill installation, retain complete skill directories and shared runtime resources in its supported location. Otherwise, explicitly identify the SKILL.md files to read.
3. Run `python tools/game_workflow.py --help` from the toolkit root, then configure the engines and services needed below.

The Codex paths below are a specific example, not defaults for every agent.

## Codex Path Reference

`~` is the user's home directory, normally `C:/Users/<username>/` on Windows. `<GAME_PROJECT>` is the game directory, not this repository.

| Item | Codex location | Setup |
| --- | --- | --- |
| Asset evidence and multiview quality review | Python + Pillow; Blender for GLB capture | Install Pillow in the executing Python and supply the Blender path | Collect → inspect original evidence → record judgments; [quality workflow](assets/quality-review.md) |
| Personal skills | `~/.agents/skills/<skill-name>/` | Copy all sixteen complete packaged skill directories here for use across projects |
| Project skills, optional | `<GAME_PROJECT>/.agents/skills/<skill-name>/` | Use for one project; normally choose personal or project installation to avoid divergent copies |
| Installed toolkit root | `game-preproduction/runtime/` inside the chosen skill root | Run tools such as tools/game_workflow.py here; do not copy only SKILL.md |
| Skill display metadata | Each skill's `agents/openai.yaml` | Keep it with the skill; it is not MCP configuration or game design data |
| User configuration and MCP | Normally `~/.codex/config.toml` | Merge with existing settings; resolve the actual directory if CODEX_HOME is set |
| Project configuration and MCP, optional | `<GAME_PROJECT>/.codex/config.toml` | Applies to trusted projects; choose the intended scope and avoid duplicate registrations |
| Game working directory | `<GAME_PROJECT>/` | Start the Codex task here; project management and five specialist entry documents live here |
| Native game project | `<GAME_PROJECT>/game/` for a new project | The actual directory contains .uproject, project.godot, or package.json; connect existing projects in place |
| Engine and command configuration | `<GAME_PROJECT>/.openaigame/project.json` | Toolkit engine paths, executables, and commands; this does not register MCP |
| Asset-tool configuration | `<GAME_PROJECT>/.openaigame/asset-providers.json` | Records real generation or processing tools; it does not install models or engine plugins |

After installation, start a new Codex task and check that all sixteen skills are discoverable. Explicitly request `game-preproduction` to inspect the game's stage, then check natural-language activation. File presence, skill loading, CLI execution, and engine connectivity are separate checks.

References: [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp). Use the relevant product documentation for other agents' installation directories and connection formats.

## Prerequisites

| Task | Required environment | Where to configure | Check |
| --- | --- | --- | --- |
| Discuss concept, GDD, art, or architecture and maintain files | Agent with project file access and relevant skills | Host skill directory; start in the game project | Read skills and save known facts and open questions; an engine is not required yet |
| Initialize documents, record tasks, and check runs | Python 3.10+ and the complete runtime | Local Python and source tools/ or installed runtime/tools/ | Run python tools/game_workflow.py --help |
| Three.js 3D / Phaser 2D | Node compatible with the project's Vite, npm/pnpm, browser | Install Node and project dependencies; configure executable paths | Install → build → serve exported output over HTTP → interact; [web guide](engines/web.md) |
| Godot prototype and playtest | The project's Godot 4 executable | Install/extract locally and configure the path | Query version, import, run a real scene; [Godot setup](engines/godot/README.md#environment-setup) |
| Godot standalone build | Matching export templates and platform tools | Editor → Manage Export Templates and export presets | Launch the exported package independently |
| Unity authoring | Matching editor, project packages, target modules | Unity Hub and Package Manager | Import, compile, enter Play; [Unity setup](engines/unity/README.md#environment-setup) |
| Unreal authoring | Matching UE; C++ projects/plugins also need toolchain and SDK | Launcher or existing install; Visual Studio Installer on Windows | Open the project and build C++ when required; [UE setup](engines/unreal/README.md#environment-setup) |
| Editor control through MCP | Provider server/dependencies and any required plugin | Engine plugin + local server + agent connection | Discover tools, verify project identity, read/write, save/reopen; [three-part setup](#mcp-setup-across-three-layers) |
| UE animation integration | Selected or authorized assets/modules compatible with the engine | Import into Content; install third-party code per provider | Check skeleton, controls, dependencies, preview, playback, timing, cancellation, and playtesting separately |
| Tripo / Hunyuan3D generation | Python, network, account, credentials | Save API keys in [local settings](assets/local-settings.md); TC3 uses environment variables | Doctor checks presence; then generate a small job; [API setup](assets/generation-api.md) |
| Proxy access for asset APIs/downloads | curl; Windows auto proxy uses WinHTTP | System proxy or proxy environment variables; curl on PATH outside Windows | Check connection/authentication with an official read-only endpoint; [host proxy](assets/local-settings.md#host-proxy-settings) |
| Find and acquire free/paid assets | Python, network; some sites need browser login | [Asset directory](assets/asset-sources.md) | Search → acquire → verify → import; no local generation model needed |
| Other image, 3D, or audio generation | Selected real service/tool and wrapper | Tool environment and asset-providers.json | Run a small job and inspect real files/logs; [asset integration](assets/README.md) |
| Animation and weapon alignment | game-animation-pipeline; Blender, UE, and C++ tools as needed | Inspect existing UE assets directly; configure source tools for external edits | Validate standalone actions and the actual game separately; follow the skill's rig/event contracts |
| Blender model processing | Blender and supported input/dependency files | Configure its executable in asset providers | Reopen outputs and inspect models, materials, animation; [asset processing](assets/README.md) |
| CSV parameter round trip | Python, authoritative JSON, field bindings | Project binding file and a spreadsheet editor | Export → edit → compare → apply → reload in engine |
| Read Excel parameters | Above plus openpyxl in the executing Python | python -m pip install openpyxl | Read the selected sheet and inspect differences; [numerical exchange](../tools/README.md#numerical-table-round-trip) |

Spreadsheet authoring, concept-image generation, and similar capabilities depend on tools provided by the host. Configure GPUs, VRAM, model weights, and credentials for the actual selected tools; there is no universal model environment required by this project.

## MCP Setup Across Three Layers

| Layer | Configuration location | Setup | Verification |
| --- | --- | --- | --- |
| Engine | Project plugin directory, plugin panel, or package manager | Install and enable a compatible plugin; compile source plugins and restart when required | Plugin loads without introducing compilation errors |
| Local server | Provider directory, Python environment, or Node environment | Install pinned dependencies and configure the startup command | Server starts and connects to the intended editor without connection errors |
| Agent | Host MCP connection settings | Actual command/URL, working directory, and required environment variables | Discover tools, make a read-only query, and verify project identity |

Not every MCP provider requires an engine plugin. Follow the chosen provider's actual requirements rather than applying UE-specific steps to every engine.

For Codex, use user `~/.codex/config.toml`, trusted-project `.codex/config.toml`, or `codex mcp add`. Commands and arguments must refer to actual installations. Another client's `mcpServers` JSON is not Codex TOML. Reconnect and confirm tools are visible in the session. See [official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp).

See [candidate providers](engines/mcp.md#candidate-providers). These external projects are not installed by this toolkit; validate compatibility with your engine. MCP is optional, and project scripts and commands remain usable.

## Where Configuration Belongs

| Information | Location | Maintainer |
| --- | --- | --- |
| Engine, Node, and other programs | Local software installations | User or agent execution environment |
| Engine choice, native project, build/test commands | Game .openaigame/project.json | Initialization tool or agent; read existing settings before editing |
| Asset generation/conversion commands | Game .openaigame/asset-providers.json | Configure real installed tools and wrappers |
| MCP connections | Agent MCP configuration | User or agent; project.json alone does not connect MCP |
| Chosen versions, rationale, gaps | Technical Design.md, optionally design/technical/engine-connection.md | Agent updates from actual checks |
| Installation/build/call evidence | Game runs/ and validation reports | Executor records results; project management links summaries |

Fill in your own absolute paths. Example paths are placeholders. Keep credentials out of archived command arguments and documents; use credential storage or environment-variable references.

## User and Agent Responsibilities

The user provides the task, engine choice, and existing project location where applicable, and completes account logins for authorized resources. The agent checks the environment, explains missing prerequisites and their impact, and performs authorized downloads, configuration, and tests. Steps requiring interaction, such as administrator prompts, account login, or license acceptance, should identify the exact screen and action.

For example:

```text
Use Unreal for this task and check the authoring environment and MCP prerequisites.
The existing project is D:/Games/MyGame/MyGame.uproject.
List what is available, what is missing, and where each item is configured.
```

Report each item as not installed, not configured, configured but unverified, verified, or failed, with a next step. Doctor covers only its adapter's checks; it does not install or validate the entire environment. Unity/UE file checks do not prove MCP, compilation, or packaging works.

Configure once when connecting a project, then revisit affected parts after engine/plugin updates, a machine change, or a target-platform change.

### ElevenLabs Audio

For cloud sound effects, music, or dialogue, configure a local ElevenLabs API key and FFmpeg for the executing Python environment through PATH, OAGD_FFMPEG, or imageio-ffmpeg. `asset_workflow.py --project PROJECT doctor --provider elevenlabs` checks presence without generating anything. Review the request and cost in the job page before execution. See [audio integration](assets/elevenlabs-audio.md).

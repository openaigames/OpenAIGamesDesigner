# Configure and Extend Adapters

[English](README.md) | [简体中文](README.zh-CN.md)

## Choose an Integration Layer

| What to connect | Entry |
| --- | --- |
| Project execution, editor authoring, MCP, and observation | [Engine integration](engines/README.md) |
| Reusable in-game behavior | [Core components](engines/runtime_components/README.md), Godot / UE 5.8 |
| Native animation import, sampling, and playback | [Sampling](engines/motion/README.md), [playback](engines/motion_playback/README.md) |
| Multi-node scenes, replacement, and reception | [Static scenes](engines/static_scene/README.md) |
| Blender, procedural models, and animation processing | [Processing](processing/README.md) |
| Asset sources and generation services | [Asset integration](assets/README.md) |

Each directory documents its prerequisites, entry points, and limitations. Combine project commands, runtime components, and external services as needed.

## Environment and Command Configuration

Start with [environment setup](environment-setup.md), select the required components, then configure commands here.

Prefer connecting existing project tools through configuration. Add an adapter only when formats or execution semantics differ. Keep workflows general, gameplay methods in the relevant skill references, and engine instructions alongside their implementation.

Engine and framework adapters live under [engines](engines/README.md). Reuse verified MCP connections available in the agent host for editor operations; native commands handle builds, tests, and packaging. See [MCP integration](engines/mcp.md) for discovery, save/reopen checks, and evidence. A provider that has not been connected is only a candidate.

## Engine Commands

Web games use Three.js for 3D or Phaser for 2D. Both support empty-project initialization, dependency installation, a local Vite server, and build export. See [web games](engines/web.md) for setup, testing, and persistent processes. The default smoke check can load a build in a real Playwright browser; gameplay still requires project-specific tests and playtesting.

See [execution configuration](engines/execution.md) for defaults. Unity and Unreal can override actions through `commands` in `.openaigame/project.json`. For example, an initialized Unity project can add:

```json
{
  "schema_version": 1,
  "engine": "unity",
  "engine_root": "game",
  "editor_executable": "C:/Tools/Unity/Editor/Unity.exe",
  "commands": {
    "test": ["C:/Tools/Python/python.exe", "C:/MyTools/unity_tests.py", "--project", "{project}", "--run", "{run}"],
    "export": ["C:/Tools/Python/python.exe", "C:/MyTools/unity_build.py", "--project", "{project}", "--output", "{output}"]
  }
}
```

The project must supply these wrappers; the example is not a ready-to-run Unity builder. For Unreal, set engine to `unreal` and add `project_file`, relative to `engine_root`, such as `MyGame.uproject`. `expected_version` checks the project's declaration; it does not prove the installed Unity/UE editor matches.

Only `{project}` (native project root), `{run}` (run record directory), and `{output}` (export directory) are expanded. Other arguments are unchanged. The first argument is an absolute executable path; cwd is the native project root and execution uses `shell=False`. Pass the actual `.uproject` filename rather than treating `{project}` as a file. Commands come from project configuration, not Markdown parsing.

See the [execution matrix](engines/execution.md). Missing prerequisites produce `blocked`; process, report, or output failures produce `failed`. `build` compiles a target in UE and produces a deliverable in the other adapters. `export` registers complete delivery files.

A test wrapper must execute real tests, preserve the original engine report, and write `{"tests":3,"failed":0,"errors":0}` to `{run}/test-results.json`. All three values must be integers, with tests > 0 and no failures or errors. Exit code zero with no report, zero tests, or invalid data does not pass. Never manufacture a report to satisfy the runner.

Export must create nonempty deliverables under output; the runner records their hashes. Wrappers check completeness and convert engine failures to nonzero exits; log matching is supplementary. All actions have timeouts and logs. Record gameplay and visual results separately from process success.

## New Providers and Records

See [asset integration](assets/README.md) for the command protocol. A native provider implements command/validate, registers with the tools, and updates provider enums, documentation, and failure-case tests. An empty module is not an integration. Blender processors use the same asset-job records.

Schema files define record formats. `validate_records.py` uses the standard library to interpret their supported keywords and rejects unsupported keywords; it is not a general JSON Schema implementation. Update its interpreter and tests when extending contracts, preserving compatibility and migration instructions. Record checks inspect files, path boundaries, and hashes; they do not run tools or verify specialist judgments.

Source `tests/adapters/` contains contract fixtures run by the root test entry. Test missing configuration, nonzero exits, invalid output, timeout, and absent artifacts with controlled local processes, then connect real tools following the [validation guide](../tests/README.md). Also execute packaged CLIs from a directory without access to source imports.

References: [Unity editor CLI](https://docs.unity.com/en-us/engine/6000.7/manual/unity-editor/command-line-arguments/editor), [Unity command-line builds](https://docs.unity3d.com/6000.0/Documentation/Manual/build-command-line.html), [Unreal build and packaging](https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine). Match commands to the project's installed engine.

Cloud audio uses [ElevenLabs](assets/elevenlabs-audio.md), with source-window binding, original-file preservation, and duration calibration alongside local audio wrappers.

Cloud images and video use [Seedream / Seedance](assets/ark-generation.md), sharing an Ark credential while handling synchronous image responses and asynchronous video jobs separately.

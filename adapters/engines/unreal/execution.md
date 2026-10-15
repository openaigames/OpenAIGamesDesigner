# Unreal Execution Configuration

[English](execution.md) | [简体中文](execution.zh-CN.md)

```json
{
  "unreal": {
    "smoke_map": "/Game/Maps/Prototype",
    "smoke_seconds": 3,
    "test_filter": "MyGame.Functional",
    "dotnet_executable": "D:/UE/Engine/Binaries/ThirdParty/DotNet/VERSION/win-x64/dotnet.exe",
    "platform": "Win64",
    "configuration": "Development",
    "build_target": "MyGameEditor",
    "export_maps": ["/Game/Maps/Prototype"]
  }
}
```

prepare temporarily enables the engine's PythonScriptPlugin to run a read-only inspection script. It does not change `.uproject` plugin settings or save Actors. Actual project paths and versions are recorded in `unreal-result.json`. smoke uses `-game -NullRHI` and requires logs showing the specified World starting and engine initialization. It does not validate rendering, animation quality, or game feel.

test runs only the specified Automation filter, saves `automation/index.json`, and normalizes it. Not-run, in-progress, failed, or zero-test results cannot pass. Compilation invokes the matching engine's UnrealBuildTool.dll; export invokes AutomationTool.dll BuildCookRun. Matching .NET, toolchain, SDK, platform support, and a packageable project are required. build_target must name a real Target; do not invent an Editor Target for a content-only project.

Automation reports and the overall editor process are evaluated separately. If tests pass but startup logs contain errors, retain the failed run and raw report, then investigate before acceptance. Error lines are not automatically ignored.

Default export targets a game client. Use project command overrides for servers, distributed builds, special signing, or store publication. Default NullRHI test / smoke commands are unsuitable for GPU tests; override them and retain real reports when needed. The project chooses its gameplay framework; none is required by generic startup or build operations.

For shared commands, states, and evidence conventions, see the [execution overview](../execution.md).

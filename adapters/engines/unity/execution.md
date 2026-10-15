# Unity Execution Configuration

[English](execution.md) | [简体中文](execution.zh-CN.md)

Explicitly install the two Editor helpers. Existing files with different contents are not overwritten:

```sh
python tools/engine_setup.py --project "MyGame"
```

This installs `OAGDEngineBridge.cs` and its shared build dependency, `OAGDBuild.cs`. Both files are checked before either is written. Compare and back up differing versions or user modifications before an explicit upgrade. Execution also checks that both dependencies are present and match the toolkit.

```json
{
  "unity": {
    "smoke_scene": "Assets/Scenes/Prototype.unity",
    "smoke_seconds": 3,
    "test_platform": "EditMode",
    "test_filter": "MyGame.Tests",
    "build_target": "StandaloneWindows64",
    "build_scenes": ["Assets/Scenes/Prototype.unity"],
    "build_name": "MyGame.exe",
    "development": true
  }
}
```

`test_platform` accepts EditMode / PlayMode. The project must have the corresponding Unity Test Framework and real tests. Outputs include raw `unity-tests.xml` and normalized `test-results.json`; zero tests, failures, and unknown states cannot pass. Asynchronous tests omit `-quit`, which would exit too early.

smoke / build / export use the supplied [helper](OAGDEngineBridge.cs) to record the actual project, editor version, errors, and results. smoke verifies that Play Mode starts and runs for the requested duration, recording actual frame changes. It does not modify or save the test scene. Close other editor instances for the same project before running to avoid project locks; the runner does not forcibly close them.

After the Play Mode check, the editor process must also exit normally. If it remains hung, the runner records a timeout even if the helper reported success. Inspect the editor log, version, and project shutdown logic before repeating validation.

For shared commands, states, and evidence conventions, see the [execution overview](../execution.md).

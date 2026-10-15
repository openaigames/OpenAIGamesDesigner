# Godot Execution Configuration

[English](execution.md) | [简体中文](execution.zh-CN.md)

```json
{
  "godot": {"export_filename": "MyGame.exe", "export_mode": "debug"}
}
```

Build and export require --preset and an existing export_presets.cfg. export_mode accepts debug or release. Choose an output name for the target, such as MyGame.x86_64 for Linux or index.html for web. Export templates and SDKs must match the project. File existence alone does not prove standalone playability.

See [execution overview](../execution.md) for shared commands, states, and evidence.

## Project Commands

Configure prepare, smoke, test, play, build, or export under commands in .openaigame/project.json to override Godot defaults. Actual Godot version checks still run; doctor remains built in. Commands are argument arrays with {project}, {run}, and {output}, without shell concatenation.

Custom tests do not need --script or the GDScript marker. They must supply a real {run}/test-results.json with tests > 0, failed = 0, errors = 0 and preserve original evidence. Custom build/export do not require a preset, but must create nonempty outputs under {output}. Nonzero exits, errors, or missing reports/artifacts fail. Native GDScript tests retain the assertion-marker protocol.

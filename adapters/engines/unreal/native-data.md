# Native Parameter and Curve Access

[English](native-data.md) | [简体中文](native-data.zh-CN.md)

Uses `engine_workflow execute` and session checkpoints. Native DataAsset/CurveFloat assets remain the editable source of truth. Request/result JSON carries interchange data and evidence; games need not become JSON-driven.

Add `native_reads` to an `inspect` request. Each entry specifies id, path, and properties to read. For CurveFloat, `curve_times` evaluates the native curve at specified times. These samples are neither the complete curve keys nor observed runtime values.

```json
{"engine":"unreal","mode":"inspect","native_reads":[
  {"id":"hero","path":"/Game/Data/Hero","properties":["move_speed","commit_delay"]},
  {"id":"damage","path":"/Game/Data/DamageCurve","curve_times":[0,0.1,0.2,0.3]}
]}
```

For authorized changes, use edit's `native_patch`. Set expected to the values just read, and include only fields needed for the task in values:

```json
{"engine":"unreal","mode":"edit","operations":[
  {"op":"native_patch","path":"/Game/Data/Hero",
   "expected":{"move_speed":500.0},"values":{"move_speed":550.0}}
]}
```

The tool compares the baseline exactly before writing, then reads back task fields before saving with native floating-point precision. Export/import complex data and curve keys through project UFunctions: reads use `read_method`; writes specify both `read_method` and `write_method`. Read methods return a complete JSON object string. Write methods accept a JSON string of task changes and return bool. The project controls field scope, curve keys, interpolation, and transactions. Unknown methods must not be assumed to be safe importers.

expected must equal the entire project export snapshot. values is the authorized subset of fields, and the subsequent export must contain the intended results. Failures are not replayed automatically: inspect side effects and checkpoints, then use the existing recovery entry point if needed. Exporters must not secretly repair, save, or create assets.

A save is recorded as `native_asset_saved`. Then start **a separate inspect session** to reload from disk and verify. Run the actual game consumer and use shared observations to record effective values and override conditions. Reading the same UObject is not a disk reload; correct authored values do not establish correct runtime instances or satisfactory game feel.

Engine/plugin differences can make properties unavailable through reflection. Report the specific read failure and use a verified project read-only interface rather than forcing a change of native asset format.

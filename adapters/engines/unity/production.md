# Unity Production Interface

[English](production.md) | [简体中文](production.zh-CN.md)

## Creation and Startup

[production.py](production.py) maintains Unity request rules, project creation, helper installation, and commands. It requires Windows, a valid Unity license, and Windows Build Support for standalone Players.

```powershell
python tools/engine_workflow.py create --project "D:/Games/MyGame" --engine unity --editor "D:/Unity/Editor/Unity.exe" --name MyGame --brief "Agreed scope of the task"
```

The editor's createProject operation creates an empty project, then loads it to verify the actual version. edit/inspect use C# executeMethod. playback builds a standalone Development Player and runs scripted actions. Installation hashes identify user modifications; helpers are upgraded only when a checkpoint exists and the previous files are unchanged.

Timed actions and PNG/frame-time sampling do not verify real keyboard/mouse input or constitute a formal performance assessment. Recording adds overhead; disable capture_interval for separate performance measurements. Camera rendering does not capture independent Overlay UI or audio.

Shared entry points and recovery: [session management](../sessions.md). Native execution is in [OAGDProduction.cs](OAGDProduction.cs), and standalone playback in [OAGDPlayback.cs](OAGDPlayback.cs). Scripts are installed only in the target project; session records include versions and actual processes.

Standalone playback and formal builds share the low-level build operation in [OAGDBuild.cs](OAGDBuild.cs), while retaining their own outputs, targets, and acceptance rules. Production checks and installs this dependency automatically, updating only registered, unmodified helpers after creating a checkpoint. Formal builds explicitly install `OAGDEngineBridge.cs` and `OAGDBuild.cs` through `tools/engine_setup.py`; see [execution configuration](execution.md).

| Operation | Required fields and purpose |
| --- | --- |
| scene | `path: Assets/...unity`; `create: true` creates a scene, otherwise opens it |
| object | Exact hierarchy `target`; creation requires `create: true` and a single-name target, with optional `parent`; supports `primitive` or an existing prefab/model `source` |
| components | Object entries with `type` (full name, such as UnityEngine.Rigidbody) and `properties`; reuse a unique existing component or add one |
| import | Absolute source file `source` and project `path`; replacement requires `replace: true` |
| model | Model `path`, `animation_type` (None/Legacy/Generic/Human), and optional asset `avatar` containing a valid Avatar |
| animation | `target`, new `controller` path, and `states`; optional parameters, transitions, and avatar |

Object position / rotation / scale use local xyz coordinates. Component properties use Unity **serialized property names**, such as Rigidbody's `m_UseGravity`, rather than arbitrary C# property names. Entries `{name, kind, ...}` accept number for float/int, boolean for bool, text for string/enum, vector for vector3, asset paths for asset, and object_path for object. Native type constraints apply; missing fields and invalid types fail. Complex nested arrays require real SerializedProperty paths; changing array length requires an interface extension.

Animation states are `{name, clip, clip_name?}`. Select a specific clip_name when a model contains multiple AnimationClips. Parameters are `{name, type}` (Float/Int/Bool/Trigger). Transitions are `{from,to,duration,parameter?,condition?,threshold?}`, with AnimatorConditionMode names for condition. The first state is the default. Existing Controllers are not overwritten, preserving hand-authored state machines; use targeted project editing instead. Human configuration does not replace manual bone mapping or animation acceptance checks.

Copy and adapt the [scene example](examples/scene.json) and [playback example](examples/playback.json). They create verification geometry, not a default game design or art direction.

Standalone playback uses `scene`, `seconds`, and `camera`. Set `capture_interval: 0` to disable recording. Supported actions include:

```json
{"at": 1, "op": "position", "target": "Player", "position": [1, 0, 0]}
```

Alternatively, `{at,op:"message",target,method,argument?}` calls an explicitly provided project MonoBehaviour method; a missing receiver is an error. Reports check actual execution counts and retain frame times. Project assertions and tests must still verify the method's gameplay behavior.

Use `mode: inspect` with a scene to read hierarchy, transforms, component types, and persisted asset references in a new editor process. Import and instantiate character models first, configure Avatar/Animator next, then play them to check poses, displacement, transitions, and collisions.

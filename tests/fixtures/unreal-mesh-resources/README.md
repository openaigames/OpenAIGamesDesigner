# Native UE Mesh Resource Tests

[English](README.md) | [简体中文](README.zh-CN.md)

Uses an isolated empty content project and Engine Sphere, without game maps. Requires Unreal Editor, PythonScriptPlugin, and EditorScriptingUtilities. Create the project through tools/engine_workflow.py create, then run:

```powershell
python tests/fixtures/unreal-mesh-resources/check_native.py --project "D:/Tests/MeshResources"
```

The runner performs baseline inspect → test map/two derived meshes → fresh-session reopen inspect. Checks actual three-level LOD counts, persistent Nanite settings, unchanged source readback, consumers, and instancing candidates. Results: mesh-native-validation-1/verification.json; raw sessions: runs/engine-*.

Existing evidence directories are protected. Inspect failures/logs first. Use --attempt 2 only after confirming no test assets were created; otherwise use a new isolated project or explicitly resolve partial state. Never target production projects. Tests do not validate map appearance, foliage wind, frame times, or whole-game performance.

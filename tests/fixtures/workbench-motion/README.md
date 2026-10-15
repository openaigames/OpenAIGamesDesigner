# Workbench Motion Fixture

[English](README.md) | [简体中文](README.zh-CN.md)

Run generate.py inside Blender, targeting a new directory:

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/fixtures/workbench-motion/generate.py -- /absolute/new-fixture
python tools/project_workbench.py --project /absolute/new-fixture --view assets
```

Original shapes, rigs, and clips test direct glTF, duplicate clip names, animation-only FBX with characters, bindings, and linked previews. mapped-native.uasset is an explicit interface placeholder and cannot import into UE. This checks browser mapping, not native export or motion quality.

Check save, character/clip/preview-character switches, discard, refresh, navigation, export, and two-window conflicts. Verify actual paths/context against history. Changed sources/bindings invalidate conclusions while retaining notes. Fixture shapes are not recommended game assets.

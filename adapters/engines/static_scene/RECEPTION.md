# Scene Handoff and Verification

[English](RECEPTION.md) | [简体中文](RECEPTION.zh-CN.md)

Combine static import, graybox replacement, collision, and rollback in reproducible Godot / UE 5.8 projects, with file handoff verification.

## Receive a Project

`scene_handoff.py` uses the existing `environment.handoff` packager, preserving authoritative selection records, hashes, and glTF image/buffer dependency checks. The handoff specification declares engine versions, entry points, and provenance files. The receiver verifies file contents after copying them to a new location. It does not run bundled scripts or infer undeclared native dependencies.

```json
{
  "id": "MySceneRevision",
  "files": ["RECEIVE.md", "scene.glb", "provenance/SELECTION.md"],
  "engines": {"godot": "4.7.2", "unreal": "5.8.2"},
  "entrypoints": {"instructions": "RECEIVE.md"},
  "provenance": ["provenance/SELECTION.md"]
}
```

The first `provenance` entry is the project's authoritative selection record. All files are project-relative; entry points and provenance must appear in files. Existing pipeline logic includes external GLB/glTF dependencies automatically. Reception instructions must specify required engine plugins, build tools, private asset licenses, and build steps.

```sh
python tools/scene_handoff.py create --project AUTHOR --spec SPEC.json --output NEW_SNAPSHOT
python tools/scene_handoff.py check NEW_SNAPSHOT --pristine
python tools/scene_handoff.py receive NEW_SNAPSHOT --output NEW_RECEIVER
python tools/scene_handoff.py check NEW_RECEIVER
```

The sealing manifest `scene-handoff.json` is written last. The pristine check rejects missing, corrupt, or extra files. Existing output directories are always rejected to protect receiver edits. Interrupted directories remain for diagnosis; fix storage issues and receive into a fresh directory. Normal check permits engine caches/outputs but still requires unchanged input bytes. After intentional source edits, create a new revision rather than rewriting the old manifest.

Engines may modify input configuration during startup, causing post-run integrity differences. Record those changes and retain the prebuild snapshot, then hand off a new project revision.

## Six Combined Cases

The [scene template](../../../templates/static_scene/reception/RECEIVE.md) includes two doors with different positions/orientations/scales, a box retaining graybox collision, a triangle-collision box, and two building-fragment instances. A continuous route passes through both doors, testing independent operation, shared resource instances, building walls, and exterior passage.

```sh
python tools/scene_reception.py --revisions FROZEN_REVISIONS --provenance PROVENANCE --output NEW_CASE
python tools/scene_handoff.py create --project NEW_CASE --spec NEW_CASE/handoff-spec.json --output NEW_SNAPSHOT
```

This reception case has an explicit input contract; it is not an arbitrary map-layout generator. `FROZEN_REVISIONS` contains box, door, and clockhill directories. box/door use `make_fixtures.py` geometry/hierarchy. clockhill uses nodes 1, 3, and 25 and the original case's coordinate bounds. Other assets need their own layouts/probes; renaming files does not make the acceptance criteria applicable. `PROVENANCE` contains `SELECTION.md` and referenced license/source records. Real FPS art is not distributed with the toolkit.

`OAGD_ENGINE_CONFIG` points to JSON with `godot` executable, `unreal` installation, `godot_template` Windows export template, and `ddc` cache path. Project scripts read inputs, tools, and native resources only from the received directory. Follow the template RECEIVE.md order; use a different `--label` for each run. Reports go to evidence.

## Failures and Compatibility

Cases cover corrupt frozen GLB rejection, interrupted copies/existing-directory protection, later-group Godot staging failures, rollback after save failure, UE staging/target-hiding exceptions, invalid receipts, new-process rollback/reapply, and deliberate door-collision misbinding. After recovery, repeat the full route.

UE baselines/receipts use `fingerprint_format: canonical-zero/1`. This normalizes `-0.0` and `0.0` across saves while retaining 1e-5 precision; actual transform/resource/collision changes still conflict. Unmarked older records keep the older algorithm and are not rewritten. If an old receipt encounters signed-zero differences, preserve its baseline and recapture/apply into a new revision rather than forcing deletion through conflicts.

Record file verification, native rebuilding, standalone execution, technical image checks, and review by the recipient separately. Handoff verification includes regenerating native assets, compiling, and running from a new directory. It does not imply independent-user acceptance, complete interior navigation, or final lighting for the Clockhill map.

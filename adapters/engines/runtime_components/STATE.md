# Settings, Scenes, and Local Game State

[English](STATE.md) | [简体中文](STATE.zh-CN.md)

For Godot and UE 5.8, independent of character animation. Integrates with the project approach in [input, focus, and pause](INPUT.md).

## Files and Responsibilities

| Responsibility | Godot | UE 5.8 |
| --- | --- | --- |
| Two-generation local storage | `godot/oagd_store.gd`: `OAGDStore` | `OAGDStore.h/.cpp`: `FOAGDStore` |
| Settings validation/application | `godot/oagd_settings.gd`: `OAGDSettings` | `OAGDStore.h/.cpp`: `FOAGDSettings` |
| Scene staging/commit | `godot/oagd_scene.gd`: `OAGDScene` | `OAGDScene.h/.cpp`: `UOAGDSceneComponent` |
| Game state, stable IDs, checkpoints, menus, tests | `templates/runtime_state/godot/` | `templates/runtime_state/unreal/` |

The toolkit stores JSON objects; it does not automatically scan/serialize engine objects. Projects define versions, validate references, collect snapshots, stage scenes, and apply state. The example declares `scene`, `checkpoint`, `objects`, and `player`. Door IDs `door-a` and `door-b` are independent of Actor enumeration order. UE identifies Actor Tags and rejects duplicate IDs; Godot room adapters declare room ownership and doors. Positions use native engine coordinates/units; saves are not guaranteed interchangeable between examples.

## Storage Integration

Godot: `Store.new(directory, project_id, data_version)`. `write_slot(slot, dictionary)` returns an error string, empty on success. `read_slot(slot)` returns `error` and, on success, `data/seq/generation/recovered`.

UE: `FOAGDStore(Directory, ProjectId, DataVersion)`. `Write(Slot, Data, Error)` and `Read(Slot, Data, Recovered, Error)` return bool. JSON types are public dependencies. The host chooses a writable game data directory. Examples use Godot `user://state` and UE `Saved/OAGDState/<project-id>`.

Each slot uses `<slot>.0.json` and `<slot>.1.json`. The envelope contains a raw JSON `body` string and its UTF-8 SHA-1 checksum. body contains `schema=1`, `project`, `version`, increasing `seq`, and project `data`. Checksums detect accidental corruption, not cheating, and do not encrypt data. Files are limited to 2 MiB. Slot names accept 1–64 lowercase ASCII letters, digits, underscores, and hyphens.

Write order: validate project data → find newest valid generation → write the older generation's `.tmp` → close/read/verify → commit that generation. The newest valid generation survives the commit. Reads skip corrupt generations and set `recovered=true`. If the newest **intact** record has incompatible project/format/data versions, loading fails rather than silently using an older compatible record. With only corrupt files, storage does not overwrite automatically: back up the slot and choose a new one or explicitly recover. Leftover `.tmp` files are not committed records.

Validate cross-object references and rules **before writing**, and again after reading but before modifying the world. Components cannot know whether a door ID exists in your game. Loading should assign final state idempotently rather than repeat rewards. The example uses `slot1` and a separate `checkpoint`; components accept multiple named slots, while games own slot-selection UI.

Storage assumes one writer in one process. It has no multiprocess locking, cloud saves, networking, automatic version migration, or arbitrary object serialization. Physical power-loss behavior is untested; successful commits do not guarantee zero hardware-loss risk. Explicitly migrate formats into new slots while preserving originals. Rolling back toolkit code does not roll back player data.

## Settings and Consumers

`defaults/Defaults`, `validate/Validate`, and `apply/Apply` support:

| Field | Range | Consumer |
| --- | --- | --- |
| `fps` | 0 (unlimited), 30, 60, 120 | Godot `Engine.max_fps`; UE `GameUserSettings` frame-rate limit |
| `vsync` | bool | Godot DisplayServer; UE GameUserSettings non-resolution settings |
| `camera_sensitivity` | 0.1–4 | Project camera controller; examples multiply actual camera rotation deltas |

Validate/save before applying settings and updating camera parameters. On startup, validate loaded data. Missing files use defaults; corrupt/incompatible files use defaults with a message, as does recovery from an older generation. Example menus change settings and restore defaults. Rebinding remains in the separate input-preference interface.

Frame-limit and VSync readback do not measure refresh rate or performance. Headless checks do not verify real VSync. Volume controls, resolution-confirmation countdowns, and platform graphics presets are not provided.

## Scene Transitions and Checkpoints

The model is **persistent player/UI plus replaceable passive scene blocks**: actual `.umap` streaming in UE and PackedScene in Godot. It is not a general OpenLevel migration across arbitrary GameModes or an open-world streaming strategy. Block initialization must not trigger irreversible rewards, saves, or global events.

Godot `stage(path)` synchronously loads/instantiates a candidate while retaining the current scene. Projects validate its adapter and apply state off-tree; `commit()` replaces the current child scene. `cancel()` frees the candidate. Large synchronous loads may stall frames; projects can supply their own asynchronous preparation layer.

UE `Stage(Package, Error)` asynchronously loads a hidden candidate. After `Prepared`, projects inspect stable IDs in `Staged->GetLoadedLevel()`, apply state, then call `Commit(Error)`. `OnLevelShown` replaces Current, unloads the old scene, and broadcasts `Completed`. `Cancel()` works during preparation, not after display commit. A 30-second wall-clock timeout discards the candidate and keeps the old scene. Engine lifecycle callbacks still run; candidate BeginPlay must avoid irreversible side effects.

Acquire a `transition` pause reason before requesting and release it on every success/rejection/cancel/timeout branch. The example preserves an independent `menu` reason and clears velocity/old input. The player stays in the persistent container and moves only after successful commit. Invalid saves, missing maps/adapters/IDs leave the old scene and state intact.

A checkpoint is a project-defined persistent snapshot. The example records scene, position, door state, and `a-entry/a-door/b-entry/b-door` IDs. Save successfully before updating the runtime checkpoint ID. Respawn follows the same validation/scene-commit path. This is not project-file rollback and does not prescribe checkpoint rules for every game.

## Creation and Validation

```sh
python tools/runtime_components.py create --engine godot --scenario state --project NEW_GODOT_DIR
python tools/runtime_components.py create --engine unreal --scenario state --project NEW_UE_DIR --ue-root D:/UE_5.8
```

Open `project.godot`, or compile OAGDExamplesEditor, run project `create_map.py`, and open `/Game/Example`. Generation preserves existing maps. Cook Room_a and Room_b for release. InvalidRoom intentionally lacks a state object and is included in the validation project's cook configuration.

```sh
python tools/runtime_validation.py --engine godot --project NEW_GODOT_DIR --executable GODOT_EXE --visual
python tools/runtime_validation.py --engine unreal --project NEW_UE_DIR --executable UNREAL_EDITOR_EXE --visual
```

The validator identifies state scenarios, creates a fresh evidence directory, runs exercise, exits, then launches resume. Both independent processes must pass. Test data stays in evidence and does not touch interactive saves. Reports inspect actual objects, collision, player positions, settings consumers, and recovery; they are not physical-device or manual-player tests.

Direct case arguments: Godot `-- --self-test --state-phase=exercise --save-root=ABSOLUTE_DIR --report=ABSOLUTE_JSON`; UE `-OAGDSelfTest -StatePhase=exercise -StateRoot=ABSOLUTE_DIR -StateReport=ABSOLUTE_JSON`. exercise requires a fresh directory; resume explicitly reuses it. Interactive runs need no test arguments.

New projects receive distinct identities. Later releases of the same game should retain identity and use explicit data versions. Components are project-locked copies; migrate differences deliberately and preserve customizations when upgrading.

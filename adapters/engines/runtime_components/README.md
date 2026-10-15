# Optional Runtime Components

[English](README.md) | [简体中文](README.zh-CN.md)

For projects that have chosen Godot or UE 5.8 and need basic movement, cameras, or interaction queries. Existing character frameworks can use just the query, session, or geometry interfaces. Components are copied into each project and locked by hash. Games do not share writable component files, and toolkit updates do not change existing games.

## Responsibilities and Entry Points

| Shared feature | Godot | Unreal 5.8 | Project responsibility |
| --- | --- | --- | --- |
| Input, rebinding, contexts, pause reasons | OAGDInput / OAGDFocus | UOAGDInputComponent / FOAGDFocusStack | Action names, consumers, menus, actual engine pause |
| Native navigation and movement goals | OAGDNavigation | UOAGDNavigationComponent | NPC behavior, retries, movement integration, performance scope |
| Derived static assets and replacement | OAGDStaticAssets | UOAGDStaticAssets | Stable object mapping, collision policy, asset and level acceptance |
| Ground movement, gravity, jumping, collision | OAGDActor / CharacterBody3D | AOAGDCharacter / CharacterMovement | Input mapping, speeds, sprinting, combat restrictions |
| Follow camera and obstruction handling | OAGDCamera / SpringArm3D | CameraArm / SpringArmComponent | Camera modes, input, lock-on, framing |
| Occlusion-aware proximity queries | OAGDQuery.ray | UOAGDQuery::VisibleHit | Interaction conditions, damage, doors, pickups |
| State notifications and restart generations | OAGDSession | UOAGDSessionComponent | State names, win/loss rules, cleanup, rebuilding |
| Local settings and named save slots | OAGDSettings / OAGDStore | FOAGDSettings / FOAGDStore | Saved fields, data versions, directories, recovery messages |
| Scene staging and commit | OAGDScene | UOAGDSceneComponent | Passive scene adapters, stable IDs, checkpoints, pause ownership |
| Interaction targets and requests | OAGDInteractable / OAGDInteraction | UOAGDInteractableComponent / UOAGDInteractionComponent | Conditions, synchronous commit rules, viewpoint, input, UI |
| Sound, visual, and camera feedback | OAGDFeedback | UOAGDFeedbackComponent | Event meanings, cue assets, positions/owners, scene scope, camera composition |
| Generated geometry | OAGDGeometry.load_scene | AOAGDGeometry::LoadScene | Selected revision, level and art acceptance |

Godot modules can be used independently. UE query and session components do not require AOAGDCharacter; that optional character base includes a follow camera. Both implementations use native engine physics. Shared components do not prescribe damage, quests, inventories, or progression, and do not introduce an all-purpose engine-independent runtime.

## Install into an Existing Project

Run from the shared toolkit runtime root, substituting actual paths:

```powershell
python tools/runtime_components.py install --engine godot --project C:/Games/MyGodotGame
python tools/runtime_components.py install --engine unreal --project C:/Games/MyUEGame --ue-root D:/UE_5.8
python tools/runtime_components.py status --project C:/Games/MyUEGame
```

Godot installs to `addons/oagd`; UE installs to `Plugins/OAGDCore`. UE consumer C++ modules must depend on `OAGDCore`; the plugin depends on the engine's ProceduralMeshComponent. Installation does not replace main scenes, GameModes, input mappings, or characters. Files alone do not connect the components to gameplay.

`.openaigame/runtime-components.json` records component versions, engine targets, and file hashes. Reinstalling the same version reads its status. Unowned files, manual edits, or a different locked version produce conflicts. Merge project changes and explicitly migrate in a separate copy. There is no background upgrade or force-overwrite option.

The installer stages files and cleans up after catchable write errors, allowing a retry. It does not guarantee recovery after power loss or forced termination. UE projects declaring a different numeric engine version are rejected. GUID-based custom engine associations still require caller verification; `--ue-root` verifies only the selected engine version. Examples disable movement and new jumps after win/loss; R restarts.

Both engines validate formats, object IDs, arrays, colors, and indices before scene instantiation. Invalid documents are rejected as a whole to avoid partial objects.

## Create a Task-Specific Example

| scenario | Guide |
| --- | --- |
| training / puzzle | Basic training and key-door examples below |
| input | [Input, focus, and pause](INPUT.md), including modifier keys and mouse wheel |
| state | [Settings, scenes, and local state](STATE.md) |
| feedback | [Sound, visual, and camera feedback](FEEDBACK.md) |
| interaction | [Queries, prompts, instant/hold interactions](INTERACTION.md) |
| navigation | [Native navigation and project NPCs](NAVIGATION.md) |
| scene | [Specification-driven scenes and traversal](SCENE.md); accepts --scene-spec |
| static | [Single-mesh replacement](STATIC_ASSETS.md); use [static scenes](../static_scene/README.md) for multi-node assets |

Substitute the desired scenario in the commands below. Always use a new directory; UE also requires a 5.8 engine path. Upgrade installed components with [runtime_migration](../../../docs/INSTALLATION.md), not by treating install as an overwrite command.

## Training and Puzzle Projects

```powershell
python tools/runtime_components.py create --engine godot --scenario training --project C:/Trials/GodotTraining
python tools/runtime_components.py create --engine godot --scenario puzzle --project C:/Trials/GodotPuzzle
python tools/runtime_components.py create --engine unreal --scenario training --project C:/Trials/UETraining --ue-root D:/UE_5.8
python tools/runtime_components.py create --engine unreal --scenario puzzle --project C:/Trials/UEPuzzle --ue-root D:/UE_5.8
```

Each project needs a new directory. Training defines three hits and a win condition; the puzzle defines keys, doors, and an exit. Both support restarting after failure. WASD moves, Space jumps, E attacks/interacts, R restarts, and holding the right mouse button rotates the camera. These are engineering grayboxes, not finished character animation, art, audio, or game feel.

Open `project.godot` in Godot. For UE, compile `OAGDExamplesEditor Win64 Development`, then run the project's `create_map.py`:

```powershell
& D:/UE_5.8/Engine/Build/BatchFiles/Build.bat OAGDExamplesEditor Win64 Development -Project=C:/Trials/UETraining/OAGDExamples.uproject -WaitMutex -NoHotReloadFromIDE
& D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe C:/Trials/UETraining/OAGDExamples.uproject -run=pythonscript -script=C:/Trials/UETraining/create_map.py -unattended -nullrhi
```

The map script creates the editor map; gameplay lives in the project's C++ module. Run directly or use Play in the editor. Example sources are editable, and their rules do not alter the shared library.

## Repeatable Validation

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/GodotTraining --executable C:/Tools/Godot.exe
python tools/runtime_validation.py --engine unreal --project C:/Trials/UETraining --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe
```

Add `--visual` to render and capture screenshots. Godot reports to project `validation.json`; UE to `Saved/validation.json`. The runner archives old results and evaluates fresh reports, exit codes, and individual assertions, not success strings in logs. Commands, output, and reports are stored in `.openaigame/runtime-validation/<run>`.

Checks cover actual movement, generated geometry collision, wall blocking, occlusion queries, interaction distance, project win/loss, restart, and terrain units. Godot drives movement through Input actions; UE calls native project input handlers. These are not manual keyboard/mouse playtests. Packaged releases, networking, arbitrary terrain reachability, and every Godot 4.x version are outside these checks.

## Specifications and Content Replacement

See [procedural generation](../../processing/PROCEDURAL.md) for geometry specifications, GLB, `scene.json`, and reports. Both engines consume the same scene structure: right-handed, Y-up, meters. Godot keeps the scale; UE converts to X-forward/Y-right/Z-up centimeters. Winding follows engine conventions. Source object IDs become Godot node names and UE Actor Tags.

[Static assets](STATIC_ASSETS.md) provides fixed-baseline mappings, derived meshes/materials/LODs, native replacement, and rollback. Follow its input contract and limits. Loaders create native runtime objects; they do not automatically convert edited engine scenes back into specifications. Object-level JSON three-way merging protects only edits represented in that JSON.

## Implementation and License

Components use native mechanisms such as CharacterBody3D, CharacterMovement, and SpringArm, and are distributed under the repository LICENSE. Engine integration entry points are listed above.

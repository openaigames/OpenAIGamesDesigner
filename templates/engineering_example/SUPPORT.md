# Combined Example Integration

[English](SUPPORT.md) | [简体中文](SUPPORT.zh-CN.md)

The combined example runs on Windows with Godot or UE 5.8. You can also integrate its modules independently. The table shows what the example connects and which checks belong to your game.

| Module | Reusable functions | Example integration | Project-specific checks and limits |
| --- | --- | --- | --- |
| Project infrastructure | Input routing and rebinding, focus, pause reasons, settings, scene loading, and versioned local saves for declared fields | Keyboard and simulated controller input, nested pauses, native rooms, save/load/restart, and resuming in a new process | Test rebinding menus, settings, checkpoints, recovery from corrupt save generations, physical controllers, and usability |
| Feedback | Sound, visual, and camera cues; attachment, concurrency, pause/cancel, and object/scene cleanup | Pickup sounds, held loops, pause, cancellation, and scene cleanup | Test UI cues, overlapping effects, and failure cases; review the actual mix by listening |
| Interaction and NPCs | Target queries, conditions, hold-to-commit interactions, cancellation, ground navigation, and chase/return examples | The character picks up a scene object; an NPC patrols the generated scene and replans after pause, cancellation, or loading | Test occlusion, competing targets, unreachable goals, pursuit, and dynamic obstacles. Combat, dialogue, and crowd systems require game-specific implementation |
| Scenes and static assets | Scene specifications, stable IDs, three-way merging, native navigation, asset replacement, materials, collision, and LOD | Two rooms with a curved path, replacement of a doorframe with an original model, and saved native resources and navigation | Test ramps, narrow passages, disconnected areas, replacement policies, and conflicts. Arbitrary material conversion and open-world generation are outside this example |
| Characters and animation | Processing and playback for configured humanoids, bounded root motion, foot IK, and primary/support-hand grips | CesiumMan animation, controller movement, foot contacts, two-hand grip, and reconstruction after pause, release, or loading | Root motion, turning, and layers have separate examples. Test combinations in your game; networked root motion, moving platforms, and finger posing require additional implementation |

`core` and `playback` are independently installable source packages, delivered as project-local Godot addons or UE plugins. Core components can be instantiated separately, but UE compiles them together as the `OAGDCore` plugin; selecting a component does not remove other C++ files. Playback has no dependency on core. This combined example uses both packages.

Each game owns its input mappings, rooms, save fields, cues, patrol rules, character bindings, and props. Games do not share writable configuration, and toolkit updates do not automatically alter them.

## Integration and Migration

For examples without a character, `runtime_components.py create` provides input, state, feedback, interaction, navigation, scene, and static-asset examples without playback. Existing projects can install core or select core and playback through `runtime_migration.py`. Connect the installed components to your game's characters and rules.

`engineering_example.py` uses verified character revisions and bindings to create new project directories for both engines. UE requires a 5.8 installation specified by `--ue-root`. Follow the generated README to prepare resources; a prepared handoff already includes them.

```text
python tools/runtime_migration.py plan --project GAME --engine godot --packages core playback --plan review.json
python tools/runtime_migration.py apply --project GAME --plan review.json --receipt BACKUP_OUTSIDE_GAME
python tools/runtime_migration.py rollback --project GAME --receipt BACKUP_OUTSIDE_GAME
```

`plan` compares the previous lock, the project's current files, and the incoming package. It updates files changed only upstream and preserves files changed only in the project. If both sides changed the same file differently, the entire apply operation is rejected. Game scripts, assets, character bindings, and saves stay outside migration.

`apply` checks that the plan is still valid, and the receipt preserves original file contents and hashes. Rollback refuses to overwrite subsequent edits. Recoverable I/O errors restore the original files; power loss or forced termination can interrupt that recovery. Keep the receipt and project version history.

## Trial Feedback

Use [TRIAL_REPORT.md](TRIAL_REPORT.md) to record toolkit and engine versions, selected modules, the task, reproduction steps, expected and actual results, logs or images, manual adjustments, and blockers. State whether the tester helped create the example and whether input came from software or physical devices. Record technical results and playtest impressions separately.

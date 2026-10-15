# Interaction Components

[English](INTERACTION.md) | [简体中文](INTERACTION.zh-CN.md)

Optional native components handle candidate discovery, distance/direction/occlusion filtering, prompts, hold progress, cancellation, and request lifecycle. Games own conditions and commit rules. No animation plugin, sample character, key, or door is required.

## Projects and Files

```powershell
python tools/runtime_components.py create --engine godot --scenario interaction --project C:/Trials/InteractionGodot
python tools/runtime_components.py create --engine unreal --scenario interaction --project C:/Trials/InteractionUE --ue-root D:/UE_5.8
```

Open `project.godot` in Godot. For UE, compile `OAGDExamplesEditor Win64 Development`, run the new project's `create_map.py`, and open `/Game/Example`. The script saves a persistent map and `Content/Interaction/Tint.uasset`; native game code creates room objects and destroys them together with the room.

WASD moves and changes facing; Space/controller South starts an interaction and release cancels; Esc opens pause. Face key / Face door menu options adjust facing. Pick up the blue cube key, then hold to open the door. Tests use native software input and direct case calls, not physical controllers or manual playtesting.

`interaction-profile.json` is in the Godot root or UE `Content/OAGDData/`, with schema=1, range_m, half_angle_degrees, and door_hold_seconds. Input uses `input-profile.json`. Each generated project gets independent input identity and local configuration. Toolkit upgrades do not update locked game components automatically.

## Modules and Interfaces

| Responsibility | Godot | UE 5.8 |
| --- | --- | --- |
| Target | `OAGDInteractable` Node3D | `UOAGDInteractableComponent` ActorComponent |
| Queries and requests | `OAGDInteraction` Node3D | `UOAGDInteractionComponent` ActorComponent |
| Configuration | `configure(distance_m, half_angle)` | `Configure(distance_cm, half_angle)` |
| Registration | `register_target(target)` / `unregister_target(id)` | `RegisterTarget(target)` / `UnregisterTarget(id)` |
| Viewpoint and update | `update_query(requester, origin, direction, delta)` | `UpdateQuery(requester, origin, direction, delta)` |
| Press / release | `begin(unique_request_id)` / `cancel(reason)` | `Begin(unique_request_id)` / `Cancel(reason)` |
| Pause / scene changes | `set_suspended(true)` / `clear()` | `SetSuspended(true)` / `Clear()` |
| Prompt readback | `focused_id()`, `prompt`, `allowed`, `reason`, `progress` | `FocusedId()`, `Prompt`, `Allowed`, `Reason`, `Progress` |
| Events | `lifecycle(request_id,target_id,state,reason)` | `Lifecycle` dynamic delegate, same fields |

Components do not select cameras or listen for keys. Projects provide origin, direction, and game delta, then route input to Begin/Cancel. The example uses character center and the latest movement direction; camera or hand origins are project choices. Godot queries in physics updates and refreshes with delta=0 on input. UE refreshes in controller Tick and again at input start.

Limits: 128 candidates; nonempty stable IDs up to 80 characters; prompts up to 160; hold duration 0–10 seconds, with 0 meaning instant. Distance must be positive and at most 100 m / 10,000 cm; half-angle positive and at most 89 degrees. Invalid or duplicate IDs are rejected; registering the same object is idempotent. Later queries also validate changed target properties.

Godot `condition` Callables return `{allowed: bool, reason: String}`; `commit` returns strict bool. An unbound condition allows interaction; an unbound commit or wrong return type fails. UE subclasses return `FOAGDInteractionOffer` from `Query` and bool from `Execute`, with Blueprint overrides supported. Query must be read-only: do not change registrations, destroy objects, or modify the manager from it.

## Selection, Commit, and Cancellation

1. Registered, enabled targets pass range, direction, and native ray visibility checks. Godot uses `OAGDQuery.ray` collision layer 1; UE uses `UOAGDQuery::VisibleHit` on Visibility, ignoring the requester. Godot accepts the target or its child physics objects; UE accepts its owning Actor. Projects configure complex attached collision channels; there is no arbitrary ignore list.
2. Sort by angle, distance, then stable ID, using tolerances of 0.00001 for 1-dot and 1 mm for distance. Locked targets remain selected with a reason; selection does not skip them for objects behind. Disabled targets are excluded.
3. Begin requeries using the latest supplied viewpoint and conditions, then locks the target and hold duration. Updates cancel if the target disappears, leaves range, becomes occluded/disabled, loses selection through facing, or changes eligibility. Requests do not switch targets automatically.
4. At completion, conditions are checked again. The request leaves the waiting state before synchronous project commit, then emits completed/failed. Commit functions must keep their own state changes consistent; the component cannot roll back partial inventory or cost changes.

Each accepted request emits one started and exactly one completed/failed/cancelled. Begin returning true means accepted, not successful; read events even for instant interactions. Rejected requests emit no started and expose LastError. The last 256 accepted IDs are deduplicated; use a new ID after cancellation. Clear resets room registrations and ID history, with no cross-process/network guarantee.

Only one request can wait at a time. Reconfiguration while waiting is rejected. Lifecycle callbacks and commit functions cannot nest Begin, registration, or reconfiguration, but can Cancel/Clear. References do not keep targets alive; destruction is observed on the next valid Update. Continue updating, and explicitly suspend/clear before pause or unload.

Switching input to menus releases game actions before the pause signal suspends interaction. Cancelled holds do not resume; press again after returning. Leaving the scene or ending play also clears. Reset room destroys and rebuilds registered objects; it is not general level streaming or save restoration.

## Example Game Rules

Shared components do not know key counts or door state. `main.gd` / `ExampleGame.cpp` owns them. Key commit increments the count, hides and disables the pickup; door conditions read the count, and commit rotates the door and disables collision. Prompts and progress read these states and the interaction component.

Projects can call Feedback from completed events, deriving event IDs from request_id. This example uses state, native geometry changes, and UI; projects configure audio and effects.

## Validation and Limits

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/InteractionGodot --executable C:/Tools/Godot.exe --visual
python tools/runtime_validation.py --engine unreal --project C:/Trials/InteractionUE --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe --visual
```

Fresh reports are stored at `.openaigame/runtime-validation/<run-id>/interaction.json`. Godot imports automatically; UE needs compilation and map creation first. The 49 checks cover actual request startup, occlusion, distance, selection, changing conditions, duplicate commits, cancellation, destruction, room replacement, execution failures, and one terminal event per request. Screenshots inspect prompts and real door geometry; automation is not manual experience evaluation.

Scope: Windows single-player, synchronous commits, explicit candidate registration, one ray anchor per target, instant/hold interactions. Networking arbitration, multiplayer contention, asynchronous tasks, multi-action menus, spatial indexes, selection hysteresis, NPC navigation, and production inventories are not included. Adapt native physics and cameras to the game and verify queries, occlusion, and cancellation there.

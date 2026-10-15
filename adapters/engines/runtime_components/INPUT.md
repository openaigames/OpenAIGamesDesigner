# Input, Focus, and Pause

[English](INPUT.md) | [简体中文](INPUT.zh-CN.md)

Optional single-player input components for Godot and UE 5.8, independent of OAGDPlayback, skeletons, animation graphs, and game rules. Projects can adopt input routing and focus helpers while retaining their own characters and menus.

## Creation and Integration

```powershell
python tools/runtime_components.py create --engine godot --scenario input --project C:/Trials/GodotInput
python tools/runtime_components.py create --engine unreal --scenario input --project C:/Trials/UnrealInput --ue-root D:/UE_5.8
```

Use new directories. Open `project.godot` in Godot. For UE, compile `OAGDExamplesEditor Win64 Development`, run `create_map.py`, and open `/Game/Example`. The training/puzzle entry points remain available.

The example supports start, movement, action counting, pause, rebinding, defaults, and exit. WASD/left stick moves; Space/South performs the sample action; Escape/Start opens the menu. Up/Down or D-pad selects, Enter/South confirms. Select a binding and press a new key; Escape cancels. Conflicts within an input context are rejected with a reason. Buttons also accept mouse clicks. Layout and action counting belong to project files.

Install into existing projects with `runtime_components.py install`. Version conflicts and local edits require merging and migration in a separate copy. Installation does not replace main scenes, PlayerControllers, characters, or input frameworks.

| Project-relative location | Integration responsibility |
| --- | --- |
| Godot `addons/oagd/oagd_input.gd` | Add a node, configure the profile, read strength or subscribe to action_changed; ALWAYS processing receives native events |
| Godot `addons/oagd/oagd_focus.gd` | Optional push/pop focus helper; restores only existing, visible Controls |
| UE `Plugins/OAGDCore/.../OAGDInput.h` | Add UOAGDInputComponent, call LoadProfile, forward PlayerController `InputKey(const FInputKeyEventArgs&)` to HandleInput; forward through one entry point to avoid duplicate execution |
| UE `Plugins/OAGDCore/.../OAGDFocus.h` | Optional Slate focus stack; UMG can use native focus APIs with the same enter/exit responsibilities |
| Example `main.gd` / `Source/OAGDExamples/ExampleGame.cpp` | Menus, focus targets, movement consumers, action count, actual engine pause, validation; editable project code |

Godot consumers should not bypass the router with `Input.get_vector` / `is_action_pressed`: global Input state is not controlled by GUI event consumption. Existing UE Enhanced Input or other controllers must likewise designate one action consumer instead of executing both old callbacks and the new route.

## Configuration

The reference profile is `templates/runtime_input/input-profile.json`. Project creation assigns an independent profile ID; Godot application names also use independent IDs to avoid sharing preferences across examples.

| Field | Contract |
| --- | --- |
| schema / id | `oagd.input/1` and project profile identity; preferences must match the identity |
| deadzone | 0.05–0.8 per left-stick axis, remapped to 0–1 above the threshold; not radial |
| actions | Up to 128 named, project-defined actions; lowercase ASCII is recommended because UE FName is case-insensitive |
| context | game, ui, or global; inactive contexts output zero; game is also gated by pause reasons |
| keys | 1–8 bindings per action; multiple inputs use maximum strength, not a sum; projects compose and clamp 2D movement |
| rebindable | Whether players can replace existing slots; reserved and UI actions can use false |

Supported inputs: A–Z, 0–9, Space, Escape, Enter, Tab, Backspace, Up/Down/Left/Right, Shift/Ctrl/Alt; MouseLeft/Right/Middle, MouseWheelUp/Down; PadSouth/East/West/North, PadStart/Back, PadL1/R1, PadUp/Down/Left/Right, and PadLeftX+/X-/Y+/Y-. Left-stick Y is positive downward; the UE adapter converts native input. Chords, IME text, touch, right-stick/trigger configuration, and local multiplayer device assignment are not supported.

Shift, Ctrl, and Alt merge their left/right physical keys. Pressing both produces one aggregated action; releasing one keeps it held until both are released. Godot uses InputEventKey.location; UE uses separate FKeys. External Godot events without location count as one undifferentiated source. Pause/context barriers require the merged key to be fully released before reuse; focus loss clears physical sources. Modifiers can be standalone actions, but `Ctrl+K` is not a supported chord.

Mouse wheel input is discrete: each native directional press synchronously sends 1 then 0, including repeated events within one frame. Use positive action_changed / ActionChanged callbacks for weapon switching or paging; polling strength between frames cannot observe a held wheel. Native release adds no trigger. Each event counts as one step, not trackpad distance. UE consumes MouseScrollUp/Down and ignores concurrent MouseWheelAxis to prevent duplicates. The `Feed` (UE) and `feed` (Godot) interfaces use the same pulse rules. Forward only one native wheel channel to avoid duplicate events.

Multiple bindings still use maximum strength. If a held key already keeps an action at 1, wheel movement creates no second rising edge. Use separate wheel actions for step counting and combine effects in project callbacks. Capturing a wheel event only rebinds; the next scroll can act. Captured modifiers require release and another press.

For example, a project can define `sprint: Shift`, `crouch: Ctrl`, and `next_weapon: MouseWheelUp`. The component emits actions; the project implements speed, crouch collision/camera, weapon selection, and switching rules. The profile remains `oagd.input/1`, and existing profiles need not add actions. After action-set changes, incompatible preferences are explicitly rejected rather than silently discarded.

game and ui can share a key; global conflicts with either are rejected. Rebinding checks the complete candidate before changing the configuration. Escape cancels capture and cannot be rebound through capture. During capture, neither game nor menu actions are emitted; the captured key must be released before acting.

## Pause and Lifecycle

`set_context / SetContext` switches game/ui. Held inputs wait for release, preventing menu confirmation or movement from leaking into gameplay on close.

`set_pause / SetPause(reason, active)` maintains named reasons such as menu and dialog. Removing menu leaves dialog active; repeated assignment is idempotent. It emits pause state without pausing the engine itself. Projects subscribe to pause_changed / PauseChanged and use SceneTree.paused or PlayerController.SetPause, or connect their own session system.

The UE example clears residual character movement on pause to avoid consuming it that frame. Movement and pause policy remain project responsibilities; this example policy is not universal for physics objects or inertia-based games.

Godot listens for joy_connection_changed and application focus loss. UE listens for native device notifications and application focus loss, and checks viewport focus. Disconnect clears the selected device's axes/buttons and allows later reselection. The first event selects one controller; others are ignored. Focus loss releases state and cancels capture without deciding whether the game should open a pause menu.

When destroying menus, switching scenes, or replacing input components, cancel capture, release owned pause reasons, and clean the focus stack. Components remove native device listeners; projects manage their other subscriptions.

## Input Preferences

Godot uses `user://`; UE uses `Saved/OAGDInput/<filename>`. Examples save bindings and deadzone. Loading checks profile ID, action set, contexts, binding counts, and protected actions. Corrupt or incompatible data returns an error and leaves the active configuration unchanged.

Saving writes a temporary file before replacing the target and reports errors. Preferences do not provide a complete save-game transaction system; see [local state](STATE.md). Godot export template paths come from local configuration rather than a developer-machine path embedded in templates.

## Validation and Limits

`tools/runtime_validation.py` recognizes the input scenario and supplies the report location. Godot uses `Input.parse_input_event`; UE uses PlayerController InputKey and Slate focus routing during menus. Software events, disconnect handler calls, and physical hardware are reported separately. Simulated disconnects do not verify controller hot-plug compatibility.

Cases check actual movement, usable paused menus, no resume leakage, multiple pause reasons, conflict rejection, rebinding, defaults, preferences, invalid profiles, axis deadzone, disconnect cleanup, and focus restoration. Packaged builds require separate launches; export success is not a runtime check.

After integration, check keyboard/mouse, target controllers, rebinding, focus loss, and pause in the game. Physical devices and usability need direct validation.

Native references: [Godot input and GUI propagation](https://docs.godotengine.org/en/stable/classes/class_input.html), [Godot user data paths](https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html), and [UE PlayerController InputKey](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/APlayerController/InputKey).

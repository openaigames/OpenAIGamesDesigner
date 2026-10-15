# Unreal Native Project Fixture

[English](README.md) | [简体中文](README.zh-CN.md)

Original C++ module under the repository LICENSE using Engine BasicShapes only, without private/third-party character animation. Tests native data, operable rules, bindings, observation, and handoff, not final character animation/art.

Create isolated ToolkitObservation.uproject with PythonScriptPlugin, EditorScriptingUtilities, and Runtime module ToolkitObservation; copy Source into it. UE 5.8 Win64 needs a compatible C++ toolchain.

Compile the editor target, then execute requests through engine_workflow.py execute:

1. create-space.json creates ground, cover, scale references, camera, and light.
2. create-native-fixture.json creates UObservationSettings and its Pawn consumer.
3. patch-native.json demonstrates explicit read/write, expected baseline checks, saving, and position calibration.
4. read-native.json reads native values in a separate process.
5. observe-complete-flow.json drives/records hits, cancellation, victory, recovery, and retry in real PIE.

Creation requests run once. After failure/timeout, inspect/recover sessions before retrying. If native floating-point readback differs from expected, inspect actual values and derive a justified new baseline without removing conflict protection.

W/S moves, left mouse attacks, Space cancels, R retries. Capsule/FloatingPawnMovement has actual collision; a 250 cm ray determines hits. CurveFloat at .5 returns 21 damage, clearing a 42 HP target in two hits. HUD shows input, health/state, and end messages. BeginPlay creates debug weapon geometry on custom GripAnchor, not a universal character socket.

observe-complete-flow calls timed handlers, not manual keys. Captures have no audio; this fixture authors none. Godot covers synthetic audio observation separately. Delivery is an editable native project for the declared UE environment, not a store build, cross-platform release, or universal game example.

Use [native animation](../../../adapters/engines/unreal/native-animation.md) for real character assets, separately from this skeleton-free rule probe. Animation test code can live in an isolated module with ProceduralMeshComponent. Read real attachment bindings from their project configurations.

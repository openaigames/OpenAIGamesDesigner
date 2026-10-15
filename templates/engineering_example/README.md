# Combined Engineering Example

[English](README.md) | [简体中文](README.zh-CN.md)

Combines character movement, interaction, feedback, saves, navigation, and scene assets in one editable game project. See [integration and responsibilities](SUPPORT.md).

One character brings together movement, interaction, held props, and feedback. NPCs use native navigation; scenes combine generated grayboxes and derived doorframes. Rules live in main.gd / CombinedGame.cpp; configurations/assets belong to the project.

WASD moves; hold E near the gold object to pick up; Q cancels/releases; Esc pauses; K saves; L loads; Tab changes rooms; R restarts. Saves contain stable room ID, player position, and held state only. Loading restores stable state, cancels ongoing interaction/navigation/feedback, and restarts NPC patrol. Pause preserves grip pose but cancels unfinished interactions; press again after resume.

Godot: import, run prepare.gd, build_assets.gd, prepare_combined.gd in order, then open main.tscn.

Prepared handoff projects can import/run main.tscn directly. Preparation is needed only when regenerating assets. Windows re-export requires official templates matching the project's Godot version.

UE 5.8: compile MotionPlayEditor, run prepare.py then prepare_combined.py, and open /Game/Playback/Example. Prepared handoffs contain native resources and need no regeneration.

Automation: Godot `-- --report=ABSOLUTE_PATH --save-dir=NEW_DIRECTORY --mode=exercise`; UE `-CombinedReport=ABSOLUTE_PATH -CombinedSaveDir=NEW_DIRECTORY -CombinedMode=exercise`. Then run resume with the same save directory and a different report to check cross-process continuation. Check reports and exit codes.

Components are locked project copies. Inspect runtime_migration.py plan before apply; rollback uses receipts. Migration excludes game rules, assets, bindings, and saves. Files changed by both toolkit and project conflict and preserve the current state.

This combination uses controller movement, native animation, and foot/hand constraints. Root motion, layers, and turns retain separate cases; other combinations require their own integration tests. Check target builds, physical input, visuals, and audio separately.

Read [SUPPORT.md](SUPPORT.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md), and bundled licenses. Record issues with [TRIAL_REPORT.md](TRIAL_REPORT.md).

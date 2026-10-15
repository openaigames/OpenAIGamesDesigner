# Godot Native Production and Observation Fixture

[English](README.md) | [简体中文](README.zh-CN.md)

Original geometry and editable synthetic audio under the repository LICENSE. This verifies engineering interfaces, not finished action-game art or listening quality.

Copy into an isolated project and copy adapters/engines/godot/OAGDObservation.gd to its root. Verify import/tests with the selected Godot installation. Arrow keys move, Space attacks, Esc cancels, Restart retries. Uses real CharacterBody2D, collision, rays, Camera2D, Control, and AudioStreamPlayer. Attack-arc radius matches ray range.

Automation drives actual movement/attack/cancel handlers and InputEventAction on the focused retry button. It is not human playtesting or physical keyboard latency. Cases cover movement, hits, cancellation, repeat attack, target removal, collision, and retry. Outputs capture.json and asserted test-results.json.

```powershell
Godot.exe --headless --path <ISOLATED_PROJECT> -- --automated --cleanup-delay=0 --output=<ISOLATED_PROJECT>/runs/test/capture.json
Godot.exe --path <ISOLATED_PROJECT> -- --automated --cleanup-delay=0 --capture-media --output=<ISOLATED_PROJECT>/runs/media/capture.json
```

Create a fresh output directory each run. game_workflow run creates directories/revision records; configure these argv as test/play commands if desired. Default cleanup_delay=.075 intentionally retains brief effects/continuous audio for comparison; --cleanup-delay=0 clears immediately. Record measured game-clock differences rather than treating settings as measurements.

Visual mode emits PNGs with actual game-time anchors and main-bus mix.wav. Audio start anchors are estimates, not hardware synchronization; capture adds overhead. Hit body and sustained-state sound are separate layers. Listening must be recorded separately; WAV existence/playback/assertions do not approve quality.

continuity.tscn tests movement/stop → attack → backward-dodge cancel → hit interruption → recovery → buffered next attack → cleanup. Run `Godot.exe --path <PROJECT> res://continuity.tscn -- --cleanup-delay=0 --capture-media --output=<NEW_DIRECTORY>/capture.json` **without --automated**, avoiding the main scene's short flow. Four native assertions inspect actual handlers/collision/frames. Geometric characters test state/movement continuity, not natural humanoid animation. Use the main scene's separate audio capture/review for listening.

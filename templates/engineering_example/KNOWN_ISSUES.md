# Example Limits and Notes

[English](KNOWN_ISSUES.md) | [简体中文](KNOWN_ISSUES.zh-CN.md)

- An editable Windows Godot/UE 5.8 engineering example, not a complete game or final art.
- Saves cover rooms a/b, player positions within declared starting-room bounds, and held state. Out-of-range saves fail. Arbitrary objects, NPC paths, and active effects are not serialized; NPCs resume patrol after loading.
- Controller movement and foot/hand constraints are combined here. Root motion, turning, layers, and other navigation/interaction/save failures use separate cases; this does not validate every combination.
- Losing window focus while holding E cancels interaction. Release/repress after focus returns. Switching windows during automated rendering triggers the same policy.
- The original sample audio tests playback and cleanup. Replace it to suit the game and review the result by listening. Test physical controllers, hot-plug behavior, installation on another machine, and manual gameplay separately from simulated input.
- UE first launch may show a briefly invisible character, shader compilation waits, or spikes. Check cold start, steady runtime, and packaged behavior separately.
- UE source requires UE 5.8 and a matching C++ environment. Godot Windows re-export needs matching official templates. Prepared Windows development builds are not store-release builds.
- The UE example sets r.PSOPrecache.ProxyCreationStrategy=0 so brief feedback is not hidden by deferred PSO proxy creation. First PSO creation may still stall. This is a sample display policy, not a shared-plugin default or performance fix.
- File migration rejects divergent edits to the same file. Catchable write failures have recovery paths; power loss/forced termination have no transaction guarantee. Preserve receipts and version history.

Use [TRIAL_REPORT.md](TRIAL_REPORT.md) with goals, environment, minimal reproduction, logs, and impact. Automated passes are not human acceptance.

# Optional Upper-Body and Full-Body Layers

[English](LAYERS.md) | [简体中文](LAYERS.zh-CN.md)

For Godot and UE 5.8. Bindings without layers use the base graph. Copied components belong to each game; configurations, clips, and request logic remain independently editable.

## Scope and Responsibilities

The base layer retains idle, locomotion, turns, jumping, and landing. The optional `upper` layer starts at the calibrated spine, includes the head and arms, and excludes the root, hips, and legs. The `full` layer overrides the entire body and takes precedence over `upper`. Import checks real ancestry rather than trusting a spine name. Weights perform pose overrides, **not additive animation**.

Godot uses filtered Blend2, TimeScale, TimeSeek, and two AnimationNodeAnimation slots per layer. UE uses editable LayeredBoneBlend for Upper and TwoWayBlend for Full, with two SequencePlayers each. Each UE slot has its own sync group. New selections reset only the chosen slot once; normal playback neither seeks every frame nor writes bones directly.

Shared components own playback generations, weights, priorities, and events. Games decide action eligibility while moving/airborne, movement locks, interaction results, skills, and damage. Sample full-body gestures require grounded stillness; upper-body gestures can overlay movement, turning, and jumping.

## Bindings

Add to complete playback bindings:

```json
{
  "layers": {
    "mode": "upper_full_v1",
    "upper_root": "Actual bone mapped to dst_spine in the character profile",
    "clips": ["upper_wave", "upper_alt", "upper_loop", "full_tuck"],
    "fade_in_s": 0.12,
    "fade_out_s": 0.16,
    "replace_s": 0.12,
    "event_policy": "current_visible"
  }
}
```

Listed IDs must be separate layer_only: true entries with clip, duration_s, loop, motion_owner: controller, and in_place: true. Aliases may reuse processed clips. Base/default IDs cannot become layer-only. Creation/staging checks processing reports, character profiles, roots, and resource hashes; looping layers also check source seam poses.

These four IDs are sample conventions: upper_wave and upper_alt are gesture choices; automated playback also uses upper_loop and full_tuck. The shared components do not require these clip names. Update project requests when changing IDs; choose clips that meet the project's quality requirements.

Nonlooping markers accept [0,duration]; looping markers accept [0,duration), using zero for the seam. Names are unique and times ordered. Loop markers repeat per cycle; basic-layer event restrictions remain unchanged.

## Calls and Rules

Godot uses motion.layers after `configure(tree, definitions, layer_policy)`. UE adds UOAGDLayersComponent and calls Configure(Bindings), alongside UOAGDPlaybackAnimInstance and its graph.

| Operation | Godot | UE |
| --- | --- | --- |
| Request | `play(channel, action, priority, weight, speed, restart)` | `Play(Channel, Action, Priority, Weight, Speed, Restart)` |
| Weight | `set_weight(channel, value)` | `SetLayerWeight(Channel, Value)` |
| Rate | `set_rate(channel, value)` | `SetLayerRate(Channel, Value)` |
| Cancel | `cancel(channel, reason)` | `Cancel(Channel, Reason)` |
| Clear | `reset()` | `ResetLayers()` |

- Request weights are (0.001,1], rates [0,4], with no reverse. Fade durations describe a full 0→1 change; 0→0.5 takes half as long. Rate zero freezes clip time while weights can still fade.
- Lower-priority same-layer requests are rejected. Same action with restart=false is idempotent. New actions use the other slot; replacement during crossfade returns transition_busy for the game to retry/discard. There is no arbitrary-length queue.
- Accepting full-body playback interrupts upper-body logic. Upper requests are rejected while full is active or fading; layer precedence outranks numeric priority.
- Weight zero cancels with weight_zero, rather than hiding a continuing clip. Cancel/preemption stops old-generation events immediately while its pose fades.
- Reset clears weights/generations. Sample P freezes the whole character/layers. Changing only one layer's rate leaves other layers/movement available.

## Events

Godot `event(Dictionary)` and UE `Event(FOAGDLayerEvent)` provide channel, action, run, kind, name, cycle, clip position, accumulated actual play time, and weight. UE fields use PascalCase (TotalSeconds); sample reports normalize to total_s.

FName-derived channel, operation, and rejection strings may differ in case between editor/packages, such as upper/Upper or priority/Priority. Compare these control IDs case-insensitively; toolkit auditors do so while preserving raw records.

Only current visible-weight generations emit markers. Multiple crossed cycles are ordered by cycle/time. Nonlooping clips can complete in the first frame without repeating endpoint markers. Outgoing slots emit no gameplay events. Marker callbacks may cancel; remaining same-frame markers then stop. Interruption/reset notifications reject recursive replacement.

This is a visible-interval event policy, not a hidden-notification buffer. Sample pause stops the full tree and rejects new actions. Projects requesting actions at global rate zero or while invisible must define their own zero-time catch-up policy.

Clocks come from native sequence positions. Godot unwraps cycles using actual advance delta/rate and checks native position; UE reads SequencePlayer DeltaTimeRecord. Differences over 2 ms produce clock_mismatch and cancel. End reasons include completed, interrupted, cancelled, overridden, reset, weight_zero, callback_cancelled, and clock_mismatch.

## Integration and Validation Limits

New projects use motion_playback.py create. Existing generated projects must explicitly update owned components/templates before stage → native prepare → activate. Asset staging alone does not update code. Complex graphs, Montages, parallel updates, and networking need specific integration.

Sample controls: WASD move, Shift run, Space jump, E upper body, F full body, Q cancel, R reset, P pause. F's grounded requirement is a sample rule. full_tuck reuses jump solely to demonstrate leg-mask effects, not finished jumping gameplay.

Validate masks, weights, loop markers, and interruption cleanup. Root-motion/contact composition requires explicit update order and separate checks.

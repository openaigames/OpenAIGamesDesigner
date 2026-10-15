# Navigation and Basic NPCs

[English](NAVIGATION.md) | [简体中文](NAVIGATION.zh-CN.md)

Optional components query native navigation meshes and output desired world-space ground velocity. Project collision movers apply velocity; project behavior decides when to patrol, chase, search, or return. No animation plugin, AIController, behavior tree, or shared hostility rules are imposed.

## Creation and Integration

```powershell
python tools/runtime_components.py create --engine godot --scenario navigation --project C:/Trials/NavigationGodot
python tools/runtime_components.py create --engine unreal --scenario navigation --project C:/Trials/NavigationUE --ue-root D:/UE_5.8
```

Godot opens `project.godot` and bakes navigation from static graybox collision at startup. For UE, compile `OAGDExamplesEditor`, run `create_map.py` in the new project, and open `/Game/Example`. The map contains static collision and navigation bounds; Recast generates navigation at runtime. Creation never overwrites existing maps. After geometry changes, rebake/update with native engine tools; the component does not replace map authoring tools.

WASD moves the yellow target; the blue NPC patrols and chases when distance and visibility conditions hold. Space starts/retries patrol; Esc pauses. Buttons reset the NPC, toggle a physical blocker, or exit. These are project debugging controls, not a fully validated controller menu. Tests use native software input, not physical devices or manual playtests.

`navigation-profile.json` resides in the Godot root or UE `Content/OAGDData/`. It defines speed, arrival distance, blocked/overall timeout, repath interval, detection range, lost-target/search times, and patrol points. JSON lengths use meters and points `[x,y,z]` with Y-up. The UE example maps `(x,z,y)*100` for its shared configuration only; this is not a universal project coordinate conversion.

## Component Contract

| Purpose | Godot | UE 5.8 |
| --- | --- | --- |
| Type | `OAGDNavigation` Node3D | `UOAGDNavigationComponent` |
| Configure | `configure(speed, arrival, blocked, deadline, repath)` | `Configure(SpeedCm, ArrivalCm, BlockedSeconds, MaxSeconds, RepathSeconds)` |
| Request | `request(id,mover,destination,target,foot_offset,target_offset)` | `Request(Id,Mover,Destination,Target,FootOffset,TargetOffset)` |
| Update | `step(delta)` | `Step(Delta)` |
| Cancel / pause / unload | `cancel(reason)`, `set_suspended(value)`, `clear()` | `Cancel`, `SetSuspended`, `Clear` |
| Readback | `desired_velocity`, `path`, `goal`, `state`, `reason`, `last_error`, `busy()` | `DesiredVelocity`, `Path`, `Goal`, `State`, `Reason`, `LastError`, `Busy()` |
| Events | `lifecycle(request_id,state,reason)` | `Lifecycle` delegate, same fields |

Godot uses meters; UE uses centimeters. Offsets follow world axes: example center-to-foot offsets are `(0,-0.9,0)` and `(0,0,-90)`. A target object supplies its position plus target_offset; otherwise destination is fixed. Mover/target references are weak. Godot uses the component World3D's default navigation map; UE uses default supported-agent navigation data, without selecting multiple agent types or filters.

Configure before requesting. Active requests and callbacks prohibit reconfiguration/new requests. Limits: speed `(0,20]` m/s, arrival radius `(0,2]` m, blocked timeout `(0,60]` s, overall timeout `(0,600]` s, repath interval `[0.1,5]` s. Match arrival radius to collision size. The sample chase stops at 1 m so two 0.35 m radius capsules do not remain jammed short of arrival.

Requests project start feet and goal onto native navigation, allowing at most 0.5 m horizontal and 0.6 m vertical displacement; otherwise they return outside_navigation. Godot checks that the path endpoint matches the projected goal; UE also rejects IsPartial. Rejection returns false and LastError without started. ReadyMap indicates data/map existence, **not a generated or reachable route**; check the request result.

Accepted requests requery native navigation at the configured interval. Actual mover positions determine progress: less than 3 cm accumulated movement over the blocked interval produces blocked; the overall limit produces timeout. Intermediate waypoint tolerance is 20 cm; arrival uses the configured radius and 60 cm vertical tolerance, rechecking a complete path before completion. Output velocity is horizontal; the ground mover handles slopes.

Each instance permits one request. The last 256 accepted IDs are deduplicated. Each emits started and one arrived/failed/cancelled; Clear resets room history. Acceptance does not mean arrival. Failures include lost targets/movers, invalid navigation, disconnected target regions, blockage, and timeout. Cancel, pause, Clear, and scene exit zero desired velocity; resume does not revive requests.

Projects must call Step, feed the mover, and clear cached input/inertia after termination. Godot sets OAGDActor.move_wish; UE uses CharacterMovement and clears input/velocity on stop. Components do not teleport or implement acceleration, aerial movement, root motion, or turn animation. Periodic queries detect updated meshes but do not automatically turn blockers into navigation obstacles. The dynamic blocker case checks collision-driven failure, not universal dynamic avoidance.

Callbacks reject nested requests/reconfiguration and permit Cancel/Clear. Clear before unloading; tree exit/EndPlay also cleans up. Do not continue consuming a request's old path from callbacks.

## Project Behavior Example

Godot uses `npc_behavior.gd`; UE uses BehaviorTick/ChangeBehavior/BehaviorMove in `ExampleGame.cpp`. States are patrol, chase, search, return, blocked, and stopped; the entire behavior can be replaced.

- patrol requests moves between project waypoints.
- Distance and native ray visibility trigger chase of a weak target reference.
- Sustained target loss starts a timed search, then return; reaching spawn resumes patrol. Target destruction immediately enters return.
- Failed requests stop in blocked until an explicit retry, without endless resubmission. Pause cancels movement; resume creates a new request according to behavior state.

detectable is a sample switch for testing target loss; normal operation still uses real distance and occlusion. No quest, damage, faction, or inventory system is included. Projects may compose feedback and interaction through events; neither is a required behavior dependency.

## Validation and Scope

Run `runtime_validation.py --engine godot|unreal --project ... --executable ... --visual`. Godot imports first; UE requires compilation/map creation. Fresh reports are `.openaigame/runtime-validation/<id>/navigation.json`. Scope is Windows, one ground NPC, and complete routes on static baked or engine-generated navigation. Cases cover real movement around walls, isolated platforms, moving targets becoming unreachable, physical blockers, pause/cancel, destroyed targets/movers, timeouts, callback cleanup, and behavior transitions. They do not cover full combat AI, crowd avoidance, automatic dynamic rebaking, smart jump links, flying, moving platforms, open-world streaming, networking, or complex slope/height connections.

Implementation uses UE NavigationSystem/NavigationPath and ActorFactory volume APIs. Godot references: [NavigationRegion3D](https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html) and [NavigationServer3D](https://docs.godotengine.org/en/stable/classes/class_navigationserver3d.html).

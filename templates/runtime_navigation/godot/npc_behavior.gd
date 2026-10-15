extends RefCounted
## Project-owned example rules. Replace this without replacing the navigator/motor.
var state := "stopped"
var home := Vector3.ZERO
var patrol: Array[Vector3] = []
var index := 0
var detection := 6.0
var loss_seconds := 0.6
var search_seconds := 0.5
var transitions: Array[String] = []
var _clock := 0.0
var _serial := 0
var config: Dictionary
var _nav: Node3D
var _actor: CharacterBody3D
var _target: WeakRef
var offset := Vector3(0,-0.9,0)

func setup(nav: Node3D, actor: CharacterBody3D, target: Node3D, profile: Dictionary) -> void:
	config = profile
	_nav = nav; _actor = actor; _target = weakref(target); home = actor.global_position+offset
	detection = profile.detection_m; loss_seconds = profile.loss_seconds; search_seconds = profile.search_seconds
	patrol.clear()
	for p in profile.patrol_points: patrol.append(Vector3(p[0],p[1],p[2]))
func change(value: String) -> void:
	if state == value: return
	_nav.cancel("behavior_changed"); state = value; _clock = 0; transitions.append(value)
func start() -> void: index = 0; change("patrol")
func stop() -> void: change("stopped"); _nav.cancel("behavior_stopped")
func _move(to: Vector3, target: Node3D = null) -> void:
	_nav.configure(config.speed_mps,1.0 if target != null else config.arrival_m,config.blocked_seconds,config.deadline_seconds,config.repath_seconds)
	_serial += 1
	if not _nav.request("npc-"+str(_serial), _actor, to, target, offset, offset): change("blocked")
func _visible(target: Node3D) -> bool:
	if not is_instance_valid(target) or target.get_meta("detectable",true) == false: return false
	var a := _actor.global_position
	if a.distance_to(target.global_position) > detection: return false
	var query := PhysicsRayQueryParameters3D.create(a,target.global_position,1,[_actor.get_rid()])
	var hit := _actor.get_world_3d().direct_space_state.intersect_ray(query)
	return hit.is_empty() or hit.collider == target
func tick(delta: float) -> void:
	if _nav.suspended or state == "stopped" or state == "blocked": return
	var target = _target.get_ref() if _target else null
	var seen := _visible(target)
	if seen and state != "chase": change("chase")
	if state == "chase":
		_clock = 0 if seen else _clock+delta
		if not is_instance_valid(target): change("return")
		elif _clock >= loss_seconds: change("search")
		elif not _nav.busy():
			if _nav.state == "failed": change("blocked")
			elif Vector2(_actor.position.x-target.position.x,_actor.position.z-target.position.z).length() > 1.15: _move(target.global_position+offset,target)
	elif state == "search":
		_clock += delta
		if _clock >= search_seconds: change("return")
	elif state == "return" or state == "patrol":
		if _nav.busy(): return
		if _nav.state == "failed": change("blocked"); return
		if state == "return":
			if Vector2(_actor.global_position.x-home.x,_actor.global_position.z-home.z).length() <= .4: change("patrol")
			else: _move(home)
		else:
			var at := _actor.global_position+offset
			if Vector2(at.x-patrol[index].x,at.z-patrol[index].z).length() <= .4: index = (index+1)%patrol.size()
			_move(patrol[index])

class_name OAGDNavigation
extends Node3D
## Ground navigation only. The project applies desired_velocity through its motor.
signal lifecycle(request_id: String, state: String, reason: String)
var speed := 3.0
var arrival := 0.35
var blocked_seconds := 1.0
var max_seconds := 20.0
var repath_seconds := 0.5
var desired_velocity := Vector3.ZERO
var state := "idle"
var reason := ""
var last_error := ""
var path := PackedVector3Array()
var goal := Vector3.ZERO
var suspended := false
var _id := ""
var _seen: Array[String] = []
var _mover: WeakRef
var _target: WeakRef
var _tracking := false
var _offset := Vector3.ZERO
var _target_offset := Vector3.ZERO
var _index := 0
var _elapsed := 0.0
var _stalled := 0.0
var _repath := 0.0
var _anchor := Vector3.ZERO
var _notifying := false

func configure(new_speed: float, radius: float, blocked: float, deadline: float, repath: float = 0.5) -> bool:
	if busy() or _notifying: return false
	for v in [new_speed, radius, blocked, deadline, repath]:
		if not is_finite(v) or v <= 0.0: return false
	if new_speed > 20.0 or radius > 2.0 or blocked > 60.0 or deadline > 600.0 or repath < 0.1 or repath > 5.0: return false
	speed = new_speed; arrival = radius; blocked_seconds = blocked; max_seconds = deadline; repath_seconds = repath
	return true

func busy() -> bool: return not _id.is_empty()
func ready_map() -> bool:
	if not is_inside_tree(): return false
	var map := get_world_3d().navigation_map
	return map.is_valid() and NavigationServer3D.map_get_iteration_id(map) > 0 and not NavigationServer3D.map_get_regions(map).is_empty()
func _horizontal(v: Vector3) -> Vector3: return Vector3(v.x, 0, v.z)
func _near(a: Vector3, b: Vector3, radius: float) -> bool:
	return _horizontal(a-b).length() <= radius and absf(a.y-b.y) <= 0.6
func _resolve(ref: WeakRef) -> Node3D:
	var node = ref.get_ref() if ref else null
	return node if is_instance_valid(node) and node is Node3D and node.is_inside_tree() else null
func _plan(at: Vector3) -> bool:
	path.clear(); _index = 0
	if not ready_map(): last_error = "navigation_unavailable"; return false
	var map := get_world_3d().navigation_map
	var start := NavigationServer3D.map_get_closest_point(map, at)
	var end := NavigationServer3D.map_get_closest_point(map, goal)
	if not _near(at, start, 0.5) or not _near(goal, end, 0.5): last_error = "outside_navigation"; return false
	path = NavigationServer3D.map_get_path(map, start, end, true)
	if path.is_empty() or not _near(path[-1], end, 0.1): last_error = "unreachable"; path.clear(); return false
	return true

func request(request_id: String, mover: Node3D, destination: Vector3, target: Node3D = null, foot_offset: Vector3 = Vector3.ZERO, target_offset: Vector3 = Vector3.ZERO) -> bool:
	last_error = ""
	if _notifying or busy() or suspended: last_error = "busy_or_suspended"; return false
	if request_id.is_empty() or request_id.length() > 80 or request_id in _seen: last_error = "invalid_or_duplicate_id"; return false
	if not is_instance_valid(mover) or not mover.is_inside_tree() or not destination.is_finite() or not foot_offset.is_finite() or not target_offset.is_finite(): last_error = "invalid_request"; return false
	if target != null and (not is_instance_valid(target) or not target.is_inside_tree()): last_error = "invalid_target"; return false
	goal = target.global_position + target_offset if target != null else destination
	if not goal.is_finite(): last_error = "invalid_goal"; return false
	var at := mover.global_position + foot_offset
	if not at.is_finite() or not _plan(at): return false
	_mover = weakref(mover); _target = weakref(target) if target != null else null; _tracking = target != null
	_offset = foot_offset; _target_offset = target_offset; _anchor = at
	_elapsed = 0; _stalled = 0; _repath = 0; desired_velocity = Vector3.ZERO
	_id = request_id; _seen.append(request_id)
	if _seen.size() > 256: _seen.pop_front()
	state = "moving"; reason = ""; _emit(request_id, "started", "")
	return true

func step(delta: float) -> void:
	desired_velocity = Vector3.ZERO
	if not busy() or suspended or _notifying: return
	if not is_finite(delta) or delta < 0: _finish("failed", "invalid_delta"); return
	var mover := _resolve(_mover)
	if mover == null: _finish("failed", "mover_lost"); return
	var at := mover.global_position + _offset
	if not at.is_finite(): _finish("failed", "invalid_position"); return
	if _tracking:
		var target := _resolve(_target)
		if target == null: _finish("failed", "target_lost"); return
		goal = target.global_position + _target_offset
		if not goal.is_finite(): _finish("failed", "invalid_target"); return
	_elapsed += delta; _repath += delta
	if _elapsed > max_seconds: _finish("failed", "timeout"); return
	if _repath >= repath_seconds:
		_repath = 0
		if not _plan(at): _finish("failed", last_error); return
	if _near(at, goal, arrival):
		if not _plan(at): _finish("failed", last_error)
		else: _finish("arrived", "")
		return
	if _horizontal(at-_anchor).length() >= 0.03: _anchor = at; _stalled = 0
	else: _stalled += delta
	if _stalled >= blocked_seconds: _finish("failed", "blocked"); return
	while _index < path.size() and _near(at, path[_index], 0.2): _index += 1
	if _index >= path.size(): return # Await bounded replan; never steer outside the last checked path.
	var diff := _horizontal(path[_index]-at)
	desired_velocity = diff.normalized() * minf(speed, diff.length()/maxf(delta, 0.001))

func _emit(id: String, event: String, why: String) -> void:
	var previous := _notifying; _notifying = true
	lifecycle.emit(id, event, why)
	_notifying = previous
func _finish(result: String, why: String) -> void:
	if not busy(): return
	var id := _id; _id = ""; state = result; reason = why
	desired_velocity = Vector3.ZERO; path.clear(); _mover = null; _target = null
	_emit(id, result, why)
func cancel(why: String = "cancelled") -> void: _finish("cancelled", why)
func set_suspended(value: bool) -> void:
	suspended = value
	if value: cancel("suspended")
func clear() -> void:
	cancel("cleared"); _seen.clear(); path.clear(); desired_velocity = Vector3.ZERO; state = "idle"; reason = ""
func _exit_tree() -> void: clear()

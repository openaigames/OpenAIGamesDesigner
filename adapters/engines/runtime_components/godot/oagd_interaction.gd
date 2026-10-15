class_name OAGDInteraction
extends Node3D
const Target = preload("oagd_interactable.gd")
const Query = preload("oagd_query.gd")
signal lifecycle(request_id: String, target_id: String, state: String, reason: String)
var max_distance := 3.0
var half_angle := 55.0
var prompt := ""
var reason := ""
var allowed := false
var progress := 0.0
var last_error := ""
var suspended := false
var _targets: Dictionary = {}
var _focus: WeakRef
var _pending: WeakRef
var _actor: WeakRef
var _origin := Vector3.ZERO
var _direction := Vector3.FORWARD
var _has_view := false
var _request := ""
var _target_id := ""
var _elapsed := 0.0
var _duration := 0.0
var _seen: Dictionary = {}
var _notifying := false
var _committing := false

func configure(distance: float, angle: float) -> bool:
	if _notifying or _committing or holding(): return false
	if not is_finite(distance) or distance <= 0 or distance > 100 or not is_finite(angle) or angle <= 0 or angle > 89: return false
	max_distance = distance; half_angle = angle
	return true

func register_target(target: Node3D) -> bool:
	if _notifying or _committing or not target is Target or not _valid_spec(target): return false
	var existing = _targets.get(target.stable_id)
	if existing != null and is_instance_valid(existing.get_ref()): return existing.get_ref() == target
	if _targets.size() >= 128: return false
	_targets[target.stable_id] = weakref(target)
	return true

func unregister_target(id: String) -> void:
	_targets.erase(id)
	if _target_id == id: cancel("unregistered")
	if focused_id() == id: _set_focus(null)

func focused_id() -> String:
	var target = _resolve(_focus)
	return target.stable_id if target != null else ""

func holding() -> bool:
	return not _request.is_empty()

func _resolve(ref: WeakRef):
	return ref.get_ref() if ref != null and is_instance_valid(ref.get_ref()) else null

func _valid_spec(target) -> bool:
	return not target.stable_id.is_empty() and target.stable_id.length() <= 80 and not target.prompt.is_empty() and target.prompt.length() <= 160 and is_finite(target.hold_seconds) and target.hold_seconds >= 0 and target.hold_seconds <= 10 and target.anchor().is_finite()

func _visible(target, actor: Node3D) -> bool:
	var exclude: Array[RID] = []
	if actor is CollisionObject3D: exclude.append(actor.get_rid())
	var offset: Vector3 = target.anchor() - _origin
	var hit := Query.ray(get_world_3d(), _origin, offset, offset.length() + .01, exclude)
	return hit.is_empty() or hit.collider == target or target.is_ancestor_of(hit.collider)

func _set_focus(target) -> void:
	_focus = weakref(target) if target != null else null
	prompt = target.prompt if target != null else ""; reason = ""; allowed = false
	if target != null:
		var offer: Dictionary = target.offer(_resolve(_actor)); allowed = offer.allowed; reason = offer.reason

func _refresh() -> void:
	var actor = _resolve(_actor)
	if suspended or not _has_view or actor == null: _set_focus(null); return
	var best = null
	var best_angle := INF; var best_distance := INF; var best_id := ""
	for id in _targets.keys():
		var target = _resolve(_targets[id])
		if target == null: _targets.erase(id); continue
		if not _valid_spec(target) or target.stable_id != id or not target.enabled: continue
		var offset: Vector3 = target.anchor() - _origin
		var distance := offset.length()
		if distance > max_distance: continue
		var alignment := _direction.dot(offset.normalized()) if distance > .001 else 1.0
		if alignment < cos(deg_to_rad(half_angle)) or not _visible(target, actor): continue
		var angle := 1.0 - alignment
		if angle < best_angle - .00001 or (absf(angle-best_angle) <= .00001 and (distance < best_distance - .001 or (absf(distance-best_distance) <= .001 and str(id) < best_id))):
			best = target; best_angle = angle; best_distance = distance; best_id = id
	_set_focus(best)

func update_query(actor: Node3D, origin: Vector3, direction: Vector3, delta: float) -> void:
	if _committing or _notifying: return
	if not is_instance_valid(actor) or not origin.is_finite() or not direction.is_finite() or direction.length_squared() < .0001 or not is_finite(delta) or delta < 0:
		_has_view = false; cancel("invalid query"); _set_focus(null); return
	if holding() and _resolve(_actor) != actor: cancel("requester changed")
	_actor = weakref(actor); _origin = origin; _direction = direction.normalized(); _has_view = true
	_refresh()
	if not holding(): return
	if _resolve(_pending) == null: cancel("target ended"); return
	if _resolve(_focus) != _resolve(_pending): cancel("focus lost"); return
	if not allowed: cancel(reason); return
	_elapsed += delta; progress = clampf(_elapsed / maxf(_duration, .00001), 0, 1)
	if _elapsed >= _duration: _finish()

func begin(request_id: String) -> bool:
	last_error = ""
	if _notifying or _committing: return _reject("defer begin until callback returns")
	if suspended or holding(): return _reject("paused or busy")
	if request_id.is_empty() or request_id.length() > 120 or _seen.has(request_id): return _reject("invalid or duplicate request")
	_refresh()
	var target = _resolve(_focus)
	if target == null or not allowed: return _reject(reason if target != null else "no target")
	_request = request_id; _target_id = target.stable_id; _pending = weakref(target); _elapsed = 0; progress = 0; _duration = target.hold_seconds
	_seen[request_id] = true
	if _seen.size() > 256: _seen.erase(_seen.keys()[0])
	_emit(request_id, _target_id, "started", "")
	if holding() and _duration == 0: _finish()
	return true

func _reject(value: String) -> bool:
	last_error = value
	return false

func _finish() -> void:
	_refresh()
	var target = _resolve(_pending); var actor = _resolve(_actor)
	if target == null or actor == null or target != _resolve(_focus) or not allowed: cancel("condition changed before commit"); return
	var request := _request; var id := _target_id
	_request = ""; _target_id = ""; _pending = null; progress = 0
	_committing = true
	var success: bool = target.execute(actor)
	_committing = false
	_emit(request, id, "completed" if success else "failed", "" if success else "project commit rejected")
	_refresh()

func cancel(value := "released") -> bool:
	if not holding(): return false
	var request := _request; var id := _target_id
	_request = ""; _target_id = ""; _pending = null; progress = 0
	_emit(request, id, "cancelled", value)
	return true

func set_suspended(value: bool) -> void:
	suspended = value
	if value: cancel("paused"); _set_focus(null)

func clear() -> void:
	_targets.clear(); _has_view = false; _set_focus(null); cancel("scene ended"); _seen.clear()

func _emit(request: String, id: String, state: String, detail: String) -> void:
	var previous := _notifying; _notifying = true
	lifecycle.emit(request, id, state, detail)
	_notifying = previous

func _exit_tree() -> void:
	clear()

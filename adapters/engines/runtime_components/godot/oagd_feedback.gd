class_name OAGDFeedback
extends Node3D
## One native player per handle; rules and asset bindings belong to the game.
signal lifecycle(handle: int, event_id: String, cue: String, state: String)
var cues: Dictionary = {}
var active: Dictionary = {}
var camera_offset := Vector3.ZERO # degrees, absolute additive contribution
var game_paused := false
var max_active := 8
var last_error := ""
var _emitting := false
var _next := 0
var _seen: Dictionary = {}
var _wall_usec := 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = -10
	_wall_usec = Time.get_ticks_usec()

func configure(config: Dictionary, audio: Dictionary, visuals: Dictionary) -> String:
	if _emitting: return "defer play/configure until lifecycle callback returns"
	if not active.is_empty(): return "cannot reconfigure active feedback"
	if config.get("schema") != 1 or not config.get("cues") is Dictionary: return "invalid feedback schema"
	if not _number(config.get("max_active"), 1, 32) or config.max_active != floor(config.max_active): return "invalid global budget"
	if config.cues.is_empty() or config.cues.size() > 128: return "invalid cue count"
	var candidate := {}
	for id in config.cues:
		var value = config.cues[id]
		if not id is String or id.is_empty() or id.length() > 80 or not value is Dictionary: return "invalid cue id"
		if not value.get("domain") in ["game", "ui"] or not value.get("overflow") in ["reject", "oldest"]: return "invalid cue policy: " + id
		if not value.get("loop") is bool or not value.get("spatial") is bool: return "invalid cue flags: " + id
		if not _number(value.get("duration"), .02, 60) or not _number(value.get("volume"), 0, 1) or not _number(value.get("camera"), 0, 3): return "invalid cue range: " + id
		if not _number(value.get("limit"), 1, 16) or value.limit != floor(value.limit): return "invalid cue budget: " + id
		if not value.get("color") is Array or value.color.size() != 3: return "invalid tint: " + id
		for channel in value.color:
			if not _number(channel, 0, 1): return "invalid tint channel: " + id
		if not value.get("audio") is String or not value.get("visual") is String: return "invalid bindings: " + id
		var sound = audio.get(value.audio)
		var scene = visuals.get(value.visual)
		if value.audio != "" and not sound is AudioStream: return "missing audio: " + id
		if value.visual != "" and not scene is PackedScene: return "missing visual: " + id
		if scene != null:
			var probe = scene.instantiate()
			var valid: bool = probe is Node3D and probe.has_method("sample")
			probe.free()
			if not valid: return "visual needs Node3D.sample(age, strength, color): " + id
		if sound is AudioStreamWAV and (sound.loop_mode != AudioStreamWAV.LOOP_DISABLED) != value.loop: return "audio loop binding mismatch: " + id
		if value.loop and value.domain == "ui": return "UI loops are not supported"
		candidate[id] = value.duplicate(true)
		candidate[id]["sound"] = sound; candidate[id]["scene"] = scene
	cues = candidate; max_active = int(config.max_active); _seen.clear()
	return ""

func _number(value, low: float, high: float) -> bool:
	return (value is int or value is float) and is_finite(value) and value >= low and value <= high

func play(cue: String, event_id: String, owner: Node3D = null, position := Vector3.ZERO, follow := false, scope := "scene", intensity := 1.0) -> int:
	last_error = ""
	if _emitting: return _reject("defer play/configure until lifecycle callback returns")
	if not cues.has(cue) or event_id.is_empty() or event_id.length() > 120 or scope.is_empty() or not position.is_finite() or not _number(intensity, 0, 2): return _reject("invalid feedback request")
	var spec: Dictionary = cues[cue]
	if game_paused and spec.domain == "game": return _reject("game feedback paused")
	if (follow or spec.loop) and not is_instance_valid(owner): return _reject("follow/loop requires live owner")
	if _seen.has(event_id): return _reject("duplicate event")
	var same: Array = []
	for handle in active:
		if active[handle].cue == cue: same.append(handle)
	var replace := -1
	if same.size() >= int(spec.limit):
		if spec.overflow == "reject": return _reject("cue concurrency limit")
		replace = int(same[0])
	if active.size() >= max_active and replace == -1: return _reject("global concurrency limit")
	var visual: Node3D
	if spec.scene != null: visual = spec.scene.instantiate()
	if replace != -1: stop(replace, "replaced")
	if (follow or spec.loop) and not is_instance_valid(owner):
		if visual != null: visual.free()
		return _reject("owner ended during replacement")
	_next += 1
	var container := Node3D.new(); container.name = "Feedback" + str(_next); add_child(container)
	container.global_position = owner.global_position + position if follow else position
	if visual != null: container.add_child(visual); visual.sample(0.0, intensity, Color(spec.color[0], spec.color[1], spec.color[2]))
	var player = null
	if spec.sound != null:
		player = AudioStreamPlayer3D.new() if spec.spatial else AudioStreamPlayer.new()
		player.stream = spec.sound; player.volume_db = linear_to_db(maxf(.00001, float(spec.volume) * intensity))
		if spec.spatial: player.max_distance = 25.0; player.unit_size = 4.0
		container.add_child(player); player.play()
	active[_next] = {"cue": cue, "event": event_id, "scope": scope, "owner": weakref(owner) if is_instance_valid(owner) else null, "follow": follow, "offset": position, "age": 0.0, "strength": intensity, "node": container, "visual": visual, "audio": player}
	_seen[event_id] = true
	if _seen.size() > 256: _seen.erase(_seen.keys()[0])
	_emit(_next, event_id, cue, "started")
	return _next

func _emit(handle: int, event_id: String, cue: String, state: String) -> void:
	var previous := _emitting; _emitting = true
	lifecycle.emit(handle, event_id, cue, state)
	_emitting = previous

func _reject(reason: String) -> int:
	last_error = reason
	return -1

func stop(handle: int, reason := "stopped") -> bool:
	if not active.has(handle): return false
	var item: Dictionary = active[handle]
	active.erase(handle)
	if is_instance_valid(item.audio): item.audio.stop()
	item.node.visible = false; item.node.queue_free()
	_emit(handle, item.event, item.cue, reason)
	_recompute_camera()
	return true

func stop_scope(scope: String) -> void:
	for handle in active.keys():
		if active.has(handle) and active[handle].scope == scope: stop(handle, "scope-ended")

func clear() -> void:
	for handle in active.keys(): stop(handle, "cleared")
	_seen.clear(); camera_offset = Vector3.ZERO

func set_game_paused(value: bool) -> void:
	game_paused = value
	for item in active.values():
		if is_instance_valid(item.audio): item.audio.stream_paused = value and cues[item.cue].domain == "game"

func _process(delta: float) -> void:
	var now := Time.get_ticks_usec()
	var wall := float(now - _wall_usec) / 1000000.0; _wall_usec = now
	for handle in active.keys():
		if not active.has(handle): continue
		var item: Dictionary = active[handle]
		var spec: Dictionary = cues[item.cue]
		if item.owner != null and not is_instance_valid(item.owner.get_ref()): stop(handle, "owner-ended"); continue
		if item.follow: item.node.global_position = item.owner.get_ref().global_position + item.offset
		if game_paused and spec.domain == "game": continue
		item.age += wall if spec.domain == "ui" else delta
		if not spec.loop and item.age >= spec.duration: stop(handle, "finished"); continue
		if is_instance_valid(item.visual): item.visual.sample(item.age, item.strength, Color(spec.color[0], spec.color[1], spec.color[2]))
	_recompute_camera()

func _recompute_camera() -> void:
	var angle := 0.0
	for item in active.values():
		var spec: Dictionary = cues[item.cue]
		var envelope := 1.0 if spec.loop else maxf(0, 1.0 - item.age / spec.duration)
		angle += sin(item.age * 35.0) * spec.camera * item.strength * envelope
	camera_offset = Vector3(clampf(angle, -3, 3), 0, clampf(angle * .5, -1.5, 1.5))

func _exit_tree() -> void:
	clear()

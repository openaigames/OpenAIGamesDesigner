class_name OAGDPlayback
extends Node
## Optional AnimationTree adapter. The project owns its graph, rules and movement.
signal marker(action: StringName, run: int, name: StringName)
signal ended(action: StringName, run: int, reason: StringName)

var tree: AnimationTree
var playback: AnimationNodeStateMachinePlayback
var bindings: Dictionary
var current: StringName = &""
var generation := 0
var position_s := 0.0
var rate := 1.0
var finished := false
var fired: Dictionary = {}
var _valid := false
var _changing := false
var locomotion_enabled := false
var move_weight := 0.0
var run_weight := 0.0
var cycle_hz := 0.0
var walk_speed := 1.0
var run_speed := 2.5
var walk_duration := 1.0
var run_duration := 0.6
var layers
var base_graph: AnimationNodeStateMachine
var base_parameters := "parameters/"
var root_enabled := false

func configure_locomotion(speeds: Dictionary) -> bool:
	if not _valid or not base_graph.has_node("locomotion"): return false
	var walk := float(speeds.get("walk", 0)); var sprint := float(speeds.get("run", 0))
	if not is_finite(walk) or not is_finite(sprint) or walk <= 0 or sprint <= walk: return false
	for key in ["idle", "walk", "run"]:
		if not bindings.has(key) or not bindings[key].get("loop", false) or not bindings[key].get("markers", []).is_empty(): return false
	walk_speed = walk; run_speed = sprint
	walk_duration = float(bindings.walk.duration_s); run_duration = float(bindings.run.duration_s)
	bindings["locomotion"] = {"duration_s":walk_duration,"loop":true,"markers":[]}
	locomotion_enabled = true
	return set_locomotion_speed(0.0)

func set_locomotion_speed(speed_mps: float) -> bool:
	if not locomotion_enabled or not is_finite(speed_mps) or speed_mps < 0 or speed_mps > 20: return false
	move_weight = clampf(speed_mps / walk_speed, 0, 1)
	run_weight = clampf((speed_mps - walk_speed) / (run_speed - walk_speed), 0, 1)
	var stride := lerpf(walk_speed * walk_duration, run_speed * run_duration, run_weight)
	cycle_hz = speed_mps / maxf(move_weight * stride, 0.000001)
	tree.set(base_parameters + "locomotion/move/blend_amount", move_weight)
	tree.set(base_parameters + "locomotion/gait/blend_amount", run_weight)
	tree.set(base_parameters + "locomotion/walk_rate/scale", cycle_hz * walk_duration)
	tree.set(base_parameters + "locomotion/run_rate/scale", cycle_hz * run_duration)
	return true

func locomotion_times() -> Dictionary:
	# Actual child sequence time, not an independently integrated phase estimate.
	return {"walk":float(tree.get(base_parameters + "locomotion/walk/current_position")), "run":float(tree.get(base_parameters + "locomotion/run/current_position"))} if locomotion_enabled else {}

func configure(animation_tree: AnimationTree, definitions: Dictionary, layer_policy: Dictionary = {}, root_policy: Dictionary = {}) -> bool:
	if definitions.is_empty() or not is_instance_valid(animation_tree):
		return false
	# Resource nodes must be local to each character instance, including bank assets.
	animation_tree.tree_root = animation_tree.tree_root.duplicate(true)
	var graph: AnimationNodeStateMachine
	if layer_policy.is_empty(): graph = animation_tree.tree_root as AnimationNodeStateMachine
	elif animation_tree.tree_root is AnimationNodeBlendTree:
		graph = animation_tree.tree_root.get_node("base") as AnimationNodeStateMachine
		base_parameters = "parameters/base/"
	if graph == null: return false
	if not layer_policy.is_empty() and not preload("res://addons/oagd_playback/oagd_layers.gd").valid_contract(animation_tree, definitions, layer_policy): return false
	root_enabled = not root_policy.is_empty()
	if root_enabled and (root_policy != {"mode":"planar_v1","vertical":"physics","rotation":"controller","transition_s":0.0} or not layer_policy.is_empty() or animation_tree.root_motion_track.is_empty()): return false
	if root_enabled:
		if graph.has_node("locomotion"): return false
		for index in range(graph.get_transition_count()):
			if graph.get_transition(index).xfade_time != 0: return false
	for key in definitions:
		var row: Dictionary = definitions[key]
		if not is_finite(float(row.get("duration_s", 0))) or float(row.get("duration_s", 0)) <= 0: return false
		var rooted: bool = row.get("motion_owner") == "animation"
		if not graph.has_node(key): return false
		if rooted:
			if not root_enabled or row.get("in_place", true) or row.get("loop", true) or row.get("layer_only", false): return false
			if not graph.get_node(key) is AnimationNodeAnimation: return false
		elif row.get("motion_owner") != "controller" or not row.get("in_place", false): return false
		var names := {}
		if row.get("layer_only", false):
			if layer_policy.is_empty() or not layer_policy.clips.has(key): return false
			continue
		for event in row.get("markers", []):
			if event.get("name", "").is_empty() or names.has(event.name) or not is_finite(float(event.at_s)) or event.at_s <= 0 or event.at_s >= float(row.duration_s):
				return false
			names[event.name] = true
		if row.get("loop", false) and not names.is_empty(): return false
	tree = animation_tree
	base_graph = graph
	bindings = definitions.duplicate(true)
	playback = tree.get(base_parameters + "playback")
	if not layer_policy.is_empty(): layers = preload("res://addons/oagd_playback/oagd_layers.gd").new(tree, bindings, layer_policy)
	_valid = true
	return true

func select(action: StringName) -> bool:
	if _changing or not _valid or not bindings.has(action) or bindings[action].get("layer_only", false): return false
	if current == action: return true
	_changing = true
	if current != &"" and not finished: ended.emit(current, generation, &"interrupted")
	generation += 1
	current = action
	position_s = 0.0
	fired.clear()
	finished = false
	if root_enabled: playback.start(action, true)
	elif playback.is_playing(): playback.travel(action)
	else: playback.start(action)
	_changing = false
	return true

func set_rate(value: float) -> bool:
	if not is_finite(value) or value < 0 or value > 4: return false
	rate = value
	return true

func advance(delta: float) -> void:
	if not _valid or current == &"" or not is_finite(delta) or delta < 0: return
	# AnimationTree performs real sequence evaluation and transitions; never seek.
	if layers != null: layers.before_advance(delta * rate)
	var advance_s := delta * rate
	if root_enabled and bindings[current].get("motion_owner") == "animation":
		advance_s = minf(advance_s, maxf(0.0, float(bindings[current].duration_s) - position_s))
	tree.advance(advance_s)
	if layers != null: layers.after_advance(delta * rate)
	if playback.get_current_node() != current: return
	position_s = playback.get_current_play_position()
	if finished or bindings[current].get("loop", false): return
	var token := generation
	var action := current
	for event in bindings[action].get("markers", []):
		if position_s + 0.000001 >= float(event.at_s) and not fired.has(event.name):
			fired[event.name] = true
			marker.emit(action, token, event.name)
			# A consumer can cancel or replace the action from inside a callback.
			if token != generation: return
	if position_s >= float(bindings[action].duration_s) - 0.0001:
		finished = true
		ended.emit(action, token, &"completed")

func reset(action: StringName) -> void:
	if _changing or not _valid or not bindings.has(action) or bindings[action].get("layer_only", false): return
	_changing = true
	if layers != null: layers.reset()
	if current != &"" and not finished: ended.emit(current, generation, &"reset")
	generation += 1
	current = action
	position_s = 0.0
	fired.clear()
	finished = false
	playback.start(action, true)
	tree.advance(0.0)
	_changing = false

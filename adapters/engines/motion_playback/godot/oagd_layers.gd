class_name OAGDLayers
extends RefCounted
## Two optional native pose layers. This class never writes Skeleton3D transforms.
signal event(data: Dictionary)
var tree: AnimationTree
var clips: Dictionary
var settings: Dictionary
var channels := {}
var changing := false
var rejection := ""
var faults: Array = []

static func valid_contract(animation_tree: AnimationTree, definitions: Dictionary, policy: Dictionary) -> bool:
	if policy.get("mode") != "upper_full_v1" or policy.get("event_policy") != "current_visible": return false
	for key in ["fade_in_s", "fade_out_s", "replace_s"]:
		var value := float(policy.get(key, 0))
		if not is_finite(value) or value < .04 or value > 1: return false
	if not policy.get("clips", []) is Array: return false
	var ids: Array = policy.get("clips", [])
	if ids.is_empty() or not animation_tree.tree_root is AnimationNodeBlendTree: return false
	var seen := {}
	for id in ids:
		if seen.has(id) or not definitions.has(id) or definitions[id].get("layer_only") != true: return false
		seen[id] = true
		var row: Dictionary = definitions[id]; var duration := float(row.get("duration_s", 0)); var previous := -1.0; var names := {}
		if not is_finite(duration) or duration <= 0 or not row.get("loop") is bool: return false
		for mark in row.get("markers", []):
			var at := float(mark.get("at_s", -1)); var name := str(mark.get("name", ""))
			if name.is_empty() or names.has(name) or not is_finite(at) or at < 0 or at < previous or at > duration or (row.loop and at >= duration): return false
			previous = at; names[name] = true
	for channel in ["upper", "full"]:
		for suffix in ["0", "1", "0_rate", "1_rate", "0_seek", "1_seek", "banks", "weight"]:
			if not animation_tree.tree_root.has_node(channel + ("_" if suffix in ["banks", "weight"] else "") + suffix): return false
	return true

func _init(animation_tree: AnimationTree, definitions: Dictionary, policy: Dictionary) -> void:
	tree = animation_tree; clips = definitions; settings = policy
	for name in ["upper", "full"]:
		channels[name] = {"action":"", "run":0, "active":false, "bank":0, "mix":0.0, "weight":0.0, "target":0.0, "rate":1.0, "priority":0, "position_s":0.0, "total_s":0.0, "first":true, "bank_rates":[0.0,0.0]}

func play(channel: String, action: String, priority := 0, weight := 1.0, speed := 1.0, restart := true) -> bool:
	rejection = ""
	if changing: rejection = "reentrant_request"; return false
	if not channels.has(channel) or not settings.clips.has(action): rejection = "invalid_binding"; return false
	if not is_finite(weight) or weight <= .001 or weight > 1 or not is_finite(speed) or speed < 0 or speed > 4: rejection = "invalid_parameter"; return false
	var c: Dictionary = channels[channel]
	if channel == "upper" and (channels.full.active or channels.full.weight > .000001): rejection = "full_override"; return false
	if c.active and priority < c.priority: rejection = "priority"; return false
	if c.active and c.action == action and not restart: return true
	if c.weight > .000001 and absf(c.mix - float(c.bank)) > .000001: rejection = "transition_busy"; return false
	changing = true
	if channel == "full": _end("upper", "overridden")
	_end(channel, "interrupted")
	c.run += 1; c.bank = 1 - int(c.bank); c.action = action; c.active = true; c.target = weight; c.rate = speed; c.priority = priority
	c.position_s = 0.0; c.total_s = 0.0; c.first = true; c.bank_rates[c.bank] = speed
	if c.weight <= .000001: c.mix = float(c.bank)
	var name := channel + str(c.bank)
	(tree.tree_root.get_node(name) as AnimationNodeAnimation).animation = action
	# A request resets only its newly selected bank, never the base locomotion tree.
	tree.set("parameters/" + name + "_seek/seek_request", 0.0)
	changing = false
	return true

func _emit(channel: String, kind: String, name: String, cycle: int, at: float) -> void:
	var c: Dictionary = channels[channel]
	event.emit({"channel":channel,"action":c.action,"run":c.run,"kind":kind,"name":name,"cycle":cycle,"at_s":at,"position_s":c.position_s,"total_s":c.total_s,"weight":c.weight})

func _end(channel: String, reason: String) -> void:
	var c: Dictionary = channels[channel]
	if not c.active: return
	c.active = false; c.target = 0.0
	_emit(channel, "ended", reason, int(floor(c.total_s / float(clips[c.action].duration_s))), c.position_s)

func cancel(channel: String, reason := "cancelled") -> bool:
	if changing or not channels.has(channel): return false
	changing = true; _end(channel, reason); changing = false
	return true

func set_weight(channel: String, value: float) -> bool:
	if changing or not channels.has(channel) or not is_finite(value) or value < 0 or value > 1: return false
	if value <= .001: return cancel(channel, "weight_zero")
	if not channels[channel].active: return false
	channels[channel].target = value; return true

func set_rate(channel: String, value: float) -> bool:
	if changing or not channels.has(channel) or not is_finite(value) or value < 0 or value > 4: return false
	var c: Dictionary = channels[channel]
	c.rate = value; c.bank_rates[c.bank] = value; return true

func reset() -> void:
	if changing: return
	changing = true
	for name in channels:
		_end(name, "reset")
		var c: Dictionary = channels[name]
		c.run += 1; c.action = ""; c.weight = 0.0; c.target = 0.0; c.position_s = 0.0; c.total_s = 0.0; c.bank_rates = [0.0,0.0]
		tree.set("parameters/" + name + "_weight/blend_amount", 0.0)
	changing = false

func before_advance(delta: float) -> void:
	for name in channels:
		var c: Dictionary = channels[name]
		var fade: float = settings.fade_in_s if c.target > c.weight else settings.fade_out_s
		c.weight = move_toward(c.weight, c.target, delta / fade)
		c.mix = move_toward(c.mix, float(c.bank), delta / float(settings.replace_s))
		tree.set("parameters/" + name + "_weight/blend_amount", c.weight)
		tree.set("parameters/" + name + "_banks/blend_amount", c.mix)
		for bank in [0,1]: tree.set("parameters/" + name + str(bank) + "_rate/scale", c.bank_rates[bank])

func after_advance(delta: float) -> void:
	for name in channels:
		var c: Dictionary = channels[name]
		if not c.active: continue
		var row: Dictionary = clips[c.action]
		var duration: float = row.duration_s
		var position := float(tree.get("parameters/" + name + str(c.bank) + "/current_position"))
		var previous: float = -.000002 if c.first else c.total_s
		var total: float = position if c.first else c.total_s + delta * c.rate
		if not row.loop: total = minf(total, duration)
		var expected: float = fposmod(total, duration) if row.loop else total
		var error := absf(position - expected)
		if row.loop: error = minf(error, absf(error - duration))
		# Unwrapping is accepted only when it agrees with the actual native player.
		if error > .002:
			faults.append({"channel":name,"run":c.run,"native":position,"expected":expected})
			cancel(name, "clock_mismatch"); continue
		c.position_s = position; c.total_s = total; c.first = false
		var token: int = c.run
		var first_cycle := maxi(0, int(floor(maxf(previous, 0) / duration)))
		var last_cycle := int(floor((total + .000001) / duration)) if row.loop else 0
		for cycle in range(first_cycle, last_cycle + 1):
			for mark in row.get("markers", []):
				var at: float = float(mark.at_s) + cycle * duration
				if at > previous + .000001 and at <= total + .000001 and c.weight > .001:
					_emit(name, "marker", mark.name, cycle, mark.at_s)
					if not c.active or token != c.run: break
			if not c.active or token != c.run: break
		if c.active and token == c.run and not row.loop and total >= duration - .00001: _end(name, "completed")

func snapshot() -> Dictionary:
	return channels.duplicate(true)

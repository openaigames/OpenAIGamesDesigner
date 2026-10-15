class_name OAGDInput
extends Node
## Optional local input router. Project consumers must use strength()/action_changed,
## not global Input polling, which ignores GUI event consumption and this context.
signal action_changed(action: String, value: float)
signal capture_finished(ok: bool, detail: String)
signal pause_changed(paused: bool)

var profile: Dictionary = {}
var defaults: Dictionary = {}
var context := "game"
var selected_pad := -1
var _raw: Dictionary = {}
var _modifier_sources: Dictionary = {}
var _blocked: Dictionary = {}
var _values: Dictionary = {}
var _pauses: Dictionary = {}
var _capture := ""
var _slot := 0
const SPECIAL := {"Space": KEY_SPACE, "Escape": KEY_ESCAPE, "Enter": KEY_ENTER,
	"Tab": KEY_TAB, "Backspace": KEY_BACKSPACE, "Up": KEY_UP, "Down": KEY_DOWN,
	"Left": KEY_LEFT, "Right": KEY_RIGHT, "Shift": KEY_SHIFT, "Ctrl": KEY_CTRL, "Alt": KEY_ALT}
const MODIFIERS := ["Shift", "Ctrl", "Alt"]
const WHEEL := {MOUSE_BUTTON_WHEEL_UP: "MouseWheelUp", MOUSE_BUTTON_WHEEL_DOWN: "MouseWheelDown"}
const PAD := {JOY_BUTTON_A: "PadSouth", JOY_BUTTON_B: "PadEast", JOY_BUTTON_X: "PadWest",
	JOY_BUTTON_Y: "PadNorth", JOY_BUTTON_START: "PadStart", JOY_BUTTON_BACK: "PadBack",
	JOY_BUTTON_LEFT_SHOULDER: "PadL1", JOY_BUTTON_RIGHT_SHOULDER: "PadR1",
	JOY_BUTTON_DPAD_UP: "PadUp", JOY_BUTTON_DPAD_DOWN: "PadDown",
	JOY_BUTTON_DPAD_LEFT: "PadLeft", JOY_BUTTON_DPAD_RIGHT: "PadRight"}

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	Input.joy_connection_changed.connect(_connection)

static func supported(key: String) -> bool:
	return (key.length() == 1 and ((key >= "A" and key <= "Z") or (key >= "0" and key <= "9"))) or SPECIAL.has(key) or key in PAD.values() or key in WHEEL.values() or key in ["MouseLeft", "MouseRight", "MouseMiddle", "PadLeftX+", "PadLeftX-", "PadLeftY+", "PadLeftY-"]

static func validate(data: Variant) -> String:
	if not data is Dictionary or data.get("schema") != "oagd.input/1" or not data.get("id") is String or data.id.is_empty(): return "Invalid input profile identity"
	if not data.get("deadzone") is float and not data.get("deadzone") is int: return "Missing deadzone"
	if not is_finite(float(data.deadzone)) or data.deadzone < 0.05 or data.deadzone > 0.8: return "Deadzone must be 0.05..0.8"
	if not data.get("actions") is Dictionary or data.actions.is_empty() or data.actions.size() > 128: return "Invalid actions"
	var used: Dictionary = {}
	for id in data.actions:
		var row: Variant = data.actions[id]
		if not id is String or id.is_empty() or not row is Dictionary: return "Invalid action"
		if row.get("context") not in ["game", "ui", "global"] or not row.get("rebindable") is bool: return "Invalid action context or rebindable flag"
		if not row.get("keys") is Array or row.keys.is_empty() or row.keys.size() > 8: return "Invalid key list"
		for key in row.keys:
			if not key is String or not supported(key): return "Unsupported key: " + str(key)
			for entry in used.get(key, []):
				if entry.context == row.context or entry.context == "global" or row.context == "global": return "Binding conflict: " + key + " (" + entry.id + ", " + id + ")"
			if not used.has(key): used[key] = []
			used[key].append({"id": id, "context": row.context})
	return ""

func configure(data: Dictionary) -> String:
	var error := validate(data)
	if not error.is_empty(): return error
	cancel_capture()
	flush()
	profile = data.duplicate(true)
	defaults = data.duplicate(true)
	_values.clear()
	return ""

func strength(id: String) -> float:
	return float(_values.get(id, 0.0))

func paused() -> bool:
	return not _pauses.is_empty()

func set_pause(reason: String, active: bool) -> void:
	if reason.is_empty(): return
	var before := paused()
	if active: _pauses[reason] = true
	else: _pauses.erase(reason)
	if before != paused():
		barrier()
		pause_changed.emit(paused())

func set_context(value: String) -> bool:
	if value not in ["game", "ui"]: return false
	if context != value:
		context = value
		cancel_capture()
		barrier()
	return true

func barrier() -> void:
	for key in _raw:
		if float(_raw[key]) > 0.0: _blocked[key] = true
	_publish()

func flush() -> void:
	_raw.clear()
	_modifier_sources.clear()
	_blocked.clear()
	_publish()

func focus_lost() -> void:
	cancel_capture()
	flush()

func disconnect_pad(device: int) -> void:
	if device != selected_pad: return
	for key in _raw.keys():
		if str(key).begins_with("Pad"): _raw.erase(key)
	for key in _blocked.keys():
		if str(key).begins_with("Pad"): _blocked.erase(key)
	selected_pad = -1
	cancel_capture()
	_publish()

func _connection(device: int, connected: bool) -> void:
	if not connected: disconnect_pad(device)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT: focus_lost()

func _input(event: InputEvent) -> void:
	if handle_event(event): get_viewport().set_input_as_handled()

func handle_event(event: InputEvent) -> bool:
	if profile.is_empty(): return false
	if event is InputEventJoypadButton or event is InputEventJoypadMotion:
		if selected_pad < 0: selected_pad = event.device
		if selected_pad != event.device: return false
	if event is InputEventJoypadMotion:
		if event.axis not in [JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y]: return false
		var base := "PadLeftX" if event.axis == JOY_AXIS_LEFT_X else "PadLeftY"
		feed(base + "+", maxf(event.axis_value, 0.0))
		feed(base + "-", maxf(-event.axis_value, 0.0))
		return true
	var key := ""
	if event is InputEventKey:
		if event.echo: return true
		var code: int = event.physical_keycode if event.physical_keycode else event.keycode
		key = OS.get_keycode_string(code)
		for token in SPECIAL:
			if SPECIAL[token] == code: key = token
		if key in MODIFIERS:
			var source := key + ":" + str(event.location)
			if event.pressed: _modifier_sources[source] = key
			else: _modifier_sources.erase(source)
			return feed(key, 1.0 if key in _modifier_sources.values() else 0.0)
	elif event is InputEventJoypadButton:
		key = PAD.get(event.button_index, "")
	elif event is InputEventMouseButton:
		if WHEEL.has(event.button_index):
			var capturing_wheel := not _capture.is_empty()
			var handled_wheel := feed(WHEEL[event.button_index], 1.0 if event.pressed else 0.0)
			return handled_wheel and (context != "ui" or capturing_wheel)
		key = {MOUSE_BUTTON_LEFT: "MouseLeft", MOUSE_BUTTON_RIGHT: "MouseRight", MOUSE_BUTTON_MIDDLE: "MouseMiddle"}.get(event.button_index, "")
	if not supported(key): return false
	# Mouse clicks over UI must reach native Controls; still retain release state.
	var capturing := not _capture.is_empty()
	var handled := feed(key, 1.0 if event.is_pressed() else 0.0)
	return handled and not (context == "ui" and event is InputEventMouseButton and not capturing)

func feed(key: String, value: float) -> bool:
	if profile.is_empty() or not supported(key) or not is_finite(value): return false
	if key in WHEEL.values():
		# Discrete input is delivered synchronously, including its release. Native
		# platforms may omit a wheel release or send several steps in one frame.
		var handled := _feed_state(key, 1.0 if value > 0.0 else 0.0)
		if value > 0.0: _feed_state(key, 0.0)
		return handled
	return _feed_state(key, value)

func _feed_state(key: String, value: float) -> bool:
	var amount := clampf(value, 0.0, 1.0)
	if key.ends_with("+") or key.ends_with("-"):
		amount = maxf(0.0, (amount - float(profile.deadzone)) / (1.0 - float(profile.deadzone)))
	_raw[key] = amount
	if amount == 0.0: _blocked.erase(key)
	if not _capture.is_empty():
		if amount >= 0.5 and not _blocked.has(key):
			if key == "Escape": cancel_capture()
			else:
				var action := _capture
				_capture = ""
				var error := rebind(action, _slot, key)
				_blocked[key] = true
				_publish()
				capture_finished.emit(error.is_empty(), key if error.is_empty() else error)
		return true
	_publish()
	for row in profile.actions.values():
		if key in row.keys and row.context in [context, "global"]: return true
	return false

func _publish() -> void:
	var changes: Array = []
	for id in profile.get("actions", {}):
		var row: Dictionary = profile.actions[id]
		var value := 0.0
		if _capture.is_empty() and (row.context == "global" or (row.context == context and (row.context != "game" or not paused()))):
			for key in row.keys:
				if not _blocked.has(key): value = maxf(value, float(_raw.get(key, 0.0)))
		if not is_equal_approx(value, strength(id)): changes.append([id, value])
		_values[id] = value
	for change in changes:
		# A callback may switch context and invalidate a pending positive event.
		if is_equal_approx(strength(change[0]), change[1]): action_changed.emit(change[0], change[1])

func rebind(id: String, slot: int, key: String) -> String:
	if not profile.get("actions", {}).has(id): return "Unknown action"
	var row: Dictionary = profile.actions[id]
	if not row.rebindable or slot < 0 or slot >= row.keys.size(): return "Action or slot cannot be rebound"
	var candidate := profile.duplicate(true)
	candidate.actions[id].keys[slot] = key
	var error := validate(candidate)
	if not error.is_empty(): return error
	profile = candidate
	barrier()
	return ""

func begin_capture(id: String, slot: int) -> bool:
	if context != "ui" or not profile.actions.has(id): return false
	var row: Dictionary = profile.actions[id]
	if not row.rebindable or slot < 0 or slot >= row.keys.size(): return false
	_capture = id
	_slot = slot
	barrier()
	return true

func cancel_capture() -> void:
	if _capture.is_empty(): return
	_capture = ""
	barrier()
	capture_finished.emit(false, "Capture cancelled")

func restore_defaults() -> void:
	cancel_capture()
	profile = defaults.duplicate(true)
	barrier()

func save_preferences(path: String) -> String:
	if not path.begins_with("user://") or path.ends_with("/"): return "Preferences require a user:// file"
	var output := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if output == null: return "Cannot write preferences"
	output.store_string(JSON.stringify(profile, "  "))
	output.flush()
	var error := output.get_error()
	output.close()
	if error != OK: return "Preferences write failed"
	if DirAccess.rename_absolute(path + ".tmp", path) != OK: return "Cannot replace preferences; previous file retained"
	return ""

func load_preferences(path: String) -> String:
	if not path.begins_with("user://"): return "Preferences require a user:// file"
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	var error := validate(data)
	if not error.is_empty(): return error
	if data.id != defaults.id or data.actions.size() != defaults.actions.size(): return "Profile mismatch"
	for id in defaults.actions:
		if not data.actions.has(id): return "Action mismatch"
		var base: Dictionary = defaults.actions[id]
		var row: Dictionary = data.actions[id]
		if row.context != base.context or row.rebindable != base.rebindable or row.keys.size() != base.keys.size(): return "Action contract mismatch"
		if not base.rebindable and row.keys != base.keys: return "Reserved binding changed"
	cancel_capture()
	profile = data.duplicate(true)
	barrier()
	return ""

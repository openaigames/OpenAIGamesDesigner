class_name OAGDSettings
extends RefCounted

static func defaults() -> Dictionary:
	return {"fps": 60, "vsync": true, "camera_sensitivity": 1.0}

static func validate(value: Dictionary) -> String:
	if value.size() != 3: return "unexpected settings fields"
	if not (value.get("fps") is float or value.get("fps") is int): return "fps must be numeric"
	if value.fps != 30 and value.fps != 60 and value.fps != 120 and value.fps != 0: return "fps must be 0, 30, 60 or 120"
	if not value.get("vsync") is bool: return "vsync must be boolean"
	if not (value.get("camera_sensitivity") is float or value.get("camera_sensitivity") is int): return "invalid camera sensitivity"
	if not is_finite(value.camera_sensitivity) or value.camera_sensitivity < 0.1 or value.camera_sensitivity > 4.0: return "camera sensitivity outside 0.1..4"
	return ""

static func apply(value: Dictionary) -> String:
	var error := validate(value)
	if error != "": return error
	Engine.max_fps = int(value.fps)
	if DisplayServer.get_name() != "headless":
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if value.vsync else DisplayServer.VSYNC_DISABLED)
	# Camera sensitivity is deliberately consumed by the project's camera controller.
	return ""

class_name ActionEventRecorder
extends Node

# Call on the main thread. Real elapsed time includes pause and Engine.time_scale changes.
var is_recording := false
var last_saved_path := ""
@export var output_directory := "user://action-timing"
var _start_usec := 0
var _capture: Dictionary = {}
var _counts: Dictionary = {}
var _token := RegEx.create_from_string("^[A-Za-z0-9_.:/-]{1,120}$")

func start_recording(action: String, revision: String, source: String, input_mode: String, input_description: String) -> Error:
	if is_recording:
		return ERR_ALREADY_IN_USE
	for value in [action, revision, source, input_description]:
		if value.strip_edges().is_empty() or value.length() > 300 or RegEx.create_from_string("[\\x00-\\x1f]").search(value):
			return ERR_INVALID_PARAMETER
	if input_mode not in ["human", "software", "mixed", "unknown"]:
		return ERR_INVALID_PARAMETER
	_capture = {"schema": "action-events/1", "engine": "godot", "engine_version": Engine.get_version_info()["string"],
		"action": action, "revision": revision, "source": source, "input_mode": input_mode, "input_description": input_description,
		"clock": "monotonic_seconds", "zero_s": 0.0, "duration_s": 0.0, "complete": false, "dropped_events": 0, "events": []}
	_counts.clear()
	_start_usec = Time.get_ticks_usec()
	is_recording = true
	last_saved_path = ""
	return OK

func record_event(track: String, event_name: String, uncertainty_seconds: float = 0.0) -> Error:
	if not is_recording:
		return ERR_UNAVAILABLE
	if not _token.search(track) or not _token.search(event_name) or not is_finite(uncertainty_seconds) or uncertainty_seconds < 0:
		return ERR_INVALID_PARAMETER
	if _capture.events.size() >= 10000:
		_capture.dropped_events += 1
		return ERR_OUT_OF_MEMORY
	var key := track + "\n" + event_name
	_counts[key] = _counts.get(key, 0) + 1
	_capture.events.append({"track": track, "id": event_name + "#" + str(_counts[key]),
		"t_s": float(Time.get_ticks_usec() - _start_usec) / 1000000.0, "uncertainty_s": uncertainty_seconds})
	return OK

# Suitable for AnimationPlayer method tracks. AnimationTree transitions should call record_event at their actual decision point.
func record_animation_event(event_name: String) -> void:
	record_event("animation", event_name)

func stop_and_save(complete: bool = true) -> String:
	if not is_recording:
		return last_saved_path
	_capture.duration_s = float(Time.get_ticks_usec() - _start_usec) / 1000000.0
	_capture.complete = complete
	is_recording = false
	var directory := ProjectSettings.globalize_path(output_directory)
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		push_error("Cannot create action timing directory")
		return ""
	var path := directory + "/" + Crypto.new().generate_random_bytes(16).hex_encode() + ".json"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if not file:
		push_error("Cannot save action timing recording")
		return ""
	file.store_string(JSON.stringify(_capture, "  "))
	file.flush()
	if file.get_error() != OK:
		push_error("Action timing write failed")
		return ""
	file.close()
	last_saved_path = ProjectSettings.globalize_path(path)
	print("ACTION_TIMING_SAVED " + last_saved_path)
	return last_saved_path

func _exit_tree() -> void:
	if is_recording:
		stop_and_save(false)

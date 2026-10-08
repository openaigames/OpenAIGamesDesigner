class_name ActionPreviewBridge
extends Node

# Development test scene only. The host owns actual animation/audio/game bindings.
@export var project_root := ""
@export var consumer_id := "animation_lab"
@export var action_ids: PackedStringArray = []
@export var views: Array[Dictionary] = []
@export var frame_rate := 8.0
var host: Node
var viewport: Viewport
var _base := ""
var _instance := ""
var _request := ""
var _client := ""
var _run := ""
var _action := ""
var _sha := ""
var _sequence: Dictionary = {}
var _state := "idle"
var _error := ""
var _paused := false
var _speed := 1.0
var _view := ""
var _frame := 0
var _poll := 0.0
var _capture_due := 0.0
var _capturing := false
var _applied := false
var _recording := false
var _skip_advance := false
var _last_delta := 0.0
var _start_usec := 0
var _capture: Dictionary = {}
var _counts: Dictionary = {}
var _events: Array[Dictionary] = []
var _token := RegEx.create_from_string("^[A-Za-z0-9_-]{1,64}$")

func _ready() -> void:
	set_process(false)
	if project_root.is_empty() or not _token.search(consumer_id) or not is_instance_valid(host):
		push_error("ActionPreviewBridge needs an explicit project root, consumer and test-scene host")
		return
	for method in ["preview_load", "preview_advance", "preview_state", "preview_cancel", "preview_view", "preview_transport"]:
		if not host.has_method(method):
			push_error("Action preview consumer is missing " + method)
			return
	_base = project_root.path_join(".openaigame/action-preview").path_join(consumer_id)
	if DirAccess.make_dir_recursive_absolute(_base) != OK: return
	var previous := _read(_base.path_join("ready.json"))
	if not previous.is_empty() and OS.is_process_running(int(previous.get("pid", 0))) and absf(Time.get_unix_time_from_system() - float(previous.get("updated_at", 0))) < 4.0:
		push_error("Another action preview scene already owns this consumer")
		return
	_instance = Crypto.new().generate_random_bytes(16).hex_encode()
	if not is_instance_valid(viewport): viewport = get_viewport()
	if not views.is_empty():
		_view = views[0].id
		host.preview_view(_view)
	_ready_packet()
	set_process(true)

func _read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if not file or file.get_length() > 8 * 1024 * 1024: return {}
	var result: Variant = JSON.parse_string(file.get_as_text())
	return result if result is Dictionary else {}

func _write(path: String, value: Dictionary) -> void:
	var temporary := path + "." + _instance + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if not file: return
	file.store_string(JSON.stringify(value,"",true,true))
	file.close()
	DirAccess.rename_absolute(temporary, path)

func _ready_packet() -> void:
	_write(_base.path_join("ready.json"), {"schema":"action-preview/1", "instance":_instance,
		"engine":"godot", "engine_version":Engine.get_version_info().string, "actions":action_ids, "pid":OS.get_process_id(), "updated_at":Time.get_unix_time_from_system(),
		"views":views, "controls":["replay","pause","resume","step","view","speed","stop"]})

func _process(delta: float) -> void:
	_last_delta = delta
	_poll += delta
	_capture_due += delta
	if _poll >= 0.1:
		_poll = 0.0
		_ready_packet()
		var request := _read(_base.path_join("request.json"))
		if request.get("instance") == _instance and request.get("request", "") != _request:
			_consume(request)
		if not _client.is_empty():
			var pulse := _read(_base.path_join("client.json"))
			var expired: bool = pulse.get("released", false) or pulse.get("instance") != _instance or pulse.get("client") != _client or Time.get_unix_time_from_system() - FileAccess.get_modified_time(_base.path_join("client.json")) > 7.0
			if expired:
				_stop("disconnected")
				_client = ""
		_publish()
	if _state == "playing" and not _paused:
		if _skip_advance: _skip_advance = false
		else:
			host.preview_advance(delta * _speed)
			_check_complete()
	if _applied and _capture_due >= 1.0 / maxf(1.0, frame_rate) and not _capturing:
		_capture_due = 0.0
		_send_frame()

func _consume(command: Dictionary) -> void:
	_request = str(command.get("request", ""))
	if not _token.search(_request) or not _token.search(str(command.get("run", ""))) or command.get("action") not in action_ids:
		return
	if absf(Time.get_unix_time_from_system() - float(command.get("issued_at", 0))) > 7.0:
		return
	var operation: String = command.get("operation", "")
	if operation == "replay":
		_stop("idle")
		_client = command.client
		_run = command.run
		_action = command.action
		_sha = command.sequence_sha256
		_frame = 0
		_error = ""
		var path := _base.path_join("runs").path_join(_run).path_join("sequence.json")
		_sequence = _read(path)
		if FileAccess.get_sha256(path) != _sha or _sequence.get("id") != _action:
			_fail("预览配置读取失败或版本不符")
			return
		_start_recording()
		var result: Dictionary = host.preview_load(_sequence.duplicate(true))
		if not result.get("ok", false) or result.get("sequence") != _sequence:
			_fail(str(result.get("error", "消费者没有确认实际读取的配置")))
			return
		_applied = true
		_paused = false
		_state = "playing"
		_skip_advance = true
		host.preview_transport(false, _speed)
	elif command.run != _run or command.client != _client:
		return
	elif operation == "pause":
		_paused = true
		_state = "paused" if _state == "playing" else _state
		host.preview_transport(true, _speed)
	elif operation == "resume" and _state == "paused":
		_paused = false
		_state = "playing"
		_skip_advance = true
		host.preview_transport(false, _speed)
	elif operation == "step" and _state in ["playing", "paused"]:
		_paused = true
		_state = "paused"
		host.preview_transport(true, _speed)
		host.preview_advance(1.0 / 30.0)
		_check_complete()
	elif operation == "view":
		for view in views:
			if view.id == command.get("view"):
				if host.preview_view(view.id): _view = view.id
	elif operation == "speed":
		_speed = clampf(float(command.get("speed", 1.0)), 0.1, 2.0)
		host.preview_transport(_paused, _speed)
	elif operation == "stop":
		_stop("stopped")
	if _recording and operation != "replay":
		_capture.preview_controls.append({"operation":operation,"view":_view,"speed":_speed,"t_s":float(Time.get_ticks_usec()-_start_usec)/1000000.0})
	_publish()

func _check_complete() -> void:
	var actual: Dictionary = host.preview_state()
	if actual.get("complete", false):
		_state = "complete"
		_finish_recording(true)

func _stop(next_state: String) -> void:
	if is_instance_valid(host): host.preview_cancel()
	_finish_recording(false)
	_applied = false
	_paused = false
	_state = next_state

func _fail(message: String) -> void:
	_stop("error")
	_error = message

func _start_recording() -> void:
	_start_usec = Time.get_ticks_usec()
	_counts.clear()
	_events.clear()
	_capture = {"schema":"action-events/1", "engine":"godot", "engine_version":Engine.get_version_info().string,
		"action":_action, "revision":_sha, "source":consumer_id, "input_mode":"software",
		"input_description":"Native action test scene; inspect preview_controls for pause, speed and camera",
		"clock":"monotonic_seconds", "zero_s":0.0, "duration_s":0.0, "complete":false,
		"dropped_events":0, "events":[], "preview_sequence":_sequence.duplicate(true), "preview_controls":[{"operation":"replay","view":_view,"speed":_speed}]}
	_recording = true

# Call after the actual consumer starts/stops an animation, sound or rule event.
func record_event(track: String, event_name: String) -> void:
	if not _recording: return
	if _capture.events.size() >= 10000:
		_capture.dropped_events += 1
		return
	var key := track + "/" + event_name
	_counts[key] = _counts.get(key, 0) + 1
	var row := {"track":track,"id":event_name+"#"+str(_counts[key]),"t_s":float(Time.get_ticks_usec()-_start_usec)/1000000.0,"uncertainty_s":maxf(_last_delta,1.0/maxf(1.0,Engine.get_frames_per_second()))}
	_capture.events.append(row)
	_events.append(row)
	if _events.size() > 6: _events.pop_front()

func _finish_recording(complete: bool) -> void:
	if not _recording: return
	_recording = false
	_capture.duration_s = float(Time.get_ticks_usec() - _start_usec) / 1000000.0
	_capture.complete = complete
	_capture.input_description = "Native preview controls " + JSON.stringify(_capture.preview_controls).sha256_text()
	_write(_base.path_join("runs").path_join(_run).path_join("capture.json"), _capture)

func _publish() -> void:
	if _base.is_empty() or _instance.is_empty(): return
	var actual: Dictionary = host.preview_state() if is_instance_valid(host) else {}
	_write(_base.path_join("status.json"), {"schema":"action-preview/1","instance":_instance,
		"action":_action,"request":_request,"run":_run,"client":_client,"sequence_sha256":_sha,
		"applied":_applied,"state":_state,"error":_error,"actual":actual,
		"speed":_speed,"view":_view,"frame":_frame,"events":_events,
		"record_ready":_state=="complete", "readback_sequence":_sequence if _applied else {}})

func _send_frame() -> void:
	_capturing = true
	var run := _run
	await RenderingServer.frame_post_draw
	if is_inside_tree() and _applied and run == _run:
		var image := viewport.get_texture().get_image()
		if image and not image.is_empty():
			if image.get_width() > 960: image.resize(960, roundi(image.get_height()*960.0/image.get_width()))
			var next := _frame + 1
			var path := _base.path_join("runs").path_join(run).path_join("frame-"+str(next%2)+".png")
			if image.save_png(path+".tmp") == OK:
				if DirAccess.rename_absolute(path+".tmp", path) == OK: _frame = next
	_capturing = false

func _exit_tree() -> void:
	_stop("offline")
	_publish()

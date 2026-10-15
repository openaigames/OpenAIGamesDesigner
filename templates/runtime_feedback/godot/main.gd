extends "res://state_base.gd"
const Feedback = preload("res://addons/oagd/oagd_feedback.gd")
var feedback: Node3D
var profile: Dictionary
var sounds: Dictionary = {}
var effects: Dictionary = {}
var event_serial := 0
var zone_handle := -1
var zone_inside := false
var previous_camera := Vector3.ZERO
var peak_camera := 0.0
var callback_test := false
var callback_rejected := false
var transitions: Array = []
var recording: AudioEffectRecord

func _ready() -> void:
	super._ready()
	feedback = Feedback.new(); add_child(feedback)
	profile = JSON.parse_string(FileAccess.get_file_as_string("res://feedback-profile.json"))
	for id in ["door", "ui", "action", "zone"]:
		var sound = load("res://audio/" + id + ".wav")
		if sound == null: push_error("Missing imported audio " + id); get_tree().quit(2); return
		sound = sound.duplicate()
		if id == "zone": sound.loop_mode = AudioStreamWAV.LOOP_FORWARD; sound.loop_end = roundi(sound.get_length() * sound.mix_rate)
		sounds[id] = sound
	effects.pulse = preload("res://pulse.tscn")
	var error: String = feedback.configure(profile, sounds, effects)
	if error != "": push_error(error); get_tree().quit(2); return
	feedback.set_game_paused(router.paused())
	router.pause_changed.connect(feedback.set_game_paused)
	feedback.lifecycle.connect(func(handle: int, event: String, cue: String, value: String):
		transitions.append({"t_usec": Time.get_ticks_usec(), "handle": handle, "event": event, "cue": cue, "state": value})
		if callback_test and value == "scope-ended":
			callback_test = false
			callback_rejected = feedback.play("ui", "nested") == -1 and feedback.configure(profile, sounds, effects) != ""
			feedback.clear())
	buttons[5].text = "Action feedback (attached to player)"
	buttons[6].text = "Enter / leave feedback zone"

func choose(index: int) -> void:
	if feedback == null: super.choose(index); return
	if index == 1:
		if menu.visible: close_menu()
		super.choose(index)
		feedback.play("door", event("door"), null, scenes.current.get_node("Door").global_position, false, "scene")
	elif index == 5:
		if menu.visible: close_menu()
		feedback.play("action", event("action"), actor, Vector3(0, -.7, 0), true, "scene")
	elif index == 6:
		if menu.visible: close_menu()
		actor.reset_motor(Vector3(0 if zone_inside else 5, 1, 0))
	else:
		super.choose(index)
		if index != 10: feedback.play("ui", event("ui"), null, Vector3.ZERO, false, "ui")

func event(kind: String) -> String:
	event_serial += 1
	return kind + ":" + str(event_serial)

func transition(value: Dictionary) -> String:
	var result := super.transition(value)
	if result == "" and feedback != null:
		feedback.stop_scope("scene"); zone_inside = false; zone_handle = -1
	return result

func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if feedback == null or router.paused() or busy: return
	var inside := Vector2(actor.position.x - 5, actor.position.z).length() < 1.5
	if inside and not zone_inside:
		zone_handle = feedback.play("zone", event("zone"), scenes.current, Vector3(5, .05, 0), true, "scene")
	elif not inside and zone_inside: feedback.stop(zone_handle, "zone-exit"); zone_handle = -1
	zone_inside = inside

func _process(delta: float) -> void:
	super._process(delta)
	if feedback == null: return
	camera.rotation_degrees += feedback.camera_offset - previous_camera
	previous_camera = feedback.camera_offset
	peak_camera = maxf(peak_camera, previous_camera.length())
	label.text = label.text.replace("State and settings", "Feedback") + "\nActive feedback: %d | Zone: %s | Esc opens examples menu" % [feedback.active.size(), zone_inside]

func wait_seconds(value: float) -> void:
	await get_tree().create_timer(value, true).timeout

func screenshot(suffix: String) -> void:
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report + suffix + ".png")

func run_tests() -> void:
	await wait_seconds(.15)
	recording = AudioEffectRecord.new(); AudioServer.add_bus_effect(0, recording)
	recording.set_recording_active(true)
	check(feedback.cues.size() == 4, "four event families resolve native resources")
	var bad := profile.duplicate(true); bad.cues.door.audio = "missing"
	check(feedback.configure(bad, sounds, effects) != "" and feedback.cues.size() == 4, "bad binding rejected without replacing working profile")
	bad = profile.duplicate(true); bad.cues.zone.loop = false
	check(feedback.configure(bad, sounds, effects) != "", "loop resource mismatch rejected")
	close_menu(); choose(1)
	var handle: int = feedback.active.keys()[0]
	check(state.objects["door-a"] and feedback.active[handle].cue == "door", "committed door state emits mapped feedback")
	await wait_seconds(.12)
	check(feedback.active[handle].audio.playing and feedback.active[handle].visual.is_visible_in_tree(), "real audio player and rendered effect active")
	check(peak_camera > .001, "camera contribution reaches actual camera")
	await screenshot("-peak")
	open_menu()
	var frozen: float = feedback.active[handle].age
	check(feedback.active[handle].audio.stream_paused, "pause suspends native game audio")
	check(feedback.play("action", event("paused"), actor) == -1, "game feedback rejected during pause")
	var ui: int = feedback.play("ui", event("ui"), null, Vector3.ZERO, false, "ui")
	check(ui > 0 and not feedback.active[ui].audio.stream_paused, "UI audio continues while game paused")
	await wait_seconds(.42)
	check(is_equal_approx(feedback.active[handle].age, frozen), "game visual and camera clock frozen during pause")
	check(not feedback.active.has(ui), "UI feedback expires on real-time clock while paused")
	close_menu(); await wait_seconds(.65)
	check(feedback.active.is_empty() and feedback.camera_offset == Vector3.ZERO, "one-shot finishes and camera returns without drift")
	var duplicate := event("duplicate")
	var first: int = feedback.play("door", duplicate)
	check(feedback.play("door", duplicate) == -1 and feedback.active.size() == 1, "same event not played twice")
	var second: int = feedback.play("door", event("door"))
	var third: int = feedback.play("door", event("door"))
	check(not feedback.active.has(first) and feedback.active.has(second) and feedback.active.has(third), "per-cue budget replaces oldest deterministically")
	check(feedback.configure(profile, sounds, effects) != "", "live reconfiguration rejected")
	check(feedback.stop(second) and not feedback.stop(second), "stop handle is idempotent")
	check(feedback.play("door", duplicate) == -1, "event deduplication survives instance completion")
	check(feedback.play("action", event("invalid"), null, Vector3.ZERO, false, "scene", NAN) == -1, "nonfinite strength rejected")
	feedback.clear()
	var limited := profile.duplicate(true); limited.max_active = 1; feedback.configure(limited, sounds, effects)
	feedback.play("door", event("budget"))
	check(feedback.play("action", event("budget")) == -1 and feedback.active.size() == 1, "global budget rejects excess across cues")
	feedback.clear(); feedback.configure(profile, sounds, effects)
	check(feedback.play("zone", event("orphan")) == -1, "loop cannot start without owner")
	var owner := Node3D.new(); add_child(owner)
	var loop: int = feedback.play("zone", event("zone"), owner, Vector3(1, 0, 0), true)
	check(feedback.play("zone", event("zone"), owner) == -1, "loop concurrency rejects repeat owner emission")
	owner.position = Vector3(2, 0, 0); await wait_seconds(.12)
	check(feedback.active[loop].node.global_position.is_equal_approx(Vector3(3, 0, 0)), "visual and 3D audio follow live attachment")
	await wait_seconds(1.15)
	check(feedback.active[loop].audio.playing and feedback.active[loop].age > 1.0, "native loop continues beyond source clip duration")
	var independent: int = feedback.play("action", event("world"), null, Vector3.ZERO)
	owner.queue_free(); await wait_seconds(.1)
	check(not feedback.active.has(loop) and feedback.active.has(independent), "owner destruction stops its loop but preserves independent effect")
	feedback.clear(); choose(6); await wait_seconds(.2)
	check(zone_inside and zone_handle > 0 and feedback.active.has(zone_handle), "actual player position enters zone and starts loop")
	await screenshot("-zone")
	choose(6); await wait_seconds(.12)
	check(not zone_inside and zone_handle == -1 and feedback.active.is_empty(), "leaving zone stops native loop and visual")
	choose(5); await wait_seconds(.12)
	check(feedback.active.size() == 1 and feedback.active.values()[0].cue == "action", "action event uses same independent feedback interface")
	var retained: int = feedback.play("ui", event("global"), null, Vector3.ZERO, false, "ui")
	feedback.stop_scope("scene")
	check(feedback.active.size() == 1 and feedback.active.has(retained), "scene scope cleanup preserves unrelated UI feedback")
	feedback.clear()
	feedback.play("door", event("callback")); feedback.play("action", event("callback"))
	callback_test = true; feedback.stop_scope("scene")
	check(callback_rejected and feedback.active.is_empty(), "callback cleanup is safe and nested play/configure rejected")
	feedback.clear(); choose(6); await wait_seconds(.12); choose(2); await wait_seconds(.12)
	check(state.scene == "b" and feedback.active.values().all(func(item): return item.scope != "scene"), "real scene replacement clears old feedback")
	feedback.clear(); await wait_seconds(.1)
	check(previous_camera.length() < .0001 and feedback.get_child_count() == 0, "clear removes nodes and camera contribution")
	var starts := transitions.filter(func(item): return item.state == "started").size()
	var ends := transitions.size() - starts
	check(starts == ends, "every started instance has a terminal lifecycle record")
	await wait_seconds(.3)
	recording.set_recording_active(false)
	var wave: AudioStreamWAV = recording.get_recording()
	check(wave != null and wave.data.size() > 4096 and wave.save_to_wav(report + ".wav") == OK, "native mixer output captured as playable WAV")
	AudioServer.remove_bus_effect(0, AudioServer.get_bus_effect_count(0) - 1)
	open_menu(); await screenshot("-clear")
	var output := FileAccess.open(report, FileAccess.WRITE)
	output.store_string(JSON.stringify({"engine": Engine.get_version_info().string, "checks": checks, "failures": failures, "events": transitions, "input": "project events and native consumers; no human listening claim", "audio": report + ".wav", "no_animation_plugin": true}, "\t")); output.close()
	get_tree().quit(0 if failures.is_empty() else 1)

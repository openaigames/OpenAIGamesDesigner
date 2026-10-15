extends Node3D
const Router = preload("res://addons/oagd/oagd_input.gd")
const Focus = preload("res://addons/oagd/oagd_focus.gd")
const Motor = preload("res://addons/oagd/oagd_actor.gd")
const Store = preload("res://addons/oagd/oagd_store.gd")
const Settings = preload("res://addons/oagd/oagd_settings.gd")
const Scenes = preload("res://addons/oagd/oagd_scene.gd")
var router: Node
var scenes: Node
var actor: CharacterBody3D
var camera: Camera3D
var store: RefCounted
var focus = Focus.new()
var menu: PanelContainer
var label: Label
var buttons: Array[Button] = []
var selection := 0
var state := {"scene": "a", "checkpoint": "a-entry", "objects": {"door-a": false, "door-b": false}, "player": [0.0, 1.0, 0.0]}
var settings: Dictionary = Settings.defaults()
var pending: Dictionary = {}
var message := ""
var notice := ""
var scene_paths := {"a": "res://room_a.tscn", "b": "res://room_b.tscn"}
var testing := false
var phase := "exercise"
var report := "user://state-validation.json"
var save_root := "user://state"
var checks: Array = []
var failures: Array = []
var busy := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for arg in OS.get_cmdline_user_args():
		if arg == "--self-test": testing = true
		if arg.begins_with("--report="): report = arg.trim_prefix("--report=")
		if arg.begins_with("--state-phase="): phase = arg.trim_prefix("--state-phase=")
		if arg.begins_with("--save-root="): save_root = arg.trim_prefix("--save-root=")
	var profile = JSON.parse_string(FileAccess.get_file_as_string("res://input-profile.json"))
	store = Store.new(save_root, profile.id, 1)
	router = Router.new(); add_child(router)
	if router.configure(profile) != "": get_tree().quit(2); return
	router.action_changed.connect(on_action)
	router.pause_changed.connect(func(value: bool):
		actor.velocity = Vector3.ZERO
		get_tree().paused = value)
	scenes = Scenes.new(); add_child(scenes)
	build_world(); build_ui()
	var saved: Dictionary = store.read_slot("settings")
	if saved.error == "" and Settings.validate(saved.data) == "":
		settings = saved.data
		if saved.recovered: notice = "Settings recovered from previous valid generation"
	elif saved.error != "slot not found": notice = "Saved settings rejected; using defaults"
	Settings.apply(settings)
	message = transition(state)
	open_menu()
	if testing: call_deferred("run_tests")

func build_world() -> void:
	actor = Motor.new(); actor.process_mode = Node.PROCESS_MODE_PAUSABLE
	var collision := CollisionShape3D.new(); collision.shape = CapsuleShape3D.new(); collision.shape.height = 1.8; collision.shape.radius = .35
	actor.add_child(collision)
	var mesh := MeshInstance3D.new(); mesh.mesh = CapsuleMesh.new(); actor.add_child(mesh)
	add_child(actor)
	camera = Camera3D.new(); camera.position = Vector3(10, 10, 12); add_child(camera); camera.look_at(Vector3.ZERO)
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-60, -30, 0); add_child(light)

func build_ui() -> void:
	var canvas := CanvasLayer.new(); add_child(canvas)
	label = Label.new(); label.position = Vector2(20, 16); label.add_theme_font_size_override("font_size", 19); canvas.add_child(label)
	menu = PanelContainer.new(); menu.position = Vector2(320, 155); menu.custom_minimum_size = Vector2(510, 0); canvas.add_child(menu)
	var column := VBoxContainer.new(); column.add_theme_constant_override("separation", 9); menu.add_child(column)
	for text in ["Resume / Start", "Toggle this room's door", "Switch room A / B", "Save slot 1", "Continue from slot 1", "Set checkpoint here", "Respawn at checkpoint", "Settings: cycle FPS / camera sensitivity", "Toggle VSync", "Restore default settings", "Quit"]:
		var button := Button.new(); button.text = text; button.custom_minimum_size.y = 40; column.add_child(button)
		var index := buttons.size(); buttons.append(button)
		button.pressed.connect(func(): choose(index))
		button.focus_entered.connect(func(): selection = index)

func validate(value: Dictionary) -> String:
	if value.size() != 4 or not value.get("scene") in ["a", "b"]: return "unknown scene"
	if not value.get("checkpoint") in [value.scene + "-entry", value.scene + "-door"]: return "checkpoint does not belong to scene"
	if not value.get("objects") is Dictionary or value.objects.size() != 2: return "invalid object set"
	for id in ["door-a", "door-b"]:
		if not value.objects.get(id) is bool: return "missing stable object " + id
	if not value.get("player") is Array or value.player.size() != 3: return "invalid player position"
	for number in value.player:
		if not (number is float or number is int) or not is_finite(number) or abs(number) > 9: return "position outside playable bounds"
	if value.player[1] < 0 or value.player[1] > 5: return "invalid player height"
	return ""

func snapshot() -> Dictionary:
	var value := state.duplicate(true)
	value.player = [actor.position.x, actor.position.y, actor.position.z]
	return value

func transition(value: Dictionary) -> String:
	if busy: return "transition busy"
	var error := validate(value)
	if error != "": return error
	busy = true; router.set_pause("transition", true)
	error = scenes.stage(scene_paths[value.scene])
	if error == "":
		if not scenes.staged.has_method("apply_state"): error = "scene state adapter missing"
		else: error = scenes.staged.apply_state(value.objects)
	if error == "":
		scenes.commit(); state = value.duplicate(true)
		actor.reset_motor(Vector3(value.player[0], value.player[1], value.player[2]))
	else: scenes.cancel()
	busy = false; router.set_pause("transition", false)
	return error

func save_game(slot: String, value: Dictionary) -> String:
	if busy: return "transition busy"
	var error := validate(value)
	return store.write_slot(slot, value) if error == "" else error

func load_game(slot: String) -> String:
	if busy: return "transition busy"
	var result: Dictionary = store.read_slot(slot)
	if result.error != "": return result.error
	var error := transition(result.data)
	if error == "" and result.recovered: notice = "Recovered previous valid generation"
	return error

func apply_settings(value: Dictionary) -> String:
	var error := Settings.validate(value)
	if error != "": return error
	error = store.write_slot("settings", value)
	if error != "": return error
	error = Settings.apply(value)
	if error == "": settings = value.duplicate(true)
	return error

func open_menu() -> void:
	router.set_context("ui"); router.set_pause("menu", true); menu.show(); focus.push(buttons[0])

func close_menu() -> void:
	menu.hide(); focus.pop(); router.set_context("game"); router.set_pause("menu", false)

func choose(index: int) -> void:
	if busy: return
	var error := ""
	if index == 0: close_menu()
	elif index == 1:
		var id: String = "door-" + state.scene
		state.objects[id] = not state.objects[id]; scenes.current.apply_state(state.objects)
	elif index == 2:
		var value := snapshot(); value.scene = "b" if state.scene == "a" else "a"; value.checkpoint = value.scene + "-entry"; value.player = [0, 1, 0]
		error = transition(value)
	elif index == 3: error = save_game("slot1", snapshot())
	elif index == 4: error = load_game("slot1")
	elif index == 5:
		var value := snapshot(); value.checkpoint = value.scene + "-door"
		error = save_game("checkpoint", value)
		if error == "": state.checkpoint = value.checkpoint
	elif index == 6: error = load_game("checkpoint")
	elif index == 7:
		var value := settings.duplicate(); value.fps = 120 if settings.fps == 60 else 60; value.camera_sensitivity = 2.0 if settings.camera_sensitivity == 1 else 1.0
		error = apply_settings(value)
	elif index == 8:
		var value := settings.duplicate(); value.vsync = not settings.vsync; error = apply_settings(value)
	elif index == 9: error = apply_settings(Settings.defaults())
	elif index == 10: get_tree().quit()
	message = "Completed" if error == "" else error

func on_action(id: String, value: float) -> void:
	if value < .5 or busy: return
	if id == "pause":
		if menu.visible: close_menu()
		else: open_menu()
	elif id == "act": choose(1)
	elif id == "ui_up" or id == "ui_down": selection = posmod(selection + (-1 if id == "ui_up" else 1), buttons.size()); buttons[selection].grab_focus()
	elif id == "ui_accept": choose(selection)
	elif id == "ui_back": close_menu()

func _input(event: InputEvent) -> void:
	if router != null and router.handle_event(event): get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and not menu.visible and not busy and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		orbit(event.relative.x)

func orbit(delta: float) -> void:
	camera.rotate_y(-delta * .003 * float(settings.camera_sensitivity))

func _physics_process(_delta: float) -> void:
	actor.move_wish = Vector2(router.strength("right") - router.strength("left"), router.strength("back") - router.strength("forward")).limit_length()

func _process(_delta: float) -> void:
	label.text = "State and settings | Godot | Room %s | %s | Door open: %s\nWASD move | Space toggle door | Esc menu | Hold RMB to look\nFPS %s | VSync %s | Camera %s | %s\n%s" % [state.scene.to_upper(), state.checkpoint, state.objects["door-" + state.scene], settings.fps, settings.vsync, settings.camera_sensitivity, message, notice]

func check(ok: bool, name: String) -> void:
	checks.append(name)
	if not ok: failures.append(name)

func run_tests() -> void:
	await get_tree().process_frame
	if phase == "resume":
		check(settings.fps == 120 and Engine.max_fps == 120, "new process restores actual FPS setting")
		check(settings.camera_sensitivity == 2, "new process restores camera setting")
		check(load_game("slot1") == "", "new process loads persisted slot")
		check(state.scene == "b" and scenes.current.room_id == "b", "new process restores real scene B")
		check(state.objects["door-b"] and not scenes.current.get_node("Door").visible, "new process restores stable door state")
		check(actor.position.is_equal_approx(Vector3(2, 1, 3)), "new process restores pawn position")
		check(state.checkpoint == "b-door", "new process restores checkpoint id")
		check(load_game("checkpoint") == "" and actor.position.is_equal_approx(Vector3(1, 1, 2)), "independent checkpoint survives process restart")
	else:
		check(scenes.current.room_id == "a" and scenes.get_child_count() == 1, "initial native scene A")
		check(Engine.max_fps == 60, "default FPS applied to engine")
		choose(1)
		check(not scenes.current.get_node("Door").visible and scenes.current.get_node("Door").collision_layer == 0, "door state changes visible mesh and physics collision")
		check(save_game("slot1", snapshot()) == "", "validated game snapshot saved")
		var original := FileAccess.get_file_as_bytes(store.path("slot1", 0))
		var bad := snapshot(); bad.objects = {"unknown": true, "door-b": false}
		check(save_game("slot1", bad) != "" and original == FileAccess.get_file_as_bytes(store.path("slot1", 0)), "invalid stable IDs rejected before overwrite")
		actor.position = Vector3(4, 1, 0); choose(1)
		check(load_game("slot1") == "" and state.objects["door-a"] and actor.position.x == 0, "load restores world and player")
		check(load_game("slot1") == "" and scenes.get_child_count() == 1, "repeated load does not duplicate active scene or door")
		choose(2)
		check(state.scene == "b" and scenes.current.room_id == "b", "switch commits distinct scene resource B")
		check(state.objects["door-a"] and scenes.current.get_node("Door").visible, "off-scene stable state retained independently")
		actor.position = Vector3(1, 1, 2); choose(5); actor.position = Vector3(4, 1, 4); choose(1); choose(6)
		check(actor.position.is_equal_approx(Vector3(1, 1, 2)) and not state.objects["door-b"], "checkpoint restores location and object state")
		check(get_tree().paused and router.paused(), "transition preserves menu pause owner")
		var old = scenes.current
		var candidate := snapshot(); candidate.scene = "a"; candidate.checkpoint = "a-entry"
		scene_paths.a = "res://absent.tscn"
		check(transition(candidate) != "" and scenes.current == old and not busy and router.paused(), "failed transition releases its pause and preserves menu/world")
		scene_paths.a = "res://invalid_room.tscn"
		check(transition(candidate) != "" and scenes.current == old and scenes.staged == null, "scene without project adapter rejected before commit")
		scene_paths.a = "res://room_a.tscn"
		check(scenes.stage("res://absent.tscn") != "" and scenes.current == old, "missing scene preserves working scene")
		check(scenes.stage("res://room_a.tscn") == "", "candidate scene prepared separately")
		check(scenes.stage("res://room_b.tscn") != "", "overlapping transition rejected")
		scenes.cancel()
		check(scenes.current == old and scenes.staged == null, "cancel discards candidate and retains current scene")
		var first := snapshot(); store.write_slot("recover", first)
		var second := first.duplicate(true); second.objects["door-b"] = true; store.write_slot("recover", second)
		var f := FileAccess.open(store.path("recover", 1), FileAccess.WRITE); f.store_string("{truncated"); f.close()
		var recovery: Dictionary = store.read_slot("recover")
		check(recovery.error == "" and recovery.recovered and not recovery.data.objects["door-b"], "truncated newest generation recovers earlier valid data")
		check(store.write_slot("recover", first) == "" and not store.read_slot("recover").recovered, "recovery can write a new validated generation")
		store.write_slot("checksum", first); store.write_slot("checksum", second)
		var envelope = JSON.parse_string(FileAccess.get_file_as_string(store.path("checksum", 1)))
		envelope.body += " "
		f = FileAccess.open(store.path("checksum", 1), FileAccess.WRITE); f.store_string(JSON.stringify(envelope)); f.close()
		check(store.read_slot("checksum").recovered and not store.read_slot("checksum").data.objects["door-b"], "checksum mismatch cannot supersede intact generation")
		check(Store.new(save_root, store.project_id, 99).write_slot("future", first) == "" and store.read_slot("future").error != "", "future data version rejected")
		check(Store.new(save_root, "another-project").read_slot("slot1").error != "", "foreign project identity rejected")
		check(store.write_slot("../escape", first) != "", "unsafe slot path rejected")
		store.write_slot("invalid-state", bad)
		check(load_game("invalid-state") != "" and scenes.current == old, "integrity-valid bad project data cannot mutate world")
		f = FileAccess.open(store.path("broken", 0), FileAccess.WRITE); f.store_string("bad"); f.close()
		check(load_game("broken") != "" and scenes.current == old, "wholly corrupt slot leaves current world intact")
		f = FileAccess.open(save_root.path_join("blocked"), FileAccess.WRITE); f.store_string("file blocks directory"); f.close()
		check(Store.new(save_root.path_join("blocked"), store.project_id).write_slot("slot", first) != "", "storage write failure returned")
		var invalid := settings.duplicate(); invalid.camera_sensitivity = 99
		check(apply_settings(invalid) != "" and settings.camera_sensitivity == 1, "invalid settings preserve active values")
		check(apply_settings({"fps": 120, "vsync": false, "camera_sensitivity": 2.0}) == "" and Engine.max_fps == 120, "persisted settings reach engine FPS consumer")
		var before := camera.rotation.y; orbit(10)
		check(is_equal_approx(camera.rotation.y - before, -.06), "sensitivity changes actual camera rotation")
		check(DisplayServer.get_name() == "headless" or DisplayServer.window_get_vsync_mode() == DisplayServer.VSYNC_DISABLED, "requested vsync mode read back (headless not applicable)")
		choose(9)
		check(settings == Settings.defaults() and Engine.max_fps == 60, "restore defaults updates persistent settings and engine")
		apply_settings({"fps": 120, "vsync": false, "camera_sensitivity": 2.0})
		actor.position = Vector3(2, 1, 3); choose(1)
		check(save_game("slot1", snapshot()) == "", "continue snapshot committed for next process")
		close_menu()
		check(not get_tree().paused and router.strength("forward") == 0, "transition lifecycle returns control without held input")
		open_menu()
	await get_tree().process_frame
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report + ".png")
	var out := FileAccess.open(report, FileAccess.WRITE)
	out.store_string(JSON.stringify({"engine": Engine.get_version_info().string, "phase": phase, "checks": checks, "failures": failures, "no_animation_plugin": true, "input": "project API + native consumers; no human/device claim"}, "\t")); out.close()
	get_tree().quit(0 if failures.is_empty() else 1)

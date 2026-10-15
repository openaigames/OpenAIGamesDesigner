extends Node3D
const Router = preload("res://addons/oagd/oagd_input.gd")
const Focus = preload("res://addons/oagd/oagd_focus.gd")
const Motor = preload("res://addons/oagd/oagd_actor.gd")
var router: Node
var actor: CharacterBody3D
var focus = Focus.new()
var menu: PanelContainer
var title: Label
var status: Label
var buttons: Array[Button] = []
var selection := 0
var started := false
var actions := 0
var message := ""
var checks: Array = []
var failures: Array = []
var testing := false
var report := "user://input-validation.json"
var pref := "user://input-preferences.json"

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for arg in OS.get_cmdline_user_args():
		if arg == "--self-test": testing = true
		if arg.begins_with("--report="): report = arg.trim_prefix("--report=")
	if testing: pref = "user://input-test-preferences.json"
	router = Router.new()
	add_child(router)
	var error: String = router.configure(JSON.parse_string(FileAccess.get_file_as_string("res://input-profile.json")))
	if not error.is_empty(): push_error(error); get_tree().quit(2); return
	if not testing and FileAccess.file_exists(pref): message = router.load_preferences(pref)
	router.action_changed.connect(on_action)
	router.pause_changed.connect(func(value: bool): get_tree().paused = value)
	router.capture_finished.connect(on_capture)
	build_world()
	build_ui()
	open_menu()
	if testing: run_tests()

func build_world() -> void:
	var floor_body := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	collision.shape = BoxShape3D.new()
	collision.shape.size = Vector3(30, 1, 30)
	floor_body.position.y = -0.5
	floor_body.add_child(collision)
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	mesh.mesh.size = Vector3(30, 1, 30)
	floor_body.add_child(mesh)
	add_child(floor_body)
	actor = Motor.new()
	actor.process_mode = Node.PROCESS_MODE_PAUSABLE
	actor.position = Vector3(0, 1, 0)
	var shape := CollisionShape3D.new()
	shape.shape = CapsuleShape3D.new()
	shape.shape.height = 1.8
	shape.shape.radius = .35
	actor.add_child(shape)
	var body := MeshInstance3D.new()
	body.mesh = CapsuleMesh.new()
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(.15, .65, .9)
	body.material_override = material
	actor.add_child(body)
	add_child(actor)
	var camera := Camera3D.new()
	camera.position = Vector3(9, 10, 12)
	add_child(camera)
	camera.look_at(Vector3.ZERO)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-60, -30, 0)
	add_child(light)

func build_ui() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)
	status = Label.new()
	status.position = Vector2(24, 20)
	status.add_theme_font_size_override("font_size", 20)
	canvas.add_child(status)
	menu = PanelContainer.new()
	menu.position = Vector2(300, 140)
	menu.custom_minimum_size = Vector2(520, 460)
	canvas.add_child(menu)
	var margin := MarginContainer.new()
	for edge in ["left", "right", "top", "bottom"]: margin.add_theme_constant_override("margin_" + edge, 20)
	menu.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	margin.add_child(column)
	title = Label.new()
	title.add_theme_font_size_override("font_size", 25)
	column.add_child(title)
	for i in 9:
		var button := Button.new()
		button.custom_minimum_size.y = 34
		column.add_child(button)
		buttons.append(button)
		button.pressed.connect(func(): choose(i))
		button.focus_entered.connect(func(): selection = i)
	refresh()

func refresh() -> void:
	title.text = "PAUSED / INPUT SETTINGS" if started else "INPUT & PAUSE EXAMPLE"
	buttons[0].text = "Resume" if started else "Start"
	var names := ["forward", "back", "left", "right", "act"]
	for i in names.size(): buttons[i+1].text = "Rebind " + names[i] + ": " + router.profile.actions[names[i]].keys[0]
	buttons[6].text = "Rebind gamepad action: " + router.profile.actions.act.keys[1]
	buttons[7].text = "Restore defaults"
	buttons[8].text = "Quit"

func _physics_process(_delta: float) -> void:
	actor.move_wish = Vector2(router.strength("right") - router.strength("left"), router.strength("back") - router.strength("forward")).limit_length()

func _process(_delta: float) -> void:
	status.text = "OAGD Input | Godot | Actions: %d\nMove: WASD / left stick | Act: Space / South | Menu: Esc / Start\nMenu: arrows / D-pad, Enter / South | Capture cancel: Esc\n%s" % [actions, message]

func open_menu() -> void:
	router.set_context("ui")
	router.set_pause("menu", true)
	menu.show()
	selection = 0
	focus.push(buttons[0])
	refresh()

func close_menu() -> void:
	started = true
	router.cancel_capture()
	menu.hide()
	focus.pop()
	router.set_context("game")
	router.set_pause("menu", false)

func choose(index: int) -> void:
	if index == 0: close_menu()
	elif index == 7:
		router.restore_defaults()
		message = router.save_preferences(pref)
		refresh()
	elif index == 8: get_tree().quit()
	else:
		var names := ["forward", "back", "left", "right", "act", "act"]
		if router.begin_capture(names[index-1], 1 if index == 6 else 0): message = "Press a new key / button; Esc cancels"

func on_action(id: String, value: float) -> void:
	if value < .5: return
	if id == "pause":
		if menu.visible and started: close_menu()
		elif not menu.visible: open_menu()
	elif id == "act": actions += 1
	elif id == "ui_up" or id == "ui_down":
		selection = posmod(selection + (-1 if id == "ui_up" else 1), buttons.size())
		buttons[selection].grab_focus()
	elif id == "ui_accept": choose(selection)
	elif id == "ui_back" and started: close_menu()

func on_capture(ok: bool, detail: String) -> void:
	message = ("Bound: " if ok else "Not changed: ") + detail
	if ok:
		var error: String = router.save_preferences(pref)
		if not error.is_empty(): message = error
	refresh()

func key(code: int, down: bool) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.pressed = down
	Input.parse_input_event(event)
	Input.flush_buffered_events()

func pad(axis_value: float) -> void:
	var event := InputEventJoypadMotion.new()
	event.device = 7
	event.axis = JOY_AXIS_LEFT_X
	event.axis_value = axis_value
	Input.parse_input_event(event)
	Input.flush_buffered_events()

func frames(count: int) -> void:
	for i in count: await get_tree().process_frame

func check(condition: bool, name: String) -> void:
	checks.append(name)
	if not condition: failures.append(name)

func run_tests() -> void:
	await frames(8)
	check(menu.visible and get_tree().paused and buttons[0].has_focus(), "start menu owns native focus while world paused")
	key(KEY_DOWN, true); key(KEY_DOWN, false)
	check(selection == 1 and buttons[1].has_focus(), "UI navigation works during pause")
	key(KEY_UP, true); key(KEY_UP, false); key(KEY_ENTER, true); key(KEY_ENTER, false)
	await frames(8)
	check(started and not get_tree().paused and not menu.visible, "native input starts game and restores world")
	var before := actor.position
	key(KEY_D, true)
	await frames(25)
	check(actor.position.x > before.x + .3, "native physical-key events move real CharacterBody")
	key(KEY_ESCAPE, true); key(KEY_ESCAPE, false)
	before = actor.position
	await frames(15)
	check(actor.position.distance_to(before) < .001 and router.strength("right") == 0, "pause freezes physics and suppresses held movement")
	key(KEY_ENTER, true); key(KEY_ENTER, false)
	await frames(5)
	check(router.strength("right") == 0, "held key does not leak across resume")
	key(KEY_D, false); key(KEY_D, true)
	check(router.strength("right") == 1, "release and repress re-arms movement")
	key(KEY_D, false)
	var count := actions
	key(KEY_SPACE, true); key(KEY_SPACE, false)
	check(actions == count + 1, "project callback receives game action")
	open_menu()
	key(KEY_SPACE, true); key(KEY_SPACE, false)
	check(actions == count + 1, "menu input cannot trigger gameplay")
	router.set_pause("dialog", true); close_menu()
	check(get_tree().paused, "closing menu preserves another pause owner")
	router.set_pause("dialog", false)
	check(not get_tree().paused, "last pause owner releases world")
	var original: Dictionary = router.profile.duplicate(true)
	check(not router.rebind("act", 0, "W").is_empty() and router.profile == original, "same-context conflict rejected without mutation")
	check(not router.rebind("act", 0, "Escape").is_empty(), "global binding conflict rejected")
	open_menu(); choose(5); key(KEY_F, true); key(KEY_F, false)
	check(router.profile.actions.act.keys[0] == "F" and message.begins_with("Bound"), "native capture updates binding and preferences")
	close_menu(); count = actions
	key(KEY_SPACE, true); key(KEY_SPACE, false); key(KEY_F, true); key(KEY_F, false)
	check(actions == count + 1, "old key stops and new key invokes game action")
	router.restore_defaults()
	check(router.profile.actions.act.keys[0] == "Space", "defaults restored")
	check(router.load_preferences(pref).is_empty() and router.profile.actions.act.keys[0] == "F", "preferences reload into actual consumer")
	open_menu(); choose(5); key(KEY_ESCAPE, true); key(KEY_ESCAPE, false)
	check(menu.visible and router.profile.actions.act.keys[0] == "F", "capture cancellation does not close menu or mutate binding")
	close_menu(); pad(.1)
	check(router.strength("right") == 0, "analog deadzone suppresses drift")
	pad(.6)
	check(absf(router.strength("right") - .5) < .001, "gamepad axis rescaled beyond deadzone")
	router.disconnect_pad(7)
	check(router.strength("right") == 0 and router.selected_pad == -1, "device disconnect releases active axis")
	pad(.8)
	check(router.strength("right") > .7, "reconnected device can produce new input")
	pad(0); key(KEY_W, true); router.focus_lost()
	check(router.strength("forward") == 0, "window focus loss releases active input")
	key(KEY_W, false)
	var bad: Dictionary = router.profile.duplicate(true)
	bad.actions.act.context = "global"
	bad.actions.act.keys[0] = "Escape"
	var f := FileAccess.open("user://invalid-input-test.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(bad)); f.close()
	original = router.profile.duplicate(true)
	check(not router.load_preferences("user://invalid-input-test.json").is_empty() and router.profile == original, "invalid preferences preserve active configuration")
	open_menu()
	focus.push(buttons[5]); focus.pop()
	check(buttons[0].has_focus(), "nested focus scope restores previous live control")
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report + ".png")
	var output := FileAccess.open(report, FileAccess.WRITE)
	output.store_string(JSON.stringify({"engine": Engine.get_version_info(), "checks": checks, "failures": failures, "input": "Input.parse_input_event through native dispatch; disconnect/focus hooks simulated; no physical device or human claim", "no_animation_plugin": true}, "  ")); output.close()
	get_tree().paused = false
	get_tree().quit(0 if failures.is_empty() else 1)

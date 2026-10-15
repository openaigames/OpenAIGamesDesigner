extends Node3D
const Router = preload("res://addons/oagd/oagd_input.gd")
const Focus = preload("res://addons/oagd/oagd_focus.gd")
const Motor = preload("res://addons/oagd/oagd_actor.gd")
const Interaction = preload("res://addons/oagd/oagd_interaction.gd")
const Target = preload("res://addons/oagd/oagd_interactable.gd")
var router: Node
var interaction: Node3D
var actor: CharacterBody3D
var camera: Camera3D
var room: Node3D
var door: Node3D
var pickup: Node3D
var label: Label
var menu: PanelContainer
var buttons: Array[Button] = []
var focus = Focus.new()
var aim := Vector3.FORWARD
var keys := 0
var door_open := false
var commits := 0
var serial := 0
var generation := 0
var fail_commit := false
var callback_mode := ""
var callback_rejected := false
var selection := 0
var testing := false
var report := "user://interaction-validation.json"
var events: Array = []
var checks: Array = []
var failures: Array = []
var profile: Dictionary

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for arg in OS.get_cmdline_user_args():
		if arg == "--self-test": testing = true
		if arg.begins_with("--report="): report = arg.trim_prefix("--report=")
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://interaction-profile.json"))
	if not parsed is Dictionary: get_tree().quit(2); return
	profile = parsed
	for field in ["range_m", "half_angle_degrees", "door_hold_seconds"]:
		if not (profile.get(field) is int or profile.get(field) is float) or not is_finite(profile[field]): get_tree().quit(2); return
	if profile.door_hold_seconds < 0 or profile.door_hold_seconds > 10: get_tree().quit(2); return
	router = Router.new(); add_child(router)
	if router.configure(JSON.parse_string(FileAccess.get_file_as_string("res://input-profile.json"))) != "": get_tree().quit(2); return
	interaction = Interaction.new(); add_child(interaction)
	if profile.get("schema") != 1 or not interaction.configure(profile.get("range_m", -1), profile.get("half_angle_degrees", -1)): get_tree().quit(2); return
	interaction.lifecycle.connect(on_lifecycle)
	actor = Motor.new(); actor.process_mode = Node.PROCESS_MODE_PAUSABLE
	var collision := CollisionShape3D.new(); collision.shape = CapsuleShape3D.new(); actor.add_child(collision)
	var mesh := MeshInstance3D.new(); mesh.mesh = CapsuleMesh.new(); actor.add_child(mesh); add_child(actor)
	camera = Camera3D.new(); camera.position = Vector3(6, 7, 8); add_child(camera); camera.look_at(Vector3(0, 0, -1))
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-55,-30,0); add_child(light)
	build_ui(); reset_room()
	router.action_changed.connect(on_action)
	router.pause_changed.connect(func(value: bool):
		interaction.set_suspended(value); actor.velocity = Vector3.ZERO; get_tree().paused = value)
	open_menu()
	if testing: call_deferred("run_tests")

func box(parent: Node3D, at: Vector3, size: Vector3, color: Color) -> StaticBody3D:
	var body := StaticBody3D.new(); parent.add_child(body); body.position = at
	var collision := CollisionShape3D.new(); collision.shape = BoxShape3D.new(); collision.shape.size = size; body.add_child(collision)
	var mesh := MeshInstance3D.new(); mesh.mesh = BoxMesh.new(); mesh.mesh.size = size
	var material := StandardMaterial3D.new(); material.albedo_color = color; mesh.material_override = material; body.add_child(mesh)
	return body

func prop(id: String, at: Vector3, size: Vector3, color: Color) -> Node3D:
	var target = Target.new(); target.stable_id = id; room.add_child(target); target.position = at
	box(target, Vector3.ZERO, size, color); interaction.register_target(target)
	return target

func reset_room() -> void:
	interaction.clear()
	if is_instance_valid(room): room.free()
	generation += 1; room = Node3D.new(); room.name = "Room" + str(generation); add_child(room)
	box(room, Vector3(0,-.5,0), Vector3(16,1,16), Color(.23,.28,.34))
	keys = 0; door_open = false; fail_commit = false
	door = prop("door", Vector3(0,1,-2.5), Vector3(1.6,2,.18), Color(.7,.35,.1)); door.prompt = "Open door (hold)"; door.hold_seconds = profile.door_hold_seconds
	door.condition = func(_who): return {"allowed": keys > 0 and not door_open, "reason": "Door already open" if door_open else ("Need the blue key" if keys == 0 else "")}
	door.commit = func(_who):
		if fail_commit: return false
		commits += 1; door_open = true; door.rotation.y = PI / 2; door.get_child(0).collision_layer = 0; return true
	pickup = prop("key", Vector3(1.2,1,-1.2), Vector3(.35,.35,.35), Color(.05,.6,1)); pickup.prompt = "Pick up blue key"
	pickup.commit = func(_who):
		keys += 1; commits += 1; pickup.enabled = false; pickup.hide(); pickup.get_child(0).collision_layer = 0; return true
	actor.reset_motor(Vector3(0,1,0)); aim = Vector3.FORWARD

func build_ui() -> void:
	var canvas := CanvasLayer.new(); add_child(canvas)
	label = Label.new(); label.position = Vector2(20,18); label.add_theme_font_size_override("font_size",20); canvas.add_child(label)
	menu = PanelContainer.new(); menu.position = Vector2(330,300); menu.custom_minimum_size.x = 480; canvas.add_child(menu)
	var column := VBoxContainer.new(); column.add_theme_constant_override("separation",12); menu.add_child(column)
	for text in ["Resume / Start", "Face blue key", "Face door", "Reset room", "Quit"]:
		var button := Button.new(); button.text = text; button.custom_minimum_size.y = 48; column.add_child(button)
		var index := buttons.size(); buttons.append(button); button.pressed.connect(func(): choose(index)); button.focus_entered.connect(func(): selection = index)

func choose(index: int) -> void:
	if index == 4: get_tree().quit(); return
	if index == 1: aim = (pickup.global_position - actor.global_position).normalized()
	if index == 2: aim = (door.global_position - actor.global_position).normalized()
	if index == 3: reset_room()
	close_menu()

func open_menu() -> void:
	router.set_context("ui"); router.set_pause("menu",true); menu.show(); focus.push(buttons[0])

func close_menu() -> void:
	menu.hide(); focus.pop(); router.set_context("game"); router.set_pause("menu",false)

func on_action(id: String, value: float) -> void:
	if id == "act":
		if value >= .5: query(); serial += 1; interaction.begin("input-" + str(serial))
		else: interaction.cancel()
	elif value >= .5:
		if id == "pause":
			if menu.visible: close_menu()
			else: open_menu()
		elif id == "ui_up" or id == "ui_down": selection = posmod(selection + (-1 if id == "ui_up" else 1), buttons.size()); buttons[selection].grab_focus()
		elif id == "ui_accept": choose(selection)
		elif id == "ui_back": close_menu()

func _input(event: InputEvent) -> void:
	if router != null and router.handle_event(event): get_viewport().set_input_as_handled()

func _physics_process(delta: float) -> void:
	if actor == null: return
	actor.move_wish = Vector2(router.strength("right")-router.strength("left"),router.strength("back")-router.strength("forward")).limit_length()
	if actor.move_wish.length() > .1: aim = Vector3(actor.move_wish.x,0,actor.move_wish.y).normalized()
	query(delta)

func query(delta := 0.0) -> void:
	interaction.update_query(actor, actor.global_position, aim, delta)

func _process(_delta: float) -> void:
	if label == null: return
	label.text = "Interaction | Godot | Keys %d | Door %s | Room %d\nWASD move / face | Hold Space or gamepad South | Release cancels | Esc menu\n\n%s\n%s\nHold progress: %d%%" % [keys, "open" if door_open else "closed", generation, interaction.prompt if interaction.prompt != "" else "No target in reach", interaction.reason if not interaction.allowed else "Space / South to interact", roundi(interaction.progress*100)]

func on_lifecycle(request: String, id: String, value: String, why: String) -> void:
	events.append({"request":request,"target":id,"state":value,"reason":why,"paused":router.paused()})
	if value == "started" and callback_mode != "":
		var mode := callback_mode; callback_mode = ""
		callback_rejected = not interaction.begin("nested")
		if mode == "clear": interaction.clear()

func check(ok: bool, name: String) -> void:
	checks.append(name)
	if not ok: failures.append(name)

func wait_seconds(seconds: float) -> void:
	await get_tree().create_timer(seconds,true).timeout

func press(down: bool) -> void:
	var event := InputEventKey.new(); event.keycode = KEY_SPACE; event.physical_keycode = KEY_SPACE; event.pressed = down; Input.parse_input_event(event)

func screenshot(suffix: String) -> void:
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report+suffix+".png")

func start_case(id: String) -> void:
	check(interaction.begin(id), "request accepted: " + id)

func run_tests() -> void:
	await wait_seconds(.2); close_menu(); query()
	check(interaction.focused_id() == "door", "aim ranks central door over nearby off-axis key")
	check(not interaction.allowed and interaction.reason == "Need the blue key", "locked target exposes project denial prompt")
	check(not interaction.begin("locked") and commits == 0, "denied interaction has no gameplay side effect")
	check(not interaction.configure(NAN,55) and not interaction.configure(3,90), "invalid query configuration rejected")
	var duplicate = Target.new(); duplicate.stable_id = "door"; room.add_child(duplicate)
	check(not interaction.register_target(duplicate), "duplicate stable IDs rejected"); duplicate.free()
	check(interaction.register_target(door), "same target registration is idempotent")
	aim = (pickup.position-actor.position).normalized(); query(); check(interaction.focused_id() == "key", "aim selects visible pickup")
	press(true); await wait_seconds(.08); press(false)
	check(keys == 1 and commits == 1 and not pickup.visible, "native input commits pickup once and removes its visual")
	query(); check(interaction.focused_id() != "key", "disabled consumed pickup is no longer selectable")
	aim = Vector3.FORWARD; query(); check(interaction.allowed and interaction.focused_id() == "door", "pickup changes door condition through project state")
	keys = 0; check(not interaction.begin("stale-prompt"), "condition is rechecked at begin after stale prompt"); keys = 1; query()
	press(true); await wait_seconds(.15)
	check(interaction.holding() and interaction.progress > 0 and interaction.progress < 1, "native hold advances visible interaction progress")
	press(false); await wait_seconds(.03)
	check(not interaction.holding() and not door_open and commits == 1, "release cancels hold without committing")
	check(not interaction.cancel(), "repeated cancellation is harmless")
	start_case("complete"); check(not interaction.begin("complete"), "duplicate submit while busy is rejected")
	await wait_seconds(.15); await screenshot("-hold"); await wait_seconds(.35)
	check(door_open and commits == 2 and door.get_child(0).collision_layer == 0, "hold commits native door transform and collision once")
	check(not interaction.begin("complete") and commits == 2, "completed request cannot commit again")
	await screenshot("-complete")
	reset_room(); keys = 1; await wait_seconds(.05); query(); start_case("pause"); open_menu(); await wait_seconds(.1)
	check(not interaction.holding() and interaction.focused_id() == "" and not door_open, "menu pause cancels pending interaction and clears prompt")
	check(not interaction.begin("paused"), "new interaction rejected while UI owns pause"); close_menu(); query()
	start_case("distance"); actor.reset_motor(Vector3(0,1,5)); query()
	check(not interaction.holding() and interaction.focused_id() == "", "moving out of range cancels pinned target")
	actor.reset_motor(Vector3(0,1,0)); aim = Vector3.FORWARD; query(); start_case("occluded")
	var wall := box(room,Vector3(0,1,-1),Vector3(2,2,.2),Color.GRAY); await wait_seconds(.06); query()
	check(not interaction.holding() and interaction.focused_id() != "door", "real physics obstruction cancels hold and hides blocked target")
	wall.free(); await wait_seconds(.05); aim = Vector3.FORWARD; query()
	check(interaction.focused_id() == "door", "removing obstruction restores target acquisition")
	start_case("turn"); aim = Vector3.BACK; query(); check(not interaction.holding() and interaction.focused_id() == "", "turning away cancels without retargeting")
	aim = Vector3.FORWARD; query(); start_case("condition"); keys = 0; query(); check(not interaction.holding() and not interaction.allowed, "condition loss during hold cancels before commit"); keys = 1
	query(); start_case("disabled"); door.enabled = false; query(); check(not interaction.holding(), "target disabled mid-hold cancels"); door.enabled = true
	query(); start_case("invalid"); interaction.update_query(actor, actor.position, Vector3.ZERO,.1); check(not interaction.holding() and interaction.focused_id() == "", "invalid view invalidates pending request")
	query(); start_case("unregister"); interaction.unregister_target("door"); check(not interaction.holding(), "unregister cancels its pending request"); interaction.register_target(door)
	query(); fail_commit = true; start_case("rejected-commit"); await wait_seconds(.5)
	check(not door_open and events.any(func(e): return e.request == "rejected-commit" and e.state == "failed"), "project commit rejection produces failed result"); fail_commit = false
	query(); callback_mode = "cancel"; start_case("callback"); check(callback_rejected, "lifecycle callback cannot reenter begin"); interaction.cancel()
	query(); callback_mode = "clear"; start_case("clear-callback"); check(not interaction.holding() and interaction.focused_id() == "", "callback may clear without later commit")
	interaction.register_target(door); query(); start_case("destroy"); door.queue_free(); await wait_seconds(.08); check(not interaction.holding(), "destroyed target cancels safely on update")
	reset_room(); keys = 1; await wait_seconds(.06); query(); start_case("replace-room"); var old: WeakRef = weakref(room); reset_room(); await wait_seconds(.05)
	check(not is_instance_valid(old.get_ref()) and not interaction.holding() and keys == 0 and not door_open, "room replacement destroys old objects and clears request state")
	interaction.clear(); door.enabled = false; pickup.enabled = false
	var b = Target.new(); b.stable_id = "tie-b"; room.add_child(b); b.position = Vector3(0,1,-2)
	var a = Target.new(); a.stable_id = "tie-a"; room.add_child(a); a.position = b.position
	interaction.register_target(b); interaction.register_target(a); query(); check(interaction.focused_id() == "tie-a", "equal candidates tie-break by stable ID independent of registration order")
	b.position.z = -1; query(); check(interaction.focused_id() == "tie-b", "equal angle candidates prefer shorter distance")
	interaction.clear(); reset_room(); query()
	var starts := events.filter(func(e): return e.state == "started").size()
	var per_request := {}
	for item in events:
		if not per_request.has(item.request): per_request[item.request] = []
		per_request[item.request].append(item.state)
	var paired: bool = per_request.values().all(func(states): return states.size() == 2 and states[0] == "started" and states[1] in ["completed", "cancelled", "failed"])
	check(paired and events.size() == starts*2, "each accepted request has exactly one terminal lifecycle event")
	await screenshot("-clear")
	var file := FileAccess.open(report,FileAccess.WRITE); file.store_string(JSON.stringify({"engine":Engine.get_version_info().string,"checks":checks,"failures":failures,"events":events,"input":"native software events and project callbacks; no human or device claim","no_animation_plugin":true},"\t")); file.close()
	get_tree().quit(0 if failures.is_empty() else 1)

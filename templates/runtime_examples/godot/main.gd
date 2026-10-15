extends Node3D
const ActorMotor = preload("res://addons/oagd/oagd_actor.gd")
const CameraRig = preload("res://addons/oagd/oagd_camera.gd")
const Query = preload("res://addons/oagd/oagd_query.gd")
const Session = preload("res://addons/oagd/oagd_session.gd")
const Geometry = preload("res://addons/oagd/oagd_geometry.gd")
var actor: CharacterBody3D
var camera_rig: SpringArm3D
var session: Node
var target: StaticBody3D
var door: StaticBody3D
var label: Label
var target_hp := 3
var player_hp := 3
var has_key := false
var door_open := false
var scenario := "training"
var testing := false
var checks: Array[String] = []
var failures: Array[String] = []
var clock := 0.0
var hit_at := -100.0
var facing := Vector3.FORWARD
var generated: Dictionary

func _ready() -> void:
	scenario = str(JSON.parse_string(FileAccess.get_file_as_string("res://scenario.json"))["scenario"])
	testing = "--self-test" in OS.get_cmdline_user_args()
	for name in ["forward", "back", "left", "right"]:
		InputMap.add_action(name)
	var keys := {"forward": KEY_W, "back": KEY_S, "left": KEY_A, "right": KEY_D}
	for name in keys:
		var event := InputEventKey.new()
		event.physical_keycode = keys[name]
		InputMap.action_add_event(name, event)
	generated = Geometry.load_scene("res://generated/parts/scene.json", self)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55, -25, 0)
	light.shadow_enabled = true
	add_child(light)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(.08,.13,.20)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(.65,.72,.82)
	environment.environment.ambient_light_energy = .7
	add_child(environment)
	actor = ActorMotor.new()
	actor.name = "Player"
	var shape := CollisionShape3D.new()
	shape.shape = CapsuleShape3D.new()
	shape.shape.radius = .35
	shape.shape.height = 1.8
	actor.add_child(shape)
	var body := MeshInstance3D.new()
	body.mesh = CapsuleMesh.new()
	body.mesh.radius = .35
	body.mesh.height = 1.8
	actor.add_child(body)
	add_child(actor)
	camera_rig = CameraRig.new()
	camera_rig.position.y = .8
	camera_rig.rotation.x = -.38
	actor.add_child(camera_rig)
	target = make_box("Target", Vector3(0,.7,-2),Vector3(1,1.4,1),Color(.95,.60,.12))
	door = make_box("Door",Vector3(0,1,-4),Vector3(2,2,.3),Color(.15,.65,.75))
	door.visible = scenario == "puzzle"
	door.collision_layer = 1 if scenario == "puzzle" else 0
	session = Session.new()
	add_child(session)
	session.restarted.connect(reset_rules)
	var canvas := CanvasLayer.new()
	label = Label.new()
	label.position = Vector2(24,20)
	label.add_theme_font_size_override("font_size",22)
	canvas.add_child(label)
	add_child(canvas)
	reset_rules(0)
	if testing: run_tests()

func make_box(id: String, at: Vector3, size: Vector3, tint: Color) -> StaticBody3D:
	var node := StaticBody3D.new()
	node.name = id
	node.position = at
	var collision := CollisionShape3D.new()
	collision.shape = BoxShape3D.new()
	collision.shape.size = size
	node.add_child(collision)
	var visual := MeshInstance3D.new()
	visual.mesh = BoxMesh.new()
	visual.mesh.size = size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = tint
	visual.material_override = mat
	node.add_child(visual)
	add_child(node)
	return node

func reset_rules(_generation: int) -> void:
	target_hp = 3
	player_hp = 3
	has_key = false
	door_open = false
	hit_at = -100
	target.visible = true
	target.collision_layer = 1
	door.visible = scenario == "puzzle"
	door.collision_layer = 1 if scenario == "puzzle" else 0
	actor.reset_motor(Vector3(0,.92,2))
	facing = Vector3.FORWARD

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_R: session.restart()
		if event.physical_keycode == KEY_E: act()
		if event.physical_keycode == KEY_SPACE and session.state == &"playing": actor.request_jump()
		if event.physical_keycode == KEY_ESCAPE: Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		camera_rig.orbit(event.relative * .003)

func _physics_process(delta: float) -> void:
	clock += delta
	var wish := Input.get_vector("left","right","forward","back")
	var rotated := Vector3(wish.x,0,wish.y).rotated(Vector3.UP,camera_rig.rotation.y)
	actor.move_wish = Vector2(rotated.x,rotated.z) if session.state == &"playing" else Vector2.ZERO
	if rotated.length_squared() > .01: facing = rotated.normalized()
	if actor.position.y < -5: damage(3)
	if scenario == "puzzle" and door_open and actor.position.z < -5:
		session.set_state(&"won")
	label.text = "OAGD | " + scenario + " | " + str(session.state) + "\nWASD move   Space jump   E act   R restart   RMB orbit\nHP: %d   Target: %d   Key: %s   Door: %s" % [player_hp,target_hp,str(has_key),str(door_open)]

func act() -> void:
	if session.state != &"playing" or clock - hit_at < .2: return
	var hit := Query.ray(get_world_3d(),actor.global_position,facing,2.6,[actor.get_rid()])
	if hit.is_empty(): return
	if hit.collider == target:
		hit_at = clock
		if scenario == "training":
			target_hp -= 1
			if target_hp == 0: session.set_state(&"won")
		else:
			has_key = true
			target.visible = false
			target.collision_layer = 0
	elif hit.collider == door and has_key:
		door_open = true
		door.visible = false
		door.collision_layer = 0

func damage(amount: int) -> void:
	player_hp = maxi(0,player_hp - amount)
	if player_hp == 0: session.set_state(&"lost")

func verify(condition: bool, name: String) -> void:
	checks.append(name)
	if not condition: failures.append(name)

func frames(count: int) -> void:
	for i in count: await get_tree().physics_frame

func run_tests() -> void:
	await frames(10)
	verify(generated.size() == 8,"generated parts imported with stable IDs")
	verify(actor.is_on_floor(),"generated mesh floor collision")
	var before := actor.position
	Input.action_press("right")
	await frames(20)
	Input.action_release("right")
	await frames(3)
	verify(actor.position.x > before.x + .7,"game input moves native motor")
	actor.reset_motor(Vector3(0,.92,-4.8))
	Input.action_press("forward")
	await frames(35)
	Input.action_release("forward")
	await frames(3)
	verify(actor.position.z > -5.6 and actor.position.z < -5.3,"generated wall blocks motor")
	var blocked := Query.ray(get_world_3d(),Vector3(0,1,-4.8),Vector3.FORWARD,4,[actor.get_rid()])
	verify(not blocked.is_empty() and blocked.position.z > -6.1,"query stops at nearest obstruction")
	session.restart()
	await frames(3)
	act()
	verify(target_hp == 3 and not has_key,"interaction rejects out of range")
	actor.reset_motor(Vector3(0,.92,0))
	await frames(3)
	if scenario == "training":
		for i in 3:
			act()
			await frames(15)
		verify(target_hp == 0 and session.state == &"won","training damage and win")
	else:
		act()
		verify(has_key,"puzzle collects visible key")
		await frames(15)
		actor.reset_motor(Vector3(0,.92,-2))
		await frames(3)
		act()
		verify(door_open and door.collision_layer == 0,"key opens door and releases collision")
		Input.action_press("forward")
		await frames(50)
		Input.action_release("forward")
		verify(session.state == &"won","walk through open door to exit")
	session.restart()
	await frames(3)
	verify(target_hp==3 and not has_key and not door_open and session.state == &"playing","restart restores game-owned state")
	damage(3)
	verify(session.state == &"lost","failure state")
	session.restart()
	await frames(4)
	verify(player_hp==3 and session.state == &"playing" and actor.velocity.length()<.2,"retry clears movement and failure")
	var terrain_root := Node3D.new()
	add_child(terrain_root)
	terrain_root.position = Vector3(35,0,0)
	var terrain_nodes := Geometry.load_scene("res://generated/terrain/scene.json",terrain_root)
	verify(terrain_nodes.size()==13,"terrain and clearance scatter imported")
	await frames(3)
	var ground := Query.ray(get_world_3d(),Vector3(35,5,0),Vector3.DOWN,10,[actor.get_rid()])
	verify(not ground.is_empty() and absf(ground.position.y)<.01,"terrain road height and coordinate scale")
	var result := {"engine":Engine.get_version_info(),"scenario":scenario,"checks":checks,"failures":failures,"input":"movement via Input actions; game rules via same act handler; no manual play claimed"}
	var out := FileAccess.open("res://validation.json",FileAccess.WRITE)
	out.store_string(JSON.stringify(result,"  "))
	out.close()
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://validation.png")
	print("OAGD_TEST_" + ("PASS" if failures.is_empty() else "FAIL") + " count=" + str(checks.size()) + " " + str(failures))
	get_tree().quit(0 if failures.is_empty() else 1)
